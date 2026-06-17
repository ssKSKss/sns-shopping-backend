from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Bookmark(Base):
    """SNSから共有された商品紹介投稿を保存するテーブルです。"""

    # 実際のテーブル名です。
    __tablename__ = "bookmarks"

    # 1件ごとの自動採番IDです。
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # 店舗名です。対象店舗以外は「その他」を入れます。
    store_name: Mapped[str] = mapped_column(String(80), index=True, nullable=False)

    # 商品名です。特定できない場合は「〇〇紹介投稿」のように保存します。
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # InstagramやTikTokなどの発信者アカウント名です。
    post_account: Mapped[str] = mapped_column(String(120), index=True, nullable=False)

    # ユーザーが送信した元URLです。
    original_url: Mapped[str] = mapped_column(Text, nullable=False)

    # キッチン、収納、掃除、インテリアなどのジャンルです。
    category: Mapped[str] = mapped_column(String(80), index=True, nullable=False)

    # 実店舗確認が必要そうかどうかを保存します。
    location_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # 解析に使った投稿テキストやメタ情報です。後で再解析するときに役立ちます。
    source_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # レコード作成日時です。
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
