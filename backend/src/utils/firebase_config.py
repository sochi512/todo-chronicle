import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# 環境変数の読み込み
load_dotenv()

def initialize_firebase():
    """Firebaseの初期化を行う関数"""
    print("本番環境のFirebase認証を初期化します")
    try:
        # service-account.jsonから認証情報を取得
        cred = credentials.Certificate(
            os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        )
        
        # Firebase Admin SDKの初期化
        firebase_admin.initialize_app(cred)
        print("Firebase Admin SDKの初期化が成功しました")
        
        # Firestoreクライアントの取得
        db = firestore.client()
        print("Firestoreクライアントの初期化が成功しました")
        return db
        
    except Exception as e:
        print(f"Firebase初期化エラー: {str(e)}")
        raise

# グローバル変数としてdbを初期化
db = initialize_firebase() 