# SNS商品紹介URL 自動仕分けバックエンド

Instagram、TikTokなどから共有された商品紹介URLを受け取り、投稿テキストやメタデータを解析して、店舗別・発信アカウント別に保存するPythonバックエンドです。

## できること

- URLを受け取って投稿ページのタイトル・説明文などを取得
- OpenAI APIで `store_name`、`product_name`、`post_account`、`category` などをJSON抽出
- OpenAI APIキーがない場合も簡易ルールで仮抽出
- SQLiteに保存
- 店舗ごと、発信アカウントごとに一覧取得

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

OpenAI APIを使う場合は、`.env` の `OPENAI_API_KEY` にキーを入れてください。

## 起動

```bash
uvicorn app.main:app --reload
```

ブラウザで以下を開くとAPIを試せます。

- http://127.0.0.1:8000/docs

## 主なAPI

### URLを保存

`POST /bookmarks`

```json
{
  "url": "https://www.instagram.com/p/example/"
}
```

### 店舗ごとに一覧取得

`GET /bookmarks?store_name=DAISO`

### 発信アカウントごとに一覧取得

`GET /bookmarks?post_account=example_account`

### 店舗一覧

`GET /stores`

### 発信アカウント一覧

`GET /accounts`
