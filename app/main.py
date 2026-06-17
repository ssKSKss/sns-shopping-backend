from __future__ import annotations
from typing import Dict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from app.extractor import extract_info

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

@app.get("/stores")
async def get_stores():
    """対応店舗一覧を返す"""
    from app.extractor import STORE_KEYWORDS
    return {"stores": list(STORE_KEYWORDS.keys())}
