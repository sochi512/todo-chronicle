from typing import List
from datetime import datetime
from google.cloud import firestore
from src.models.types import Story, StoryPhase
from src.models.types import User, Season
from src.services.story_generator import StoryGenerator
from src.services.task_service import TaskService

class StoryService:
    def __init__(self, db: firestore.Client):
        self.db = db
        self.story_generator = StoryGenerator(db)
        self.task_service = TaskService(db)

    async def generate_story(self, user: User, season: Season, is_final_chapter: bool = False) -> Story:
        """経験値に基づいてストーリーを生成"""
        # 完了したタスクを取得
        completed_tasks = self.task_service.get_completed_tasks(user.id)
        completed_task_titles = [task.title for task in completed_tasks]
        
        # 前章の要約を取得
        previous_summary = ""
        if season.current_chapter > 0:
            previous_story = await self._get_previous_story(user.id, season.id)
            if previous_story:
                previous_summary = previous_story.summary or ""
        else:
            previous_summary = season.previous_summary

        # 物語を生成
        story_data = await self.story_generator.generate_story(
            player_name=user.player_name or "",
            chapter_no=season.current_chapter + 1,
            phase=season.current_phase,
            completed_tasks=completed_task_titles,
            previous_summary=previous_summary,
            is_final_chapter=is_final_chapter,
            user_id=user.id,
            season_id=season.id
        )
        # print(f"story_data: {story_data}")
        
        # 初回のストーリー生成時（第1章）かつplayer_nameが未設定の場合、生成されたplayer_nameを設定
        if season.current_chapter == 0 and not user.player_name and story_data.get("player_name"):
            await self._update_user_player_name(user.id, story_data["player_name"])
            user.player_name = story_data["player_name"]
        
        # ストーリーオブジェクトを作成
        story = Story(
            season_id=season.id,
            chapter_no=season.current_chapter + 1,
            title=story_data["title"],
            content=story_data["story"],
            insight=story_data["insight"],
            name=story_data["name"],
            phase=season.current_phase,
            created_at=datetime.now(),
            summary=story_data["summary"],
            completed_tasks=story_data["completed_tasks"]
        )
        
        return story

    async def _update_user_player_name(self, user_id: str, player_name: str) -> None:
        """ユーザーのplayer_nameを更新"""
        user_ref = self.db.collection('users').document(user_id)
        user_ref.update({
            'player_name': player_name
        })

    async def _get_previous_story(self, user_id: str, season_id: str) -> Story:
        """前章のストーリーを取得"""
        user_ref = self.db.collection('users').document(user_id)
        season_ref = user_ref.collection('seasons').document(season_id)
        
        # 最新のストーリーを取得
        stories = season_ref.collection('stories')\
            .order_by('chapter_no', direction=firestore.Query.DESCENDING)\
            .limit(1)\
            .stream()
        
        for story in stories:
            return Story(**story.to_dict())
        return None

    async def get_stories(self, user_id: str, season_id: str) -> List[Story]:
        """ユーザーのシーズン内の物語を取得"""
        # シーズンの存在確認
        user_ref = self.db.collection('users').document(user_id)
        season_ref = user_ref.collection('seasons').document(season_id)
        season = season_ref.get()
        if not season.exists:
            raise ValueError(f"Season {season_id} not found")

        # シーズンのサブコレクションからストーリーを取得
        stories = season_ref.collection('stories')\
            .order_by('chapter_no')\
            .stream()
        
        return [Story(**story.to_dict()) for story in stories]

    async def get_story(self, user_id: str, season_id: str, story_id: str) -> Story:
        """特定の物語を取得"""
        # シーズンの存在確認
        user_ref = self.db.collection('users').document(user_id)
        season_ref = user_ref.collection('seasons').document(season_id)
        season = season_ref.get()
        if not season.exists:
            raise ValueError(f"Season {season_id} not found")

        # シーズンのサブコレクションからストーリーを取得
        story = season_ref.collection('stories').document(story_id).get()
        if not story.exists:
            raise ValueError("Story not found")
        return Story(**story.to_dict()) 