from collections import defaultdict
import time
import os
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    APIレート制限を管理するサービス
    
    このクラスは、クライアントのIPアドレスベースでAPIエンドポイントへの
    アクセス頻度を制限し、過度なリクエストを防ぎます。
    
    機能:
    - エンドポイント別のレート制限設定
    - 時間枠ベースのリクエストカウント
    - 過度なリクエストに対する一時的なブロック
    - 環境変数による設定のカスタマイズ
    
    Attributes:
        requests: クライアントIP別のリクエスト履歴（タイムスタンプのリスト）
        blocked_ips: ブロック中のIPアドレスとブロック終了時刻
        window_size: レート制限の時間枠（秒）
        block_duration: ブロック期間（秒）
        limits: エンドポイント別のレート制限設定
    """

    def __init__(self):
        """
        RateLimiterの初期化
        
        環境変数からレート制限の設定を読み込み、各エンドポイントの
        制限値を設定します。
        
        Environment Variables:
            RATE_LIMIT_WINDOW_SIZE: レート制限の時間枠（秒）
            RATE_LIMIT_BLOCK_DURATION: ブロック期間（秒）
            RATE_LIMIT_USER_CREATE: ユーザー作成の制限
            RATE_LIMIT_TASK_CREATE: タスク作成の制限
            RATE_LIMIT_TASK_UPDATE: タスク更新の制限
            RATE_LIMIT_TASK_DELETE: タスク削除の制限
            RATE_LIMIT_EXP_UPDATE: 経験値更新の制限
            RATE_LIMIT_READ: 参照系エンドポイントの制限
        """
        self.requests = defaultdict(list)
        self.blocked_ips = defaultdict(float)
        self.window_size = int(os.getenv("RATE_LIMIT_WINDOW_SIZE"))
        self.block_duration = int(os.getenv("RATE_LIMIT_BLOCK_DURATION"))
        self.limits = {
            # 更新系エンドポイント
            "user_create": int(os.getenv("RATE_LIMIT_USER_CREATE")),
            "task_create": int(os.getenv("RATE_LIMIT_TASK_CREATE")),
            "task_update": int(os.getenv("RATE_LIMIT_TASK_UPDATE")),
            "task_delete": int(os.getenv("RATE_LIMIT_TASK_DELETE")),  # タスク削除用の制限を追加
            "exp_update": int(os.getenv("RATE_LIMIT_EXP_UPDATE")),
            
            # 参照系エンドポイント（共通設定）
            "read": int(os.getenv("RATE_LIMIT_READ")),  # 1分間に30回まで
        }

    def check_limit(self, key: str, endpoint: str) -> bool:
        """
        レート制限をチェックし、必要に応じてブロックを実行する
        
        指定されたキー（通常はIPアドレス）とエンドポイントに対して
        レート制限をチェックします。制限を超過した場合は適切な
        エラーレスポンスを返します。
        
        Args:
            key (str): クライアントの識別子（通常はIPアドレス）
            endpoint (str): アクセス対象のエンドポイント名
            
        Returns:
            bool: レート制限内の場合はFalse、制限超過の場合はTrue
            
        Raises:
            HTTPException: レート制限を超過した場合（429エラー）
            
        Note:
            - 参照系エンドポイント（GET_で始まる）は共通の制限を適用
            - 1分間に60回以上のリクエストがあると一時的なブロックが実行される
            - ブロック期間中は429エラーが返される
        """
        now = time.time()
        
        # デバッグログの追加
        logger.debug(f"Rate limit check - Key: {key}, Endpoint: {endpoint}")
        logger.debug(f"Current requests: {self.requests[key]}")
        logger.debug(f"Window size: {self.window_size}, Block duration: {self.block_duration}")
        logger.debug(f"Limit for {endpoint}: {self.limits.get(endpoint)}")
        
        # ブロック状態のチェック
        if key in self.blocked_ips:
            if now < self.blocked_ips[key]:
                logger.debug(f"IP {key} is blocked until {self.blocked_ips[key]}")
                raise HTTPException(
                    status_code=429,
                    detail=f"レート制限を超過したため、{int((self.blocked_ips[key] - now) / 60)}分間ブロックされています。"
                )
            else:
                del self.blocked_ips[key]
                logger.debug(f"Block for IP {key} has expired")
        
        # 時間枠内のリクエストのみを保持
        window_start = now - self.window_size
        self.requests[key] = [t for t in self.requests[key] if t > window_start]
        logger.debug(f"Requests in current window: {len(self.requests[key])}")
        
        # 参照系エンドポイントの場合は共通の制限を適用
        if endpoint.startswith("GET_"):
            limit = self.limits.get("read")
        else:
            limit = self.limits.get(endpoint)
            
        if not limit:
            logger.debug(f"No limit set for endpoint {endpoint}")
            return False
            
        # 現在の時間枠内のリクエスト数を確認
        current_requests = len(self.requests[key])
        logger.debug(f"Current requests: {current_requests}, Limit: {limit}")
        
        if current_requests >= limit:
            # 1分間に60回以上のリクエストがあった場合、ブロックを開始
            if current_requests >= 60:
                self.blocked_ips[key] = now + self.block_duration
                logger.debug(f"IP {key} blocked for {self.block_duration} seconds")
                raise HTTPException(
                    status_code=429,
                    detail=f"レート制限を大幅に超過したため、{self.block_duration / 60}分間ブロックされます。"
                )
            logger.debug(f"Rate limit exceeded for {endpoint}")
            return True
            
        self.requests[key].append(now)
        logger.debug(f"Request added to counter for {endpoint}")
        return False

    def get_limit(self, endpoint: str) -> int:
        """
        指定されたエンドポイントのレート制限値を取得する
        
        Args:
            endpoint (str): エンドポイント名
            
        Returns:
            int: エンドポイントのレート制限値（設定されていない場合は0）
            
        """
        return self.limits.get(endpoint, 0) 