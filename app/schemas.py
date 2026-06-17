from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class BookmarkCreateRequest(BaseModel):
    """URL保存APIが受け取る入力データです。"""

    url: HttpUrl = Field(..., description="InstagramやTikTokなどから共有されたURL")


class ExtractedBookmark(BaseModel):
    """AIまたはルールで抽出した商品紹介データです。"""

    store_name: str
    product_name: str
    post_account: str
    original_url: str
    category: str
    location_required: bool


class BookmarkResponse(ExtractedBookmark):
    """APIが返す保存済みデータです。"""

    id: int
    source_text: str
    created_at: datetime

    model_config = {"from_attributes": True}
