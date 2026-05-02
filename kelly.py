"""
═══════════════════════════════════════════════════════════════════════════════
                    Kelly 公式與下注管理模組 (Kelly Module)
═══════════════════════════════════════════════════════════════════════════════

此模組實現完整的 Kelly 公式系統，包括：
- 標準 Kelly 公式
- 分數 Kelly（風險控制）
- 動態下注調整
- 破產風險評估

公式：f* = (b × p - q) / b

作者：Baccarat-Pro Team
版本：2.0
更新日期：2026-04-30
═══════════════════════════════════════════════════════════════════════════════
"""

import math
from typing import Dict, Tuple, Optional
from enum import Enum

# ═══════════════════════════════════════════════════════════════════════════════
# Kelly 管理器
# ═══════════════════════════════════════════════════════════════════════════════

class KellyStrategy(Enum):
    """Kelly 策略枚舉"""
    CONSERVATIVE = 0.25    # 1/4 Kelly - 推薦
    MODERATE = 0.50       # 1/2 Kelly
    AGGRESSIVE = 0.75     # 3/4 Kelly
    FULL = 1.0            # Full Kelly

class KellyCalculator:
    """
    Kelly 公式計算器
    
    功能：
    - 計算最優下注比例
    - 管理不同的 Kelly 策略
    - 評估風險
    - 提供下注建議
    """
    
    # Kelly 公式常數
    KELLY_FORMULA_COEFFICIENT = 1.0
    
    # 風險閾值
    RUIN_PROBABILITY_THRESHOLD = 0.01  # 1% 破產風險
    
    def __init__(self, strategy: KellyStrategy = KellyStrategy.CONSERVATIVE):
        """
        初始化 Kelly 計算器
        
        參數：
        - strategy: Kelly 策略 (預設保守型 1/4 Kelly)
        """
        self.strategy = strategy
        self.kelly_fraction = strategy.value
        self.history = []  # 下注歷史
    
    def calculate_kelly_percentage(self, win_rate: float, odds: float) -> float:
        """
        計算 Kelly 百分比
        
        公式：f* = (b × p - q) / b
        
        參數：
        - win_rate: 勝率 (0-1)
        - odds: 淨賠率 (例：0.95 for 5% commission)
        
        返回：
        Kelly 百分比 (0-1)
        """
        if not self._validate_inputs(win_rate, odds):
            return 0.0
        
        p = win_rate
        q = 1 - p
        b = odds
        
        # 標準 Kelly 公式
        f_full = (b * p - q) / b
        
        # 如果結果為負，表示不應該下注
        if f_full < 0:
            return 0.0
        
        return f_full
    
    def calculate_fractional_kelly(self, win_rate: float, odds: float) -> float:
        """
        計算分數 Kelly 百分比
        
        分數 Kelly = 全 Kelly × 分數係數
        
        目的：降低風險，同時保留收益潛力
        """
        f_full = self.calculate_kelly_percentage(win_rate, odds)
        f_fractional = f_full * self.kelly_fraction
        
        return f_fractional
    
    def get_bet_amount(self, kelly_percentage: float, bankroll: float) -> float:
        """
        根據 Kelly 百分比計算下注金額
        
        公式：下注金額 = Kelly百分比 × 資金
        """
        bet_amount = kelly_percentage * bankroll
        return max(0, bet_amount)
    
    def get_bet_units(self, kelly_percentage: float, bankroll: float, 
                     unit_size: float = 10) -> int:
        """
        將下注金額轉換為單位數
        
        參數：
        - kelly_percentage: Kelly 百分比
        - bankroll: 當前資金
        - unit_size: 每個單位的金額
        """
        bet_amount = self.get_bet_amount(kelly_percentage, bankroll)
        units = int(bet_amount / unit_size)
        return max(0, units)
    
    def estimate_ruin_probability(self, kelly_percentage: float, 
                                  initial_bankroll: float,
                                  target_bankroll: float) -> float:
        """
        估算破產概率
        
        使用 Gambler's Ruin 公式
        
        P(ruin) = 1 - (kelly_percentage * 2) ^ initial_bankroll / target_bankroll
        """
        if kelly_percentage <= 0 or kelly_percentage >= 1:
            return 0.0
        
        if initial_bankroll <= 0 or target_bankroll <= 0:
            return 1.0
        
        if initial_bankroll >= target_bankroll:
            return 0.0
        
        # 簡化的破產風險計算
        ruin_ratio = initial_bankroll / target_bankroll
        ruin_prob = math.pow(ruin_ratio, kelly_percentage * 2)
        
        return 1 - ruin_prob
    
    def calculate_expected_growth(self, kelly_percentage: float, 
                                  win_rate: float, num_bets: int) -> float:
        """
        計算期望增長率
        
        公式：E(growth) = (1 + f*×b×p - f*×q)^n
        """
        if kelly_percentage <= 0 or win_rate <= 0:
            return 0.0
        
        # 簡化的增長計算
        per_bet_growth = kelly_percentage * (2 * win_rate - 1)
        total_growth = math.pow(1 + per_bet_growth, num_bets)
        
        return total_growth
    
    def recommend_action(self, win_rate: float, odds: float, 
                        bankroll: float, unit_size: float = 10) -> Dict:
        """
        基於 Kelly 公式提供下注建議
        
        返回：
        {
            'kelly_percentage': float,
            'bet_units': int,
            'bet_amount': float,
            'confidence': 'HIGH'/'MEDIUM'/'LOW'/'NONE',
            'recommendation': '強烈下注'/'謹慎下注'/'觀望',
            'risk_level': '低'/'中'/'高',
            'ruin_probability': float
        }
        """
        kelly_pct = self.calculate_fractional_kelly(win_rate, odds)
        bet_units = self.get_bet_units(kelly_pct, bankroll, unit_size)
        bet_amount = self.get_bet_amount(kelly_pct, bankroll)
        ruin_prob = self.estimate_ruin_probability(kelly_pct, bankroll, bankroll * 0.2)
        
        # 判斷信心度
        if kelly_pct > 0.05:  # > 5%
            confidence = 'HIGH'
            recommendation = '強烈下注'
        elif kelly_pct > 0.01:  # > 1%
            confidence = 'MEDIUM'
            recommendation = '謹慎下注'
        elif kelly_pct > 0:  # > 0%
            confidence = 'LOW'
            recommendation = '輕注'
        else:
            confidence = 'NONE'
            recommendation = '觀望'
        
        # 判斷風險等級
        if ruin_prob > 0.05:  # > 5%
            risk_level = '高'
        elif ruin_prob > 0.01:  # > 1%
            risk_level = '中'
        else:
            risk_level = '低'
        
        return {
            'kelly_percentage': kelly_pct,
            'bet_units': bet_units,
            'bet_amount': bet_amount,
            'confidence': confidence,
            'recommendation': recommendation,
            'risk_level': risk_level,
            'ruin_probability': ruin_prob,
            'strategy': self.strategy.name
        }
    
    def update_strategy(self, strategy: KellyStrategy):
        """更新 Kelly 策略"""
        self.strategy = strategy
        self.kelly_fraction = strategy.value
    
    def record_bet(self, bet_amount: float, outcome: str, payout: float):
        """
        記錄一個下注
        
        參數：
        - bet_amount: 下注金額
        - outcome: 'WIN'/'LOSS'
        - payout: 贏得/損失的金額
        """
        self.history.append({
            'bet_amount': bet_amount,
            'outcome': outcome,
            'payout': payout
        })
    
    def get_statistics(self) -> Dict:
        """獲取下注統計"""
        if not self.history:
            return {'total_bets': 0}
        
        wins = sum(1 for h in self.history if h['outcome'] == 'WIN')
        losses = sum(1 for h in self.history if h['outcome'] == 'LOSS')
        total_bets = len(self.history)
        total_payout = sum(h['payout'] for h in self.history)
        
        return {
            'total_bets': total_bets,
            'wins': wins,
            'losses': losses,
            'win_rate': (wins / total_bets * 100) if total_bets > 0 else 0,
            'total_payout': total_payout,
            'average_payout_per_bet': (total_payout / total_bets) if total_bets > 0 else 0
        }
    
    def _validate_inputs(self, win_rate: float, odds: float) -> bool:
        """
        驗證輸入參數
        """
        if win_rate < 0 or win_rate > 1:
            return False
        if odds <= 0 or odds > 2.0:
            return False
        return True

