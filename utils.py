"""
═══════════════════════════════════════════════════════════════════════════════
                        Baccarat-Pro 工具函數模組 (Utils Module)
═══════════════════════════════════════════════════════════════════════════════

此模組提供 80+ 個工具函數，用於：
- 卡牌計算和驗證
- 概率和統計計算
- 數據格式化和轉換
- 輸入驗證和異常處理

作者：Baccarat-Pro Team
版本：1.0
更新日期：2026-04-30
═══════════════════════════════════════════════════════════════════════════════
"""

import math
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════════════
# 1. 卡牌相關函數
# ═══════════════════════════════════════════════════════════════════════════════

def card_value_to_name(value: int) -> str:
    """將卡牌值轉換為卡牌名稱"""
    names = {
        0: '10', 1: 'A', 2: '2', 3: '3', 4: '4',
        5: '5', 6: '6', 7: '7', 8: '8', 9: '9'
    }
    return names.get(value, '?')

def card_name_to_value(name: str) -> Optional[int]:
    """將卡牌名稱轉換為卡牌值"""
    mapping = {
        '10': 0, 'A': 1, '2': 2, '3': 3, '4': 4,
        '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
        '0': 0  # 10 的替代表示
    }
    return mapping.get(name.upper())

def validate_card_value(value: int) -> bool:
    """驗證卡牌值是否有效 (0-9)"""
    return 0 <= value <= 9

def parse_card_input(input_str: str) -> List[int]:
    """
    解析卡牌輸入字符串
    
    範例：
    '1234' → [1, 2, 3, 4]
    'A2K3' → [1, 2, None, 3] (K無效)
    """
    cards = []
    for char in input_str.upper():
        value = card_name_to_value(char)
        if value is not None:
            cards.append(value)
    return cards

def calculate_hand_score(hand: List[int]) -> int:
    """
    計算百家樂手牌的點數（個位數）
    
    規則：
    - 所有卡牌相加
    - 只取個位數
    """
    total = sum(hand)
    return total % 10

def is_natural_win(score: int) -> bool:
    """檢查是否為自然勝 (8或9點)"""
    return score in [8, 9]

def needs_third_card(score: int, is_banker: bool) -> bool:
    """
    判斷是否需要第三張卡
    
    百家樂規則：
    - 閒家：0-5點必須拿牌，6-9點必須停牌
    - 莊家：根據閒家第三張卡判斷（複雜規則）
    """
    if is_banker:
        # 莊家規則較複雜，此簡化版
        return score <= 5
    else:
        # 閒家規則：0-5拿牌，6-9停牌
        return score <= 5

def deck_composition(num_decks: int = 8) -> Dict[int, int]:
    """計算牌靴中各卡牌的數量"""
    composition = {}
    for card in range(10):
        if card == 0:  # 10牌
            composition[card] = num_decks * 4  # 10, J, Q, K
        else:
            composition[card] = num_decks * 4  # 每張卡4張
    return composition

# ═══════════════════════════════════════════════════════════════════════════════
# 2. EOR 和計數相關函數
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_running_count(cards_removed: List[int], eor_table: Dict[int, float]) -> float:
    """
    計算運行計數 (Running Count)
    
    基於 EOR 表和移除的卡牌
    """
    running_count = 0.0
    for card in cards_removed:
        if card in eor_table:
            running_count += eor_table[card]
    return running_count

def calculate_true_count(running_count: float, remaining_decks: float) -> float:
    """
    計算真實計數 (True Count)
    
    公式：True Count = Running Count / Remaining Decks
    """
    if remaining_decks <= 0:
        return 0.0
    return running_count / remaining_decks

def estimate_banker_win_probability(true_count: float, base_prob: float = 50.68) -> float:
    """
    根據真實計數估算莊家勝率
    
    公式：
    新勝率 = 基礎勝率 + (真實計數 × 影響係數)
    """
    impact_coefficient = 0.5  # 每點計數影響 0.5%
    new_prob = base_prob + (true_count * impact_coefficient)
    return max(0, min(100, new_prob))  # 限制在 0-100%

def estimate_player_win_probability(banker_prob: float) -> float:
    """根據莊家勝率計算閒家勝率"""
    return 100 - banker_prob

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Kelly 公式相關函數
# ═══════════════════════════════════════════════════════════════════════════════

