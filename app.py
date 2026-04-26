from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

class BaccaratPro:
    def __init__(self, num_decks=8):
        self.num_decks = num_decks
        self.EOR_B = {0: 0.03, 1: -0.08, 2: -0.11, 3: -0.16, 4: -0.29, 5: -0.18, 6: 0.20, 7: 0.13, 8: 0.21, 9: 0.13}
        
        # 🟢 新增：系統全域設定 (預設兩段式、預設保守策略)
        self.input_mode = 'TWO_STAGE' # 可選 'TWO_STAGE' (兩段式) 或 'DIRECT' (直錄式)
        self.bet_strategy = 'CONSERVATIVE' # 可選 'CONSERVATIVE' (保守) 或 'AGGRESSIVE' (積極)
        
        self.reset_game()

    def reset_game(self):
        # 初始化牌庫與狀態 (保留設定值)
        self.counts = {i: 4 * self.num_decks if i != 0 else 16 * self.num_decks for i in range(10)}
        self.initial_counts = self.counts.copy()
        self.total_cards = 52 * self.num_decks
        self.round_num = 1
        self.history = []     
        self.raw_road = []    
        self.big_road = []    
        self.session_streak = 0 
        self.current_bet_target = None
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
        # 🟢 新增：依據策略決定單把押注上限
        max_limit = 20 if self.bet_strategy == 'AGGRESSIVE' else 5 
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

    # 【兩段式專用結算】 (模擬荷官補牌)
    def _finalize_exact_cards(self, vals):
        p_cards, b_cards = [vals[0], vals[1]], [vals[2], vals[3]]
        p_score, b_score = sum(p_cards) % 10, sum(b_cards) % 10
        idx = 4
        if p_score < 8 and b_score < 8:
            p_drew = False
            p3 = -1
            if p_score <= 5:
                if idx < len(vals):
                    p3 = vals[idx]; p_cards.append(p3); idx += 1; p_drew = True
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

    # 🟢 新增：【單次直錄式專用結算】 (直接指定閒與莊的牌，不跑補牌判斷，適合補局數)
    def process_direct_cards(self, cards_str):
        vals = [int(d) for d in cards_str]
        # 根據輸入長度，精準切割閒與莊的牌
        if len(vals) == 4: p_cards, b_cards = vals[:2], vals[2:]
        elif len(vals) == 6: p_cards, b_cards = vals[:3], vals[3:]
        elif len(vals) == 5:
            # 百家樂定律：若閒前兩張 <= 5，閒必補第3張。依此反推這 5 張牌是誰的。
            if sum(vals[:2]) % 10 <= 5: p_cards, b_cards = vals[:3], vals[3:]
            else: p_cards, b_cards = vals[:2], vals[2:]
        else: return False
        
        return self._apply_cards_to_game(p_cards, b_cards, vals)

    # 共用的資料更新模組
    def _apply_cards_to_game(self, p_cards, b_cards, used_cards):
        valid_cards_str = "".join(map(str, used_cards))
        final_p, final_b = sum(p_cards) % 10, sum(b_cards) % 10
        res = 'P' if final_p > final_b else 'B' if final_b > final_p else 'T'
        
        if res != 'T' and self.current_bet_target:
            self.session_streak += 1 if self.current_bet_target == res else -1 if self.session_streak <= 0 else -(self.session_streak + 1)
                
        backup_counts = self.counts.copy()
        for val in used_cards:
            if self.counts[val] > 0: self.counts[val] -= 1; self.total_cards -= 1
                
        self.history.append(('EXACT', valid_cards_str, res, backup_counts, self.session_streak))
        self.raw_road.append(res); self._add_to_big_road(res)
        
        p_str, b_str = "+".join(map(str, p_cards)), "+".join(map(str, b_cards))
        self.history_log.insert(0, f"局數 {self.round_num}: 閒({p_str}={final_p}) 莊({b_str}={final_b}) -> {'莊贏' if res=='B' else '閒贏' if res=='P' else '和局'}")
        self.history_log = self.history_log[:5]
        self.round_num += 1
        return True

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
                self.pending_text = f"⏳ 閒({p_score}點) 莊({b_score}點) ➔ 等待輸入補牌"
                return "PENDING"
            else: return self._finalize_exact_cards(vals)
        elif len(vals) > 4: return self._finalize_exact_cards(vals)
        return False

    def process_blind_shortcut(self, cmd):
        res = cmd.upper()
        if res != 'T' and self.current_bet_target:
            self.session_streak += 1 if self.current_bet_target == res else -1 if self.session_streak <= 0 else -(self.session_streak + 1)
        self.history.append(('BLIND', res, res, self.counts.copy(), self.session_streak))
        self.raw_road.append(res); self._add_to_big_road(res)
        self.history_log.insert(0, f"局數 {self.round_num}: 快捷鍵 [{res}] -> {'莊贏' if res=='B' else '閒贏' if res=='P' else '和局'}")
        self.history_log = self.history_log[:5]
        self.round_num += 1
        return True

    def undo(self):
        if self.pending_stage:
            self.pending_stage, self.pending_vals = False, []
            self.history_log.insert(0, "⏪ 取消輸入，請重打 4 張牌")
            return True
        if not self.history: return False
        h = self.history.pop()
        self.counts, self.session_streak = h[3], h[4]
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
    
    # 執行指令
    if cmd == 'R': game.reset_game()
    elif cmd == 'U': game.undo()
    elif cmd == 'M': 
        # 🟢 切換輸入模式
        game.input_mode = 'DIRECT' if game.input_mode == 'TWO_STAGE' else 'TWO_STAGE'
        if game.pending_stage: game.pending_stage, game.pending_vals = False, []
        game.history_log.insert(0, f"⚙️ 切換輸入: {'【單次直錄 (1~3閒 4~6莊)】' if game.input_mode == 'DIRECT' else '【兩段式同步發牌】'}")
        game.history_log = game.history_log[:5]
    elif cmd == 'S': 
        # 🟢 切換下注策略
        game.bet_strategy = 'AGGRESSIVE' if game.bet_strategy == 'CONSERVATIVE' else 'CONSERVATIVE'
        game.history_log.insert(0, f"⚙️ 切換策略: {'【積極 (降低門檻/放大注碼)】' if game.bet_strategy == 'AGGRESSIVE' else '【保守 (嚴格過濾/安全注碼)】'}")
        game.history_log = game.history_log[:5]
    elif cmd in ['B', 'P', 'T']:
        if game.pending_stage: game.pending_stage, game.pending_vals = False, []
        game.process_blind_shortcut(cmd)
    elif cmd.isdigit():
        # 🟢 依據模式分發輸入邏輯
        if game.input_mode == 'DIRECT':
            if len(cmd) in [4, 5, 6]: game.process_direct_cards(cmd)
            else: 
                game.history_log.insert(0, "⚠️ 直錄模式請一次輸入 4~6 個數字")
                game.history_log = game.history_log[:5]
        else:
            if game.pending_stage and len(cmd) <= 2: game.process_exact_cards(cmd)
            elif not game.pending_stage and len(cmd) >= 4: game.process_exact_cards(cmd)
            else: 
                game.history_log.insert(0, "⚠️ 第一段請輸入 4 個數字")
                game.history_log = game.history_log[:5]

    # 運算核心
    eor_shift_total = small_removed = big_removed = 0
    if game.total_cards > 0:
        for card, eor_val in game.EOR_B.items():
            removed = game.initial_counts[card] - game.counts[card]
            eor_shift_total += removed * eor_val
            if card in [1,2,3,4,5]: small_removed += removed
            if card in [6,7,8,9,0]: big_removed += removed
            
    remaining_decks = max(0.5, game.total_cards / 52.0)
    true_count_shift = eor_shift_total / remaining_decks

    # 構建終端機文字畫面
    tw = {'B': '莊', 'P': '閒', 'T': '和'}
    lines = []
    lines.append("=========================================================")
    # 🟢 標頭新增狀態顯示
    header = f"【 第 {game.round_num} 局 】"
    if game.session_streak > 0: header += f" 🔥連勝:{game.session_streak}"
    elif game.session_streak < 0: header += f" 🧊連敗:{abs(game.session_streak)}"
    header += f" | 🛡️策略:{'積極' if game.bet_strategy=='AGGRESSIVE' else '保守'} | ⌨️輸入:{'直錄' if game.input_mode=='DIRECT' else '兩段'}"
    lines.append(header)
    lines.append("---------------------------------------------------------")

    # 決策生成 (🟢 依據策略切換進場門檻)
    b_pct, p_pct = 50.68 + true_count_shift, 49.32 - true_count_shift
    
    if game.bet_strategy == 'AGGRESSIVE':
        threshold = 51.5 if remaining_decks > 4 else 51.0 if remaining_decks > 2 else 50.5
    else:
        threshold = 55.0 if remaining_decks > 4 else 53.0 if remaining_decks > 2 else 51.5

    units = 0
    game.current_bet_target = None
    
    if game.pending_stage:
        advice = game.pending_text
    elif b_pct >= threshold:
        game.current_bet_target = 'B'
        units = game.calculate_kelly_units(b_pct, True)
        advice = f"🔥 系統強推！重注押【莊】 ({units} 單位)"
    elif p_pct >= threshold:
        game.current_bet_target = 'P'
        units = game.calculate_kelly_units(p_pct, False)
        advice = f"🔥 系統強推！重注押【閒】 ({units} 單位)"
    else:
        advice = "⚪ 局勢膠著，建議【觀望】 (0 單位)"
        
    lines.append(f"🎯 系統策略: {advice}")
    lines.append("---------------------------------------------------------")
    
    lines.append("📊 [牌庫優勢分析]")
    lines.append(f"   機率偏移: 莊 {true_count_shift:+.3f}% | 閒 {-true_count_shift:+.3f}%")
    diff = big_removed - small_removed 
    math_sig = f"🔴 指向【莊】 (小牌偏多 {diff:+})" if diff > 0 else f"🔵 指向【閒】 (大牌偏多 {-diff:+})" if diff < 0 else "⚪ 牌流平衡"
    lines.append(f"   💡 數學訊號: {math_sig}")
    lines.append("---------------------------------------------------------")
    
    lines.append("🛣️ [下三路順勢指引]")
    recent_road = [tw.get(r, r) for r in game.raw_road[-6:]]
    lines.append(f"   ⭕ 大路近期：{' - '.join(recent_road) if recent_road else '無'}\n")

    roads_config = {'大眼仔路': 1, '小路趨勢': 2, '蟑螂路　': 3}
    v_b = v_p = 0
    for name, k in roads_config.items():
        b_red = game._simulate_derived_road(game.big_road, k, 'B')
        p_red = game._simulate_derived_road(game.big_road, k, 'P')
        
        if b_red is True: vote_str, v_b = "👉 🔴 建議押【莊】", v_b + 1
        elif p_red is True: vote_str, v_p = "👉 🔵 建議押【閒】", v_p + 1
        else: vote_str = "⏳ 等待成路       "

        is_stable = game._simulate_derived_road(game.big_road[:-1], k, game.raw_road[-1]) if game.raw_road else True
        stab_str = "✅ 平穩 (規律成型)" if is_stable else "⚠️ 波動 (單跳破路)"
        lines.append(f"   {'👁️' if k==1 else '🛣️' if k==2 else '🪳'} {name}：{vote_str.ljust(12)} | 📝 路況: {stab_str}")

    lines.append("")
    road_sig = f"🔴 指向【莊】 ({v_b}票 vs {v_p}票)" if v_b > v_p else f"🔵 指向【閒】 ({v_p}票 vs {v_b}票)" if v_p > v_b else "⚪ 訊號分歧"
    lines.append(f"   💡 路單訊號: {road_sig}")
    lines.append("---------------------------------------------------------")
    
    last_act = game.history_log[0] if game.history_log else "等待指令..."
    lines.append(f"⏳ 動態: {last_act}")
    lines.append("=========================================================")

    return jsonify({"terminal_text": "\n".join(lines)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
