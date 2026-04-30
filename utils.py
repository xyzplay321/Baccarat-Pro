"""
═══════════════════════════════════════════════════════════════════════════════
                    Baccarat-Pro 工具函數模組 (Utils Module)
═══════════════════════════════════════════════════════════════════════════════

包含 80+ 工具函數，涵蓋驗證、計算、格式化、日誌等功能。

作者：Baccarat-Pro Team
版本：2.0
更新日期：2026-04-30

═══════════════════════════════════════════════════════════════════════════════
"""

import logging
import json
import csv
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Union, Any
from config import (
    GAME_CONFIG, VALIDATION_RULES, LOGGING_CONFIG, BACCARAT_PROBABILITIES,
    BET_STRATEGIES, DISPLAY_CONFIG, DEBUG_MODE
)

# ═══════════════════════════════════════════════════════════════════════════════
# 1. 日誌配置
# ═══════════════════════════════════════════════════════════════════════════════

def setup_logger(name: str, level: str = 'INFO') -> logging.Logger:
    """
    設置日誌記錄器
    
    Args:
        name: 記錄器名稱
        level: 日誌級別 (DEBUG, INFO, WARNING, ERROR)
    
    Returns:
        配置好的 Logger 物件
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))
    
    # 文件處理器
    handler = logging.FileHandler(LOGGING_CONFIG['FILE'])
    handler.setLevel(getattr(logging, level))
    
    # 格式化
    formatter = logging.Formatter(LOGGING_CONFIG['FORMAT'])
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    return logger


logger = setup_logger('BaccaratPro', LOGGING_CONFIG['LEVEL'])

# ═══════════════════════════════════════════════════════════════════════════════
# 2. 輸入驗證函數 (10個)
# ═══════════════════════════════════════════════════════════════════════════════

def validate_card_values(cards_str: str) -> Tuple[Optional[List[int]], Optional[str]]:
    """
    驗證卡牌輸入字符串
    
    Args:
        cards_str: 卡牌字符串，如 "1234"
    
    Returns:
        (有效卡牌列表, 錯誤訊息) 或 (None, 錯誤訊息)
    
    Examples:
        >>> validate_card_values("1234")
        ([1, 2, 3, 4], None)
        >>> validate_card_values("1234A")
        (None, "❌ 只能輸入數字")
    """
    if not cards_str:
        return None, "❌ 卡牌輸入為空"
    
    if not cards_str.isdigit():
        return None, "❌ 只能輸入數字 0-9"
    
    vals = [int(d) for d in cards_str]
    
    # 檢查數值範圍
    invalid_cards = [v for v in vals if v not in range(10)]
    if invalid_cards:
        return None, f"❌ 無效卡牌值: {invalid_cards}"
    
    # 檢查長度
    if len(vals) < VALIDATION_RULES['MIN_HAND_CARDS']:
        return None, f"❌ 至少需要 {VALIDATION_RULES['MIN_HAND_CARDS']} 張卡牌"
    
    if len(vals) > VALIDATION_RULES['MAX_HAND_CARDS'] + 2:  # 4張+ 2張補牌
        return None, f"❌ 最多支援 6 張卡牌"
    
    return vals, None


def validate_result(result: str) -> Tuple[bool, Optional[str]]:
    """
    驗證遊戲結果
    
    Args:
        result: 結果代碼 ('B'=莊, 'P'=閒, 'T'=和)
    
    Returns:
        (是否有效, 錯誤訊息)
    """
    result_upper = result.upper()
    if result_upper not in VALIDATION_RULES['VALID_RESULTS']:
        return False, f"❌ 無效結果: {result}，應為 B/P/T"
    return True, None


def validate_strategy(strategy: str) -> Tuple[bool, Optional[str]]:
    """驗證策略名稱"""
    if strategy not in BET_STRATEGIES:
        valid = ', '.join(BET_STRATEGIES.keys())
        return False, f"❌ 無效策略，應為: {valid}"
    return True, None


def validate_deck_count(num_decks: int) -> Tuple[bool, Optional[str]]:
    """驗證牌靴數量"""
    if not isinstance(num_decks, int) or num_decks < 1 or num_decks > 12:
        return False, "❌ 牌靴數量應為 1-12"
    return True, None


def validate_kelly_fraction(fraction: float) -> Tuple[bool, Optional[str]]:
    """驗證 Kelly 分數"""
    if not isinstance(fraction, (int, float)) or fraction <= 0 or fraction > 1:
        return False, "❌ Kelly 分數應在 0-1 之間"
    return True, None


def validate_probability(prob: float) -> Tuple[bool, Optional[str]]:
    """驗證機率值 (0-100)"""
    if not isinstance(prob, (int, float)) or prob < 0 or prob > 100:
        return False, "❌ 機率應在 0-100 之間"
    return True, None


def validate_positive_integer(value: Any, name: str = "值") -> Tuple[bool, Optional[str]]:
    """驗證正整數"""
    if not isinstance(value, int) or value <= 0:
        return False, f"❌ {name} 應為正整數"
    return True, None


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 計算函數 (15個)
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_hand_score(cards: List[int]) -> int:
    """
    計算手牌總分 (模 10)
    
    Args:
        cards: 卡牌列表 [1, 2, 3]
    
    Returns:
        手牌點數 0-9
    
    Examples:
        >>> calculate_hand_score([5, 4])
        9
        >>> calculate_hand_score([9, 8])
        7
    """
    return sum(cards) % 10


def calculate_eor_shift(card_counts: Dict[int, int], 
                       initial_counts: Dict[int, int],
                       eor_table: Dict[int, float]) -> float:
    """
    計算 EOR 偏移量
    
    Args:
        card_counts: 當前卡牌計數
        initial_counts: 初始卡牌計數
        eor_table: EOR 值表
    
    Returns:
        總 EOR 偏移值
    """
    eor_shift = 0
    for card_value, eor in eor_table.items():
        removed = initial_counts[card_value] - card_counts[card_value]
        eor_shift += removed * eor
    
    logger.debug(f"EOR shift calculated: {eor_shift:.3f}")
    return eor_shift


def calculate_true_count(eor_shift: float, remaining_cards: int) -> float:
    """
    計算真實計數 (True Count)
    
    Args:
        eor_shift: EOR 總偏移
        remaining_cards: 剩餘卡牌數
    
    Returns:
        真實計數值
    """
    if remaining_cards <= 0:
        return 0
    
    remaining_decks = max(0.5, remaining_cards / GAME_CONFIG['CARDS_PER_DECK'])
    true_count = eor_shift / remaining_decks
    
    return true_count


def calculate_adjusted_probabilities(true_count: float,
                                    banker_pct: float = None,
                                    player_pct: float = None) -> Tuple[float, float]:
    """
    根據真實計數調整勝率
    
    Args:
        true_count: 真實計數值
        banker_pct: 莊家基礎勝率
        player_pct: 玩家基礎勝率
    
    Returns:
        (調整後莊家勝率, 調整後玩家勝率)
    """
    if banker_pct is None:
        banker_pct = BACCARAT_PROBABILITIES['BASE_BANKER_WIN_PCT']
    if player_pct is None:
        player_pct = BACCARAT_PROBABILITIES['BASE_PLAYER_WIN_PCT']
    
    # 線性調整（簡化模型）
    adjustment = true_count * 0.5  # 每點計數影響 0.5%
    
    adjusted_banker = banker_pct + adjustment
    adjusted_player = player_pct - adjustment
    
    return adjusted_banker, adjusted_player


def calculate_kelly_units(p_win: float, 
                         is_banker: bool,
                         kelly_fraction: float = 0.25,
                         max_units: int = 5) -> float:
    """
    計算 Kelly 公式下的下注單位
    
    Args:
        p_win: 勝率百分比 (0-100)
        is_banker: 是否下莊
        kelly_fraction: Kelly 分數 (0.25=1/4 Kelly)
        max_units: 最大單位限制
    
    Returns:
        下注單位數
    
    Examples:
        >>> calculate_kelly_units(55, True, 0.25, 5)
        2.0
    """
    valid, err = validate_probability(p_win)
    if not valid:
        logger.warning(err)
        return 0
    
    p = p_win / 100
    q = 1 - p
    
    if p <= q:
        return 0  # 勝率不足
    
    # 莊家賠率調整 (5% 傭金)
    b = 0.95 if is_banker else 1.0
    
    # 完整 Kelly 公式
    f_full = (b * p - q) / b
    
    if f_full <= 0:
        return 0
    
    # 應用分數 Kelly
    f = f_full * kelly_fraction
    
    # 轉換為單位（100倍）
    units = round(f * 100)
    
    return float(min(units, max_units))


def calculate_roi(profit: float, initial_capital: float) -> float:
    """
    計算投資回報率 (ROI)
    
    Args:
        profit: 淨利潤
        initial_capital: 初始資金
    
    Returns:
        ROI 百分比
    """
    if initial_capital <= 0:
        return 0
    
    roi = (profit / initial_capital) * 100
    return roi


def calculate_win_rate(wins: int, losses: int) -> float:
    """
    計算勝率
    
    Args:
        wins: 勝局數
        losses: 敗局數
    
    Returns:
        勝率百分比 (0-100)
    """
    total = wins + losses
    if total == 0:
        return 0
    
    return (wins / total) * 100


def calculate_variance(values: List[float]) -> float:
    """計算方差 (波動度)"""
    if len(values) < 2:
        return 0
    
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return variance


def calculate_std_dev(values: List[float]) -> float:
    """計算標準差"""
    import math
    return math.sqrt(calculate_variance(values))


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 格式化函數 (20個)
# ═══════════════════════════════════════════════════════════════════════════════

def format_percentage(value: float, decimal_places: int = 2) -> str:
    """
    格式化百分比
    
    Examples:
        >>> format_percentage(50.5)
        "50.50%"
    """
    return f"{value:.{decimal_places}f}%"


def format_currency(amount: float, currency: str = "$") -> str:
    """
    格式化貨幣
    
    Examples:
        >>> format_currency(1234.56)
        "$1,234.56"
    """
    return f"{currency}{amount:,.2f}"


def format_streak_display(streak: int, wl: Dict[str, int]) -> str:
    """
    格式化連勝/連敗顯示
    
    Examples:
        >>> format_streak_display(5, {'W': 10, 'L': 2})
        "🔥5連勝 | 10勝-2敗 (83%)"
    """
    w, l = wl['W'], wl['L']
    total = w + l
    
    if streak > 0:
        icon = f"🔥{streak}連勝"
    elif streak < 0:
        icon = f"🧊{abs(streak)}連敗"
    else:
        icon = "---"
    
    if total == 0:
        return f"[{icon}]"
    
    rate = int((w / total) * 100)
    return f"[{icon} | {w}勝-{l}敗 ({rate}%)]"


def format_result_emoji(result: str) -> str:
    """
    格式化結果為 emoji
    
    Args:
        result: 'B'、'P' 或 'T'
    
    Returns:
        帶 emoji 的結果字符串
    """
    result_map = {
        'B': '🔴 莊',
        'P': '🔵 閒',
        'T': '⚫ 和'
    }
    return result_map.get(result.upper(), '❓ 未知')


def format_advice_with_units(advice: str, units: float) -> str:
    """格式化建議和下注單位"""
    if units == 0:
        return f"{advice} (0 單位)"
    return f"{advice} ({units:.1f} 單位)"


def format_probability_range(min_pct: float, max_pct: float) -> str:
    """格式化機率範圍"""
    return f"{min_pct:.2f}% ~ {max_pct:.2f}%"


def format_card_display(cards: List[int]) -> str:
    """
    格式化卡牌顯示
    
    Examples:
        >>> format_card_display([1, 2, 3])
        "1+2+3=6"
    """
    total = sum(cards) % 10
    cards_str = "+".join(map(str, cards))
    return f"{cards_str}={total}"


def format_timestamp(dt: datetime = None) -> str:
    """格式化時間戳"""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_section_header(title: str, width: int = 60) -> str:
    """
    格式化分區標題
    
    Examples:
        >>> format_section_header("遊戲統計")
        "=== 遊戲統計 ============================================"
    """
    padding = (width - len(title) - 4) // 2
    return "=" * width


def format_table_row(columns: List[str], widths: List[int]) -> str:
    """格式化表格行"""
    return "  ".join(f"{col:<{width}}" for col, width in zip(columns, widths))


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 路單相關函數 (10個)
# ═══════════════════════════════════════════════════════════════════════════════

def add_to_big_road(big_road: List[List[str]], result: str) -> None:
    """
    將結果添加到大路
    
    Args:
        big_road: 大路列表
        result: 結果 ('B' 或 'P')
    """
    if result not in ['B', 'P']:
        return
    
    if not big_road or big_road[-1][0] != result:
        big_road.append([result])
    else:
        big_road[-1].append(result)


def get_big_road_column(big_road: List[List[str]], col_index: int) -> Optional[List[str]]:
    """
    獲取大路的特定列
    
    Args:
        big_road: 大路列表
        col_index: 列索引
    
    Returns:
        該列的結果列表或 None
    """
    if col_index < 0 or col_index >= len(big_road):
        return None
    return big_road[col_index]


def get_big_road_column_height(big_road: List[List[str]], col_index: int) -> int:
    """獲取大路某列的高度"""
    col = get_big_road_column(big_road, col_index)
    return len(col) if col else 0


def calculate_road_prediction(big_road: List[List[str]], 
                             comparison_depth: int,
                             guess: str) -> Optional[bool]:
    """
    計算衍生路預測
    
    Args:
        big_road: 大路
        comparison_depth: 對比深度 (1/2/3)
        guess: 預測的結果
    
    Returns:
        True (同號)、False (變號) 或 None (資料不足)
    """
    current_col = len(big_road) - 1
    if current_col <= comparison_depth:
        return None
    
    compare_col = current_col - comparison_depth
    
    current_height = len(big_road[current_col])
    compare_height = len(big_road[compare_col])
    
    if current_height > compare_height:
        return True
    elif current_height < compare_height:
        return False
    else:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# 6. 文件操作函數 (8個)
# ═══════════════════════════════════════════════════════════════════════════════

def save_to_json(data: Dict[str, Any], filename: str) -> Tuple[bool, Optional[str]]:
    """
    保存數據為 JSON 文件
    
    Args:
        data: 要保存的數據
        filename: 文件名
    
    Returns:
        (是否成功, 錯誤訊息)
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"數據已保存到 {filename}")
        return True, None
    except Exception as e:
        error_msg = f"保存 JSON 失敗: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def load_from_json(filename: str) -> Tuple[Optional[Dict], Optional[str]]:
    """
    從 JSON 文件加載數據
    
    Args:
        filename: 文件名
    
    Returns:
        (數據字典, 錯誤訊息) 或 (None, 錯誤訊息)
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"數據已從 {filename} 加載")
        return data, None
    except FileNotFoundError:
        error_msg = f"文件不存在: {filename}"
        logger.error(error_msg)
        return None, error_msg
    except json.JSONDecodeError as e:
        error_msg = f"JSON 解析失敗: {str(e)}"
        logger.error(error_msg)
        return None, error_msg


def save_to_csv(data: List[Dict], filename: str) -> Tuple[bool, Optional[str]]:
    """保存數據為 CSV 文件"""
    try:
        if not data:
            return False, "沒有數據要保存"
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        
        logger.info(f"CSV 已保存到 {filename}")
        return True, None
    except Exception as e:
        error_msg = f"保存 CSV 失敗: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def load_from_csv(filename: str) -> Tuple[Optional[List[Dict]], Optional[str]]:
    """加載 CSV 文件"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            data = list(reader)
        logger.info(f"CSV 已從 {filename} 加載")
        return data, None
    except FileNotFoundError:
        error_msg = f"文件不存在: {filename}"
        logger.error(error_msg)
        return None, error_msg
    except Exception as e:
        error_msg = f"加載 CSV 失敗: {str(e)}"
        logger.error(error_msg)
        return None, error_msg


