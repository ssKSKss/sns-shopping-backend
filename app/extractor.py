"""
extractor.py
OpenAI APIなしでも高精度に店舗・商品情報を抽出するモジュール。
InstagramのURLからOGPメタデータを取得し、キーワードマッチで判別する。
"""

import re
import httpx
from bs4 import BeautifulSoup

# ── 店舗キーワード辞書（多ければ多いほど精度UP）──
STORE_KEYWORDS = {
    "DAISO": [
        "daiso", "ダイソー", "だいそー", "DAISO", "大創",
        "100均", "100円ショップ", "百均", "ひゃっきん",
        "#daiso", "#ダイソー", "#100均"
    ],
    "Seria": [
        "seria", "セリア", "#seria", "#セリア",
        "100均", "百均"
    ],
    "CanDo": [
        "cando", "can★do", "キャンドゥ", "キャンドゥー",
        "#cando", "#キャンドゥ", "100均", "百均"
    ],
    "3COINS": [
        "3coins", "3コインズ", "スリーコインズ", "3COINS",
        "#3coins", "#3コインズ", "#スリーコインズ"
    ],
    "Standard Products": [
        "standard products", "スタンダードプロダクツ",
        "#standardproducts", "#スタンダードプロダクツ"
    ],
    "無印良品": [
        "muji", "無印良品", "無印", "MUJI",
        "#muji", "#無印良品", "#無印"
    ],
    "ニトリ": [
        "nitori", "ニトリ", "デコホーム", "decohome",
        "#nitori", "#ニトリ", "#デコホーム"
    ],
    "IKEA": [
        "ikea", "イケア", "IKEA",
        "#ikea", "#イケア"
    ],
    "ワークマン": [
        "workman", "ワークマン", "workman plus",
        "#workman", "#ワークマン", "#ワークマン女子"
    ],
}

# ── カテゴリキーワード辞書 ──
CATEGORY_KEYWORDS = {
    "収納": ["収納", "ボックス", "ケース", "仕切り", "整理", "棚", "シェルフ", "ラック", "カゴ", "バスケット"],
    "キッチン": ["キッチン", "料理", "調理", "まな板", "フライパン", "鍋", "食器", "タッパー", "弁当", "お弁当", "食洗機"],
    "インテリア": ["インテリア", "部屋", "リビング", "ルーム", "ディスプレイ", "飾り", "アロマ", "照明", "クッション", "ラグ"],
    "掃除": ["掃除", "クリーナー", "モップ", "雑巾", "洗剤", "スポンジ", "ブラシ", "汚れ", "きれい"],
    "洗面・バス": ["バス", "洗面", "お風呂", "シャンプー", "洗顔", "タオル", "歯ブラシ"],
    "寝具": ["寝具", "布団", "枕", "ベッド", "マットレス", "毛布", "シーツ", "パッド"],
    "ファッション": ["ファッション", "服", "コーデ", "着こなし", "アウター", "トップス", "パンツ", "靴", "バッグ"],
    "ホビー": ["ハンドメイド", "DIY", "デコ", "アクセサリー", "手芸", "クラフト", "ネイル"],
    "生活雑貨": ["雑貨", "日用品", "生活", "便利", "グッズ", "アイテム"],
}

# 実店舗確認が必要な店舗
LOCATION_REQUIRED_STORES = {"ニトリ", "IKEA", "ワークマン"}

