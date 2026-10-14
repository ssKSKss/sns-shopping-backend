from __future__ import annotations
from typing import Dict, Optional
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from app.extractor import extract_info
from app.ai_analyzer import ALLOWED_IMAGE_TYPES, analyze_post

app = FastAPI(
    title="SNS買い物リスト API",
    description="SNS投稿URLを解析して店舗・商品情報を返すAPI",
    version="0.2.0",
)

# フロントエンド（Netlify）からのアクセスを許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class BookmarkRequest(BaseModel):
    url: str
    hint_text: str = ""  # ユーザーが貼り付けた投稿テキスト（任意）

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/bookmarks")
async def create_bookmark(request: BookmarkRequest):
    """URLを受け取り、店舗・商品名・カテゴリを解析して返す"""
    result = await extract_info(request.url)
    
    # hint_textが渡された場合はそちらも使って再判別
    if request.hint_text:
        from app.extractor import detect_store, detect_category, extract_product_name
        combined = f"{result.get('product_name','')} {request.hint_text}".lower()
        store = detect_store(combined, request.url)
        if store != "その他":
            result["store_name"] = store
        result["category"] = detect_category(combined)
        if len(request.hint_text) > 5:
            result["product_name"] = extract_product_name(
                request.hint_text, request.hint_text, result["store_name"]
            )
    
    return result

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5MBまで


@app.post("/analyze")
async def analyze(
    image: Optional[UploadFile] = File(None, description="投稿のスクリーンショット（任意）"),
    caption: str = Form("", description="投稿のキャプション文（任意）"),
    url: str = Form("", description="投稿のURL（任意）"),
):
    """スクショ画像・キャプションをAIに見せて、店舗・商品を判定する"""
    image_bytes = None
    image_type = None
    if image is not None and image.filename:
        image_type = image.content_type
        if image_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(400, "画像は JPEG / PNG / WebP / GIF で送ってください")
        image_bytes = await image.read()
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(400, "画像が大きすぎます（5MBまで）")

    if not image_bytes and not caption.strip():
        raise HTTPException(400, "画像かキャプションのどちらかを送ってください")

    # Claude APIの呼び出しは時間がかかるので別スレッドで実行
    return await asyncio.to_thread(
        analyze_post, image_bytes, image_type, caption, url
    )


@app.get("/stores")
async def get_stores():
    """対応店舗一覧を返す"""
    from app.extractor import STORE_KEYWORDS
    return {"stores": list(STORE_KEYWORDS.keys())}
