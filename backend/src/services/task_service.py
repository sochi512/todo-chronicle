from typing import List, Dict
from google.cloud import firestore
from fastapi import HTTPException
from src.models.types import TaskStatus, ErrorMessages, Task
from src.services.experience_calculator import ExperienceCalculator
from src.services.story_generator import StoryGenerator
from datetime import datetime
from google.cloud.firestore import FieldFilter
from src.utils.encoders import custom_json_response
import logging

logger = logging.getLogger(__name__)

class TaskService:
    def __init__(self, db: firestore.Client):
        self.db = db
        self.exp_calculator = ExperienceCalculator()
        self.story_generator = StoryGenerator(db)

    def create_task(self, task: Task, user_id: str) -> Task:
        """タスクを作成"""
        task_ref = self.db.collection('users').document(user_id).collection('tasks').document()
        task_dict = task.model_dump()
        task_dict['id'] = task_ref.id
        task_ref.set(task_dict)
        return Task(**task_dict)

    def get_tasks(self, user_id: str) -> List[Task]:
        """ユーザーのタスク一覧を取得"""
        tasks_ref = self.db.collection('users').document(user_id).collection('tasks')
        tasks = tasks_ref.order_by('created_at', direction=firestore.Query.DESCENDING).get()
        return [Task(**task.to_dict()) for task in tasks]

    def get_tasks_for_dashboard(self, user_ref: firestore.DocumentReference) -> List[Dict]:
        """ダッシュボード用のタスク一覧を取得（ステータス、期限、完了日時、作成日時でソート）"""
        tasks_ref = user_ref.collection('tasks')
        tasks = tasks_ref.order_by('created_at', direction=firestore.Query.DESCENDING)\
            .stream()
        return [task.to_dict() for task in tasks]

    def get_task(self, user_id: str, task_id: str) -> Task:
        """特定のタスクを取得"""
        task_ref = self.db.collection('users').document(user_id).collection('tasks').document(task_id)
        task = task_ref.get()
        if not task.exists:
            raise HTTPException(status_code=404, detail=ErrorMessages.TASK_NOT_FOUND)
        return Task(**task.to_dict())

    def update_task(self, task: Task, user_id: str) -> Task:
        """タスクを更新"""
        task_ref = self.db.collection('users').document(user_id).collection('tasks').document(task.id)
        
        # タスクの存在確認
        existing_task = task_ref.get()
        if not existing_task.exists:
            logger.warning(f"タスクが存在しません: user_id={user_id}, task_id={task.id}")
            raise HTTPException(status_code=404, detail=ErrorMessages.TASK_NOT_FOUND)
            
        task_dict = task.model_dump()
        task_ref.update(task_dict)
        logger.info(f"タスクを更新しました: user_id={user_id}, task_id={task.id}")
        return task

    def delete_task(self, task_id: str, user_id: str) -> None:
        """タスクを削除"""
        task_ref = self.db.collection('users').document(user_id).collection('tasks').document(task_id)
        
        # タスクの存在確認
        task = task_ref.get()
        if not task.exists:
            logger.warning(f"タスクが存在しません: user_id={user_id}, task_id={task_id}")
            raise HTTPException(status_code=404, detail=ErrorMessages.TASK_NOT_FOUND)
            
        # タスクを削除
        task_ref.delete()
        logger.info(f"タスクを削除しました: user_id={user_id}, task_id={task_id}")

    def get_completed_tasks(self, user_id: str) -> List[Task]:
        """完了したタスクを取得（経験値獲得済みでないもの）"""
        tasks_ref = self.db.collection('users').document(user_id).collection('tasks')
        tasks = tasks_ref.where(filter=FieldFilter("status", "==", TaskStatus.COMPLETED))\
            .where(filter=FieldFilter("experienced_at", "==", None))\
            .get()
        return [Task(**task.to_dict()) for task in tasks]

    def count_already_done_tasks(self, user_id: str) -> int:
        """当日完了したタスクの数を取得（経験値獲得済みのものを含む）"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tasks_ref = self.db.collection('users').document(user_id).collection('tasks')
        query = tasks_ref.where(filter=FieldFilter("completed_at", ">=", today))\
            .where(filter=FieldFilter("experienced_at", ">", datetime.min))
        return len(list(query.stream()))

    def update_tasks_to_experienced(self, tasks: List[Task], user_id: str) -> None:
        """タスクを経験値獲得済みに更新"""
        batch = self.db.batch()
        for task in tasks:
            task.experienced_at = datetime.now()
            task_ref = self.db.collection('users').document(user_id).collection('tasks').document(task.id)
            batch.update(task_ref, task.model_dump())
        batch.commit()

    def update_task_status(self, task_id: str, status: TaskStatus, user_id: str) -> Task:
        """タスクのステータスのみを更新"""
        task_ref = self.db.collection('users').document(user_id).collection('tasks').document(task_id)
        
        # タスクの存在確認
        task = task_ref.get()
        if not task.exists:
            logger.warning(f"タスクが存在しません: user_id={user_id}, task_id={task_id}")
            raise HTTPException(status_code=404, detail=ErrorMessages.TASK_NOT_FOUND)
            
        # 更新データの準備
        update_data = {'status': status}
        
        # ステータスがCOMPLETEDの場合、completed_atを更新
        if status == TaskStatus.COMPLETED:
            update_data['completed_at'] = datetime.now()
        # ステータスがPENDINGの場合、completed_atをNoneに更新
        elif status == TaskStatus.PENDING:
            update_data['completed_at'] = None
            
        # タスクを更新
        task_ref.update(update_data)
        logger.info(f"タスクステータスを更新しました: user_id={user_id}, task_id={task_id}, status={status}")
        
        # 更新後のタスクを取得して返す
        updated_task = task_ref.get()
        return Task(**updated_task.to_dict())