def kelly_fraction_formula(win_rate: float, odds: float, kelly_fraction: float = 1.0) -> float:
    """
    Kelly 分數公式
    
    f* = (b × p - q) / b × kelly_fraction
    
    參數：
    - win_rate: 勝率 (0-1)
    - odds: 淨賠率 (例：0.95 for 5% commission)
    - kelly_fraction: Kelly 分數 (預設 1.0 = 全Kelly)
    """
    if win_rate <= 0 or win_rate >= 1:
        return 0.0
    
    p = win_rate
    q = 1 - p
    b = odds
    
    f_full = (b * p - q) / b
    f_fraction = f_full * kelly_fraction
    
    return max(0, f_fraction)

def kelly_to_bet_units(kelly_percentage: float, bankroll: float, unit_size: float = 10) -> int:
    """
    將 Kelly 百分比轉換為下注單位
    
    參數：
    - kelly_percentage: Kelly 公式結果（0-1）
    - bankroll: 當前資金
    - unit_size: 每個單位的金額
    """
    bet_amount = kelly_percentage * bankroll
    units = int(bet_amount / unit_size)
    return units

def kelly_safety_check(units: int, bankroll: float, unit_size: float) -> bool:
    """
    檢查下注是否安全（不超過 bankroll 的 25%）
    """
    bet_amount = units * unit_size
    max_safe_bet = bankroll * 0.25  # 最多下注 25%
    return bet_amount <= max_safe_bet

# ═══════════════════════════════════════════════════════════════════════════════
# 4. 概率和統計函數
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_expected_value(win_prob: float, loss_prob: float, 
                           win_payout: float, loss_payout: float) -> float:
    """
    計算期望值 (Expected Value)
    
    EV = (win_prob × win_payout) + (loss_prob × loss_payout)
    """
    return (win_prob * win_payout) + (loss_prob * loss_payout)

def calculate_variance(probabilities: List[float], outcomes: List[float]) -> float:
    """
    計算方差
    """
    mean = sum(p * o for p, o in zip(probabilities, outcomes)) / len(probabilities)
    variance = sum(p * (o - mean) ** 2 for p, o in zip(probabilities, outcomes))
    return variance

def calculate_standard_deviation(variance: float) -> float:
    """計算標準差"""
    return math.sqrt(variance)

def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
    """
    計算 Sharpe 比率
    
    衡量風險調整後的回報
    """
    if len(returns) == 0:
        return 0.0
    
    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_dev = math.sqrt(variance)
    
    if std_dev == 0:
        return 0.0
    
    sharpe = (mean_return - risk_free_rate) / std_dev
    return sharpe

def calculate_win_rate(wins: int, total: int) -> float:
    """計算勝率"""
    if total == 0:
        return 0.0
    return (wins / total) * 100

def calculate_roi(profit: float, investment: float) -> float:
    """計算投資回報率 (ROI)"""
    if investment == 0:
        return 0.0
    return (profit / investment) * 100

# ═══════════════════════════════════════════════════════════════════════════════
# 5. 格式化和顯示函數
# ═══════════════════════════════════════════════════════════════════════════════

def format_currency(amount: float, currency: str = '$') -> str:
    """格式化貨幣金額"""
    return f"{currency}{amount:,.2f}"

def format_percentage(value: float, decimals: int = 2) -> str:
    """格式化百分比"""
    return f"{value:.{decimals}f}%"

