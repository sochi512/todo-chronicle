import logging
from typing import Dict, Tuple
from src.models.types import StoryPhase

logger = logging.getLogger(__name__)

class ExperienceCalculator:
    """
    経験値計算を行うサービス
    
    このクラスは、タスク完了時に獲得する経験値を計算し、
    ストーリーフェーズの進行判定を行います。
    
    フェーズは以下の5段階で構成されます：
    - KI (0): 起 - 物語の始まり (0-199 exp)
    - SHO (1): 承 - 展開 (200-399 exp)
    - TEN (2): 転 - 転換点 (400-599 exp)
    - KETSU (3): 結 - 結末 (600-699 exp)
    - KAN (4): 完 - 完結 (700+ exp)
    
    Attributes:
        PHASE_THRESHOLDS: 各フェーズの必要経験値の閾値リスト
    """
    
    # フェーズごとの必要経験値の閾値
    # PHASE_THRESHOLDS = [0, 300, 600, 900, 1000]
    PHASE_THRESHOLDS = [0, 200, 400, 600, 700]

    def calculate_experience(self, task_count: int, already_done: int, current_phase: StoryPhase, total_exp: int) -> Tuple[int, bool]:
        """
        経験値計算とフェーズ進行判定
        
        完了したタスク数に基づいて獲得経験値を計算し、
        次のフェーズに移行できるかどうかを判定します。
        
        Args:
            task_count (int): 今回完了したタスク数
            already_done (int): 当日既に完了したタスク数
            current_phase (StoryPhase): 現在のストーリーフェーズ
            total_exp (int): 現在の総経験値
            
        Returns:
            Tuple[int, bool]: (獲得経験値, 次のフェーズに移行できるかどうか)
            
        Examples:
            >>> calculator = ExperienceCalculator()
            >>> exp, can_progress = calculator.calculate_experience(3, 0, StoryPhase.KI, 150)
            >>> print(f"獲得経験値: {exp}, フェーズ進行: {can_progress}")
            # 獲得経験値: 300, フェーズ進行: True
            
        Note:
            - 1タスクあたり100経験値を獲得
            - 次のフェーズの必要経験値を超える場合は、経験値が制限される
            - タスク数が0以下の場合は経験値0を返す
        """
        # 今日のタスク数を取得
        if task_count <= 0:
            return 0, False

        # 経験値計算
        base_exp = 100          # 初回の基本経験値
        exp = 0                 # 獲得経験値の初期化

        # decay_rate = 0.8        # 2回目以降の経験値逓減係数
        # 当日完了したタスク数に応じて獲得経験値が逓減するように計算する。
        # for i in range(already_done, already_done + task_count):
        #     current_xp = base_exp * (decay_rate ** i)
        #     if current_xp < 1:
        #         current_xp = 1
        #     exp += int(current_xp)
        exp = base_exp * task_count

        # 次のフェーズの必要経験値を取得
        next_threshold = self._get_phase_thresholds(min(current_phase + 1, StoryPhase.KAN))
        logger.debug(f"次のフェーズの必要経験値: {next_threshold}")
        
        # 次のフェーズに移行できるかどうかを判定
        is_final_chapter = exp + total_exp >= next_threshold
        
        # 次のフェーズの必要経験値を超えないように経験値を制限
        if is_final_chapter:
            exp = next_threshold - total_exp
            logger.debug(f"経験値を制限: {exp}")

        # 浮動小数点数を整数に変換
        return int(exp), is_final_chapter

    # def _get_season_multiplier(self, season_number: int) -> float:
    #     """シーズン番号に応じた倍率を返す"""
    #     if season_number <= 1:
    #         return 1.0
    #     elif season_number == 2:
    #         return 1.5
    #     elif season_number in [3, 4]:
    #         return 2.0
    #     elif season_number in [5, 6]:
    #         return 3.0
    #     else:
    #         return 3.0

    def _get_phase_thresholds(self, phase: StoryPhase) -> int:
        """
        指定されたフェーズの必要経験値を取得
        
        Args:
            phase (StoryPhase): 対象のストーリーフェーズ
            
        Returns:
            int: そのフェーズに到達するために必要な経験値
            
        Examples:
            >>> calculator = ExperienceCalculator()
            >>> threshold = calculator._get_phase_thresholds(StoryPhase.SHO)
            >>> print(threshold)  # 200
        """
        return self.PHASE_THRESHOLDS[phase]

    def get_required_season_exp(self, season_no: int) -> int:
        """
        シーズン完了に必要な経験値を取得する
        
        現在は固定値（700経験値）を返しますが、
        将来的にはシーズン番号に応じて動的に計算する可能性があります。
        
        Args:
            season_no (int): シーズン番号（現在は使用されていない）
            
        Returns:
            int: シーズン完了に必要な経験値（700）
            
        Examples:
            >>> calculator = ExperienceCalculator()
            >>> required_exp = calculator.get_required_season_exp(1)
            >>> print(required_exp)  # 700
        """
        return self._get_phase_thresholds(StoryPhase.KAN)
    
    def get_phase(self, total_exp: int) -> StoryPhase:
        """
        経験値に応じて現在のフェーズを取得する
        
        総経験値から、現在のストーリーフェーズを判定します。
        
        Args:
            total_exp (int): 総経験値
            
        Returns:
            StoryPhase: 現在のストーリーフェーズ
            
        Examples:
            >>> calculator = ExperienceCalculator()
            >>> phase = calculator.get_phase(250)
            >>> print(phase)  # StoryPhase.SHO
            
        Note:
            - 経験値0の場合はKIフェーズを返す
            - 最大経験値以上の場合はKANフェーズを返す
            - フェーズの閾値はPHASE_THRESHOLDSで定義されている
        """
        # 経験値が0の場合はKIを返す
        if total_exp == 0:
            return StoryPhase.KI
            
        # 経験値に応じたフェーズを判定
        for i, threshold in enumerate(self.PHASE_THRESHOLDS):
            if total_exp < threshold:
                return StoryPhase(i - 1)
                
        # 最大経験値以上の場合はKANを返す
        return StoryPhase.KAN