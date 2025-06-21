"""
ToDo Chronicle API - メインアプリケーションファイル

このモジュールは、ToDo ChronicleアプリケーションのメインAPIサーバーを提供します。
異世界ファンタジーテーマのタスク管理アプリケーションで、ユーザーのタスク完了に応じて
ストーリーが進行し、行動分析機能も提供します。

主要機能:
- ユーザー管理（作成、取得、ダッシュボード）
- タスク管理（CRUD操作、ステータス更新）
- ストーリー生成と進行
- 行動分析（Vertex AI Gemini使用）
- 画像生成とストレージ管理
- レート制限
- 認証・認可

技術スタック:
- FastAPI: Webフレームワーク
- Firestore: データベース
- Google Cloud Storage: 画像ストレージ
- Vertex AI: AI機能（Gemini）
- Firebase Auth: 認証

環境変数:
- ENVIRONMENT: 実行環境（development/production）
- GOOGLE_APPLICATION_CREDENTIALS: GCP認証情報ファイルパス
- ALLOWED_ORIGINS: CORS許可オリジン
- GCS_BUCKET_NAME: Google Cloud Storageバケット名
"""

from fastapi import FastAPI, HTTPException, Query, Request, Depends
from pydantic import BaseModel
from typing import Optional, List, Any, Dict, Tuple
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from google.cloud import firestore, storage
from google.oauth2 import service_account
from src.services.story_generator import StoryGenerator
from src.services.experience_calculator import ExperienceCalculator
from src.services.task_service import TaskService
from src.models.types import TaskStatus, StoryPhase, Task, Story, Season, User, ErrorMessages
from src.utils.encoders import custom_json_response
from src.services.season_service import SeasonService
from fastapi.middleware.cors import CORSMiddleware
from src.services.story_service import StoryService
from src.utils.firebase_config import db
from src.utils.auth_middleware import verify_token
from src.services.rate_limiter import RateLimiter
from fastapi.responses import JSONResponse
import logging
import time
from collections import defaultdict
from google.cloud.firestore import FieldFilter
from src.services.image_generator import ImageGenerator
from src.services.storage_service import StorageService

# 環境変数の読み込み
load_dotenv()

# 環境変数で本番/テスト/開発環境を切り替え
environment = os.getenv("ENVIRONMENT", "development")
is_development = environment == "development"

# ロギングの設定を修正
logging.basicConfig(
    level=logging.DEBUG if is_development else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # 標準出力のみに変更
    ]
)
logger = logging.getLogger(__name__)

def initialize_firebase():
    """
    Firebase/Firestoreの初期化を行う
    
    Google Cloud認証情報を使用してFirestoreクライアントを初期化し、
    開発環境では接続テストも実行します。
    
    Returns:
        Tuple[Optional[firestore.Client], Optional[service_account.Credentials]]: 
            Firestoreクライアントと認証情報のタプル。
            初期化に失敗した場合は(None, None)を返す。
            
    Raises:
        Exception: 認証情報ファイルの読み込みやFirestore接続に失敗した場合
    """
    try:
        # GOOGLE_APPLICATION_CREDENTIALSから認証情報を取得
        cred = service_account.Credentials.from_service_account_file(
            os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        )
        
        # Firestoreクライアントの初期化
        db = firestore.Client(credentials=cred)
        
        # 接続テストは本番環境ではスキップ
        if is_development:
            test_doc = db.collection('test').document('test')
            test_doc.set({'test': 'test'})
            test_doc.delete()
        
        return db, cred
    except Exception as e:
        logger.error(f"Error initializing Firebase: {str(e)}")
        # エラーをログに記録するが、アプリケーションは起動を継続
        return None, None

# アプリケーションの初期化
try:
    db, cred = initialize_firebase()
    if db is None or cred is None:
        logger.error("Firebase initialization failed, but continuing with limited functionality")
        # 基本的な機能のみでアプリケーションを起動
        app = FastAPI(
            title="ToDo Chronicle API",
            description="ToDo Chronicle API (Limited Mode)",
            version="1.0.0"
        )
    else:
        # 各サービスの初期化
        story_generator = StoryGenerator(db)
        exp_calculator = ExperienceCalculator()
        task_service = TaskService(db)
        season_service = SeasonService(db)
        story_service = StoryService(db)
        rate_limiter = RateLimiter()
        image_generator = ImageGenerator()
        storage_service = StorageService(credentials=cred)

        # 開発環境の設定
        if is_development:
            app = FastAPI(
                title="ToDo Chronicle API",
                description="ToDo Chronicle API",
                version="1.0.0",
                docs_url="/docs",
                redoc_url="/redoc",
                debug=True
            )
        else:
            app = FastAPI(
                title="ToDo Chronicle API",
                description="ToDo Chronicle API",
                version="1.0.0"
            )
