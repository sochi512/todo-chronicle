import logging
import json
import os
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
import vertexai
from vertexai.preview.generative_models import GenerativeModel, GenerationConfig
from src.models.types import TaskCategory
from datetime import datetime, timezone, timedelta

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
あなたは異世界ファンタジーの賢者として、ユーザーの行動を静かに見守り、導くAIです。  
以下のタスク履歴から、ユーザーの行動傾向を洞察し、次の行動の提案も含めて次の形式で出力してください。

## 【出力形式】

次のJSON構造に正確に従ってください。

```json
{{
  "title": "語り手の称号（最大10文字、日本語）",
  "name": "語り手の名前（最大8文字、日本語）",
  "insight": "150文字以内の前向きな洞察文（2文、賢者風）",
  "keywords": ["キーワード1", "キーワード2", "キーワード3"],
  "suggest": "150文字以内の次の行動の提案（1文のみ、句点は1つ、賢者風）"
}}
```

## 【文体・出力ルール】

- 文体は「厳格で静かな賢者風」（敬語＋断定語調）
- 断定調や命令口調（例：すべきです、取り組みましょう）は避け、さり気なく控えめに提案してください
- **suggestフィールドでは、タスク名や具体的な作業名は一切出力しないでください**
- **提案文はタスクの「性質」や「傾向」に言及してください**
- 洞察文には、行動傾向や取り組み方を1〜2つ具体的に含めてください
- キーワードは抽象的な行動資質（例：継続力、柔軟性、責任感など）を選んでください
- 完了タスクの傾向（カテゴリや内容）に基づいて、語り手の称号と名前を調整してください  
  - 例：学習が多ければ「知の探求者」や「図書の賢者」、運動が多ければ「体律の観察者」「風見の導師」など
- 生成する名前は西洋ファンタジー風にし、語り手の気質や象徴に合った音感をもたせてください（カタカナで出力）

## 【文章の一貫性と流れ】

- insightとsuggestは同じ賢者キャラクターの言葉として、自然につながるようにしてください
- insightの最後の文とsuggestの最初の文が自然に接続するよう配慮してください

## 【分析方針】

- 完了したタスクから行動傾向を分析し、未完了タスクの期限や内容を考慮して次の行動を提案してください
- ユーザーの成長や継続性を促すような提案を心がけてください
- suggestフィールドには、次の行動を賢者風の文体で、断定や命令を避けて控えめに提案してください（1文のみ、句点は1つ）
- **行動の意図や性質（例：節目の行動、習慣の継続、準備行為など）を抽象的に表現してください**
- ファンタジーの世界観にふさわしい表現になるようにしてください

## 【優先順位と提案方針】

**重要：以下の順序で厳格に判定し、最も優先度の高い1つのタスクのみを提案してください**

1. **期限の過ぎたタスク（最優先）**
   - due_dateが現在日時（{current_datetime}）より過去のタスクは、必ず提案に含めてください
   - 期限超過のタスクがある場合は、他のタスクよりも優先して提案してください
   - 複数の期限超過タスクがある場合は、最も期限が古いタスク（最も長く放置されているタスク）を一つ選択してください
   - 日付の比較は、YYYY-MM-DD形式で文字列比較を行ってください（例：2025-06-25 < 2025-06-26）

2. **期限が近いタスク（中優先）**
   - due_dateが現在日（{current_datetime}）または次の日のタスクは「期限が近い」として扱ってください
   - 期限が近いタスクがある場合は、放置タスクよりも必ず優先して提案してください
   - 複数の期限が近いタスクがある場合は、最も期限が近いタスク（最も緊急性の高いタスク）を一つ選択してください

3. **放置タスク（低優先）**
   - created_atから2週間以上経過したタスクのみを提案してください
   - 期限が近いタスクがない場合のみ、放置タスクを提案してください
   - 複数の放置タスクがある場合は、最も古いタスク（最も長く放置されているタスク）を一つ選択してください