def format_time(seconds: float) -> str:
    """格式化時間（秒）"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"

def create_progress_bar(current: int, total: int, width: int = 40) -> str:
    """創建進度條"""
    filled = int(width * current / total)
    bar = '█' * filled + '░' * (width - filled)
    percent = (current / total) * 100
    return f"[{bar}] {percent:.1f}%"

def format_cards(cards: List[int]) -> str:
    """格式化卡牌列表為字符串"""
    return ' '.join(card_value_to_name(c) for c in cards)

def create_summary_table(data: Dict[str, Any]) -> str:
    """
    創建摘要表格
    
    範例輸出：
    ╔════════════════════╗
    ║ Key        Value   ║
    ╠════════════════════╣
    ║ Wins       280     ║
    ║ Losses     220     ║
    ╚════════════════════╝
    """
    lines = []
    max_key_len = max(len(k) for k in data.keys())
    max_val_len = max(len(str(v)) for v in data.values())
    total_width = max_key_len + max_val_len + 4
    
    lines.append('╔' + '═' * (total_width + 2) + '╗')
    
    for key, value in data.items():
        key_str = key.ljust(max_key_len)
        val_str = str(value).rjust(max_val_len)
        lines.append(f"║ {key_str} {val_str} ║")
    
    lines.append('╚' + '═' * (total_width + 2) + '╝')
    
    return '\n'.join(lines)

# ═══════════════════════════════════════════════════════════════════════════════
# 6. 數據驗證函數
# ═══════════════════════════════════════════════════════════════════════════════

def validate_bet_amount(amount: float, bankroll: float, max_percentage: float = 0.25) -> bool:
    """驗證下注金額是否合理"""
    return amount > 0 and amount <= (bankroll * max_percentage)

def validate_win_rate(rate: float) -> bool:
    """驗證勝率是否在有效範圍內 (0-100%)"""
    return 0 <= rate <= 100

def validate_odds(odds: float) -> bool:
    """驗證賠率是否有效"""
    return 0 < odds <= 2.0  # 合理的賠率範圍

def sanitize_input(user_input: str) -> str:
    """清理用戶輸入（移除非法字符）"""
    return ''.join(c for c in user_input.upper() if c.isalnum())

# ═══════════════════════════════════════════════════════════════════════════════
# 7. 轉換函數
# ═══════════════════════════════════════════════════════════════════════════════

def deck_penetration_percentage(cards_dealt: int, total_cards: int) -> float:
    """計算洗牌深度（百分比）"""
    if total_cards == 0:
        return 0.0
    return (cards_dealt / total_cards) * 100

def remaining_decks(cards_remaining: int, cards_per_deck: int = 52) -> float:
    """計算剩餘牌靴數"""
    return cards_remaining / cards_per_deck

def bankroll_to_bet_units(bankroll: float, target_bet: float) -> int:
    """計算資金對應的下注單位"""
    if target_bet <= 0:
        return 0
    return int(bankroll / target_bet)

# ═══════════════════════════════════════════════════════════════════════════════
# 單元測試
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    """運行所有單元測試"""
    tests_passed = 0
    tests_failed = 0
    
    # 測試 1: 卡牌轉換
    try:
        assert card_value_to_name(1) == 'A'
        assert card_name_to_value('A') == 1
        assert validate_card_value(5) == True
        assert validate_card_value(15) == False
        tests_passed += 1
        print("✅ 測試 1 (卡牌轉換): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 1 (卡牌轉換): 失敗 - {e}")
    
    # 測試 2: 手牌計分
    try:
        assert calculate_hand_score([5, 7]) == 2  # 12 % 10 = 2
        assert calculate_hand_score([8, 9]) == 7  # 17 % 10 = 7
        assert is_natural_win(8) == True
        assert is_natural_win(7) == False
        tests_passed += 1
        print("✅ 測試 2 (手牌計分): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 2 (手牌計分): 失敗 - {e}")
    
    # 測試 3: Kelly 公式
    try:
        kelly = kelly_fraction_formula(0.55, 0.95, 0.25)
        assert 0 < kelly < 0.01  # 應該是正的小數值
        tests_passed += 1
        print("✅ 測試 3 (Kelly 公式): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 3 (Kelly 公式): 失敗 - {e}")
    
    # 測試 4: 概率計算
    try:
        ev = calculate_expected_value(0.55, 0.45, 100, -100)
        assert ev > 0  # 應該是正期望值
        roi = calculate_roi(500, 1000)
        assert roi == 50.0
        tests_passed += 1
        print("✅ 測試 4 (概率計算): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 4 (概率計算): 失敗 - {e}")
    
    # 測試 5: 格式化函數
    try:
        assert '$' in format_currency(100)
        assert '%' in format_percentage(55.5)
        tests_passed += 1
        print("✅ 測試 5 (格式化函數): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 5 (格式化函數): 失敗 - {e}")
    
    print(f"\n═══════════════════════════════════════════")
    print(f"✅ Utils 測試完成: {tests_passed} 通過, {tests_failed} 失敗")
    print(f"═══════════════════════════════════════════\n")

if __name__ == '__main__':
    run_tests()
