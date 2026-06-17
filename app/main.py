from __future__ import annotations

from typing import Dict, List, Optional, Union

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from app import crud
from app.database import Base, engine, get_db
from app.extractor import extract_bookmark_data
from app.schemas import BookmarkCreateRequest, BookmarkResponse
from app.scraper import fetch_page_content


# APIアプリ本体です。
app = FastAPI(
    title="SNS商品紹介URL 自動仕分けAPI",
    description="共有されたSNS URLを解析し、店舗別・発信アカウント別に保存します。",
    version="0.1.0",
)


@app.on_event("startup")
def on_startup() -> None:
    """アプリ起動時に、必要なデータベーステーブルを作成します。"""
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check() -> dict[str, str]:
    """アプリが起動しているか確認するための簡単なAPIです。"""
    return {"status": "ok"}


@app.post("/bookmarks", response_model=BookmarkResponse)
def create_bookmark(
    request: BookmarkCreateRequest,
    db: Session = Depends(get_db),
) -> BookmarkResponse:
    """URLを受け取り、解析してデータベースへ保存します。"""
    original_url = str(request.url)
    page_content = fetch_page_content(original_url)
    source_text = page_content.to_text()
    extracted = extract_bookmark_data(original_url=original_url, source_text=source_text)
    bookmark = crud.create_bookmark(db=db, data=extracted, source_text=source_text)
    return BookmarkResponse.model_validate(bookmark)


@app.get("/bookmarks", response_model=list[BookmarkResponse])
def list_bookmarks(
    store_name: Optional[str] = None,
    post_account: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[BookmarkResponse]:
    """保存済み投稿を、店舗名・発信アカウント名・カテゴリで絞り込みます。"""
    bookmarks = crud.list_bookmarks(
        db=db,
        store_name=store_name,
        post_account=post_account,
        category=category,
    )
    return [BookmarkResponse.model_validate(bookmark) for bookmark in bookmarks]


@app.get("/stores")
def list_stores(db: Session = Depends(get_db)) -> List[Dict[str, Union[int, str]]]:
    """店舗ごとの保存件数を返します。"""
    return crud.list_store_summary(db)


@app.get("/accounts")
def list_accounts(db: Session = Depends(get_db)) -> List[Dict[str, Union[int, str]]]:
    """発信アカウントごとの保存件数を返します。"""
    return crud.list_account_summary(db)