# ── OGPメタデータ取得 ──
async def fetch_ogp(url: str) -> dict:
    """
    URLにアクセスしてOGP（Open Graph Protocol）のメタデータを取得する。
    title, description, site_name などが取れる。
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
        )
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            res = await client.get(url, headers=headers)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")

            def og(prop):
                tag = soup.find("meta", property=f"og:{prop}")
                if tag:
                    return tag.get("content", "")
                tag = soup.find("meta", attrs={"name": f"og:{prop}"})
                return tag.get("content", "") if tag else ""

            title       = og("title") or soup.title.string if soup.title else ""
            description = og("description")
            site_name   = og("site_name")

            # titleからInstagramの余分なテキストを除去
            title = re.sub(r'\s*[-|]\s*Instagram.*$', '', title or '', flags=re.IGNORECASE)
            title = re.sub(r'\s*[-|]\s*TikTok.*$',   '', title or '', flags=re.IGNORECASE)

            return {
                "title":       (title or "").strip(),
                "description": (description or "").strip(),
                "site_name":   (site_name or "").strip(),
                "full_text":   f"{title} {description}".lower(),
            }
    except Exception as e:
        print(f"OGP取得失敗: {e}")
        return {"title": "", "description": "", "site_name": "", "full_text": ""}


# ── 店舗名判別 ──
def detect_store(text: str, url: str) -> str:
    """
    テキストとURLからキーワードマッチで店舗名を判別する。
    """
    text_lower = text.lower()
    url_lower  = url.lower()

    for store, keywords in STORE_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower or kw.lower() in url_lower:
                return store

    return "その他"


# ── カテゴリ判別 ──
def detect_category(text: str) -> str:
    """
    テキストからカテゴリを判別する。
    """
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return category
    return "生活雑貨"


# ── 商品名抽出 ──
def extract_product_name(title: str, description: str, store: str) -> str:
    """
    OGPのtitleとdescriptionから商品名らしき文字列を抽出する。
    """
    # Instagramの定型文を除去
    clean_patterns = [
        r'[\d,]+\s*[いイ]いね',
        r'[\d,]+\s*件のコメント',
        r'この投稿をInstagramで見る',
        r'さんがシェアした投稿',
        r'\d+\s*likes?',
        r'\d+\s*comments?',
    ]
    text = description or title or ""
    for pat in clean_patterns:
        text = re.sub(pat, '', text, flags=re.IGNORECASE)

    # 最初の50文字を商品名として使う（長すぎる場合は切る）
    text = text.strip()
    if len(text) > 50:
        # 句読点・改行で区切って最初のフレーズを取る
        for sep in ['。', '！', '!', '、', '\n', '#']:
            if sep in text:
                text = text.split(sep)[0].strip()
                break
        if len(text) > 50:
            text = text[:47] + "..."

    if not text or len(text) < 2:
        return f"{store}紹介投稿"

    return text


# ── アカウント名抽出 ──
def extract_account(url: str, description: str) -> str:
    """
    URLまたはdescriptionからSNSアカウント名を抽出する。
    """
    # Instagram URLから @username を抽出
    ig_match = re.search(r'instagram\.com/([^/?]+)', url)
    if ig_match:
        username = ig_match.group(1)
        if username not in ('p', 'reel', 'stories', 'tv'):
            return f"@{username}"

    # TikTok URLから @username を抽出
    tt_match = re.search(r'tiktok\.com/@([^/?]+)', url)
    if tt_match:
        return f"@{tt_match.group(1)}"

    # X(Twitter) URLから @username を抽出（/status/... の投稿URL）
    x_match = re.search(r'(?:^|//)(?:www\.|mobile\.)?(?:x|twitter)\.com/([A-Za-z0-9_]+)/status', url)
    if x_match and x_match.group(1).lower() != "i":  # /i/status/... は投稿者名が含まれない形式
        return f"@{x_match.group(1)}"

    # descriptionから「@xxx さんがシェア」パターン
    desc_match = re.search(r'@([\w.]+)', description or '')
    if desc_match:
        return f"@{desc_match.group(1)}"

    return "@unknown"


# ── メイン抽出関数（app/main.py から呼ばれる）──
async def extract_info(url: str) -> dict:
    """
    URLから店舗・商品名・カテゴリなどの情報を抽出して返す。
    OpenAI APIは使わずキーワードマッチのみで判別する。
    """
    # OGPメタデータ取得
    ogp = await fetch_ogp(url)

    full_text    = ogp["full_text"]
    title        = ogp["title"]
    description  = ogp["description"]

    # 各項目を判別
    store_name   = detect_store(full_text, url)
    category     = detect_category(full_text)
    product_name = extract_product_name(title, description, store_name)
    post_account = extract_account(url, description)
    location_required = store_name in LOCATION_REQUIRED_STORES

    return {
        "store_name":        store_name,
        "product_name":      product_name,
        "post_account":      post_account,
        "category":          category,
        "location_required": location_required,
        "original_url":      url,
    }
