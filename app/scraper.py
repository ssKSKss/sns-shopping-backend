from __future__ import annotations

from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup


@dataclass
class PageContent:
    """URLから取得した、AI解析に渡すための簡単なページ情報です。"""

    url: str
    title: str
    description: str
    body_preview: str

    def to_text(self) -> str:
        """ページ情報を1つのテキストにまとめます。"""
        return "\n".join(
            [
                f"URL: {self.url}",
                f"Title: {self.title}",
                f"Description: {self.description}",
                f"Body: {self.body_preview}",
            ]
        ).strip()


def fetch_page_content(url: str, timeout_seconds: int = 10) -> PageContent:
    """共有URLへアクセスし、タイトルや説明文などのメタ情報を取得します。"""
    try:
        response = requests.get(
            url,
            timeout=timeout_seconds,
            headers={
                # SNSやECサイトに通常のブラウザらしく見せるためのUser-Agentです。
                "User-Agent": "Mozilla/5.0 (compatible; SNSBookmarkBot/1.0)",
            },
        )
        response.raise_for_status()
    except requests.RequestException:
        # SNS側の制限などで取得できない場合でも、URLだけで解析を続けます。
        return PageContent(url=url, title="", description="", body_preview="")

    soup = BeautifulSoup(response.text, "html.parser")

    title = _get_title(soup)
    description = _get_meta_content(soup, "description") or _get_og_content(soup, "og:description")
    body_preview = " ".join(soup.get_text(" ", strip=True).split())[:1200]

    return PageContent(url=url, title=title, description=description, body_preview=body_preview)


def _get_title(soup: BeautifulSoup) -> str:
    """HTMLのtitleまたはog:titleを取り出します。"""
    og_title = _get_og_content(soup, "og:title")
    if og_title:
        return og_title
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return ""


def _get_meta_content(soup: BeautifulSoup, name: str) -> str:
    """指定したname属性のmetaタグからcontentを取り出します。"""
    tag = soup.find("meta", attrs={"name": name})
    return str(tag.get("content", "")).strip() if tag else ""


def _get_og_content(soup: BeautifulSoup, property_name: str) -> str:
    """Open Graph用のmetaタグからcontentを取り出します。"""
    tag = soup.find("meta", attrs={"property": property_name})
    return str(tag.get("content", "")).strip() if tag else ""
