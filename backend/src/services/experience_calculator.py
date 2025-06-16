from typing import Dict, Tuple
from src.models.types import StoryPhase

class ExperienceCalculator:
    # フェーズごとの必要経験値の閾値
    # PHASE_THRESHOLDS = [0, 300, 600, 900, 1000]
    PHASE_THRESHOLDS = [0, 200, 400, 600, 700]

    def calculate_experience(self, task_count: int, already_done: int, current_phase: StoryPhase, total_exp: int) -> Tuple[int, bool]:
        """経験値計算

        Returns:
            Tuple[int, bool]: (獲得経験値, 次のフェーズに移行できるかどうか)
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
        print(f"next_threshold: {next_threshold}")
        
        # 次のフェーズに移行できるかどうかを判定
        is_final_chapter = exp + total_exp >= next_threshold
        
        # 次のフェーズの必要経験値を超えないように経験値を制限
        if is_final_chapter:
            exp = next_threshold - total_exp
            print(f"capped exp: {exp}")

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
        """シーズン番号に応じて、段階的に増加する各フェーズの必要経験値を返す"""
        return self.PHASE_THRESHOLDS[phase]

    def get_required_season_exp(self, season_no: int) -> int:
        """シーズン完了に必要な経験値を取得する"""
        return self._get_phase_thresholds(StoryPhase.KAN)
    
    def get_phase(self, total_exp: int) -> StoryPhase:
        """経験値に応じてフェーズを取得する"""
        # 経験値が0の場合はKIを返す
        if total_exp == 0:
            return StoryPhase.KI
            
        # 経験値に応じたフェーズを判定
        for i, threshold in enumerate(self.PHASE_THRESHOLDS):
            if total_exp < threshold:
                return StoryPhase(i - 1)
                
        # 最大経験値以上の場合はKANを返す
        return StoryPhase.KAN