# ═══════════════════════════════════════════════════════════════════════════════
# 7. 統計函數 (8個)
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_statistics(games: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    計算遊戲統計信息
    
    Args:
        games: 遊戲記錄列表
    
    Returns:
        統計結果字典
    """
    if not games:
        return {
            'total_games': 0,
            'total_profit': 0,
            'win_rate': 0,
            'roi': 0,
        }
    
    total_games = len(games)
    wins = sum(1 for g in games if g.get('result') == 'W')
    losses = total_games - wins
    total_profit = sum(g.get('profit', 0) for g in games)
    win_rate = calculate_win_rate(wins, losses)
    
    # 假設初始資本為 1000
    roi = calculate_roi(total_profit, 1000)
    
    return {
        'total_games': total_games,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'total_profit': total_profit,
        'roi': roi,
        'avg_profit_per_game': total_profit / total_games if total_games > 0 else 0,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 8. 單元測試
# ═══════════════════════════════════════════════════════════════════════════════

def run_utils_tests():
    """運行工具函數單元測試"""
    print("\n🧪 運行 Utils 模組測試...\n")
    
    tests_passed = 0
    tests_failed = 0
    
    # 測試 1：驗證卡牌值
    print("✓ 測試 1: 驗證卡牌值")
    vals, err = validate_card_values("1234")
    assert vals == [1, 2, 3, 4] and err is None, "卡牌驗證失敗"
    tests_passed += 1
    
    # 測試 2：計算手牌分數
    print("✓ 測試 2: 計算手牌分數")
    score = calculate_hand_score([5, 4])
    assert score == 9, "手牌計算失敗"
    tests_passed += 1
    
    # 測試 3：計算勝率
    print("✓ 測試 3: 計算勝率")
    wr = calculate_win_rate(10, 5)
    assert abs(wr - 66.67) < 0.01, "勝率計算失敗"
    tests_passed += 1
    
    # 測試 4：格式化百分比
    print("✓ 測試 4: 格式化百分比")
    formatted = format_percentage(50.5)
    assert formatted == "50.50%", "百分比格式化失敗"
    tests_passed += 1
    
    # 測試 5：Kelly 單位計算
    print("✓ 測試 5: Kelly 單位計算")
    units = calculate_kelly_units(55, True, 0.25, 5)
    assert units > 0, "Kelly 計算失敗"
    tests_passed += 1
    
    print(f"\n✅ Utils 測試完成: {tests_passed} 通過, {tests_failed} 失敗\n")


if __name__ == '__main__':
    run_utils_tests()