except Exception as e:
    logger.error(f"Error during application initialization: {str(e)}")
    # 基本的な機能のみでアプリケーションを起動
    app = FastAPI(
        title="ToDo Chronicle API",
        description="ToDo Chronicle API (Limited Mode)",
        version="1.0.0"
    )

# CORSの設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS").split("|"),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

def rate_limit(endpoint: str):
    """
    レート制限の依存関係を生成する
    
    指定されたエンドポイントに対してレート制限を適用します。
    OPTIONSリクエストは制限をスキップし、制限を超過した場合は429エラーを返します。
    
    Args:
        endpoint (str): レート制限を適用するエンドポイント名
        
    Returns:
        function: FastAPIの依存関係関数
        
    Raises:
        HTTPException: レート制限を超過した場合（429エラー）
    """
    async def dependency(request: Request):
        # OPTIONSリクエストはレート制限をスキップ
        if request.method == "OPTIONS":
            return
            
        # クライアントのIPアドレスを取得
        client_ip = request.client.host if request.client else "127.0.0.1"
        
        try:
            if rate_limiter.check_limit(client_ip, endpoint):
                raise HTTPException(
                    status_code=429,
                    detail=f"レート制限を超過しました。1分間に{rate_limiter.get_limit(endpoint)}回までリクエスト可能です。"
                )
        except HTTPException as e:
            raise e
    return dependency

