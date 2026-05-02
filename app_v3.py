"""
═══════════════════════════════════════════════════════════════════════════════
                    Baccarat-Pro v3.0 改進版主程序
═══════════════════════════════════════════════════════════════════════════════

整合所有改進模組的主程序

功能：
- 完整的 EOR 計算系統
- 澳門路單分析
- Kelly 公式下注建議
- 完整回測功能
- Web 界面支持

作者：Baccarat-Pro Team
版本：3.0
更新日期：2026-04-30
═══════════════════════════════════════════════════════════════════════════════
"""

import sys
import json
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from enum import Enum

# 導入改進的模組
try:
    from config import (
        EOR_SOURCES, DEFAULT_EOR_SOURCE, BET_STRATEGIES, DEFAULT_BET_STRATEGY,
        ROAD_CONFIGURATIONS, GAME_CONFIG, CONFIDENCE_LEVELS
    )
    from utils import (
        card_value_to_name, card_name_to_value, calculate_hand_score,
        parse_card_input, kelly_fraction_formula, calculate_true_count,
        estimate_banker_win_probability, format_currency, format_percentage
    )
    from road import RoadAnalyzer
    from kelly import KellyCalculator, KellyStrategy
except ImportError as e:
    print(f"⚠️ 無法導入模組: {e}")
    print("🔧 建議：確保 config.py, utils.py, road.py, kelly.py 在同一目錄")

class BaccaratProV3:
    """
    Baccarat-Pro v3.0 - 改進版百家樂預測系統
    """
    
    def __init__(self, num_decks: int = 8, eor_source: str = DEFAULT_EOR_SOURCE,
                 bet_strategy: str = DEFAULT_BET_STRATEGY):
        """
        初始化系統
        """
        self.num_decks = num_decks
        self.eor_source = eor_source
        self.eor_table = EOR_SOURCES.get(eor_source, EOR_SOURCES['JACOBSON'])
        self.bet_strategy = bet_strategy
        self.bet_config = BET_STRATEGIES.get(bet_strategy, BET_STRATEGIES['CONSERVATIVE'])
        
        # 初始化各模組
        self.road_analyzer = RoadAnalyzer()
        self.kelly_calculator = KellyCalculator(
            KellyStrategy[bet_strategy] if bet_strategy in KellyStrategy.__members__
            else KellyStrategy.CONSERVATIVE
        )
        
        # 遊戲狀態
        self.cards_dealt = 0
        self.total_cards = num_decks * GAME_CONFIG['CARDS_PER_DECK']
        self.running_count = 0.0
        self.current_hand = {'banker': [], 'player': []}
        
        print(f"\n✅ Baccarat-Pro v3.0 已初始化")
        print(f"   - EOR 來源: {eor_source}")
        print(f"   - 下注策略: {bet_strategy}")
        print(f"   - 牌靴數量: {num_decks}")
    
    def add_game_result(self, result: str) -> Dict:
        """
        添加一個遊戲結果並進行分析
        
        參數：
        - result: 'B' (莊勝), 'P' (閒勝), 'T' (和局)
        
        返回：
        分析結果字典
        """
        # 添加到路單
        self.road_analyzer.add_result(result)
        
        # 獲取路單預測
        road_prediction = self.road_analyzer.predict_next_result()
        
        # 計算數學信號
        true_count = calculate_true_count(
            self.running_count,
            (self.total_cards - self.cards_dealt) / GAME_CONFIG['CARDS_PER_DECK']
        )
        
        banker_prob = estimate_banker_win_probability(true_count)
        player_prob = 100 - banker_prob
        
        # 決定數學信號
        math_signal = None
        if banker_prob > player_prob + self.bet_config['margin']:
            math_signal = 'B'
        elif player_prob > banker_prob + self.bet_config['margin']:
            math_signal = 'P'
        
        # 綜合判斷
        consensus = road_prediction.get('consensus')
        confidence = self._calculate_confidence(math_signal, consensus)
        
        # Kelly 下注建議
        kelly_advice_banker = self.kelly_calculator.recommend_action(
            banker_prob / 100, 0.95, 1000  # 假設資金 1000
        ) if banker_prob > 50 else None
        
        kelly_advice_player = self.kelly_calculator.recommend_action(
            player_prob / 100, 1.0, 1000
        ) if player_prob > 50 else None
        
        return {
            'result': result,
            'road_prediction': road_prediction,
            'math_signal': math_signal,
            'banker_prob': banker_prob,
            'player_prob': player_prob,
            'confidence': confidence,
            'kelly_advice_banker': kelly_advice_banker,
            'kelly_advice_player': kelly_advice_player,
            'true_count': true_count,
            'timestamp': datetime.now().isoformat()
        }
    
    def _calculate_confidence(self, math_signal: Optional[str], 
                             consensus: Optional[str]) -> str:
        """
        計算信心度
        """
        if math_signal and consensus and math_signal == consensus:
            return 'HIGH'  # 強共振
        elif math_signal or consensus:
            return 'MEDIUM'  # 單邊信號
        else:
            return 'LOW'  # 無信號
    
    def display_summary(self):
        """
        顯示系統摘要
        """
        print(f"\n╔════════════════════════════════════╗")
        print(f"║   Baccarat-Pro v3.0 系統摘要      ║")
        print(f"╠════════════════════════════════════╣")
        print(f"║ EOR 來源: {self.eor_source:<20} ║")
        print(f"║ 下注策略: {self.bet_strategy:<20} ║")
        print(f"║ 牌靴數量: {self.num_decks:<20} ║")
        print(f"║ 已發牌數: {self.cards_dealt:<20} ║")
        print(f"║ 運行計數: {self.running_count:<20.2f} ║")
        print(f"║ 路單長度: {len(self.road_analyzer.big_road):<20} ║")
        print(f"╚════════════════════════════════════╝\n")
    
    def get_system_info(self) -> Dict:
        """
        獲取系統信息
        """
        return {
            'version': '3.0',
            'eor_source': self.eor_source,
            'bet_strategy': self.bet_strategy,
            'num_decks': self.num_decks,
            'cards_dealt': self.cards_dealt,
            'running_count': self.running_count,
            'road_length': len(self.road_analyzer.big_road),
            'timestamp': datetime.now().isoformat()
        }

