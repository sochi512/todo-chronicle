from fastapi import Request, HTTPException
from firebase_admin import auth
import os
from typing import Optional
from src.models.types import ErrorMessages

async def verify_token(request: Request) -> str:
    """Firebaseの認証トークンを検証する関数"""
    try:
        print(f"ENVIRONMENT: {os.getenv('ENVIRONMENT')}")
        # テスト環境の場合は認証をスキップ
        if os.getenv("ENVIRONMENT") == "test":
            # テスト用のユーザーIDを返す
            return "VNCo2pVuay3yYzdHwtvr"

        # Authorizationヘッダーからトークンを取得
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            raise HTTPException(
                status_code=401,
                detail=ErrorMessages.UNAUTHORIZED
            )

        # トークンを取得
        token = auth_header.split('Bearer ')[1]
        if not token:
            raise HTTPException(
                status_code=401,
                detail=ErrorMessages.UNAUTHORIZED
            )

        # トークンを検証
        decoded_token = auth.verify_id_token(token)
        user_id = decoded_token.get('uid')
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail=ErrorMessages.UNAUTHORIZED
            )

        return user_id
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=ErrorMessages.UNAUTHORIZED
        )