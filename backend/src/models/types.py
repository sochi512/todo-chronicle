from enum import Enum
from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel

class TaskStatus(int, Enum):
    PENDING = 0
    COMPLETED = 1

class StoryPhase(int, Enum):
    KI = 0    # 起：物語の始まり
    SHO = 1  # 承：展開
    TEN = 2  # 転：転換点
    KETSU = 3  # 結：結末
    KAN = 4  # 結：結末

class Task(BaseModel):
    id: Optional[str] = None
    title: str
    due_date: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = datetime.now()
    completed_at: Optional[datetime] = None
    experienced_at: Optional[datetime] = None

class Story(BaseModel):
    id: Optional[str] = None
    season_id: str
    chapter_no: int
    title: str
    content: str
    insight: str
    phase: StoryPhase
    created_at: datetime = datetime.now()
    summary: Optional[str] = None
    completed_tasks: List[Dict[str, str]] = []  # List of {"original": str, "converted": str}

class Season(BaseModel):
    id: Optional[str] = None
    season_no: int
    total_exp: int
    current_chapter: int = 0
    current_phase: StoryPhase = StoryPhase.KI
    previous_summary: str = ""
    created_at: Any = datetime.now()
    updated_at: Optional[datetime] = None
    required_exp: int
    story_image_filename: Optional[str] = None

class User(BaseModel):
    id: Optional[str] = None
    player_name: Optional[str] = None
    created_at: Any = datetime.now()
    current_season_id: Optional[str] = None
    season_ids: List[str] = []

class ErrorMessages:
    USER_NOT_FOUND = "User not found"
    TASK_NOT_FOUND = "Task not found"
    SEASON_NOT_FOUND = "Season not found"
    TASK_ALREADY_COMPLETED = "Task already completed"
    NO_VALID_TASKS = "No valid tasks found"
    USER_CREATION_FAILED = "Failed to create user" 
    UNAUTHORIZED = "Unauthorized access" 