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
    def __init__(self):
        self.model = "google/imagen-3"
        self.replicate_token = os.getenv("REPLICATE_API_TOKEN")
        if not self.replicate_token:
            raise ValueError("REPLICATE_API_TOKEN が設定されていません")
        
        # replicateクライアントの初期化
        self.client = replicate.Client(api_token=self.replicate_token)
        
        # プロンプト生成サービスの初期化
        self.prompt_generator = PromptGenerator()

    def compress_to_target_size(self, image_bytes, target_size_kb=500, min_quality=60, max_quality=95):
        """
        画像を圧縮して指定サイズ以下にする
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
        """"""
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
 