# グローバルエラーハンドラー
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    グローバル例外ハンドラー
    
    アプリケーション全体で発生した未処理の例外をキャッチし、
    適切なエラーレスポンスを返します。開発環境では詳細なエラー情報も含めます。
    
    Args:
        request (Request): FastAPIリクエストオブジェクト
        exc (Exception): 発生した例外
        
    Returns:
        JSONResponse: エラー情報を含むJSONレスポンス
    """
    logger.error(f"Global error: {exc}")
    if is_development:
        return JSONResponse(
            status_code=500,
            content={
                "message": "Internal server error",
                "detail": str(exc),
                "path": request.url.path
            }
        )
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error"}
    )

@app.get("/health")
async def health_check():
    """
    ヘルスチェックエンドポイント
    
    アプリケーションの稼働状況を確認するためのエンドポイントです。
    現在の環境情報とタイムスタンプを返します。
    
    Returns:
        Dict: ヘルスチェック結果
            {
                "status": "healthy",
                "environment": str,  # 実行環境
                "timestamp": str     # ISO形式のタイムスタンプ
            }
    """
    return {
        "status": "healthy",
        "environment": environment,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/")
def root():
    """
    ルートエンドポイント
    
    アプリケーションの基本情報を返します。
    
    Returns:
        Dict: アプリケーション名とメッセージ
    """
    return {"message": "ToDo Chronicle API is running"}

def handle_error(e: Exception, error_message: str):
    """
    エラーハンドリングの統一化関数
    
    各エンドポイントで発生した例外を統一的な形式で処理します。
    HTTPExceptionの場合はそのまま再送出し、それ以外は500エラーとして処理します。
    
    Args:
        e (Exception): 発生した例外
        error_message (str): エラーメッセージ
        
    Raises:
        HTTPException: 適切なHTTPステータスコードとエラーメッセージ
    """
    logger.error(f"{error_message}: {str(e)}")
    if isinstance(e, HTTPException):
        raise e
    raise HTTPException(status_code=500, detail=str(e))

@app.post("/users", dependencies=[Depends(rate_limit("user_create"))])
async def create_user(user: User, user_id: str = Depends(verify_token)):
    """
    ユーザー作成エンドポイント
    
    認証されたユーザーIDを使用して新しいユーザーを作成し、
    初期シーズンも同時に作成します。
    
    Args:
        user (User): 作成するユーザー情報
        user_id (str): 認証から取得したユーザーID
        
    Returns:
        Dict: 作成されたユーザー情報と初期シーズン情報
            {
                "user": Dict,      # ユーザー情報（ID除外）
                "tasks": List,     # 空のタスクリスト
                "seasons": List    # 初期シーズン情報
            }
            
    Raises:
        HTTPException: ユーザー作成に失敗した場合（500エラー）
    """
    try:
        logger.info(f"ユーザーID: {user_id}")
        # 認証されたユーザーIDを使用してユーザーを作成
        user_ref = db.collection('users').document(user_id)
        user.id = user_id
        user_dict = user.model_dump()
        user_dict['created_at'] = datetime.now()
        user_dict['current_season_id'] = None
        user_dict['season_ids'] = []
        logger.info(f"ユーザー作成: {user_dict}")
        
        user_ref.set(user_dict)
        saved_user = user_ref.get()
        
        if not saved_user.exists:
            raise HTTPException(status_code=500, detail=ErrorMessages.USER_CREATION_FAILED)
        
        # 初期シーズンを作成
        season, updated_user = await season_service.create_initial_season(user)
        
        # シーズンをユーザーのサブコレクションとして保存
        season_ref = user_ref.collection('seasons').document(season.id)
        season_dict = season.model_dump()
        season_ref.set(season_dict)
        
        # ダッシュボード形式のレスポンスを構築（user_idを除外）
        user_response = updated_user.model_dump()
        user_response.pop('id', None)  # user_idを除外
        
        response = {
            "user": user_response,
            "tasks": [],
            "seasons": [season_dict]
        }
        
        return custom_json_response(response)
    except Exception as e:
        handle_error(e, "ユーザー作成エラー")

@app.get("/users/me", dependencies=[Depends(rate_limit("GET_user"))])
async def get_user(user_id: str = Depends(verify_token)):
    """
    ユーザー取得エンドポイント
    
    認証されたユーザーの情報を取得します。
    
    Args:
        user_id (str): 認証から取得したユーザーID
        
    Returns:
        Dict: ユーザー情報
        
    Raises:
        HTTPException: ユーザーが見つからない場合（404エラー）
    """
    try:
        logger.info(f"/users/me: {user_id}")
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail=ErrorMessages.USER_NOT_FOUND)
        
        user_dict = user_doc.to_dict()
        return custom_json_response(user_dict)
    except Exception as e:
        handle_error(e, "ユーザー取得エラー")

@app.get("/users/me/dashboard", dependencies=[Depends(rate_limit("GET_dashboard"))])
async def get_dashboard(user_id: str = Depends(verify_token)):
    """
    ダッシュボード取得エンドポイント
    
    ユーザーのダッシュボード情報（ユーザー情報、タスク一覧、シーズン一覧）を取得します。
    
    Args:
        user_id (str): 認証から取得したユーザーID
        
    Returns:
        Dict: ダッシュボード情報
            {
                "user": Dict,      # ユーザー情報
                "tasks": List,     # タスク一覧
                "seasons": List    # シーズン一覧（現在のシーズンにはストーリーも含む）
            }
            
    Raises:
        HTTPException: ユーザーが見つからない場合（404エラー）
    """
    try:
        logger.info(f"/users/me/dashboard: {user_id}")
        user_ref = db.collection('users').document(user_id)
        user = user_ref.get()
        if not user.exists:
            raise HTTPException(status_code=404, detail=ErrorMessages.USER_NOT_FOUND)
        
        user_dict = user.to_dict()
        
        # タスクの取得
        tasks_list = task_service.get_tasks_for_dashboard(user_ref)
        
        # シーズンの取得
        seasons = season_service.get_seasons_for_dashboard(user_ref, user_dict.get('season_ids', []))
        
        # レスポンスの構築
        response = {
            "user": user_dict,
            "tasks": tasks_list,
            "seasons": seasons
        }
        return custom_json_response(response)
    except Exception as e:
        handle_error(e, "ダッシュボード取得エラー")

@app.get("/users/me/tasks", dependencies=[Depends(rate_limit("GET_tasks"))])
async def get_tasks(user_id: str = Depends(verify_token)):
    """
    タスク一覧取得エンドポイント
    
    ユーザーの全タスク一覧を取得します。
    
    Args:
        user_id (str): 認証から取得したユーザーID
        
    Returns:
        List[Dict]: タスク一覧（各タスクはTaskモデルの形式）
    """
    try:
        logger.debug(f"タスク一覧取得: {user_id}")
        tasks = task_service.get_tasks(user_id)
        logger.debug(f"タスク一覧: {tasks}")
        return [task.model_dump() for task in tasks]
    except Exception as e:
        handle_error(e, "タスク一覧取得エラー")

@app.post("/users/me/tasks", dependencies=[Depends(rate_limit("task_create"))])
async def create_task(task: Task, user_id: str = Depends(verify_token)):
    """
    タスク作成エンドポイント
    
    新しいタスクを作成します。カテゴリが未指定の場合は、
    既存タスクのタイトルから自動的にカテゴリを推定します。
    
    Args:
        task (Task): 作成するタスク情報
        user_id (str): 認証から取得したユーザーID
        
    Returns:
        Dict: 作成されたタスク情報
        
    Raises:
        HTTPException: タスク作成に失敗した場合（500エラー）
    """
    try:
        logger.info(f"タスク作成: {user_id}")
        created_task = await task_service.create_task(task, user_id)
        return custom_json_response(created_task.model_dump())
    except Exception as e:
        handle_error(e, "タスク作成エラー")

@app.put("/users/me/tasks/{task_id}", dependencies=[Depends(rate_limit("task_update"))])
async def update_task(task_id: str, task: Task, user_id: str = Depends(verify_token)):
    """
    タスク更新エンドポイント
    
    指定されたタスクの情報を更新します。
    
    Args:
        task_id (str): 更新するタスクのID
        task (Task): 更新するタスク情報
        user_id (str): 認証から取得したユーザーID
        
    Returns:
        Dict: 更新されたタスク情報
        
    Raises:
        HTTPException: タスクが見つからない場合（404エラー）または更新に失敗した場合（500エラー）
    """
    try:
        logger.info(f"タスク更新: task_id={task_id}, user_id={user_id}")
        task.id = task_id
        result = await task_service.update_task(task, user_id)
        return result
    except Exception as e:
        handle_error(e, "タスク更新エラー")

@app.delete("/users/me/tasks/{task_id}", dependencies=[Depends(rate_limit("task_delete"))])
async def delete_task(task_id: str, user_id: str = Depends(verify_token)):
    """
    タスク削除エンドポイント
    
    指定されたタスクを削除します。
    
    Args:
        task_id (str): 削除するタスクのID
        user_id (str): 認証から取得したユーザーID
        
    Raises:
        HTTPException: タスクが見つからない場合（404エラー）または削除に失敗した場合（500エラー）
    """
    try:
        logger.info(f"タスク削除リクエスト: task_id={task_id}, user_id={user_id}")
        task_service.delete_task(task_id, user_id)
        logger.info(f"タスク削除成功: task_id={task_id}")
    except Exception as e:
        handle_error(e, "タスク削除エラー")

@app.put("/users/me/tasks/{task_id}/status", dependencies=[Depends(rate_limit("task_status_update"))])
async def update_task_status(task_id: str, status_update: dict, user_id: str = Depends(verify_token)):
    """
    タスクステータス更新エンドポイント
    
    指定されたタスクのステータスを更新します。
    完了ステータスに変更した場合は、経験値計算とストーリー進行のトリガーとなります。
    
    Args:
        task_id (str): 更新するタスクのID
        status_update (dict): 更新するステータス情報 {"status": TaskStatus}
        user_id (str): 認証から取得したユーザーID
        
    Returns:
        Dict: 更新されたタスク情報
        
    Raises:
        HTTPException: ステータスが指定されていない場合（400エラー）、
                      タスクが見つからない場合（404エラー）、
                      更新に失敗した場合（500エラー）
    """
    try:
        status = status_update.get('status')
        if status is None:
            raise HTTPException(status_code=400, detail="status is required")
            
        logger.info(f"タスクステータス更新: task_id={task_id}, status={status}, user_id={user_id}")
        result = task_service.update_task_status(task_id, status, user_id)
        return result
    except Exception as e:
        handle_error(e, "タスクステータス更新エラー")

@app.put("/users/me/experience", dependencies=[Depends(rate_limit("exp_update"))])
async def update_user_experience(user_id: str = Depends(verify_token)):
    """
    ユーザー経験値更新エンドポイント
    
    完了したタスクに基づいて経験値を計算し、ストーリーを進行させます。
    必要に応じて行動分析も実行されます。
    
    Args:
        user_id (str): 認証から取得したユーザーID
        
    Returns:
        Dict: 更新結果
            {
                "user": Dict,           # 更新されたユーザー情報
                "earned_exp": int,      # 獲得経験値
                "season": Dict,         # 更新されたシーズン情報
                "story": Dict,          # 生成されたストーリー情報
                "new_season": Dict      # 新シーズン情報（作成された場合）
            }
            
    Raises:
        HTTPException: ユーザーまたはシーズンが見つからない場合（404エラー）、
                      更新に失敗した場合（500エラー）
    """
    try:
        result = await season_service.progress_story(user_id)
        return custom_json_response(result)
    except Exception as e:
        handle_error(e, "経験値更新エラー")

@app.get("/users/me/seasons/{season_id}/stories")
async def get_season_stories(user_id: str = Depends(verify_token), season_id: str = None):
    """
    シーズンのストーリー一覧取得エンドポイント
    
    指定されたシーズンの全ストーリーを取得します。
    ストーリーは章番号の降順でソートされます。
    
    Args:
        user_id (str): 認証から取得したユーザーID
        season_id (str): 取得するシーズンのID
        
    Returns:
        Dict: ストーリー一覧
            {
                "stories": List[Dict]  # ストーリー一覧（章番号降順）
            }
            
    Raises:
        HTTPException: ユーザーまたはシーズンが見つからない場合（404エラー）
    """
    try:
        user_ref = db.collection('users').document(user_id)
        user = user_ref.get()
        if not user.exists:
            raise HTTPException(status_code=404, detail=ErrorMessages.USER_NOT_FOUND)
        
        season_ref = user_ref.collection('seasons').document(season_id)
        season = season_ref.get()
        if not season.exists:
            raise HTTPException(status_code=404, detail=ErrorMessages.SEASON_NOT_FOUND)
        
        stories_ref = season_ref.collection('stories')
        # chapter_noの降順でストーリーを取得
        stories = stories_ref.order_by('chapter_no', direction=firestore.Query.DESCENDING).stream()
        stories_list = [doc.to_dict() for doc in stories]
        return custom_json_response({"stories": stories_list})
    except Exception as e:
        handle_error(e, "シーズンのストーリー一覧取得エラー")

@app.get("/users/me/seasons/{season_id}/story-image-url")
async def get_story_image_url(season_id: str, user_id: str = Depends(verify_token)):
    """
    ストーリー画像URL取得エンドポイント
    
    指定されたシーズンのストーリー画像の署名付きURLを取得します。
    URLは5分間有効です。
    
    Args:
        season_id (str): シーズンID
        user_id (str): 認証から取得したユーザーID
        
    Returns:
        Dict: 画像URL
            {
                "url": str  # 署名付きURL
            }
            
    Raises:
        HTTPException: シーズンが見つからない場合（404エラー）、
                      画像ファイル名が未設定の場合（404エラー）、
                      URL生成に失敗した場合（500エラー）
    """
    try:
        # Firestoreからファイル名を取得
        user_ref = db.collection('users').document(user_id)
        season_ref = user_ref.collection('seasons').document(season_id)
        season_doc = season_ref.get()
        if not season_doc.exists:
            raise HTTPException(status_code=404, detail="シーズンが見つかりません")
        season_data = season_doc.to_dict()
        filename = season_data.get('story_image_filename')
        if not filename:
            raise HTTPException(status_code=404, detail="画像ファイル名が未設定です")

        # StorageServiceで署名付きURL生成
        bucket_name = os.getenv("GCS_BUCKET_NAME")
        storage_path = f"images/user_{user_id}/{filename}"
        url = await storage_service.get_signed_url(bucket_name, storage_path, expiration=300)
        return {"url": url}
    except Exception as e:
        logger.error(f"ストーリー画像URL取得エラー: {str(e)}")
        handle_error(e, "ストーリー画像URL取得エラー")


