import os
from typing import Dict, Optional
import logging
import replicate
from io import BytesIO
from PIL import Image
from .prompt_generator import PromptGenerator
import io
import asyncio

logger = logging.getLogger(__name__)

class ImageGenerator:
    """
    ストーリー用の画像を生成するサービス
    
    このクラスは、ストーリーテキストから画像生成用のプロンプトを生成し、
    Replicate APIを使用してImagen-3モデルで画像を生成します。
    
    生成された画像は自動的に圧縮され、指定サイズ以下に最適化されます。
    
    Attributes:
        model (str): 使用する画像生成モデル（google/imagen-3）
        replicate_token (str): Replicate APIトークン
        client: Replicateクライアントインスタンス
        prompt_generator: プロンプト生成サービスインスタンス
    """

    def __init__(self):
        """
        ImageGeneratorの初期化
        
        Replicate APIトークンを環境変数から取得し、
        クライアントとプロンプト生成サービスを初期化します。
        
        Required Environment Variables:
            REPLICATE_API_TOKEN: Replicate APIトークン
            
        Raises:
            ValueError: REPLICATE_API_TOKENが設定されていない場合
        """
        self.model = "google/imagen-3"
        self.replicate_token = os.getenv("REPLICATE_API_TOKEN")
        if not self.replicate_token:
            raise ValueError("REPLICATE_API_TOKEN が設定されていません")
        
        # replicateクライアントの初期化
        self.client = replicate.Client(api_token=self.replicate_token)
        
        # プロンプト生成サービスの初期化
        self.prompt_generator = PromptGenerator()

    def compress_to_target_size(self, image_bytes: bytes, target_size_kb: int = 500, min_quality: int = 60, max_quality: int = 95) -> bytes:
        """
        画像を圧縮して指定サイズ以下にする
        
        WebP形式で画像を圧縮し、指定されたサイズ以下になるまで
        品質を段階的に下げて最適化します。
        
        Args:
            image_bytes (bytes): 圧縮対象の画像データ
            target_size_kb (int): 目標サイズ（KB単位、デフォルト: 500）
            min_quality (int): 最小品質（デフォルト: 60）
            max_quality (int): 最大品質（デフォルト: 95）
            
        Returns:
            bytes: 圧縮された画像データ（WebP形式）
            
        Examples:
            >>> generator = ImageGenerator()
            >>> compressed = generator.compress_to_target_size(image_data, 300)
            >>> print(f"圧縮後サイズ: {len(compressed) / 1024:.1f}KB")
            
        Note:
            - WebP形式で圧縮されます
            - 品質は5刻みで段階的に下げられます
            - 最低品質でも目標サイズを超える場合は最低品質で返されます
        """
        image = Image.open(io.BytesIO(image_bytes))
        quality = max_quality
        for q in range(max_quality, min_quality - 1, -5):
            output = io.BytesIO()
            image.save(output, format="WebP", quality=q, method=6)
            size_kb = output.tell() / 1024
            if size_kb <= target_size_kb:
                return output.getvalue()
            quality = q
        # 最低品質でも超える場合は最低品質で返す
        output = io.BytesIO()
        image.save(output, format="WebP", quality=min_quality, method=6)
        return output.getvalue()

    async def generate_story_image(self, story_text: str) -> Dict[str, bytes]:
        """
        ストーリーテキストから画像を生成する
        
        ストーリーテキストを分析して画像生成用のプロンプトを生成し、
        Replicate APIを使用してImagen-3モデルで画像を生成します。
        生成された画像は自動的に圧縮されます。
        
        Args:
            story_text (str): 画像生成の元となるストーリーテキスト
            
        Returns:
            Dict[str, bytes]: 生成された画像データを含む辞書
                - "image_data": 圧縮された画像データ（WebP形式）
                
        Raises:
            Exception: 画像生成に失敗した場合（リトライ後も失敗）
            
        Examples:
            >>> generator = ImageGenerator()
            >>> result = await generator.generate_story_image("冒険者が城に到着した")
            >>> image_data = result["image_data"]
            >>> print(f"生成された画像サイズ: {len(image_data)} bytes")
            
        Note:
            - 最大リトライ回数は環境変数IMAGE_GEN_MAX_RETRIESで設定可能（デフォルト: 3）
            - リトライ間隔は指数バックオフで増加します
            - 生成された画像は500KB以下に自動圧縮されます
            - アスペクト比は1:1（正方形）で生成されます
        """
        # 先にダミー画像（テスト用画像）があればそれを返す
        # dummy_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../tests/test_images/real_test_image.png'))
        # if os.path.exists(dummy_path):
        #     with open(dummy_path, "rb") as f:
        #         image_data = f.read()
        #     print(f"ダミー画像を返します: {dummy_path}")
        #     return {"image_data": image_data}
        # return

        # ここから下は本番用のReplicate 
        max_retries = int(os.getenv("IMAGE_GEN_MAX_RETRIES", 3))
        retry_delay = 1  # 秒

        for attempt in range(max_retries):
            try:
                # プロンプトの生成（awaitでOK）
                prompt = await self.prompt_generator.generate_prompt(story_text)
                
                # Replicate API呼び出しをスレッドプールで実行
                output = await asyncio.to_thread(
                    self.client.run,
                    "google/imagen-3",
                    input={
                        "prompt": prompt,
                        "aspect_ratio": "1:1",
                        "safety_filter_level": "block_only_high"
                    }
                )

                # 画像データ取得もスレッドで
                image_data = await asyncio.to_thread(output.read)

                # 画像圧縮もスレッドプールで実行
                compressed_data = await asyncio.to_thread(
                    self.compress_to_target_size,
                    image_data,
                    500
                )

                return {
                    "image_data": compressed_data
                }

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"画像生成リトライ {attempt + 1}/{max_retries}: {str(e)}")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                else:
                    logger.error(f"画像生成エラー（最終）: {str(e)}")
                    raise Exception(f"画像生成に失敗しました（{max_retries}回試行）: {str(e)}")
 