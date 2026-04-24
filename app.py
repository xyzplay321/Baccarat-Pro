from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

class BaccaratPro:
    def __init__(self, num_decks=8):
        self.num_decks = num_decks
        # EOR (精確牌效應矩陣)：某張牌被抽走後，對莊家勝率的影響 (%)
        self.EOR_B = {0: 0.03, 1: -0.08, 2: -0.11, 3: -0.16, 4: -0.29, 5: -0.18, 6: 0.20, 7: 0.13, 8: 0.21, 9: 0.13}
        self.reset_game()

    def reset_game(self):
        self.counts = {i: 4 * self.num_decks if i != 0 else 16 * self.num_decks for i in range(10)}
        self.initial_counts = self.counts.copy()
        self.total_cards = 52 * self.num_decks
        self.round_num = 1
        self.history = []     
        self.raw_road = []    
        self.big_road = []    
        self.is_blind_mode = False 
        self.session_streak = 0 
        self.current_bet_target = None
        self.history_log = [] # 儲存給前端顯示的詳細歷史
        
    def _add_to_big_road(self, res):
        if res not in ['B', 'P']: return
        if not self.big_road or self.big_road[-1][0] != res: self.big_road.append([res])
        else: self.big_road[-1].append(res)

    def get_volatility(self):
        """波動率過濾器：計算最近 15 局的震盪程度"""
        if len(self.raw_road) < 10: return "數據不足", 1.0 # 權重係數 1.0
        recent = [r for r in self.raw_road if r in ['B', 'P']][-15:]
        if len(recent) < 5: return "數據不足", 1.0
        switches = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i-1])
        chop_rate = switches / (len(recent) - 1)
        if chop_rate > 0.6: return "🔴 高波動 (震盪盤)", 0.5  # 削弱圖形權重
        elif chop_rate < 0.4: return "🟢 低波動 (趨勢盤)", 1.5 # 放大圖形權重
        return "🟡 中等波動", 1.0

    def detect_all_patterns(self, vol_multiplier):
        """全圖形掃描器 (加入波動率乘數)"""
        if len(self.big_road) < 4: return None, 0, "🔍 掃描中..."
        lens = [len(col) for col in self.big_road[-6:]]
        cur_side = self.big_road[-1][0]
        opp_side = 'P' if cur_side == 'B' else 'B'
        tw = {'B': '莊', 'P': '閒'}
        
        # 基礎權重乘上波動率係數 (震盪盤降低追路意願)
        if lens[-1] >= 4: return cur_side, 15 * vol_multiplier, f"🐉 {tw[cur_side]}長龍"
        if all(l == 1 for l in lens[-4:]): return opp_side, 12 * vol_multiplier, "⚡ 單跳成路"
        if lens[-4:] == [2, 2, 2, 1]: return cur_side, 10 * vol_multiplier, "✌️ 雙跳補齊"
        if lens[-4:] == [1, 2, 1, 1]: return cur_side, 8 * vol_multiplier, "🏠 一廳兩房"
        return None, 0, "⚪ 無明顯圖形"

    def calculate_kelly_units(self, p_win, is_banker):
        """凱利公式計算建議注碼單位 (1 單位 = 1% 本金)"""
        p = p_win / 100
        q = 1 - p
        b = 0.95 if is_banker else 1.0 # 莊家賠率 0.95，閒家 1.0
        f = (b * p - q) / b
        if f <= 0: return 0
        units = round(f * 100, 1)
        return min(units, 10) # 設定單局最高押注上限為 10 單位 (10%)

    def check_side_bets(self, true_count_shift):
        """高賠率邊注捕捉器 (偵測和局漏洞)"""
        # 簡單推算：0點牌大量消耗，且8/9點剩餘多時，和局機率極高
        zeros_removed = self.initial_counts[0] - self.counts[0]
        if zeros_removed > (16 * self.num_decks * 0.5) and self.total_cards < 100:
            return "🚨 高能預警：和局 EV 轉正，建議防守打【和】"
        return ""

    def process_exact_cards(self, cards_str):
        vals = [int(d) for d in cards_str]
        if len(vals) == 4: p_cards, b_cards = vals[:2], vals[2:]
        elif len(vals) == 6: p_cards, b_cards = vals[:3], vals[3:]
        elif len(vals) == 5:
            if (vals[0]+vals[1])%10 <= 5: p_cards, b_cards = vals[:3], vals[3:]
            else: p_cards, b_cards = vals[:2], vals[2:]
        else: return False
        
        p_s, b_s = sum(p_cards)%10, sum(b_cards)%10
        res = 'P' if p_s > b_s else 'B' if b_s > p_s else 'T'
        
        if res != 'T' and self.current_bet_target:
            self.session_streak += 1 if self.current_bet_target == res else -1 if self.session_streak <= 0 else -(self.session_streak + 1)
                
        backup_counts = self.counts.copy()
        for d in cards_str:
            if self.counts[int(d)] > 0: self.counts[int(d)] -= 1
            self.total_cards -= 1
            
        self.history.append(('EXACT', cards_str, res, backup_counts, self.is_blind_mode, self.session_streak))
        self.raw_road.append(res); self._add_to_big_road(res)
        
        log_text = f"局數 {self.round_num}: 閒 {p_s} - 莊 {b_s} ({'莊贏' if res=='B' else '閒贏' if res=='P' else '和局'})"
        self.history_log.insert(0, log_text)
        self.history_log = self.history_log[:5] # 只保留最新 5 筆
        
        self.round_num += 1; self.is_blind_mode = False
        return True

    def process_blind_shortcut(self, cmd):
        res = cmd.upper()
        if res != 'T' and self.current_bet_target:
            self.session_streak += 1 if self.current_bet_target == res else -1 if self.session_streak <= 0 else -(self.session_streak + 1)
        
        self.history.append(('BLIND', res, res, self.counts.copy(), self.is_blind_mode, self.session_streak))
        self.raw_road.append(res); self._add_to_big_road(res)
        
        self.history_log.insert(0, f"局數 {self.round_num}: 快捷錄入 -> {'莊贏' if res=='B' else '閒贏' if res=='P' else '和局'}")
        self.history_log = self.history_log[:5]
        
        self.round_num += 1; self.is_blind_mode = True
        return True

    def undo(self):
        if not self.history: return False
        h = self.history.pop()
        self.counts, self.is_blind_mode, self.session_streak = h[3], h[4], h[5]
        self.raw_road.pop(); self.big_road = []
        for r in self.raw_road: self._add_to_big_road(r)
        if self.history_log: self.history_log.pop(0)
        self.round_num -= 1; return True

