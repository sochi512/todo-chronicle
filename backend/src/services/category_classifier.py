import logging
import json
import os
from typing import Dict, Optional
from dotenv import load_dotenv
import vertexai
from vertexai.preview.generative_models import GenerativeModel, GenerationConfig
from src.models.types import TaskCategory

logger = logging.getLogger(__name__)

class CategoryClassifier:
    """
    タスクのカテゴリを自動分類するサービス
    
    このクラスは、Vertex AIのGeminiモデルを使用してタスクのタイトルから
    適切なカテゴリを自動的に分類します。
    
    カテゴリは以下の6つから選択されます：
    - WORK (1): 仕事 - 業務・タスク・ビジネス系
    - HEALTH (2): 健康 - 運動・休養・自己ケア
    - LEARNING (3): 学習 - 勉強・読書・スキル習得
    - LIFE (4): 生活 - 掃除・洗濯・家事・日常雑務
    - HOBBY (5): 趣味 - ゲーム・創作・音楽など娯楽全般
    - OTHER (6): その他 - 分類不能なもの、曖昧な行動など
    
    Attributes:
        model: Vertex AIのGenerativeModelインスタンス
        classification_prompt: カテゴリ分類用のプロンプトテンプレート
    """

    def __init__(self):
        """
        CategoryClassifierの初期化
        
        環境変数を読み込み、Vertex AIを初期化し、
        カテゴリ分類用のプロンプトを設定します。
        
        Raises:
            ValueError: 必要な環境変数が設定されていない場合
            Exception: Vertex AI初期化に失敗した場合
        """
        # 環境変数の読み込み
        load_dotenv()
        self._initialize_vertex_ai()
        
        # カテゴリ分類用のプロンプト
        self.classification_prompt = """
あなたは短いタスク内容を読み取り、6つのカテゴリのうちもっとも適切な1つに分類する分類アシスタントです。

以下のカテゴリの中から、もっとも適切なものを1つだけ選び、
次のJSON形式で出力してください：

{{
"category": "◯◯"
}}

カテゴリは以下から選んでください：
仕事 / 健康 / 学習 / 生活 / 趣味 / その他

補足説明や他の出力は一切不要です。
判断が難しい場合は "その他" を選んでください。

タスク内容: {task_title}
"""

    def _initialize_vertex_ai(self):
        """
        Vertex AIの初期化
        
        環境変数から設定を取得し、Vertex AIクライアントと
        GenerativeModelを初期化します。
        
        Required Environment Variables:
            GOOGLE_CLOUD_PROJECT: Google Cloud プロジェクトID
            VERTEX_AI_LOCATION: Vertex AIのリージョン
            VERTEX_AI_MODEL_NAME: 使用するモデル名
            
        Raises:
            ValueError: 必要な環境変数が設定されていない場合
            Exception: Vertex AI初期化に失敗した場合
        """
        try:
            # 環境変数から設定を取得
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
            location = os.getenv("VERTEX_AI_LOCATION")
            model_name = os.getenv("VERTEX_AI_MODEL_NAME")
            
            # Vertex AIの初期化
            vertexai.init(
                project=project_id,
                location=location
            )
            
            # モデルの初期化
            self.model = GenerativeModel(model_name)
            
        except Exception as e:
            logger.error(f"Vertex AI初期化エラー: {str(e)}")
            raise

    async def classify_task_category(self, task_title: str) -> Optional[int]:
        """
        タスクのタイトルからカテゴリを自動分類する
        
        Vertex AIのGeminiモデルを使用して、タスクのタイトルを分析し、
        最も適切なカテゴリを数値で返します。
        
        Args:
            task_title (str): 分類対象のタスクタイトル
            
        Returns:
            Optional[int]: 分類されたカテゴリの数値（TaskCategory列挙型の値）
                          分類に失敗した場合はTaskCategory.OTHERを返す
                          
        Examples:
            >>> classifier = CategoryClassifier()
            >>> category = await classifier.classify_task_category("会議の資料を準備する")
            >>> print(category)  # 1 (TaskCategory.WORK)
            
        Note:
            - AIからの応答がJSON形式でない場合はTaskCategory.OTHERを返す
            - 無効なカテゴリが返された場合もTaskCategory.OTHERを返す
            - エラーが発生した場合もTaskCategory.OTHERを返す
        """
        logger.info(f"カテゴリ分類開始: {task_title}")
        try:
            # 生成設定
            generation_config = GenerationConfig(
                temperature=0.1,  # 一貫性を重視
                max_output_tokens=128,  # JSON出力に十分な長さ
                top_p=0.9,
                top_k=40
            )
            
            # プロンプトにタスクタイトルを埋め込み
            prompt = self.classification_prompt.format(task_title=task_title)
            logger.debug(f"生成されたプロンプト: {prompt}")
            
            # Vertex AIを使用してカテゴリを分類
            response = await self.model.generate_content_async(
                prompt,
                generation_config=generation_config
            )
            
            # レスポンスからJSONを抽出
            response_text = response.text.strip()
            logger.debug(f"カテゴリ分類レスポンス: {response_text}")
            
            # Markdownのコードブロックを除去
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            # JSONパース
            try:
                result = json.loads(response_text)
                category_text = result.get("category")
                logger.debug(f"パースされたカテゴリ: {category_text}")
                
                # 文字列から数値に変換
                category_value = self._convert_category_to_value(category_text)
                if category_value is not None:
                    logger.info(f"タスク '{task_title}' をカテゴリ '{category_value}' ({category_text}) に分類しました")
                    return category_value
                else:
                    logger.warning(f"無効なカテゴリが返されました: {category_text}")
                    return TaskCategory.OTHER
                    
            except json.JSONDecodeError as e:
                logger.error(f"JSONパースエラー: {str(e)}, レスポンス: {response_text}")
                return TaskCategory.OTHER

        except Exception as e:
            logger.error(f"カテゴリ分類エラー: {str(e)}")
            return TaskCategory.OTHER

    def _convert_category_to_value(self, category_text: str) -> Optional[int]:
        """
        カテゴリの文字列を数値に変換する
        
        AIから返された文字列のカテゴリ名を、TaskCategory列挙型の
        数値に変換します。
        
        Args:
            category_text (str): カテゴリの文字列（"仕事", "健康", "学習", "生活", "趣味", "その他"）
            
        Returns:
            Optional[int]: 対応するTaskCategoryの数値、無効な場合はNone
            
        """
        category_map = {
            "仕事": TaskCategory.WORK,
            "健康": TaskCategory.HEALTH,
            "学習": TaskCategory.LEARNING,
            "生活": TaskCategory.LIFE,
            "趣味": TaskCategory.HOBBY,
            "その他": TaskCategory.OTHER
        }
        return category_map.get(category_text)

    def get_available_categories(self) -> Dict[int, str]:
        """
        利用可能なカテゴリの辞書を取得
        
        フロントエンドでカテゴリ選択UIを構築する際に使用します。
        数値をキーとし、絵文字付きの文字列を値とする辞書を返します。
        
        Returns:
            Dict[int, str]: カテゴリの数値と絵文字付き文字列の辞書
        """
        return {
            TaskCategory.WORK: "💼 仕事",
            TaskCategory.HEALTH: "🏃 健康",
            TaskCategory.LEARNING: "📖 学習",
            TaskCategory.LIFE: "🧺 生活",
            TaskCategory.HOBBY: "🧩 趣味",
            TaskCategory.OTHER: "🌐 その他"
        } 