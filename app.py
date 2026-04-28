from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

class BaccaratPro:
    def __init__(self, num_decks=8):
        self.num_decks = num_decks
        self.EOR_B = {0: 0.03, 1: -0.08, 2: -0.11, 3: -0.16, 4: -0.29, 5: -0.18, 6: 0.20, 7: 0.13, 8: 0.21, 9: 0.13}
        
        self.input_mode = 'TWO_STAGE'
        self.bet_strategy = 'CONSERVATIVE' 
        
        self.reset_game()

    def reset_game(self):
        self.counts = {i: 4 * self.num_decks if i != 0 else 16 * self.num_decks for i in range(10)}
        self.initial_counts = self.counts.copy()
        self.total_cards = 52 * self.num_decks
        self.round_num = 1
        self.history = []     
        self.raw_road = []    
        self.big_road = []    
        
        self.session_streak = 0 
        self.session_wl = {'W': 0, 'L': 0}
        
        self.math_streak = 0
        self.math_wl = {'W': 0, 'L': 0}
        
        self.road_streaks = {'大眼仔路': 0, '小路趨勢': 0, '蟑螂路': 0}
        self.road_wl = {'大眼仔路': {'W': 0, 'L': 0}, '小路趨勢': {'W': 0, 'L': 0}, '蟑螂路': {'W': 0, 'L': 0}}
        
        self.current_bet_target = None
        self.last_math_pred = None
        self.last_road_preds = {}
        
        self.history_log = [] 
        self.pending_stage = False
        self.pending_vals = []
        self.pending_text = ""

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
        if R > 0: 
            comp_len = len(temp_br[C-k])
            if R < comp_len: return True       
            elif R == comp_len: return False      
            else: return True       
        else: 
            return len(temp_br[C-1]) == len(temp_br[C-(k+1)])

    def _update_streaks_and_wl(self, res):
        if res == 'T': return 
        
        # 🟢 如果系統有給出押注目標，結算勝負
        if self.current_bet_target:
            if self.current_bet_target == res:
                self.session_streak = self.session_streak + 1 if self.session_streak >= 0 else 1
                self.session_wl['W'] += 1
            else:
                self.session_streak = self.session_streak - 1 if self.session_streak <= 0 else -1
                self.session_wl['L'] += 1
        
        if self.last_math_pred:
            if self.last_math_pred == res:
                self.math_streak = self.math_streak + 1 if self.math_streak >= 0 else 1
                self.math_wl['W'] += 1
            else:
                self.math_streak = self.math_streak - 1 if self.math_streak <= 0 else -1
                self.math_wl['L'] += 1

        for r_name, r_pred in self.last_road_preds.items():
            if r_pred:
                if r_pred == res:
                    self.road_streaks[r_name] = self.road_streaks[r_name] + 1 if self.road_streaks[r_name] >= 0 else 1
                    self.road_wl[r_name]['W'] += 1
                else:
                    self.road_streaks[r_name] = self.road_streaks[r_name] - 1 if self.road_streaks[r_name] <= 0 else -1
                    self.road_wl[r_name]['L'] += 1

    def _pack_state(self):
        return {
            's_st': self.session_streak, 'm_st': self.math_streak, 'r_st': self.road_streaks.copy(),
            's_wl': self.session_wl.copy(), 'm_wl': self.math_wl.copy(), 
            'r_wl': {k: v.copy() for k, v in self.road_wl.items()},
            'c_tgt': self.current_bet_target # 備份目標
        }

    def _unpack_state(self, state):
        self.session_streak, self.math_streak = state['s_st'], state['m_st']
        self.road_streaks, self.session_wl = state['r_st'], state['s_wl']
        self.math_wl, self.road_wl = state['m_wl'], state['r_wl']
        self.current_bet_target = state.get('c_tgt')

    def _apply_cards_to_game(self, p_cards, b_cards, used_cards):
        valid_cards_str = "".join(map(str, used_cards))
        final_p, final_b = sum(p_cards) % 10, sum(b_cards) % 10
        res = 'P' if final_p > final_b else 'B' if final_b > final_p else 'T'
        
        self._update_streaks_and_wl(res) 
                
        backup_counts = self.counts.copy()
        for val in used_cards:
            if self.counts[val] > 0: self.counts[val] -= 1; self.total_cards -= 1
                
        self.history.append(('EXACT', valid_cards_str, res, backup_counts, self._pack_state()))
        self.raw_road.append(res); self._add_to_big_road(res)
        
        p_str, b_str = "+".join(map(str, p_cards)), "+".join(map(str, b_cards))
        self.history_log.insert(0, f"局數 {self.round_num}: 閒({p_str}={final_p}) 莊({b_str}={final_b}) -> {'莊贏' if res=='B' else '閒贏' if res=='P' else '和局'}")
        self.history_log = self.history_log[:5]
        self.round_num += 1
        return True

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
        return self._apply_cards_to_game(p_cards, b_cards, used_cards)

    def process_direct_cards(self, cards_str):
        vals = [int(d) for d in cards_str]
        if len(vals) == 4: p_cards, b_cards = vals[:2], vals[2:]
        elif len(vals) == 6: p_cards, b_cards = vals[:3], vals[3:]
        elif len(vals) == 5:
            if sum(vals[:2]) % 10 <= 5: p_cards, b_cards = vals[:3], vals[3:]
            else: p_cards, b_cards = vals[:2], vals[2:]
        else: return False
        return self._apply_cards_to_game(p_cards, b_cards, vals)

    def process_exact_cards(self, cards_str):
        vals = [int(d) for d in cards_str]
        if self.pending_stage:
            full_vals = self.pending_vals + vals
            self.pending_stage, self.pending_vals = False, []
            return self._finalize_exact_cards(full_vals)
        if len(vals) == 4:
            p_score, b_score = sum(vals[:2]) % 10, sum(vals[2:4]) % 10
            if p_score >= 8 or b_score >= 8: return self._finalize_exact_cards(vals)
            p_draw = p_score <= 5
            b_draw = b_score <= 5 if not p_draw else True
            if p_draw or b_draw:
                self.pending_stage, self.pending_vals = True, vals
                self.pending_text = f"⏳ 閒({p_score}點) 莊({b_score}點) ➔ 等待補牌"
                return "PENDING"
            else: return self._finalize_exact_cards(vals)
        elif len(vals) > 4: return self._finalize_exact_cards(vals)
        return False

    def process_blind_shortcut(self, cmd):
        res = cmd.upper()
        self._update_streaks_and_wl(res)
        self.history.append(('BLIND', res, res, self.counts.copy(), self._pack_state()))
        self.raw_road.append(res); self._add_to_big_road(res)
        self.history_log.insert(0, f"快捷鍵 [{res}] -> 局數 {self.round_num} 結算")
        self.history_log = self.history_log[:5]
        self.round_num += 1
        return True

    def undo(self):
        if self.pending_stage:
            self.pending_stage, self.pending_vals = False, []
            return True
        if not self.history: return False
        h = self.history.pop()
        self.counts = h[3]
        self._unpack_state(h[4]) 
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
        if game.bet_strategy == 'CONSERVATIVE': game.bet_strategy = 'AGGRESSIVE'
        elif game.bet_strategy == 'AGGRESSIVE': game.bet_strategy = 'HYPER'
        else: game.bet_strategy = 'CONSERVATIVE'

    elif cmd in ['B', 'P', 'T']:
        if game.pending_stage: game.pending_stage, game.pending_vals = False, []
        game.process_blind_shortcut(cmd)
    elif cmd.isdigit():
        if game.input_mode == 'DIRECT': game.process_direct_cards(cmd)
        else: game.process_exact_cards(cmd) if not game.pending_stage else game.process_exact_cards(cmd)

    game.last_road_preds = {} 
    roads_cfg = {'大眼仔路': 1, '小路趨勢': 2, '蟑螂路': 3} 
    v_b = v_p = 0
    for name, k in roads_cfg.items():
        b_red = game._simulate_derived_road(game.big_road, k, 'B')
        p_red = game._simulate_derived_road(game.big_road, k, 'P')
        pred = 'B' if b_red is True else 'P' if p_red is True else None
        game.last_road_preds[name] = pred
        if pred == 'B': v_b += 1
        elif pred == 'P': v_p += 1
        
    road_target = 'B' if v_b > v_p else 'P' if v_p > v_b else None

    eor_shift_total = 0
    if game.total_cards > 0:
        for card, eor_val in game.EOR_B.items():
            removed = game.initial_counts[card] - game.counts[card]
            eor_shift_total += removed * eor_val
            
    remaining_decks = max(0.5, game.total_cards / 52.0)
    true_count_shift = eor_shift_total / remaining_decks

    game.last_math_pred = 'B' if true_count_shift > 0 else 'P' if true_count_shift < 0 else None
    b_pct, p_pct = 50.68 + true_count_shift, 49.32 - true_count_shift
    
    # 🟢 修正：改用「增幅 (Margin)」來做為門檻判斷，避免因基礎勝率不同而偏袒莊家
    if game.bet_strategy == 'HYPER': margin = 0.001 
    elif game.bet_strategy == 'AGGRESSIVE': margin = 0.8 if remaining_decks > 2 else 0.1
    else: margin = 4.32 if remaining_decks > 4 else 2.32
    
    b_threshold = 50.68 + margin
    p_threshold = 49.32 + margin
        
    new_target = None
    advice = "⚪ 局勢膠著，建議【觀望】"
    units = 0
    
    # 🟢 修正：先確認偏移方向，再確認是否達到門檻
    math_target = None
    if true_count_shift > 0 and b_pct >= b_threshold:
        math_target = 'B'
    elif true_count_shift < 0 and p_pct >= p_threshold:
        math_target = 'P'

    if game.pending_stage:
        advice = game.pending_text # 若在等待補牌，只更改顯示文字，不去動核心的目標記憶
    elif math_target:
        if math_target == road_target: 
            new_target = math_target
            advice = f"🔥 共振確認！強推【{'莊' if math_target=='B' else '閒'}】"
            units = game.calculate_kelly_units(b_pct if math_target=='B' else p_pct, math_target=='B')
        else:
            r_name = '莊' if road_target == 'B' else '閒' if road_target == 'P' else '無'
            m_name = '莊' if math_target == 'B' else '閒'
            advice = f"🛑 訊號衝突 (數學推{m_name} vs 路單推{r_name})，強制【觀望】"

    # 🟢 修正：只有在「非等待階段」時，才允許把算出來的新方向，寫入系統的記憶體中
    if not game.pending_stage:
        game.current_bet_target = new_target

    def fmt_st_wl(st, wl):
        w, l = wl['W'], wl['L']
        total = w + l
        rate = int((w / total) * 100) if total > 0 else 0
        icon = f"🔥{st}連勝" if st > 0 else f"🧊{abs(st)}連敗" if st < 0 else "---"
        if total == 0: return f" [{icon}]"
        return f" [{icon} | {w}勝-{l}敗 ({rate}%)]"

    lines = []
    lines.append("=========================================================")
    lines.append(f"【 第 {game.round_num} 局 】 | 🛡️策略:{'極進取' if game.bet_strategy=='HYPER' else '積極' if game.bet_strategy=='AGGRESSIVE' else '保守'} | ⌨️模式:{'直錄' if game.input_mode=='DIRECT' else '兩段'}")
    lines.append("---------------------------------------------------------")
    lines.append(f"🎯 系統策略: {advice} ({units} 單位){fmt_st_wl(game.session_streak, game.session_wl)}")
    lines.append("---------------------------------------------------------")
    
    lines.append(f"📊 [牌庫優勢分析]{fmt_st_wl(game.math_streak, game.math_wl)}")
    lines.append(f"   機率偏移: 莊 {true_count_shift:+.3f}% | 閒 {-true_count_shift:+.3f}%")
    lines.append(f"   💡 數學訊號: {'🔴 莊' if true_count_shift>0 else '🔵 閒' if true_count_shift<0 else '⚪ 平衡'}")
    lines.append("---------------------------------------------------------")
    
    lines.append("🛣️ [下三路順勢指引]")
    for name, k in roads_cfg.items():
        pred = game.last_road_preds[name]
        v_str = f"👉 {'🔴 莊' if pred=='B' else '🔵 閒' if pred=='P' else '⏳ 等待'}"
        is_stable = game._simulate_derived_road(game.big_road[:-1], k, game.raw_road[-1]) if game.raw_road else True
        
        display_name = "蟑螂路　" if name == '蟑螂路' else name 
        wl_info = fmt_st_wl(game.road_streaks[name], game.road_wl[name])
        lines.append(f"   {display_name}：{v_str.ljust(10)} | 📝 路況: {'✅ 平穩' if is_stable else '⚠️ 波動'}{wl_info}")

    lines.append("---------------------------------------------------------")
    last_act = game.pending_text if game.pending_stage else (game.history_log[0] if game.history_log else "等待指令...")
    lines.append(f"⏳ 動態: {last_act}")
    lines.append("=========================================================")

    return jsonify({"terminal_text": "\n".join(lines)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