### **絶対的な優先順位ルール**

- 期限超過タスク > 期限が近いタスク > 放置タスク  
- 上位の優先度のタスクがある場合は、下位の優先度のタスクは絶対に提案しないでください

---

## 【現在日時】

{current_datetime}

## 【完了タスク】
{completed_tasks}

## 【未完了タスク】
{incomplete_tasks}
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

    async def analyze_behavior(self, completed_tasks: List[Dict[str, Any]], incomplete_tasks: List[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
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
            incomplete_tasks (List[Dict[str, Any]], optional): 未完了タスクの一覧
                各タスクは以下の形式:
                {
                    "title": str,  # タスクタイトル
                    "category": int,  # カテゴリ数値（TaskCategory列挙型の値）
                    "due_date": Optional[str],  # 期限日（ISO形式）
                    "created_at": str  # 作成日時（ISO形式）
                }
            
        Returns:
            Optional[Dict[str, Any]]: 分析結果
                {
                    "title": str,  # 賢者の称号
                    "name": str,  # 語り手の名前
                    "summary": str,  # 行動の傾向から読み取れる前向きな気づき（150文字以内）
                    "keywords": List[str],  # キーワード3語のリスト
                    "suggest": str  # 次の行動の提案（100文字以内、賢者風）
                }
                分析に失敗した場合はNoneを返す
                
        Note:
            - タスクが10件未満の場合は、そのまま分析を実行
            - タスクが10件を超える場合は、最新の10件のみを使用
            - AIからの応答がJSON形式でない場合はNoneを返す
            - エラーが発生した場合もNoneを返す
        """
        logger.info(f"行動分析開始: {len(completed_tasks)}件の完了タスク, {len(incomplete_tasks) if incomplete_tasks else 0}件の未完了タスク")
        
        try:
            # タスクが10件を超える場合は最新の10件のみを使用
            if len(completed_tasks) > 10:
                completed_tasks = completed_tasks[-10:]
                logger.info(f"完了タスクを10件に制限")
            
            if incomplete_tasks and len(incomplete_tasks) > 10:
                incomplete_tasks = incomplete_tasks[:10]
                logger.info(f"未完了タスクを10件に制限")
            
            # タスクデータをプロンプト用の形式に変換
            task_data = self._format_tasks_for_analysis(completed_tasks, incomplete_tasks)
            
            # 現在日時を取得（日本時間）
            jst = timezone(timedelta(hours=9))
            current_datetime_jst = datetime.now(jst)
            # 世界時間（UTC）に変換
            current_datetime_utc = current_datetime_jst.astimezone(timezone.utc).strftime("%Y-%m-%d")
            
            # 生成設定
            generation_config = GenerationConfig(
                temperature=0.3,  # 創造性と一貫性のバランス
                max_output_tokens=256,  # JSON出力に十分な長さ
                top_p=0.9,
                top_k=40
            )
            
            # プロンプトにタスクデータを埋め込み
            prompt = self.analysis_prompt.format(
                completed_tasks=task_data[0], 
                incomplete_tasks=task_data[1],
                current_datetime=current_datetime_utc
            )
            print(prompt)
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
            
            # JSONパース
            try:
                result = json.loads(response_text)
                title = result.get("title", "")
                name = result.get("name", "")
                insight = result.get("insight", "")
                keywords = result.get("keywords", [])
                suggest = result.get("suggest", "")
                
                # 未完了タスクが0件の場合は提案を返さない
                if not incomplete_tasks or len(incomplete_tasks) == 0:
                    suggest = ""
                
                return {
                    "title": title,
                    "name": name,
                    "insight": insight,
                    "keywords": keywords,
                    "suggest": suggest
                }
                    
            except json.JSONDecodeError as e:
                logger.error(f"JSONパースエラー: {str(e)}, レスポンス: {repr(response_text)}")
                return None

        except Exception as e:
            logger.error(f"行動分析エラー: {str(e)}")
            return None

    def _convert_date_to_utc(self, date_str: str) -> str:
        """
        日付文字列を日本時間として解釈し、世界時間（UTC）に変換する
        
        Args:
            date_str (str): YYYY-MM-DD形式の日付文字列
            
        Returns:
            str: UTCに変換されたYYYY-MM-DD形式の日付文字列
        """
        try:
            if isinstance(date_str, str):
                # YYYY-MM-DD形式の文字列を想定
                date_dt = datetime.strptime(date_str, "%Y-%m-%d")
                # 日本時間として解釈してUTCに変換
                jst = timezone(timedelta(hours=9))
                date_jst = date_dt.replace(tzinfo=jst)
                date_utc = date_jst.astimezone(timezone.utc)
                return date_utc.strftime("%Y-%m-%d")
            else:
                # 既にdatetimeオブジェクトの場合
                return date_str.strftime("%Y-%m-%d")
        except Exception as e:
            logger.warning(f"日付変換エラー: {e}, 元の値: {date_str}")
            return date_str

    def _format_tasks_for_analysis(self, completed_tasks: List[Dict[str, Any]], incomplete_tasks: List[Dict[str, Any]] = None) -> List[str]:
        """
        タスクデータを分析用の形式に変換する
        
        完了したタスクと未完了タスクの一覧を、AI分析用のJSON形式の文字列に変換します。
        
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
            incomplete_tasks (List[Dict[str, Any]], optional): 未完了タスクの一覧
                各タスクは以下の形式:
                {
                    "title": str,  # タスクタイトル
                    "category": int,  # カテゴリ数値（TaskCategory列挙型の値）
                    "due_date": Optional[datetime],  # 期限日
                    "created_at": datetime  # 作成日時
                }
            
        Returns:
            List[str]: 分析用のJSON形式文字列のリスト [完了タスク, 未完了タスク]
            
        Examples:
            >>> analyzer = BehaviorAnalyzer()
            >>> tasks = [
            ...     {"title": "商談資料", "category": 1, "completed_at": "2024-01-01T10:00:00Z"}
            ... ]
            >>> formatted = analyzer._format_tasks_for_analysis(tasks)
            >>> print(formatted)
            # ["[{\"task\": \"商談資料\", \"category\": \"仕事\"}]", "[]"]
        """
        category_map = {
            TaskCategory.WORK: "仕事",
            TaskCategory.HEALTH: "健康",
            TaskCategory.LEARNING: "学習",
            TaskCategory.LIFE: "生活",
            TaskCategory.HOBBY: "趣味",
            TaskCategory.OTHER: "その他"
        }
        
        formatted_completed_tasks = []
        formatted_incomplete_tasks = []
        
        # 完了タスクの処理
        for task in completed_tasks:
            # Taskモデルから必要項目のみを抽出
            title = task.get('title', '')
            category_value = task.get('category')
            category_text = category_map.get(category_value, 'その他')
            
            # 完了日時がある場合のみ分析対象とする
            if task.get('completed_at'):
                formatted_completed_tasks.append({
                    'task': title,
                    'category': category_text
                })
        
        # 未完了タスクの処理
        if incomplete_tasks:
            for task in incomplete_tasks:
                title = task.get('title', '')
                category_value = task.get('category')
                category_text = category_map.get(category_value, 'その他')
                due_date = task.get('due_date')
                created_at = task.get('created_at')
                
                # 日付を世界時間（UTC）に変換
                due_date_str = self._convert_date_to_utc(due_date) if due_date else None
                created_at_str = self._convert_date_to_utc(created_at) if created_at else None
                
                formatted_incomplete_tasks.append({
                    'task': title,
                    'category': category_text,
                    'due_date': due_date_str,
                    'created_at': created_at_str
                })
        
        return [
            json.dumps(formatted_completed_tasks, ensure_ascii=False, indent=2),
            json.dumps(formatted_incomplete_tasks, ensure_ascii=False, indent=2)
        ]