game = BaccaratPro(8)

@app.route('/')
def home(): return render_template('index.html')

@app.route('/api/cmd', methods=['POST'])
def handle_command():
    cmd = request.json.get('cmd', '').upper()
    if cmd == 'R': game.reset_game()
    elif cmd == 'U': game.undo()
    elif cmd in ['B', 'P', 'T']: game.process_blind_shortcut(cmd)
    elif cmd.isdigit(): game.process_exact_cards(cmd)
            
    # 1. 計算 EOR 總偏移
    eor_shift_total = 0
    if game.total_cards > 0:
        for card, eor_val in game.EOR_B.items():
            removed = game.initial_counts[card] - game.counts[card]
            eor_shift_total += removed * eor_val
            
    # 2. 真數 (True Count) 計算
    remaining_decks = max(0.5, game.total_cards / 52.0)
    true_count_shift = eor_shift_total / remaining_decks

    # 3. 波動率過濾與圖形識別
    vol_status, vol_mult = game.get_volatility()
    pat_side, pat_weight, pat_name = game.detect_all_patterns(vol_mult)

    # 4. 綜合機率計算
    b_prob, p_prob = 50.68, 49.32
    b_prob += true_count_shift
    p_prob -= true_count_shift
    if pat_side == 'B': b_prob += pat_weight
    elif pat_side == 'P': p_prob += pat_weight
    
    total = b_prob + p_prob
    b_pct, p_pct = round((b_prob/total)*100, 1), round((p_prob/total)*100, 1)

    # 5. 決策與凱利注碼
    game.current_bet_target = None
    advice = "⚪ 局勢膠著，建議【觀望】"
    units = 0
    
    # 動態門檻：牌越少，信心越高，門檻越低
    threshold = 55.0 if remaining_decks > 4 else 53.0 if remaining_decks > 2 else 51.5

    if b_pct >= threshold:
        game.current_bet_target = 'B'
        units = game.calculate_kelly_units(b_pct, True)
        advice = f"🔥 訊號成立！押【莊】"
    elif p_pct >= threshold:
        game.current_bet_target = 'P'
        units = game.calculate_kelly_units(p_pct, False)
        advice = f"🔥 訊號成立！押【閒】"

    side_bet_alert = game.check_side_bets(true_count_shift)
    streak_text = f"🔥 {game.session_streak} 連勝" if game.session_streak > 0 else f"🧊 {abs(game.session_streak)} 連敗" if game.session_streak < 0 else "---"

    return jsonify({
        "round": game.round_num,
        "streak": streak_text,
        "advice": advice,
        "units": f"{units} 單位" if units > 0 else "0 單位 (空手)",
        "b_prob": f"{b_pct}%",
        "p_prob": f"{p_pct}%",
        "pattern": pat_name,
        "volatility": vol_status,
        "side_alert": side_bet_alert,
        "history": game.history_log,
        "big_road": game.big_road[-12:] # 傳送最後 12 列畫大路圖
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
