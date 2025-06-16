from typing import List, Dict, Any, Tuple
import google.cloud.aiplatform as aiplatform
from datetime import datetime
from google.cloud import firestore
from src.models.types import StoryPhase, Task
import os
from dotenv import load_dotenv
import vertexai
from vertexai.preview.generative_models import GenerativeModel, GenerationConfig
import asyncio
import json
import random

# 環境変数の読み込み
load_dotenv()

# 物語生成器のクラス
class StoryGenerator:
    def __init__(self, db: firestore.Client):
        self.db = db
        self._initialize_vertex_ai()

    def _initialize_vertex_ai(self):
        """Vertex AIの初期化"""
        try:
            # 環境変数から設定を取得
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
            location = os.getenv("VERTEX_AI_LOCATION", "asia-northeast1")
            model_name = os.getenv("VERTEX_AI_MODEL_NAME", "gemini-2.0-flash")
            
            if not project_id:
                raise ValueError("GOOGLE_CLOUD_PROJECT環境変数が設定されていません")
            
            # Vertex AIの初期化
            vertexai.init(
                project=project_id,
                location=location
            )
            
            # モデルの初期化
            self.model = GenerativeModel(model_name)
            
        except Exception as e:
            print(f"Vertex AI初期化エラー: {str(e)}")
            raise

    # 物語を生成するメソッド
    async def generate_story(self, player_name: str, chapter_no: int, phase: StoryPhase, completed_tasks: List[str], previous_summary: str = "", is_final_chapter: bool = False) -> Dict[str, str]:
        """経験値に基づいてストーリーを生成"""
        # テスト用の固定データを返す
        print(f"player_name: {player_name}")
        print(f"chapter_no: {chapter_no}")
        print(f"phase: {phase}")
        print(f"completed_tasks: {completed_tasks}")
        print(f"previous_summary: {previous_summary}")
        print(f"is_final_chapter: {is_final_chapter}")

        # return {
        #     "player_name": "テスト",
        #     "title": "タイトル",
        #     "story": "ストーリー",
        #     "insight": "洞察",
        #     "summary": "サマリ",
        #     "completed_tasks": []
        # }

        # 以下、本番用のコード（コメントアウト）
        # タスクのタイトルを取得
        if len(completed_tasks) > 2:
            sampled_tasks = random.sample(completed_tasks, 2)
        else:
            sampled_tasks = completed_tasks
        completed_tasks_str = "、".join(sampled_tasks)

        # タスクを物語の世界観にあった用語に変換
        if phase != StoryPhase.KAN:
            converted_tasks = await self._convert_task_to_story_world(completed_tasks_str)
        else:
            converted_tasks = {
                "completed_tasks": [],
                "story_world_tasks": ""
            }

        # プロンプトの準備
        system_prompt = self._get_system_prompt(player_name, chapter_no, converted_tasks["story_world_tasks"], phase, previous_summary, is_final_chapter)
        user_prompt = self._get_user_prompt(chapter_no, phase)
        

        # 物語を生成
        story_data = await self._generate_story_content(system_prompt, user_prompt)
        # 要約を生成
        story_data['summary'] = await self._generate_story_summary(story_data['story'])
        # 完了タスクを追加
        story_data['completed_tasks'] = converted_tasks["completed_tasks"]
        return story_data

    def _get_system_prompt(self, player_name: str, chapter_no: int, completed_tasks_str: str, phase: StoryPhase, previous_summary: str, is_final_chapter: bool) -> str:

        phase_str = self._get_phase_string(phase)

        """システムプロンプトを取得"""
        return f"""
### Context
player_name      = {player_name}
chapter_no       = {chapter_no}
completed_tasks  = {completed_tasks_str}
previous_summary = {previous_summary}
phase = {phase_str}
is_final_chapter = {is_final_chapter}

### 出力形式
- 以下の形式で出力してください（JSON以外の文字列、説明文、コードブロックは禁止）：
{{
  "player_name": "{player_name}",
  "title": "章タイトル（最大15文字）",
  "insight": "抽象的な気づき・内省"
  "story": "物語本文（160〜200文字、最終章は最大240文字）storyのみを出力してください",
}}

### 作家の設定と文体
あなたは日本語ライトノベルの作家です。

- 主人公は「{player_name}」という名の冒険者。一人称は「俺」。
- 第1章のみ冒頭で「俺、{player_name}は──」と名乗ってください（player_nameは自由に命名してください）。
- 世界観：剣と魔法のファンタジー。
- テンポよく、セリフ多めで、軽口・オノマトペ・俗語も自然に使用してください。
- 読みやすいよう適度に改行を。
- 各章では主人公が必ず行動し、物語が一歩前に進むようにしてください。

### フェーズごとの描写方針と文字数制限
現在のフェーズは「{phase}」です。以下のトーンと文字数で描写してください：

| フェーズ | 描写内容|
| ---- | ------------------ |
| 起    | 導入、世界観、目標提示 |
| 承    | 仲間、成長、進展 |
| 転    | 危機、敗北、葛藤 |
| 結    | 決戦、勝利、収束 |
| 完    | 感情の整理、報酬、旅立ち（戦闘禁止） |

- 同じフェーズが複数章続くことがあります。毎章で進展や変化を必ず描いてください。
- 起・承・転 でも is_final_chapter = true の場合は、区切り感（覚悟・転機・結束など）を持たせてください。
- **結フェーズ**では段階的な戦闘描写はOKですが、**is_final_chapter = true** のときは、必ず戦いに決着をつけてください（勝利・敗北・退却など）。

### タスクの利用ルール
- completed_tasks には、完了タスクが「読点（、）区切り」で複数渡されます。
- 完了タスクは、**主人公の具体的な「行動・選択・思考」の一部として描写**してください。
- 単なる説明文やセリフにせず、**背景や目的、結果**とともに自然に物語に組み込んでください。
- 完了タスクが不自然な場合、意訳や簡潔な代替語に置き換えても構いません。
- 使わない完了タスクがあっても構いません（文脈重視）。

### イベント制御（通常章のみ）
- 以下のイベントから1つを選んで自然に描写してください（final章での強調可）：
  1. 仲間加入（1回のみ、肩書きと第一声を必ず描写）
    - 仲間加入イベントはこの物語全体で1回のみです。previous_summaryで、登場済みなら選択しないでください。
  2. 中ボス撃破（敵名・特徴・撃破描写を必ず含める）
    - 敵は中ボス級にとどめてください。魔王などのラスボスを匂わせる敵は登場させないこと。
  3. 特訓／内省（技能・価値観の変化を描写）

### insightについて
- タスクに由来する**抽象的な学び・気づき・行動指針**を表現してください（60文字以内）。
- タスク名や本文の直接引用は禁止。
- 「準備」「判断」「鍛錬」「整備」「共闘」など、**行動の意図や価値**を抽象化してください。
- できれば前向きな余韻で締めてください（例：「…ことが成功の鍵になる。」）
"""

    def _get_user_prompt(self, chapter_no: int, phase: StoryPhase) -> str:
        """ユーザープロンプトを生成"""
        
        if phase == StoryPhase.KAN:
            # 最終章用のプロンプト
            return f"""

### Instructions
- この物語は最終章（第{chapter_no}章）です。フェーズは「完」です。
- 以下の3つをこの順番で1文以上ずつ描写してください：
  1. 感情の整理（達成・別れ・安堵など）  
  2. 報酬、称号、感謝、未来への布石  
  3. 新たな旅立ち、余韻、希望、誓いなど

- System Prompt の「完」フェーズ規定と出力形式に従ってください。
- 戦闘描写、敵の登場、魔法使用などは一切禁止です。
- 物語は、180〜240文字で描写してください。
- タスク内容は物語本文には含めず、insight の生成にのみ使用してください。
- 可能であれば、物語の最後に「次の冒険のきっかけ」や「主人公の新たな動き・誓い・方向性」を1文で示唆してください。
"""
        else:
            # 通常章用のプロンプト
            return f"""
## Instructions
- この物語は第{chapter_no}章です。
- previous_summary は文脈の参考にしてください（引用不要）。
- **previous_summary に戦闘描写（例：「戦いが続いていた」「剣を構えた」「攻撃を避けた」など）が含まれる場合** は、必ずその続きを描写する形で物語を始めてください（同一シーンの継続が必要です）。
- 現在のフェーズは「{phase}」です。System Prompt に従って描写してください。
- 物語は、160〜200文字で描写してください。
- 同じフェーズが続いても、毎章に変化・進展を必ず含めてください。
- is_final_chapter = true のときは、章の締めくくりにふさわしい転機・決意・成長・勝利などの要素を含めてください。
"""

    def _get_phase_string(self, phase: StoryPhase) -> str:
        """フェーズを文字列に変換"""
        phase_map = {
            StoryPhase.KI: "起",
            StoryPhase.SHO: "承",
            StoryPhase.TEN: "転",
            StoryPhase.KETSU: "結",
            StoryPhase.KAN: "完"  # 完は結として扱う
        }
        return phase_map.get(phase, "ki")

    async def _generate_story_content(self, system_prompt: str, user_prompt: str) -> Dict[str, str]:
        """Gemini APIを使用して物語本文と要約を生成（リトライ付き）
        Returns:
            Dict[str, str]: 物語データ（player_name, story, insight, summaryを含む）
        """
        max_retries = int(os.getenv("STORY_GEN_MAX_RETRIES", 3))
        for attempt in range(1, max_retries + 1):
            try:
                # 物語本文の生成
                generation_config = GenerationConfig(
                    temperature=0.75,  # 創造性と一貫性のバランスを取る
                    max_output_tokens=512,  # 必要十分な長さ
                    top_p=0.85,  # より多様な表現を許容
                    top_k=40
                )
                response = await self.model.generate_content_async(
                    f"{system_prompt}\n\n{user_prompt}",
                    generation_config=generation_config
                )
                story_content = response.text

                # JSON形式の出力を前処理
                story_content = story_content.strip()
                if story_content.startswith('```json'):
                    story_content = story_content[7:]
                if story_content.endswith('```'):
                    story_content = story_content[:-3]
                story_content = story_content.strip()

                try:
                    # JSONとして解析
                    story_data = json.loads(story_content)
                except json.JSONDecodeError as e:
                    print(f"[{attempt}回目] JSON形式での出力に失敗: {e}")
                    if attempt < max_retries:
                        await asyncio.sleep(1)
                        continue
                    else:
                        # デフォルトの形式で処理
                        story_data = {
                            'player_name': '',
                            'story': story_content,
                            'insight': ''
                        }

                # 要約の生成
                summary = await self._generate_story_summary(story_data['story'])
                # 要約をJSONに追加
                story_data['summary'] = summary
                return story_data

            except Exception as e:
                print(f"[{attempt}回目] 物語生成エラー: {str(e)}")
                if attempt < max_retries:
                    await asyncio.sleep(1)
                    continue
                else:
                    raise

    async def _generate_story_summary(self, story_content: str) -> str:
        """要約の生成"""
        try:
            # 要約の生成
            summary_prompt = f"""
以下の物語をもとに、80文字以内で物語の要約を作成してください。
- 一文で簡潔にまとめてください。
- ストーリー上の重要な出来事（戦闘・出会い・変化・決断など）を中心に要約してください。
- 仲間の加入、敵との対決、転機の発生など、大きな変化があれば必ず反映してください。
- 文体は三人称で、過去形で統一してください（例：「〜た」「〜だった」）。
- 会話やセリフ、地の文の一部をそのまま使わず、要約として自然な文にしてください。
- 出力は本文のみとし、余計な記号・マークダウン・括弧・補足を含めないでください。
物語：
{story_content}"""

            summary_config = GenerationConfig(
                temperature=0.7,
                max_output_tokens=256,
                top_p=0.8,
                top_k=40
            )
            
            summary_response = await self.model.generate_content_async(
                summary_prompt,
                generation_config=summary_config
            )
            summary = summary_response.text
            return summary
            
        except Exception as e:
            print(f"要約生成エラー: {str(e)}")
            raise

    async def _convert_task_to_story_world(self, tasks: str) -> Dict[str, Any]:
        """タスクを物語の世界観にあった用語に変換"""
        try:
            # 要約の生成
            convert_prompt = f"""
### Context
tasks      = {tasks}

タスクを、ライトファンタジー用語に変換してください。  
これらの語は、異世界風の物語の中で自然に使われる名称や行動として使われます。

### 変換ルール
- tasksは、"、"区切りで複数のタスクが渡されます（空白は区切りではありません）
- 各タスクに対して、1つだけファンタジー用語を生成してください（1対1）
- 現代語は直接使わないでください（例：「電車」「ネット」「LINE」などは禁止）  
- 変換語は、15文字以内、名詞または短い動詞句とする
- 変換語は1つのみ（複数語への変換は禁止）
- 露骨な性描写、差別的な言葉、暴力的な言葉は無視してください

### 出力形式
以下の形式で、すべてのタスクを配列としてJSON形式で出力してください。

```json
{{
  "completed_tasks": [
    {{
      "original": "元のタスク名",
      "converted": "ファンタジー用語"
    }},
    {{
      "original": "元のタスク名",
      "converted": "ファンタジー用語"
    }}
  ]
}}
"""

            convert_config = GenerationConfig(
                temperature=0.7,
                max_output_tokens=256,
                top_p=0.8,
                top_k=40
            )
            
            convert_response = await self.model.generate_content_async(
                convert_prompt,
                generation_config=convert_config
            )
            convert_result = convert_response.text

            convert_result = convert_result.strip()
            if convert_result.startswith('```json'):
                convert_result = convert_result[7:]
            if convert_result.endswith('```'):
                convert_result = convert_result[:-3]
            convert_result = convert_result.strip()
            try:
                # JSONとして解析
                convert_result_json = json.loads(convert_result)
                # convertedの値を「、」で連結してstory_world_tasksを生成
                convert_result_json["story_world_tasks"] = "、".join([task["converted"] for task in convert_result_json["completed_tasks"]])
            except json.JSONDecodeError as e:
                print(f"JSON形式での出力に失敗しました: {e}")
                # デフォルトの形式で処理
                convert_result_json = {
                    'completed_tasks': [],
                    'story_world_tasks': ''
                }
            return convert_result_json

        except Exception as e:
            print(f"タスク変換エラー: {str(e)}")
            raise
