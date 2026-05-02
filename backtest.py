"""
═══════════════════════════════════════════════════════════════════════════════
                        回測引擎 (Backtest Module)
═══════════════════════════════════════════════════════════════════════════════

完整的回測系統，用於驗證下注策略的有效性

功能：
- 加載歷史遊戲數據
- 模擬下注過程
- 計算性能指標
- 生成詳細報告
- 數據導出

作者：Baccarat-Pro Team
版本：1.0
更新日期：2026-04-30
═══════════════════════════════════════════════════════════════════════════════
"""

import csv
import json
from typing import Dict, List, Callable, Tuple, Optional
from datetime import datetime
import math

class BacktestEngine:
    """
    回測引擎
    
    用於評估下注策略的性能
    """
    
    def __init__(self, start_capital: float = 1000, unit_size: float = 10):
        """
        初始化回測引擎
        
        參數：
        - start_capital: 起始資金
        - unit_size: 每個單位的金額
        """
        self.start_capital = start_capital
        self.unit_size = unit_size
        self.current_capital = start_capital
        
        self.trades = []  # 交易記錄
        self.equity_curve = []  # 資金曲線
        self.drawdown_history = []  # 回撤歷史
    
    def load_games_from_csv(self, filename: str) -> List[Dict]:
        """
        從 CSV 文件加載遊戲數據
        
        CSV 格式：
        round_id, result, banker_score, player_score, date
        """
        games = []
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    games.append(row)
        except FileNotFoundError:
            print(f"❌ 文件不存在: {filename}")
        
        return games
    
    def load_games_from_json(self, filename: str) -> List[Dict]:
        """
        從 JSON 文件加載遊戲數據
        """
        games = []
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                games = data if isinstance(data, list) else data.get('games', [])
        except FileNotFoundError:
            print(f"❌ 文件不存在: {filename}")
        
        return games
    
    def run_backtest(self, games: List[Dict], 
                    predictor: Callable[[List], Tuple[str, int]]) -> bool:
        """
        運行回測
        
        參數：
        - games: 遊戲列表
        - predictor: 預測器函數
          接收: 歷史交易列表
          返回: (預測結果 'B'/'P'/'WAIT', 下注單位)
        
        範例預測器：
        def simple_predictor(history):
            if len(history) < 10:
                return 'WAIT', 0
            recent_wins = sum(1 for t in history[-10:] if t.get('profit', 0) > 0)
            if recent_wins >= 7:
                return 'B', 5
            return 'WAIT', 0
        """
        self.reset()
        
        for game_idx, game in enumerate(games):
            # 獲取遊戲結果
            actual_result = self._parse_game_result(game)
            if not actual_result:
                continue
            
            # 獲取預測
            prediction, units = predictor(self.trades)
            
            # 如果預測是觀望，跳過
            if prediction == 'WAIT' or units == 0:
                continue
            
            # 計算下注金額
            bet_amount = units * self.unit_size
            
            # 檢查資金是否足夠
            if bet_amount > self.current_capital:
                bet_amount = self.current_capital
                units = int(bet_amount / self.unit_size)
            
            # 計算損益
            if prediction == actual_result:
                # 勝
                if actual_result == 'B':
                    profit = bet_amount * 0.95 - bet_amount  # 莊家下注扣 5% 傭金
                else:
                    profit = bet_amount  # 閒家下注 1:1
                outcome = 'WIN'
            else:
                # 負
                profit = -bet_amount
                outcome = 'LOSS'
            
            # 更新資金
            self.current_capital += profit
            
            # 記錄交易
            trade = {
                'round': game_idx + 1,
                'prediction': prediction,
                'actual': actual_result,
                'bet_amount': bet_amount,
                'units': units,
                'profit': profit,
                'outcome': outcome,
                'capital_after': self.current_capital
            }
            self.trades.append(trade)
            self.equity_curve.append(self.current_capital)
            
            # 檢查破產
            if self.current_capital <= 0:
                print(f"⚠️ 回測在第 {game_idx + 1} 局結束 - 資金耗盡")
                break
        
        return len(self.trades) > 0
    
    def _parse_game_result(self, game: Dict) -> Optional[str]:
        """
        解析遊戲結果
        
        支持多種格式：
        - result: 'B'/'P'/'T'
        - banker_wins: True/False
        """
        if 'result' in game:
            return game['result'].upper()
        elif 'banker_wins' in game:
            return 'B' if game['banker_wins'] else 'P'
        elif 'winner' in game:
            return 'B' if game['winner'].upper() in ['BANKER', 'B'] else 'P'
        
        return None
    
    def get_statistics(self) -> Dict:
        """
        計算回測統計
        """
        if not self.trades:
            return {}
        
        wins = sum(1 for t in self.trades if t['outcome'] == 'WIN')
        losses = sum(1 for t in self.trades if t['outcome'] == 'LOSS')
        total_trades = len(self.trades)
        
        total_profit = sum(t['profit'] for t in self.trades)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        avg_win = sum(t['profit'] for t in self.trades if t['outcome'] == 'WIN') / wins if wins > 0 else 0
        avg_loss = sum(abs(t['profit']) for t in self.trades if t['outcome'] == 'LOSS') / losses if losses > 0 else 0
        
        max_drawdown = self._calculate_max_drawdown()
        roi = (total_profit / self.start_capital * 100) if self.start_capital > 0 else 0
        
        # Sharpe 比率
        returns = [t['profit'] for t in self.trades]
        sharpe = self._calculate_sharpe_ratio(returns)
        
        return {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_profit': total_profit,
            'roi_percentage': roi,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': avg_win / avg_loss if avg_loss > 0 else 0,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'final_capital': self.current_capital
        }
    
    def _calculate_max_drawdown(self) -> float:
        """
        計算最大回撤
        """
        if not self.equity_curve:
            return 0.0
        
        peak = self.equity_curve[0]
        max_dd = 0.0
        
        for value in self.equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0
            if drawdown > max_dd:
                max_dd = drawdown
        
        return max_dd * 100
    
    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """
        計算 Sharpe 比率
        """
        if len(returns) < 2:
            return 0.0
        
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0:
            return 0.0
        
        sharpe = (mean_return * 252) / std_dev  # 年化
        return sharpe
    
    def generate_summary_report(self) -> str:
        """
        生成摘要報告
        """
        stats = self.get_statistics()
        
        if not stats:
            return "❌ 無交易數據"
        
        report = []
        report.append("╔════════════════════════════════════════════════╗")
        report.append("║      Baccarat-Pro 回測摘要報告               ║")
        report.append("╠════════════════════════════════════════════════╣")
        report.append(f"║ 起始資金:        ${self.start_capital:>30,.2f} ║")
        report.append(f"║ 最終資金:        ${stats['final_capital']:>30,.2f} ║")
        report.append(f"║ 淨利潤:          ${stats['total_profit']:>30,.2f} ║")
        report.append(f"║ 回報率 (ROI):    {stats['roi_percentage']:>30.2f}% ║")
        report.append("╠════════════════════════════════════════════════╣")
        report.append(f"║ 總交易數:        {stats['total_trades']:>30} ║")
        report.append(f"║ 勝局數:          {stats['wins']:>30} ║")
        report.append(f"║ 敗局數:          {stats['losses']:>30} ║")
        report.append(f"║ 勝率:            {stats['win_rate']:>30.2f}% ║")
        report.append(f"║ 平均勝利:        ${stats['avg_win']:>30,.2f} ║")
        report.append(f"║ 平均虧損:        ${stats['avg_loss']:>30,.2f} ║")
        report.append("╠════════════════════════════════════════════════╣")
        report.append(f"║ 最大回撤:        {stats['max_drawdown']:>30.2f}% ║")
        report.append(f"║ Sharpe 比率:     {stats['sharpe_ratio']:>30.2f} ║")
        report.append(f"║ 利潤因子:        {stats['profit_factor']:>30.2f} ║")
        report.append("╚════════════════════════════════════════════════╝")
        
        return "\n".join(report)
    
    def generate_full_report(self) -> str:
        """
        生成完整報告
        """
        report = self.generate_summary_report()
        report += "\n\n【最近 10 筆交易】\n"
        
        recent_trades = self.trades[-10:] if len(self.trades) > 10 else self.trades
        
        for trade in recent_trades:
            symbol = "✓" if trade['outcome'] == 'WIN' else "✗"
            report += f"{symbol} Round {trade['round']:>4} | {trade['prediction']:>1} vs {trade['actual']:>1} | "
            report += f"${trade['profit']:>8,.2f} | ${trade['capital_after']:>10,.2f}\n"
        
        return report
    
    def export_trades_to_csv(self, filename: str):
        """
        導出交易記錄為 CSV
        """
        if not self.trades:
            print("❌ 無交易數據可導出")
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.trades[0].keys())
                writer.writeheader()
                writer.writerows(self.trades)
            print(f"✅ 交易記錄已導出: {filename}")
        except Exception as e:
            print(f"❌ 導出失敗: {e}")
    
    def export_trades_to_json(self, filename: str):
        """
        導出交易記錄為 JSON
        """
        if not self.trades:
            print("❌ 無交易數據可導出")
            return
        
        try:
            data = {
                'metadata': {
                    'start_capital': self.start_capital,
                    'final_capital': self.current_capital,
                    'total_trades': len(self.trades),
                    'generated_at': datetime.now().isoformat()
                },
                'statistics': self.get_statistics(),
                'trades': self.trades
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✅ 交易記錄已導出: {filename}")
        except Exception as e:
            print(f"❌ 導出失敗: {e}")
    
    def reset(self):
        """
        重置回測引擎
        """
        self.current_capital = self.start_capital
        self.trades = []
        self.equity_curve = [self.start_capital]
        self.drawdown_history = []

# ═══════════════════════════════════════════════════════════════════════════════
# 演示和測試
# ═══════════════════════════════════════════════════════════════════════════════

def simple_predictor(history: List[Dict]) -> Tuple[str, int]:
    """
    簡單預測器 - 基於最近 5 筆交易的勝率
    """
    if len(history) < 5:
        return 'WAIT', 0
    
    recent = history[-5:]
    wins = sum(1 for t in recent if t['outcome'] == 'WIN')
    
    if wins >= 4:
        return 'B', 3  # 連勝，跟莊
    elif wins <= 1:
        return 'P', 3  # 連敗，跟閒
    else:
        return 'WAIT', 0

def run_demo():
    """
    運行回測演示
    """
    print("\n═════════════════════════════════════════════════\n")
    print("🎰 Baccarat-Pro 回測演示\n")
    
    # 生成模擬遊戲數據
    import random
    random.seed(42)
    
    games = [
        {'result': random.choice(['B', 'P'])}
        for _ in range(200)
    ]
    
    # 創建回測引擎
    engine = BacktestEngine(start_capital=1000)
    
    # 運行回測
    print("⏳ 正在運行回測...")
    engine.run_backtest(games, simple_predictor)
    
    # 輸出報告
    print("\n" + engine.generate_summary_report())
    print("\n" + engine.generate_full_report())
    
    # 導出數據
    engine.export_trades_to_csv('backtest_results.csv')
    engine.export_trades_to_json('backtest_results.json')
    
    print("\n═════════════════════════════════════════════════\n")

if __name__ == '__main__':
    run_demo()
