from google.cloud import storage
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self, credentials=None):
        self.storage_client = storage.Client(credentials=credentials)

    async def upload_image(self, bucket_name: str, storage_path: str, image_data: bytes) -> Optional[str]:
        """
        GCSに画像をアップロードします。
        
        Args:
            bucket_name (str): バケット名
            storage_path (str): 保存先のパス
            image_data (bytes): 画像データ
            
        Returns:
            Optional[str]: アップロードされた画像のパス
        """
        try:
            logger.debug(f"bucket_name: {bucket_name}")
            logger.debug(f"storage_path: {storage_path}")
            # バケットの取得
            bucket = self.storage_client.bucket(bucket_name)
            
            # 新しいBlobを作成
            blob = bucket.blob(storage_path)
            
            # 画像データをアップロード
            blob.upload_from_string(
                image_data,
                content_type='image/png'
            )
            
            logger.info(f"画像をGCSにアップロードしました: {storage_path}")
            return storage_path
            
        except Exception as e:
            logger.error(f"GCSアップロードエラー: {str(e)}")
            raise Exception(f"GCSへのアップロードに失敗しました: {str(e)}")

    async def get_signed_url(self, bucket_name: str, storage_path: str, expiration: int = 3600) -> str:
        """
        署名付きURLを生成します。
        
        Args:
            bucket_name (str): バケット名
            storage_path (str): ファイルパス
            expiration (int): URLの有効期限（秒）
            
        Returns:
            str: 署名付きURL
        """
        try:
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(storage_path)
            
            url = blob.generate_signed_url(
                version="v4",
                expiration=expiration,
                method="GET"
            )
            
            return url
            
        except Exception as e:
            logger.error(f"署名付きURL生成エラー: {str(e)}")
            raise Exception(f"署名付きURLの生成に失敗しました: {str(e)}") 