# ═══════════════════════════════════════════════════════════════════════════════
# 演示和測試
# ═══════════════════════════════════════════════════════════════════════════════

def demo():
    """
    運行系統演示
    """
    print("\n" + "═" * 60)
    print("  Baccarat-Pro v3.0 - 完整改進系統演示")
    print("═" * 60 + "\n")
    
    # 初始化系統
    system = BaccaratProV3(
        num_decks=8,
        eor_source='JACOBSON',
        bet_strategy='CONSERVATIVE'
    )
    
    # 顯示系統信息
    system.display_summary()
    
    # 模擬幾個遊戲
    results = ['B', 'B', 'P', 'P', 'B', 'P', 'P', 'P']
    
    print("【模擬遊戲分析】\n")
    
    for i, result in enumerate(results, 1):
        analysis = system.add_game_result(result)
        
        print(f"第 {i} 局 - 結果: {result}")
        print(f"  路單預測: {analysis['road_prediction'].get('consensus', 'N/A')}")
        print(f"  信心度: {analysis['confidence']}")
        print(f"  莊家勝率: {analysis['banker_prob']:.2f}%")
        print(f"  真實計數: {analysis['true_count']:.2f}")
        print()
    
    # 最終摘要
    print("\n【系統狀態】")
    info = system.get_system_info()
    print(f"版本: {info['version']}")
    print(f"EOR來源: {info['eor_source']}")
    print(f"路單長度: {info['road_length']}")
    print(f"\n✅ 演示完成！")

if __name__ == '__main__':
    demo()
