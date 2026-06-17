import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# .envファイルがあれば読み込みます。
load_dotenv()


# DATABASE_URLが未設定の場合は、プロジェクト直下のSQLiteファイルを使います。
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./insta_bookmark.db")


# SQLiteでは複数スレッドからの利用を許可する設定が必要です。
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}


# SQLAlchemyがデータベースへ接続するためのエンジンを作ります。
engine = create_engine(DATABASE_URL, connect_args=connect_args)


# APIリクエストごとに使うデータベースセッションの作成器です。
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """すべてのテーブル定義が継承する土台クラスです。"""


def get_db():
    """FastAPIの各リクエストでDBセッションを安全に受け渡す関数です。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
