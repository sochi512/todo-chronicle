from typing import List, Dict, Tuple, Optional
from google.cloud import firestore
from fastapi import HTTPException
from src.models.types import TaskStatus, ErrorMessages, StoryPhase, Task, Season, User, Story
from src.services.experience_calculator import ExperienceCalculator
from src.services.story_service import StoryService
from src.services.task_service import TaskService
from src.services.image_generator import ImageGenerator
from src.services.storage_service import StorageService
from datetime import datetime, timedelta
from google.cloud.firestore import FieldFilter, Transaction
from src.utils.encoders import custom_json_response, custom_encoder
import json
import logging
import asyncio

logger = logging.getLogger(__name__)

class SeasonService:
    def __init__(self, db: firestore.Client):
        self.db = db
        self.exp_calculator = ExperienceCalculator()
        self.story_service = StoryService(db)
        self.task_service = TaskService(db)
        self.image_generator = ImageGenerator()
        self.storage_service = StorageService()

    async def create_initial_season(self, user: User) -> Tuple[Season, User]:
        """
        ユーザーの初期シーズンを作成し、ユーザー情報を更新
        
        Args:
            user (User): ユーザー情報
            
        Returns:
            Tuple[Season, User]: 作成されたシーズンと更新されたユーザー情報
        """
        return await self._create_season_with_user_update(user, 1, "")

    async def create_new_season(self, user: User, season_number: int, previous_summary: str) -> Tuple[Season, User]:
        """
        新シーズンを作成し、ユーザー情報を更新
        
        Args:
            user (User): ユーザー情報
            season_number (int): 新しいシーズン番号
            
        Returns:
            Tuple[Season, User]: 作成されたシーズンと更新されたユーザー情報
        """
        return await self._create_season_with_user_update(user, season_number, previous_summary)

    async def _create_season_with_user_update(self, user: User, season_number: int, previous_summary: str) -> Tuple[Season, User]:
        """
        シーズンを作成し、ユーザー情報を更新する内部メソッド
        
        Args:
            user (User): ユーザー情報
            season_number (int): シーズン番号
            
        Returns:
            Tuple[Season, User]: 作成されたシーズンと更新されたユーザー情報
        """
        # 参照を取得
        user_ref = self.db.collection('users').document(user.id)
        season_ref = user_ref.collection('seasons').document()
        
        try:
            # シーズンを作成
            required_exp = self.exp_calculator.get_required_season_exp(season_number)

            season = Season(
                season_no=season_number,
                total_exp=0,
                current_phase=StoryPhase.KI,
                previous_summary=previous_summary,
                created_at=datetime.now(),
                updated_at=None,
                required_exp=required_exp
            )

            season.id = season_ref.id
            season_dict = season.model_dump()
            
            # ユーザー情報を更新
            user.current_season_id = season.id
            if not user.season_ids:
                user.season_ids = []
            user.season_ids.append(season.id)
            
            # 更新を実行
            season_ref.set(season_dict)
            user_ref.update({
                'current_season_id': season.id,
                'season_ids': user.season_ids
            })
            
            return season, user
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"シーズン作成中にエラーが発生しました: {str(e)}"
            )

    async def _generate_and_save_story_image(self, user_id: str, season: Season, story: Story) -> None:
        """
        ストーリー画像を生成し、保存します。
        
        Args:
            user_id (str): ユーザーID
            season (Season): シーズン情報
            story (Story): ストーリー情報
        """
        try:
            # 画像生成
            image_result = await self.image_generator.generate_story_image(story.content)
            # GCSに画像を保存
            bucket_name = "todo-adv"
            file_name = f"season_{season.season_no}.png"
            storage_path = f"images/user_{user_id}/{file_name}"
            
            # GCSに画像をアップロード
            await self.storage_service.upload_image(
                bucket_name=bucket_name,
                storage_path=storage_path,
                image_data=image_result["image_data"]
            )
            
            # シーズンに画像パスを保存
            await self.save_story_image(user_id, season.id, file_name)
            
        except Exception as e:
            logger.error(f"画像生成・保存エラー: {str(e)}")
            # 画像生成に失敗しても処理は続行

    async def progress_story(self, user_id: str, client_update_at: str = None) -> Dict:
        """
        物語を進行させる
        
        Args:
            user_id (str): ユーザーID
            client_update_at (str): クライアント側の更新日時
            
        Returns:
            Dict: 更新されたシーズン情報と物語
            
        Raises:
            HTTPException: ユーザーまたはシーズンが見つからない場合
        """
        # ユーザーとシーズンを1回のトランザクションで取得
        user_ref = self.db.collection('users').document(user_id)
        user_doc = user_ref.get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail=ErrorMessages.USER_NOT_FOUND)
        
        user = User(**user_doc.to_dict())
        if not user.current_season_id:
            raise HTTPException(status_code=404, detail=ErrorMessages.SEASON_NOT_FOUND)
            
        season_ref = user_ref.collection('seasons').document(user.current_season_id)
        season_doc = season_ref.get()
        if not season_doc.exists:
            raise HTTPException(status_code=404, detail=ErrorMessages.SEASON_NOT_FOUND)
        current_season = Season(**season_doc.to_dict())
            
        # 完了したタスクを取得
        completed_tasks = self.task_service.get_completed_tasks(user_id)
        logger.debug(f"完了したタスク数: {len(completed_tasks) if completed_tasks else 0}")
        # 当日完了したタスクを取得
        already_done = self.task_service.count_already_done_tasks(user_id)
        logger.debug(f"当日既に完了したタスク数: {already_done}")

        # 完了したタスクのseason_idを更新（experienced_atはまだ更新しない）
        if completed_tasks:  # 完了したタスクが存在する場合のみ更新
            self.task_service.update_tasks_season_id(completed_tasks, user_id, current_season.id)
        
        # 経験値を計算して加算
        earned_exp, is_final_chapter = self.exp_calculator.calculate_experience(len(completed_tasks), already_done, current_season.current_phase, current_season.total_exp)
        logger.debug(f"獲得経験値: {earned_exp}")
        logger.debug(f"最終章判定: {is_final_chapter}")
        
        # 獲得経験値が0の場合はストーリーを生成せずに終了
        if earned_exp == 0:
            return {
                "earned_exp": 0,
                "total_exp": current_season.total_exp,
                "season": current_season.model_dump(),
                "story": None
            }
            
        current_season.total_exp = int(current_season.total_exp + earned_exp)
        logger.debug(f"総経験値: {current_season.total_exp}")
        # フェーズを更新
        current_season.current_phase = self.exp_calculator.get_phase(current_season.total_exp)
        logger.debug(f"現在のフェーズ: {current_season.current_phase}")
        
        # 物語を生成
        story = await self.story_service.generate_story(user, current_season, is_final_chapter)

        # ストーリーを保存
        story_ref = season_ref.collection('stories').document()
        story.id = story_ref.id
        story.season_id = current_season.id
        story_ref.set(story.model_dump())

        # シーズンを更新
        await self._update_season(user_id, current_season, story)

        # 物語の最終章かつ結のフェーズの場合、画像を生成（非同期で実行）
        if is_final_chapter and current_season.current_phase == StoryPhase.KETSU:
            # awaitを外して非同期実行
            asyncio.create_task(self._generate_and_save_story_image(user_id, current_season, story))

        # 完了済タスクのexperienced_atを更新（行動分析後に実行）
        if completed_tasks:
            self.task_service.update_tasks_to_experienced(completed_tasks, user_id)

        # シーズンが完結したら新シーズンを作成し、ユーザー情報を更新
        new_season = None
        if current_season.current_phase == StoryPhase.KAN:
            new_season, updated_user = await self.create_new_season(user, current_season.season_no + 1, story.summary)
            user = updated_user
        
        # 更新日時を更新
        current_time = datetime.now().isoformat()
        user_ref.update({
            'update_at': current_time
        })
        
        # 更新処理後の排他チェック
        if client_update_at:
            server_update_at = user.update_at
            if server_update_at != client_update_at:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "データが既に更新されています",
                        "server_update_at": server_update_at,
                        "type": "CONFLICT"
                    }
                )
        
        return {
            "user": user.model_dump(),
            "earned_exp": earned_exp,
            "season": current_season.model_dump(),
            "story": story.model_dump(),
            "new_season": new_season.model_dump() if new_season else None
        }

    async def _get_user(self, user_id: str) -> User:
        """ユーザー情報を取得"""
        user_ref = self.db.collection('users').document(user_id)
        user = user_ref.get()
        if not user.exists:
            raise HTTPException(status_code=404, detail=ErrorMessages.USER_NOT_FOUND)
        return User(**user.to_dict())

    async def _get_current_season(self, user: User) -> Season:
        """現在のシーズン情報を取得"""
        if not user.current_season_id:
            raise HTTPException(status_code=404, detail=ErrorMessages.SEASON_NOT_FOUND)
            
        user_ref = self.db.collection('users').document(user.id)
        season_ref = user_ref.collection('seasons').document(user.current_season_id)
        season = season_ref.get()
        if not season.exists:
            raise HTTPException(status_code=404, detail=ErrorMessages.SEASON_NOT_FOUND)
        return Season(**season.to_dict())

    async def _update_season(self, user_id: str, season: Season, story: Story) -> None:
        """シーズン情報を更新"""
        user_ref = self.db.collection('users').document(user_id)
        season_ref = user_ref.collection('seasons').document(season.id)
        season.current_chapter += 1
        season.updated_at = datetime.now()
        logger.debug(f"シーズン更新 - フェーズ: {season.current_phase}")
        update_data = {
            'total_exp': season.total_exp,
            'current_phase': season.current_phase,
            'current_chapter': season.current_chapter,
            'updated_at': season.updated_at
        }
        season_ref.update(update_data)

    def get_seasons_for_dashboard(self, user_ref: firestore.DocumentReference, season_ids: List[str]) -> List[Dict]:
        """ダッシュボード用のシーズン一覧を取得（ストーリーを含む）"""
        # ユーザー情報からcurrent_season_idを取得
        user_doc = user_ref.get()
        user_data = user_doc.to_dict()
        current_season_id = user_data.get('current_season_id')

        seasons = []
        for season_id in season_ids:
            season_ref = user_ref.collection('seasons').document(season_id)
            season = season_ref.get()
            if season.exists:
                season_dict = season.to_dict()
                
                # 現在のシーズンの場合のみストーリーを取得
                if season_id == current_season_id:
                    stories_ref = season_ref.collection('stories')
                    # ストーリーをchapter_noの降順で取得
                    stories = stories_ref.order_by('chapter_no', direction=firestore.Query.DESCENDING).stream()
                    stories_list = [story.to_dict() for story in stories]
                    season_dict['stories'] = stories_list
                else:
                    season_dict['stories'] = []
                
                seasons.append(season_dict)
        
        # シーズンをseason_noの降順でソート
        seasons.sort(key=lambda x: x.get('season_no', 0), reverse=True)
        return seasons

    async def save_story_image(self, user_id: str, season_id: str, file_name: str) -> None:
        """
        シーズンに画像ファイル名を保存します。
        
        Args:
            user_id (str): ユーザーID
            season_id (str): シーズンID
            file_name (str): 画像ファイル名
        """
        try:
            user_ref = self.db.collection('users').document(user_id)
            season_ref = user_ref.collection('seasons').document(season_id)
            season_ref.update({
                'story_image_filename': file_name
            })
            logger.info(f"画像ファイル名を保存しました: user_id={user_id}, season_id={season_id}")
        except Exception as e:
            logger.error(f"画像ファイル名の保存に失敗: {str(e)}")
            raise Exception(f"画像ファイル名の保存に失敗しました: {str(e)}")

    async def get_story_image_url(self, season_id: str) -> Optional[str]:
        """
        シーズンの画像URLを取得します。
        
        Args:
            season_id (str): シーズンID
            
        Returns:
            Optional[str]: 画像URL
        """
        try:
            # シーズンの取得
            season_ref = self.db.collection('seasons').document(season_id)
            season_doc = season_ref.get()
            
            if not season_doc.exists:
                raise Exception("シーズンが見つかりません")
                
            season_data = season_doc.to_dict()
            if not season_data.get('story_image_filename'):
                return None
                
            # 署名付きURLの生成
            image_url = await self.image_generator.get_signed_url(
                story_id=season_id,
                filename=season_data['story_image_filename']
            )
            
            return image_url
            
        except Exception as e:
            logger.error(f"画像URLの取得に失敗: {str(e)}")
            raise Exception(f"画像URLの取得に失敗しました: {str(e)}")

    async def generate_and_save_story_image(self, user_id: str, season_id: str, story_text: str, style: str = "light_novel") -> dict:
        """
        ストーリー画像を生成し、保存します。
        
        Args:
            user_id (str): ユーザーID
            season_id (str): シーズンID
            story_text (str): ストーリーテキスト
            style (str): 画像のスタイル
            
        Returns:
            dict: 生成された画像の情報
        """
        try:
            # 画像の生成
            result = await self.image_generator.generate_story_image(
                story_text=story_text,
                story_id=season_id,
                style=style
            )
            
            # 画像ファイル名の保存
            await self.save_story_image(user_id, season_id, result['filename'])
            
            return result
            
        except Exception as e:
            logger.error(f"画像の生成と保存に失敗: {str(e)}")
            raise Exception(f"画像の生成と保存に失敗しました: {str(e)}")
