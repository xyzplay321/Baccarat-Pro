from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

class BaccaratPro:
    def __init__(self, num_decks=8):
        self.num_decks = num_decks
        # EOR 精確權重
        self.EOR_B = {0: 0.03, 1: -0.08, 2: -0.11, 3: -0.16, 4: -0.29, 5: -0.18, 6: 0.20, 7: 0.13, 8: 0.21, 9: 0.13}
        
        # 系統狀態設定
        self.input_mode = 'TWO_STAGE'
        self.bet_strategy = 'CONSERVATIVE' # CONSERVATIVE, AGGRESSIVE, HYPER
        
        # 🟢 新增：各維度連勝負追蹤計數器
        self.math_streak = 0 # 數學引擎連勝負
        self.road_streaks = {'大眼仔路': 0, '小路趨勢': 0, '蟑螂路': 0} # 下三路各自的預測連勝負
        
        # 🟢 紀錄「前一局」的預測，用來對獎
        self.last_math_pred = None
        self.last_road_preds = {}

        self.reset_game()

    def reset_game(self):
        self.counts = {i: 4 * self.num_decks if i != 0 else 16 * self.num_decks for i in range(10)}
        self.initial_counts = self.counts.copy()
        self.total_cards = 52 * self.num_decks
        self.round_num = 1
        self.history = []     
        self.raw_road = []    
        self.big_road = []    
        self.session_streak = 0 # 總策略連勝負
        self.current_bet_target = None
        self.history_log = [] 
        self.pending_stage = False
        self.pending_vals = []
        self.pending_text = ""
        self.math_streak = 0
        self.road_streaks = {'大眼仔路': 0, '小路趨勢': 0, '蟑螂路': 0}

    def _add_to_big_road(self, res):
        if res not in ['B', 'P']: return
        if not self.big_road or self.big_road[-1][0] != res: self.big_road.append([res])
        else: self.big_road[-1].append(res)

    def calculate_kelly_units(self, p_win, is_banker):
        p = p_win / 100
        q = 1 - p
        b = 0.95 if is_banker else 1.0
        f = (b * p - q) / b
        if f <= 0: return 0
        units = round(f * 100, 1)
        # 🟢 策略上限：極進取開放到 30% 重倉
        if self.bet_strategy == 'HYPER': max_limit = 30
        elif self.bet_strategy == 'AGGRESSIVE': max_limit = 15
        else: max_limit = 5
        return min(units, max_limit)

    def _simulate_derived_road(self, board, k, guess):
        temp_br = [col[:] for col in board]
        if not temp_br or temp_br[-1][0] != guess: temp_br.append([guess])
        else: temp_br[-1].append(guess)
        C = len(temp_br) - 1 
        if C <= k: return None 
        R = len(temp_br[C]) - 1 
        if R > 0: return len(temp_br[C-k]) >= R
        else: return len(temp_br[C-1]) == len(temp_br[C-(k+1)])

    def _update_streaks(self, res):
        """🟢 每局結算後，更新所有維度的連勝負狀態"""
        if res == 'T': return # 和局不影響連勝負

        # 1. 更新總策略連勝
        if self.current_bet_target:
            if self.current_bet_target == res:
                self.session_streak = self.session_streak + 1 if self.session_streak >= 0 else 1
            else:
                self.session_streak = self.session_streak - 1 if self.session_streak <= 0 else -1
        
        # 2. 更新數學引擎連勝 (以 true_count_shift > 0 為莊)
        if self.last_math_pred:
            if self.last_math_pred == res:
                self.math_streak = self.math_streak + 1 if self.math_streak >= 0 else 1
            else:
                self.math_streak = self.math_streak - 1 if self.math_streak <= 0 else -1

        # 3. 更新下三路各自連勝
        for r_name, r_pred in self.last_road_preds.items():
            if r_pred:
                if r_pred == res:
                    self.road_streaks[r_name] = self.road_streaks[r_name] + 1 if self.road_streaks[r_name] >= 0 else 1
                else:
                    self.road_streaks[r_name] = self.road_streaks[r_name] - 1 if self.road_streaks[r_name] <= 0 else -1

    def _finalize_exact_cards(self, vals):
        p_cards, b_cards = [vals[0], vals[1]], [vals[2], vals[3]]
        p_score, b_score = sum(p_cards) % 10, sum(b_cards) % 10
        idx = 4
        if p_score < 8 and b_score < 8:
            p_drew = False
            p3 = -1
            if p_score <= 5:
                if idx < len(vals): p3 = vals[idx]; p_cards.append(p3); idx += 1; p_drew = True
            b_draw = False
            if not p_drew:
                if b_score <= 5: b_draw = True
            else:
                if b_score <= 2: b_draw = True
                elif b_score == 3 and p3 != 8: b_draw = True
                elif b_score == 4 and p3 in [2, 3, 4, 5, 6, 7]: b_draw = True
                elif b_score == 5 and p3 in [4, 5, 6, 7]: b_draw = True
                elif b_score == 6 and p3 in [6, 7]: b_draw = True
            if b_draw and idx < len(vals):
                b_cards.append(vals[idx]); idx += 1

        used_cards = vals[:idx]
        valid_cards_str = "".join(map(str, used_cards))
        final_p, final_b = sum(p_cards) % 10, sum(b_cards) % 10
        res = 'P' if final_p > final_b else 'B' if final_b > final_p else 'T'
        
        self._update_streaks(res) # 🟢 結算
                
        backup_counts = self.counts.copy()
        for val in used_cards:
            if self.counts[val] > 0: self.counts[val] -= 1; self.total_cards -= 1
                
        self.history.append(('EXACT', valid_cards_str, res, backup_counts, self.session_streak, self.math_streak, self.road_streaks.copy()))
        self.raw_road.append(res); self._add_to_big_road(res)
        
        self.history_log.insert(0, f"輸入 [{valid_cards_str}] -> 閒 {final_p} vs 莊 {final_b} ({'莊贏' if res=='B' else '閒贏' if res=='P' else '和局'})")
        self.round_num += 1
        return True

    def process_direct_cards(self, cards_str):
        vals = [int(d) for d in cards_str]
        if len(vals) == 4: p_cards, b_cards = vals[:2], vals[2:]
        elif len(vals) == 6: p_cards, b_cards = vals[:3], vals[3:]
        elif len(vals) == 5:
            if sum(vals[:2]) % 10 <= 5: p_cards, b_cards = vals[:3], vals[3:]
            else: p_cards, b_cards = vals[:2], vals[2:]
        else: return False
        
        res = 'P' if (sum(p_cards)%10) > (sum(b_cards)%10) else 'B' if (sum(b_cards)%10) > (sum(p_cards)%10) else 'T'
        self._update_streaks(res)
        
        backup_counts = self.counts.copy()
        for val in vals:
            if self.counts[val] > 0: self.counts[val] -= 1; self.total_cards -= 1
        self.history.append(('EXACT', "".join(map(str, vals)), res, backup_counts, self.session_streak, self.math_streak, self.road_streaks.copy()))
        self.raw_road.append(res); self._add_to_big_road(res)
        self.history_log.insert(0, f"直錄 [{cards_str}] -> 局數 {self.round_num} 結算")
        self.round_num += 1
        return True

    def process_blind_shortcut(self, cmd):
        res = cmd.upper()
        self._update_streaks(res)
        self.history.append(('BLIND', res, res, self.counts.copy(), self.session_streak, self.math_streak, self.road_streaks.copy()))
        self.raw_road.append(res); self._add_to_big_road(res)
        self.history_log.insert(0, f"快捷鍵 [{res}] -> 局數 {self.round_num} 結算")
        self.round_num += 1
        return True

    def undo(self):
        if self.pending_stage:
            self.pending_stage, self.pending_vals = False, []
            return True
        if not self.history: return False
        h = self.history.pop()
        self.counts, self.session_streak, self.math_streak, self.road_streaks = h[3], h[4], h[5], h[6]
        self.raw_road.pop(); self.big_road = []
        for r in self.raw_road: self._add_to_big_road(r)
        if self.history_log: self.history_log.pop(0)
        self.round_num -= 1; return True

