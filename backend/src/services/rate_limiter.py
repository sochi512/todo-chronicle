from collections import defaultdict
import time
import os
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)
        self.blocked_ips = defaultdict(float)
        self.window_size = int(os.getenv("RATE_LIMIT_WINDOW_SIZE", "60"))
        self.block_duration = int(os.getenv("RATE_LIMIT_BLOCK_DURATION", "300"))
        self.limits = {
            # 更新系エンドポイント
            "user_create": int(os.getenv("RATE_LIMIT_USER_CREATE", "3")),
            "task_create": int(os.getenv("RATE_LIMIT_TASK_CREATE", "10")),
            "task_update": int(os.getenv("RATE_LIMIT_TASK_UPDATE", "60")),
            "task_delete": int(os.getenv("RATE_LIMIT_TASK_DELETE", "60")),  # タスク削除用の制限を追加
            "exp_update": int(os.getenv("RATE_LIMIT_EXP_UPDATE", "10")),
            
            # 参照系エンドポイント（共通設定）
            "read": int(os.getenv("RATE_LIMIT_READ", "30")),  # 1分間に30回まで
        }

    def check_limit(self, key: str, endpoint: str) -> bool:
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
        return self.limits.get(endpoint, 0) 