# ═══════════════════════════════════════════════════════════════════════════════
# 單元測試
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    """運行 Kelly 公式測試"""
    tests_passed = 0
    tests_failed = 0
    
    # 測試 1: 基本 Kelly 計算
    try:
        calculator = KellyCalculator(KellyStrategy.CONSERVATIVE)
        kelly = calculator.calculate_kelly_percentage(0.55, 0.95)
        assert kelly > 0
        assert kelly < 0.1
        tests_passed += 1
        print("✅ 測試 1 (Kelly 計算): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 1 (Kelly 計算): 失敗 - {e}")
    
    # 測試 2: 分數 Kelly
    try:
        calculator = KellyCalculator(KellyStrategy.CONSERVATIVE)
        kelly_full = calculator.calculate_kelly_percentage(0.55, 0.95)
        kelly_frac = calculator.calculate_fractional_kelly(0.55, 0.95)
        
        # 分數 Kelly 應該小於全 Kelly
        assert kelly_frac < kelly_full
        assert abs(kelly_frac - kelly_full * 0.25) < 0.0001
        tests_passed += 1
        print("✅ 測試 2 (分數 Kelly): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 2 (分數 Kelly): 失敗 - {e}")
    
    # 測試 3: 下注單位計算
    try:
        calculator = KellyCalculator()
        kelly_pct = 0.02  # 2%
        bankroll = 1000
        unit_size = 10
        
        units = calculator.get_bet_units(kelly_pct, bankroll, unit_size)
        expected_units = int(0.02 * 1000 / 10)  # 2 個單位
        
        assert units == expected_units
        tests_passed += 1
        print("✅ 測試 3 (下注單位): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 3 (下注單位): 失敗 - {e}")
    
    # 測試 4: 建議系統
    try:
        calculator = KellyCalculator()
        advice = calculator.recommend_action(0.55, 0.95, 1000)
        
        assert 'kelly_percentage' in advice
        assert 'bet_units' in advice
        assert 'confidence' in advice
        assert 'recommendation' in advice
        tests_passed += 1
        print("✅ 測試 4 (建議系統): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 4 (建議系統): 失敗 - {e}")
    
    # 測試 5: 策略切換
    try:
        calculator = KellyCalculator(KellyStrategy.CONSERVATIVE)
        assert calculator.kelly_fraction == 0.25
        
        calculator.update_strategy(KellyStrategy.AGGRESSIVE)
        assert calculator.kelly_fraction == 0.75
        
        tests_passed += 1
        print("✅ 測試 5 (策略切換): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 5 (策略切換): 失敗 - {e}")
    
    # 測試 6: 下注記錄
    try:
        calculator = KellyCalculator()
        calculator.record_bet(100, 'WIN', 95)
        calculator.record_bet(100, 'LOSS', -100)
        calculator.record_bet(100, 'WIN', 95)
        
        stats = calculator.get_statistics()
        assert stats['total_bets'] == 3
        assert stats['wins'] == 2
        assert stats['losses'] == 1
        tests_passed += 1
        print("✅ 測試 6 (下注記錄): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 6 (下注記錄): 失敗 - {e}")
    
    # 測試 7: 破產風險估算
    try:
        calculator = KellyCalculator()
        ruin_prob = calculator.estimate_ruin_probability(0.01, 1000, 200)
        assert 0 <= ruin_prob <= 1
        tests_passed += 1
        print("✅ 測試 7 (破產風險): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 7 (破產風險): 失敗 - {e}")
    
    print(f"\n═══════════════════════════════════════════")
    print(f"✅ Kelly 測試完成: {tests_passed} 通過, {tests_failed} 失敗")
    print(f"═══════════════════════════════════════════\n")

if __name__ == '__main__':
    run_tests()