game = BaccaratPro(8)

@app.route('/')
def home(): return render_template('index.html')

@app.route('/api/cmd', methods=['POST'])
def handle_command():
    cmd = request.json.get('cmd', '').upper().strip()
    
    if cmd == 'R': game.reset_game()
    elif cmd == 'U': game.undo()
    elif cmd == 'M': 
        game.input_mode = 'DIRECT' if game.input_mode == 'TWO_STAGE' else 'TWO_STAGE'
    elif cmd == 'S': 
        # 🟢 循環切換：保守 -> 積極 -> 極進取
        if game.bet_strategy == 'CONSERVATIVE': game.bet_strategy = 'AGGRESSIVE'
        elif game.bet_strategy == 'AGGRESSIVE': game.bet_strategy = 'HYPER'
        else: game.bet_strategy = 'CONSERVATIVE'

    elif cmd in ['B', 'P', 'T']:
        if game.pending_stage: game.pending_stage, game.pending_vals = False, []
        game.process_blind_shortcut(cmd)
    elif cmd.isdigit():
        if game.input_mode == 'DIRECT': game.process_direct_cards(cmd)
        else: game.process_exact_cards(cmd) if not game.pending_stage else game.process_exact_cards(cmd)

    # 量化計算
    eor_shift_total = 0
    if game.total_cards > 0:
        for card, eor_val in game.EOR_B.items():
            removed = game.initial_counts[card] - game.counts[card]
            eor_shift_total += removed * eor_val
            
    remaining_decks = max(0.5, game.total_cards / 52.0)
    true_count_shift = eor_shift_total / remaining_decks

    # 🟢 儲存數學預測給下一把對獎
    game.last_math_pred = 'B' if true_count_shift > 0 else 'P' if true_count_shift < 0 else None

    # 排版與決策
    b_pct, p_pct = 50.68 + true_count_shift, 49.32 - true_count_shift
    
    # 🟢 策略門檻調整
    if game.bet_strategy == 'HYPER':
        threshold = 50.001 # 只要勝率高就下注
    elif game.bet_strategy == 'AGGRESSIVE':
        threshold = 51.5 if remaining_decks > 2 else 50.8
    else:
        threshold = 55.0 if remaining_decks > 4 else 53.0
        
    game.current_bet_target = None
    advice = "⚪ 局勢膠著，建議【觀望】"
    units = 0
    
    if b_pct >= threshold:
        game.current_bet_target = 'B'; advice = f"🔥 系統推【莊】"; units = game.calculate_kelly_units(b_pct, True)
    elif p_pct >= threshold:
        game.current_bet_target = 'P'; advice = f"🔥 系統推【閒】"; units = game.calculate_kelly_units(p_pct, False)

    # 組合連勝負文字
    def fmt_st(st):
        if st > 0: return f" [🔥連勝:{st}]"
        if st < 0: return f" [🧊連敗:{abs(st)}]"
        return " [---]"

    lines = []
    lines.append("=========================================================")
    lines.append(f"【 第 {game.round_num} 局 】 | 🛡️策略:{'極進取' if game.bet_strategy=='HYPER' else '積極' if game.bet_strategy=='AGGRESSIVE' else '保守'} | ⌨️模式:{'直錄' if game.input_mode=='DIRECT' else '兩段'}")
    lines.append("---------------------------------------------------------")
    lines.append(f"🎯 系統策略: {advice} ({units} 單位){fmt_st(game.session_streak)}")
    lines.append("---------------------------------------------------------")
    
    lines.append(f"📊 [牌庫優勢分析]{fmt_st(game.math_streak)}")
    lines.append(f"   機率偏移: 莊 {true_count_shift:+.3f}% | 閒 {-true_count_shift:+.3f}%")
    lines.append(f"   💡 數學訊號: {'🔴 莊' if true_count_shift>0 else '🔵 閒' if true_count_shift<0 else '⚪ 平衡'}")
    lines.append("---------------------------------------------------------")
    
    lines.append("🛣️ [下三路順勢指引]")
    game.last_road_preds = {} # 清空重計預測
    roads_cfg = {'大眼仔路': 1, '小路趨勢': 2, '蟑螂路　': 3}
    for name, k in roads_cfg.items():
        b_red = game._simulate_derived_road(game.big_road, k, 'B')
        p_red = game._simulate_derived_road(game.big_road, k, 'P')
        pred = 'B' if b_red is True else 'P' if p_red is True else None
        game.last_road_preds[name] = pred
        
        v_str = f"👉 {'🔴 莊' if pred=='B' else '🔵 閒' if pred=='P' else '⏳ 等待'}"
        is_stable = game._simulate_derived_road(game.big_road[:-1], k, game.raw_road[-1]) if game.raw_road else True
        lines.append(f"   {name}：{v_str.ljust(10)} | 📝 路況: {'✅ 平穩' if is_stable else '⚠️ 波動'}{fmt_st(game.road_streaks[name])}")

    lines.append("---------------------------------------------------------")
    last_act = game.pending_text if game.pending_stage else (game.history_log[0] if game.history_log else "等待指令...")
    lines.append(f"⏳ 動態: {last_act}")
    lines.append("=========================================================")

    return jsonify({"terminal_text": "\n".join(lines)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
