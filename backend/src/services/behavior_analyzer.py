import logging
import json
import os
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
import vertexai
from vertexai.preview.generative_models import GenerativeModel, GenerationConfig
from src.models.types import TaskCategory

logger = logging.getLogger(__name__)

class BehaviorAnalyzer:
    """
    ユーザーの行動パターンを分析するサービス
    
    このクラスは、Vertex AIのGeminiモデルを使用して完了したタスクの一覧から
    ユーザーの行動傾向や価値観を分析し、ポジティブな洞察とキーワードを生成します。
    
    Attributes:
        model: Vertex AIのGenerativeModelインスタンス
        analysis_prompt: 行動分析用のプロンプトテンプレート
    """

    def __init__(self):
        """
        BehaviorAnalyzerの初期化
        
        環境変数を読み込み、Vertex AIを初期化し、
        行動分析用のプロンプトを設定します。
        
        Raises:
            ValueError: 必要な環境変数が設定されていない場合
            Exception: Vertex AI初期化に失敗した場合
        """
        # 環境変数の読み込み
        load_dotenv()
        self._initialize_vertex_ai()
        
        # 行動分析用のプロンプト
        self.analysis_prompt = """
あなたは異世界ファンタジーの賢者として、ユーザーの行動を静かに見守るAIです。  
以下のタスク履歴から、ユーザーの行動傾向を洞察し、次の形式で出力してください。

【出力形式】
次のJSON構造に正確に従ってください。
```json
{{
  "title": "語り手の称号（最大10文字、日本語）",
  "name": "語り手の名前（最大8文字、日本語）",
  "insight": "150文字以内の前向きな洞察文（2文、賢者風）",
  "keywords": ["キーワード1", "キーワード2", "キーワード3"]
}}
```

【文体・出力ルール】
- 文体は「厳格で静かな賢者風」（敬語＋断定調）
- カジュアルな語尾（例：〜ですね）は使わない
- 洞察文には、行動傾向や取り組み方を1〜2つ具体的に含める
- キーワードは抽象的な行動資質（例：継続力、柔軟性、責任感など）
- タスクの傾向（カテゴリや内容）に基づいて、語り手の称号と名前を調整してください。
- たとえば、学習が多ければ「知の探求者」や「図書の賢者」、運動が多ければ「体律の観察者」「風見の導師」などが適しています。
- 生成する名前は西洋ファンタジー風にし、語り手の気質や象徴に合った音感をもたせてください。カタカナで出力してください。

【文体例】
物事に丁寧に向き合い、自らの責任を果たす姿勢が表れています。  
着実な歩みの中に、揺るぎない信念が感じられます。

【タスク】
{task_data}
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
            logger.error(f"BehaviorAnalyzer - Vertex AI初期化エラー: {str(e)}")
            raise

    async def analyze_behavior(self, completed_tasks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        完了したタスク一覧から行動分析を実行する
        
        Vertex AIのGeminiモデルを使用して、完了したタスクの一覧を分析し、
        ユーザーの行動傾向や価値観を要約した洞察とキーワードを生成します。
        
        Args:
            completed_tasks (List[Dict[str, Any]]): 完了したタスクの一覧
                各タスクは以下の形式:
                {
                    "title": str,  # タスクタイトル
                    "category": int,  # カテゴリ数値（TaskCategory列挙型の値）
                    "completed_at": str  # 完了日時（ISO形式）
                }
            
        Returns:
            Optional[Dict[str, Any]]: 分析結果
                {
                    "title": str,  # 賢者の称号
                    "name": str,  # 語り手の名前
                    "summary": str,  # 行動の傾向から読み取れる前向きな気づき（150文字以内）
                    "keywords": List[str]  # キーワード3語のリスト
                }
                分析に失敗した場合はNoneを返す
                
        Note:
            - タスクが10件未満の場合は、そのまま分析を実行
            - タスクが10件を超える場合は、最新の10件のみを使用
            - AIからの応答がJSON形式でない場合はNoneを返す
            - エラーが発生した場合もNoneを返す
        """
        logger.info(f"行動分析開始: {len(completed_tasks)}件のタスク")
        
        try:
            # タスクが10件を超える場合は最新の10件のみを使用
            if len(completed_tasks) > 10:
                completed_tasks = completed_tasks[-10:]
                logger.info(f"タスク分析を実行")
            
            # タスクデータをプロンプト用の形式に変換
            task_data = self._format_tasks_for_analysis(completed_tasks)
            
            # 生成設定
            generation_config = GenerationConfig(
                temperature=0.3,  # 創造性と一貫性のバランス
                max_output_tokens=256,  # JSON出力に十分な長さ
                top_p=0.9,
                top_k=40
            )
            
            # プロンプトにタスクデータを埋め込み
            prompt = self.analysis_prompt.format(task_data=task_data)
            # Vertex AIを使用して行動分析を実行
            response = await self.model.generate_content_async(
                prompt,
                generation_config=generation_config
            )
            
            # レスポンスからJSONを抽出
            response_text = response.text.strip()
            
            # Markdownのコードブロックを除去
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            # デバッグ用：処理後のレスポンスをログ出力
            logger.debug(f"処理後のレスポンス: {repr(response_text)}")
            
            # JSONパース
            try:
                result = json.loads(response_text)
                title = result.get("title", "")
                name = result.get("name", "")
                insight = result.get("insight", "")
                keywords = result.get("keywords", [])
                
                return {
                    "title": title,
                    "name": name,
                    "insight": insight,
                    "keywords": keywords
                }
                    
            except json.JSONDecodeError as e:
                logger.error(f"JSONパースエラー: {str(e)}, レスポンス: {repr(response_text)}")
                return None

        except Exception as e:
            logger.error(f"行動分析エラー: {str(e)}")
            return None

    def _format_tasks_for_analysis(self, completed_tasks: List[Dict[str, Any]]) -> str:
        """
        タスクデータを分析用の形式に変換する
        
        完了したタスクの一覧を、AI分析用のJSON形式の文字列に変換します。
        Taskモデルから必要項目（title, category, completed_at）のみを抽出します。
        
        Args:
            completed_tasks (List[Dict[str, Any]]): 完了したタスクの一覧
                各タスクはTaskモデルの形式:
                {
                    "id": str,
                    "title": str,  # タスクタイトル
                    "category": int,  # カテゴリ数値（TaskCategory列挙型の値）
                    "completed_at": datetime,  # 完了日時
                    "status": TaskStatus,
                    "due_date": Optional[datetime],
                    "season_id": Optional[str],
                    "created_at": datetime,
                    "experienced_at": Optional[datetime]
                }
            
        Returns:
            str: 分析用のJSON形式文字列
            
        Examples:
            >>> analyzer = BehaviorAnalyzer()
            >>> tasks = [
            ...     {"title": "商談資料", "category": 1, "completed_at": "2024-01-01T10:00:00Z"}
            ... ]
            >>> formatted = analyzer._format_tasks_for_analysis(tasks)
            >>> print(formatted)
            # [{"task": "商談資料", "category": "仕事"}]
        """
        category_map = {
            TaskCategory.WORK: "仕事",
            TaskCategory.HEALTH: "健康",
            TaskCategory.LEARNING: "学習",
            TaskCategory.LIFE: "生活",
            TaskCategory.HOBBY: "趣味",
            TaskCategory.OTHER: "その他"
        }
        
        formatted_tasks = []
        for task in completed_tasks:
            # Taskモデルから必要項目のみを抽出
            title = task.get("title", "")
            category_value = task.get("category")
            category_text = category_map.get(category_value, "その他")
            
            # 完了日時がある場合のみ分析対象とする
            if task.get("completed_at"):
                formatted_tasks.append({
                    "task": title,
                    "category": category_text
                })
        
        return json.dumps(formatted_tasks, ensure_ascii=False, indent=2)
