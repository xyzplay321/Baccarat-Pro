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
        self.stats = {'math': {'W': 0, 'L': 0}, 'road': {'W': 0, 'L': 0}}
        self.current_advice = {'math': None, 'road': None}
        self.session_streak = 0 # 新增：目前連勝負狀態

    def _add_to_big_road(self, res):
        if res not in ['B', 'P']: return
        if not self.big_road or self.big_road[-1][0] != res:
            self.big_road.append([res])
        else:
            self.big_road[-1].append(res)

    def _simulate_derived_road(self, board, k, guess):
        temp_br = [col[:] for col in board]
        if not temp_br or temp_br[-1][0] != guess:
            temp_br.append([guess])
        else:
            temp_br[-1].append(guess)
        C = len(temp_br) - 1 
        if C <= k: return None 
        R = len(temp_br[C]) - 1 
        if R > 0: 
            col_compare = temp_br[C - k]
            return len(col_compare) >= R
        else:     
            return len(temp_br[C-1]) == len(temp_br[C-(k+1)])

    def get_road_status(self):
        """計算下三路穩定度"""
        roads = {'大眼仔': 1, '小路': 2, '蟑螂路': 3}
        status_list = []
        votes = {'B': 0, 'P': 0}
        
        for name, k in roads.items():
            b_red = self._simulate_derived_road(self.big_road, k, 'B')
            p_red = self._simulate_derived_road(self.big_road, k, 'P')
            
            if b_red is None:
                status_list.append(f"{name}: ⏳")
                continue
            
            # 判斷目前最後一手的穩定度
            last_res = self.raw_road[-1] if self.raw_road else None
            temp_br = [col[:] for col in self.big_road]
            # 簡單判定：紅筆為平穩，藍筆為波動
            is_stable = self._simulate_derived_road(temp_br[:-1], k, last_res) if len(temp_br)>1 else True
            emoji = "✅" if is_stable else "⚠️"
            status_list.append(f"{name}: {emoji}")
            
            if b_red: votes['B'] += 1
            if p_red: votes['P'] += 1
            
        return " | ".join(status_list), votes

    def _update_session_streak(self, res):
        """更新目前的連續勝負"""
        if res == 'T': return # 和局不計
        
        # 這裡以「路單引擎」的建議作為對獎基準 (因為路單最常有動作)
        advice = self.current_advice['road']
        if advice:
            if advice == res:
                self.session_streak = self.session_streak + 1 if self.session_streak >= 0 else 1
            else:
                self.session_streak = self.session_streak - 1 if self.session_streak <= 0 else -1

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
        
        self._update_session_streak(res)
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
        self._update_session_streak(res)
        self.history.append(('BLIND', res, res, self.counts[:], self.is_blind_mode, self.session_streak))
        self.raw_road.append(res); self._add_to_big_road(res)
        self.round_num += 1; self.is_blind_mode = True
        self.last_action_text = f"快捷輸入 -> {res}"
        return True

    def undo(self):
        if not self.history: return False
        h = self.history.pop()
        self.counts, self.is_blind_mode, self.session_streak = h[3], h[4], h[5]
        self.raw_road.pop()
        self.big_road = []
        for r in self.raw_road: self._add_to_big_road(r)
        self.round_num -= 1
        return True

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
        
    road_status_text, votes = game.get_road_status()
    if votes['B'] > votes['P']: road_side = 'B'
    elif votes['P'] > votes['B']: road_side = 'P'

    game.current_advice = {'math': math_side, 'road': road_side}
    
    # 組合建議文字
    advice = "⚪ 建議觀望"
    if math_side == road_side and math_side: advice = f"🔥 重注【{'莊' if math_side=='B' else '閒'}】"
    elif math_side: advice = f"💡 數學【{'莊' if math_side=='B' else '閒'}】"
    elif road_side: advice = f"👉 路單【{'莊' if road_side=='B' else '閒'}】"

    streak_text = f"🔥 {game.session_streak} 連勝" if game.session_streak > 0 else f"🧊 {abs(game.session_streak)} 連敗" if game.session_streak < 0 else "---"

    return jsonify({
        "round": game.round_num,
        "streak": streak_text,
        "advice": advice,
        "stability": road_status_text,
        "last_action": game.last_action_text
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
