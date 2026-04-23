from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

class BaccaratPro:
    def __init__(self, num_decks=8):
        self.num_decks = num_decks
        self.reset_game()

    def reset_game(self):
        self.counts = [16 * self.num_decks] + [4 * self.num_decks] * 9
        self.total_cards = 52 * self.num_decks
        self.round_num = 1
        self.history = []     
        self.raw_road = []    
        self.big_road = []    
        self.is_blind_mode = False 
        self.last_action_text = "等待開局..."
        self.session_streak = 0 
        self.current_advice = {'math': None, 'road': None}
        self.current_pattern_text = "🔍 數據不足，掃描中..."

    def _add_to_big_road(self, res):
        if res not in ['B', 'P']: return
        if not self.big_road or self.big_road[-1][0] != res:
            self.big_road.append([res])
        else:
            self.big_road[-1].append(res)

    def _simulate_derived_road(self, board, k, guess):
        temp_br = [col[:] for col in board]
        if not temp_br or temp_br[-1][0] != guess: temp_br.append([guess])
        else: temp_br[-1].append(guess)
        C = len(temp_br) - 1 
        if C <= k: return None 
        R = len(temp_br[C]) - 1 
        if R > 0: return len(temp_br[C-k]) >= R
        else: return len(temp_br[C-1]) == len(temp_br[C-(k+1)])

    def detect_all_patterns(self):
        """核心：全圖形掃描器 (新增回傳圖形名稱)"""
        if len(self.big_road) < 4: return None, 0, "🔍 數據不足，掃描中..."
        
        lens = [len(col) for col in self.big_road[-6:]]
        cur_side = self.big_road[-1][0]
        opp_side = 'P' if cur_side == 'B' else 'B'
        side_tw = {'B': '莊', 'P': '閒'}
        
        if lens[-1] >= 4: return cur_side, 15, f"🐉 {side_tw[cur_side]}長龍 (連 {lens[-1]} 顆)"
        if all(l == 1 for l in lens[-4:]): return opp_side, 12, "⚡ 標準單跳路"
        if lens[-4:] == [2, 2, 2, 1]: return cur_side, 10, "✌️ 雙跳路 (準備補齊)"
        if lens[-4:] == [2, 2, 2, 2]: return opp_side, 10, "✌️ 雙跳路 (準備換邊)"
        if lens[-4:] == [1, 2, 1, 1]: return cur_side, 8, "🏠 一廳兩房 (準備補齊)"
        if lens[-4:] == [2, 1, 2, 1]: return opp_side, 8, "🏠 一廳兩房 (準備換邊)"

        history_lens = [len(col) for col in self.big_road if col[0] == opp_side]
        if len(history_lens) >= 3 and all(l == 1 for l in history_lens):
            if lens[-1] == 1 and cur_side == opp_side: 
                return ('B' if opp_side == 'P' else 'P'), 12, f"🪃 逢{side_tw[opp_side]}必跳"

        return None, 0, "⚪ 目前無特殊圖形"

    def calculate_final_prob(self, math_shift, road_votes):
        """引擎綜合計算每局百分比"""
        b_prob = 50.68
        p_prob = 49.32
        
        b_prob += math_shift * 5
        p_prob -= math_shift * 5
        
        net_votes = road_votes['B'] - road_votes['P']
        b_prob += net_votes * 3
        p_prob -= net_votes * 3
        
        pat_side, pat_weight, pat_name = self.detect_all_patterns()
        self.current_pattern_text = pat_name # 儲存圖形名稱給前端
        
        if pat_side == 'B': b_prob += pat_weight
        elif pat_side == 'P': p_prob += pat_weight
        
        total = b_prob + p_prob
        return round((b_prob / total) * 100, 1), round((p_prob / total) * 100, 1)

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
        
        if res != 'T' and self.current_advice['road']:
            if self.current_advice['road'] == res: self.session_streak = self.session_streak + 1 if self.session_streak >= 0 else 1
            else: self.session_streak = self.session_streak - 1 if self.session_streak <= 0 else -1
                
        backup_counts = self.counts[:]
        for d in cards_str:
            if self.counts[int(d)] > 0: self.counts[int(d)] -= 1
            self.total_cards -= 1
        self.history.append(('EXACT', cards_str, res, backup_counts, self.is_blind_mode, self.session_streak))
        self.raw_road.append(res); self._add_to_big_road(res)
        self.round_num += 1; self.is_blind_mode = False
        self.last_action_text = f"[{cards_str}] -> 閒 {p_s} vs 莊 {b_s}"
        return True

    def process_blind_shortcut(self, cmd):
        res = cmd.upper()
        if res != 'T' and self.current_advice['road']:
            if self.current_advice['road'] == res: self.session_streak = self.session_streak + 1 if self.session_streak >= 0 else 1
            else: self.session_streak = self.session_streak - 1 if self.session_streak <= 0 else -1
        self.history.append(('BLIND', res, res, self.counts[:], self.is_blind_mode, self.session_streak))
        self.raw_road.append(res); self._add_to_big_road(res)
        self.round_num += 1; self.is_blind_mode = True
        self.last_action_text = f"快捷輸入 -> {res}"
        return True

    def undo(self):
        if not self.history: return False
        h = self.history.pop()
        self.counts, self.is_blind_mode, self.session_streak = h[3], h[4], h[5]
        self.raw_road.pop(); self.big_road = []
        for r in self.raw_road: self._add_to_big_road(r)
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
            
    math_side, road_side, shift = None, None, 0
    if not game.is_blind_mode and game.total_cards > 0:
        s, l = sum(game.counts[1:6]), sum(game.counts[6:10]) + game.counts[0]
        shift = (s / game.total_cards - 0.3846) * 100
        if shift > 0.15: math_side = 'B'
        elif shift < -0.15: math_side = 'P'
        
    roads_config = {'大眼仔': 1, '小路': 2, '蟑螂路': 3}
    votes = {'B': 0, 'P': 0}
    stability_icons = []
    for name, k in roads_config.items():
        b_red = game._simulate_derived_road(game.big_road, k, 'B')
        p_red = game._simulate_derived_road(game.big_road, k, 'P')
        if b_red is True: votes['B'] += 1
        if p_red is True: votes['P'] += 1
        
        if game.raw_road:
            is_stable = game._simulate_derived_road(game.big_road[:-1], k, game.raw_road[-1])
            stability_icons.append(f"{name}{'✅' if is_stable else '⚠️'}")
    
    road_side = 'B' if votes['B'] > votes['P'] else 'P' if votes['P'] > votes['B'] else None
    game.current_advice = {'math': math_side, 'road': road_side}

    b_pct, p_pct = game.calculate_final_prob(shift, votes)
    
    advice = "⚪ 建議觀望"
    if b_pct >= 60: advice = f"🔥 強力推【莊】"
    elif p_pct >= 60: advice = f"🔥 強力推【閒】"
    elif b_pct > p_pct: advice = f"👉 傾向【莊】"
    else: advice = f"👉 傾向【閒】"

    streak_text = f"🔥 {game.session_streak} 連勝" if game.session_streak > 0 else f"🧊 {abs(game.session_streak)} 連敗" if game.session_streak < 0 else "---"

    return jsonify({
        "round": game.round_num,
        "streak": streak_text,
        "advice": advice,
        "b_prob": f"{b_pct}%",
        "p_prob": f"{p_pct}%",
        "pattern": game.current_pattern_text,
        "stability": " | ".join(stability_icons) if stability_icons else "等待成路",
        "last_action": game.last_action_text
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
