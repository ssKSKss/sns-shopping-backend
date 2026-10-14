"""
ai_analyzer.py
投稿のスクショ画像・キャプション文字をClaude APIに見せて、
「どの店の何の商品か」を判定するモジュール。

APIキー（ANTHROPIC_API_KEY）が未設定のときは、
従来のキーワード判定（extractor.py）で代わりに判定します。
"""

from __future__ import annotations

import base64
import os
from typing import Optional

from app.extractor import (
    LOCATION_REQUIRED_STORES,
    STORE_KEYWORDS,
    detect_category,
    detect_store,
    extract_account,
    extract_product_name,
)

# 使うモデル。.env の ANTHROPIC_MODEL で変更できます（未設定なら軽くて安いHaiku）。
DEFAULT_MODEL = "claude-haiku-5-5"

# 受け付ける画像の種類
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

# カテゴリの選択肢（extractor.py と揃える）
CATEGORIES = [
    "収納", "キッチン", "インテリア", "掃除", "洗面・バス",
    "寝具", "ファッション", "ホビー", "生活雑貨",
]

# 確信度がこれ未満なら「ユーザーに選んでもらう」扱いにする
CONFIDENCE_THRESHOLD = 0.7


def _build_tool() -> dict:
    """Claudeに必ずこの形式で答えさせるための「回答用紙」を作ります。"""
    store_names = list(STORE_KEYWORDS.keys())
    return {
        "name": "report_product",
        "description": "SNS投稿から読み取った店舗と商品の情報を報告する",
        "input_schema": {
            "type": "object",
            "properties": {
                "store_candidates": {
                    "type": "array",
                    "description": "可能性の高い順の店舗候補（最大3件）",
                    "items": {
                        "type": "object",
                        "properties": {
                            "store_name": {
                                "type": "string",
                                "description": (
                                    "店舗名。次のリストにあればその表記を使う: "
                                    + "、".join(store_names)
                                    + "。リストに無い店ならその店の一般的な名前。"
                                ),
                            },
                            "confidence": {
                                "type": "number",
                                "description": "0〜1の確信度",
                            },
                            "reason": {
                                "type": "string",
                                "description": "判断した根拠（短く。例: 『#無印良品のタグ』『ロゴが写っている』）",
                            },
                        },
                        "required": ["store_name", "confidence", "reason"],
                    },
                },
                "product_name": {
                    "type": "string",
                    "description": "商品名（分からなければ『〇〇の紹介投稿』）",
                },
                "price": {
                    "type": ["string", "null"],
                    "description": "価格（例: 『990円』）。読み取れなければnull",
                },
                "category": {"type": "string", "enum": CATEGORIES},
                "post_account": {
                    "type": ["string", "null"],
                    "description": "投稿者のアカウント名（@付き）。分からなければnull",
                },
            },
            "required": ["store_candidates", "product_name", "category"],
        },
    }


SYSTEM_PROMPT = """あなたはSNS（Instagram・TikTokなど）の商品紹介投稿を読み取るアシスタントです。
渡されたスクリーンショットやキャプション文から、紹介されている商品が「どの店で買えるか」と「何の商品か」を判定してください。

判断材料の例:
- ハッシュタグ（#無印良品 #ダイソー など）、メンション（@muji_global など）
- 位置情報タグ、写真に写ったロゴ・値札・パッケージ・店内の様子
- 「100均」だけでは店を決めつけず、ダイソー・セリア・キャンドゥを候補に並べて確信度を下げる

根拠がはっきりしない場合は無理に断定せず、確信度を低くしてください。
必ず report_product ツールで回答してください。"""


def _fallback(caption: str, url: str) -> dict:
    """APIキーが無い・エラー時に使う、従来のキーワード判定です。"""
    store = detect_store(caption.lower(), url)
    return {
        "store_name": store,
        "store_candidates": [
            {"store_name": store, "confidence": 0.5 if store != "その他" else 0.0,
             "reason": "キーワード判定"}
        ],
        "needs_confirmation": True,
        "product_name": extract_product_name(caption, caption, store),
        "price": None,
        "category": detect_category(caption),
        "post_account": extract_account(url, caption),
        "location_required": store in LOCATION_REQUIRED_STORES,
        "original_url": url,
        "analyzed_by": "keyword",
    }


def analyze_post(
    image_bytes: Optional[bytes] = None,
    image_type: Optional[str] = None,
    caption: str = "",
    url: str = "",
) -> dict:
    """画像とキャプションをClaudeに渡して、店舗・商品を判定します。"""
    # コピー時に混ざりがちな前後の空白・改行を取り除く
    api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        return _fallback(caption, url)

    import anthropic  # キーがあるときだけ読み込む

    content: list[dict] = []
    if image_bytes:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": image_type or "image/jpeg",
                "data": base64.b64encode(image_bytes).decode("ascii"),
            },
        })
    text_parts = []
    if caption:
        text_parts.append(f"キャプション:\n{caption}")
    if url:
        text_parts.append(f"投稿URL: {url}")
    text_parts.append("この投稿の商品について報告してください。")
    content.append({"type": "text", "text": "\n\n".join(text_parts)})

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL),
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[_build_tool()],
            tool_choice={"type": "tool", "name": "report_product"},
            messages=[{"role": "user", "content": content}],
        )
    except Exception as e:  # 通信エラーや残高切れなど
        # 注意: 例外の本文にはAPIキーが含まれる場合があるため、種類の名前だけを記録する
        cause = e.__cause__
        cause_name = type(cause).__name__ if cause else ""
        label = type(e).__name__ + (f" ({cause_name})" if cause_name else "")
        if isinstance(e, anthropic.APIStatusError):
            label += f" status={e.status_code}"
        print(f"Claude API呼び出し失敗: {label}")
        result = _fallback(caption, url)
        result["error"] = label
        return result

    data = next(
        (block.input for block in response.content if block.type == "tool_use"),
        None,
    )
    if not data:
        return _fallback(caption, url)

    candidates = sorted(
        data.get("store_candidates") or [],
        key=lambda c: c.get("confidence", 0),
        reverse=True,
    )[:3]
    top = candidates[0] if candidates else {"store_name": "その他", "confidence": 0.0}
    store_name = top["store_name"]

    post_account = data.get("post_account") or extract_account(url, caption)

    return {
        "store_name": store_name,
        "store_candidates": candidates,
        "needs_confirmation": top.get("confidence", 0) < CONFIDENCE_THRESHOLD,
        "product_name": data.get("product_name") or f"{store_name}の紹介投稿",
        "price": data.get("price"),
        "category": data.get("category") or "生活雑貨",
        "post_account": post_account,
        "location_required": store_name in LOCATION_REQUIRED_STORES,
        "original_url": url,
        "analyzed_by": "claude",
    }
