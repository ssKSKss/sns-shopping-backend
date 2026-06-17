from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

from app.schemas import ExtractedBookmark


# 自動仕分け対象の店舗名を、表記ゆれも含めて定義します。
STORE_ALIASES = {
    "DAISO": ["daiso", "ダイソー", "大創産業"],
    "Seria": ["seria", "セリア"],
    "CanDo": ["cando", "can do", "キャンドゥ"],
    "3COINS": ["3coins", "3 coins", "スリーコインズ", "スリコ"],
    "Standard Products": ["standard products", "スタンダードプロダクツ"],
    "ニトリ": ["ニトリ", "nitori"],
    "デコホーム": ["デコホーム", "deco home"],
    "IKEA": ["ikea", "イケア"],
}


# カテゴリ判定に使うキーワードです。
CATEGORY_KEYWORDS = {
    "キッチン": ["キッチン", "調理", "食器", "皿", "保存容器", "まな板", "包丁"],
    "収納": ["収納", "ボックス", "ケース", "棚", "ラック", "整理"],
    "掃除": ["掃除", "クリーナー", "ほこり", "洗剤", "ブラシ", "スポンジ"],
    "インテリア": ["インテリア", "家具", "照明", "カーテン", "ラグ", "ソファ"],
    "バス・トイレ": ["バス", "風呂", "トイレ", "洗面", "タオル"],
    "文房具": ["文房具", "ノート", "ペン", "手帳"],
}


def extract_bookmark_data(original_url: str, source_text: str) -> ExtractedBookmark:
    """OpenAI APIを優先して、投稿テキストから保存項目を抽出します。"""
    if os.getenv("OPENAI_API_KEY"):
        return _extract_with_openai(original_url=original_url, source_text=source_text)

    # APIキーがない開発環境では、最低限のルールベース抽出に切り替えます。
    return _extract_with_rules(original_url=original_url, source_text=source_text)


def _extract_with_openai(original_url: str, source_text: str) -> ExtractedBookmark:
    """OpenAI APIへ依頼し、必ずJSONとして抽出結果を受け取ります。"""
    client = OpenAI()

    prompt = f"""
あなたはSNSの商品紹介投稿を整理するアシスタントです。
以下のURLと取得テキストから、指定スキーマのJSONだけを返してください。

対象店舗:
- DAISO
- Seria
- CanDo
- 3COINS
- Standard Products
- ニトリ
- デコホーム
- IKEA
- その他

ルール:
- store_nameは対象店舗に一致しない場合「その他」にしてください。
- product_nameが特定できない場合は「商品紹介投稿」にしてください。
- post_accountが不明な場合は「不明」にしてください。
- categoryは「キッチン」「収納」「掃除」「インテリア」「バス・トイレ」「文房具」「その他」のどれかに寄せてください。
- location_requiredは、IKEAやニトリなど大型家具・実物確認が重要そうな商品ならtrue、それ以外は基本falseにしてください。

URL:
{original_url}

取得テキスト:
{source_text[:6000]}
""".strip()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "返答はJSONのみ。説明文やMarkdownは不要です。"},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    raw_content = response.choices[0].message.content or "{}"
    parsed = json.loads(raw_content)
    normalized = _normalize_extracted_data(parsed, original_url)
    return ExtractedBookmark(**normalized)


def _extract_with_rules(original_url: str, source_text: str) -> ExtractedBookmark:
    """OpenAI APIキーがない場合の簡易的な抽出処理です。"""
    text = f"{original_url}\n{source_text}"

    store_name = _detect_store_name(text)
    category = _detect_category(text)
    post_account = _detect_account(original_url, source_text)
    product_name = _detect_product_name(source_text, store_name)
    location_required = _detect_location_required(store_name, text)

    return ExtractedBookmark(
        store_name=store_name,
        product_name=product_name,
        post_account=post_account,
        original_url=original_url,
        category=category,
        location_required=location_required,
    )


def _normalize_extracted_data(data: dict[str, Any], original_url: str) -> dict[str, Any]:
    """AIの返答に不足や表記ゆれがあっても、DBに保存できる形へ整えます。"""
    store_name = str(data.get("store_name") or "その他").strip()
    if store_name not in STORE_ALIASES and store_name != "その他":
        store_name = _detect_store_name(store_name)

    return {
        "store_name": store_name or "その他",
        "product_name": str(data.get("product_name") or "商品紹介投稿").strip(),
        "post_account": str(data.get("post_account") or "不明").strip(),
        "original_url": str(data.get("original_url") or original_url).strip(),
        "category": str(data.get("category") or "その他").strip(),
        "location_required": bool(data.get("location_required", False)),
    }


def _detect_store_name(text: str) -> str:
    """文章内のキーワードから店舗名を判定します。"""
    lower_text = text.lower()
    for store_name, aliases in STORE_ALIASES.items():
        if any(alias.lower() in lower_text for alias in aliases):
            return store_name
    return "その他"


def _detect_category(text: str) -> str:
    """文章内のキーワードからカテゴリを判定します。"""
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return category
    return "その他"


def _detect_account(original_url: str, source_text: str) -> str:
    """URLやメタテキストから発信アカウントらしい名前を取り出します。"""
    instagram_match = re.search(r"instagram\.com/([^/?#]+)/", original_url)
    if instagram_match and instagram_match.group(1) not in {"p", "reel", "reels"}:
        return instagram_match.group(1)

    tiktok_match = re.search(r"tiktok\.com/@([^/?#]+)", original_url)
    if tiktok_match:
        return f"@{tiktok_match.group(1)}"

    account_match = re.search(r"@([A-Za-z0-9_.-]{2,50})", source_text)
    if account_match:
        return f"@{account_match.group(1)}"

    return "不明"


def _detect_product_name(source_text: str, store_name: str) -> str:
    """ページタイトルなどから、商品名らしい短い文字列を作ります。"""
    for line in source_text.splitlines():
        cleaned = line.replace("Title:", "").replace("Description:", "").strip()
        if 3 <= len(cleaned) <= 80 and "URL:" not in cleaned:
            return cleaned

    if store_name != "その他":
        return f"{store_name}紹介投稿"
    return "商品紹介投稿"


def _detect_location_required(store_name: str, text: str) -> bool:
    """店舗確認が必要そうかどうかをざっくり判定します。"""
    large_item_words = ["家具", "ソファ", "ベッド", "棚", "大型", "組み立て", "展示"]
    if store_name in {"IKEA", "ニトリ", "デコホーム"} and any(word in text for word in large_item_words):
        return True
    return False
