FROM python:3.11-slim

WORKDIR /app

# システムパッケージのインストール
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Pythonパッケージのインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# テスト用の追加パッケージ
RUN pip install --no-cache-dir pytest pytest-asyncio httpx

# アプリケーションコードのコピー
COPY . .

# ヘルスチェック用のcurlをインストール
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# 開発環境用のコマンド（docker-composeで上書き可能）
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
