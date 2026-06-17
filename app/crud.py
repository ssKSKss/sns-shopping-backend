from __future__ import annotations

from typing import Optional

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import Bookmark
from app.schemas import ExtractedBookmark


def create_bookmark(db: Session, data: ExtractedBookmark, source_text: str) -> Bookmark:
    """抽出済みデータをbookmarksテーブルへ保存します。"""
    bookmark = Bookmark(
        store_name=data.store_name,
        product_name=data.product_name,
        post_account=data.post_account,
        original_url=data.original_url,
        category=data.category,
        location_required=data.location_required,
        source_text=source_text,
    )
    db.add(bookmark)
    db.commit()
    db.refresh(bookmark)
    return bookmark


def list_bookmarks(
    db: Session,
    store_name: Optional[str] = None,
    post_account: Optional[str] = None,
    category: Optional[str] = None,
) -> list[Bookmark]:
    """店舗名、発信アカウント名、カテゴリで保存済み投稿を絞り込みます。"""
    query: Select[tuple[Bookmark]] = select(Bookmark).order_by(Bookmark.created_at.desc())

    if store_name:
        query = query.where(Bookmark.store_name == store_name)

    if post_account:
        query = query.where(Bookmark.post_account == post_account)

    if category:
        query = query.where(Bookmark.category == category)

    return list(db.scalars(query).all())


def list_store_summary(db: Session) -> list[dict[str, int | str]]:
    """店舗ごとの保存件数を一覧にします。"""
    rows = db.execute(
        select(Bookmark.store_name, func.count(Bookmark.id))
        .group_by(Bookmark.store_name)
        .order_by(Bookmark.store_name)
    ).all()
    return [{"store_name": store_name, "count": count} for store_name, count in rows]


def list_account_summary(db: Session) -> list[dict[str, int | str]]:
    """発信アカウントごとの保存件数を一覧にします。"""
    rows = db.execute(
        select(Bookmark.post_account, func.count(Bookmark.id))
        .group_by(Bookmark.post_account)
        .order_by(Bookmark.post_account)
    ).all()
    return [{"post_account": post_account, "count": count} for post_account, count in rows]
