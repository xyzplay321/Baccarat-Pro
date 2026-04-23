from flask import Flask, render_template, request, jsonify

app = Flask(__name__)


class BaccaratPro:
    def __init__(self, num_decks=8, starting_capital=10000):
        self.num_decks = num_decks
        self.capital = starting_capital
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
        self.stats = {'math': {'W': 0, 'L': 0, 'streak': 0}, 'road': {'W': 0, 'L': 0, 'streak': 0}}
        self.current_advice = {'math': None, 'road': None}
        self.current_bet_target = None
        self.current_bet_amount = 0

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
            if len(col_compare) > R: return True
            if len(col_compare) == R: return False
            return True
        else:
            col_prev1 = temp_br[C - 1]
            col_prev2 = temp_br[C - (k + 1)]
            return len(col_prev1) == len(col_prev2)

    def get_road_recommendation(self):
        recs = {'vote_B': 0, 'vote_P': 0}
        roads = {'eye': 1, 'small': 2, 'roach': 3}
        for name, k in roads.items():
            b_is_red = self._simulate_derived_road(self.big_road, k, 'B')
            p_is_red = self._simulate_derived_road(self.big_road, k, 'P')
            if b_is_red is None and p_is_red is None: continue
            if b_is_red is True and p_is_red is not True:
                recs['vote_B'] += 1
            elif p_is_red is True and b_is_red is not True:
                recs['vote_P'] += 1
            else:
                if b_is_red:
                    recs['vote_B'] += 1
                else:
                    recs['vote_P'] += 1
        return recs

    def _update_stats_and_capital(self, res):
        if res in ['B', 'P']:
            for eng in ['math', 'road']:
                adv = self.current_advice[eng]
                if adv in ['B', 'P']:
                    if adv == res:
                        self.stats[eng]['W'] += 1
                        self.stats[eng]['streak'] = self.stats[eng]['streak'] + 1 if self.stats[eng][
                                                                                         'streak'] > 0 else 1
                    else:
                        self.stats[eng]['L'] += 1
                        self.stats[eng]['streak'] = self.stats[eng]['streak'] - 1 if self.stats[eng][
                                                                                         'streak'] < 0 else -1

        wl_text = ""
        if self.current_bet_target and self.current_bet_amount > 0:
            if res == self.current_bet_target:
                profit = self.current_bet_amount
                self.capital += profit
                wl_text = f" | 💰 盈虧: +{profit}"
            elif res == 'T':
                wl_text = f" | 💰 盈虧: 0 (和局)"
            else:
                loss = self.current_bet_amount
                self.capital -= loss
                wl_text = f" | 💰 盈虧: -{loss}"
        return wl_text

    def process_exact_cards(self, cards_str):
        vals = [int(d) for d in cards_str]

        # 智能判定發牌分配 (已修復 5 張牌 BUG)
        if len(vals) == 4:
            p_cards, b_cards = vals[:2], vals[2:]
        elif len(vals) == 6:
            p_cards, b_cards = vals[:3], vals[3:]
        elif len(vals) == 5:
            p_initial = (vals[0] + vals[1]) % 10
            if p_initial <= 5:
                p_cards, b_cards = vals[:3], vals[3:]
            else:
                p_cards, b_cards = vals[:2], vals[2:]
        else:
            return False

        p_score = sum(p_cards) % 10
        b_score = sum(b_cards) % 10

        if p_score > b_score:
            res = 'P'
        elif b_score > p_score:
            res = 'B'
        else:
            res = 'T'

        backup_counts, backup_stats, backup_capital = self.counts[:], {k: v.copy() for k, v in
                                                                       self.stats.items()}, self.capital
        wl_text = self._update_stats_and_capital(res)

        for d in cards_str:
            val = int(d)
            if self.counts[val] > 0:
                self.counts[val] -= 1
                self.total_cards -= 1

        self.history.append(('EXACT', cards_str, res, backup_counts, self.is_blind_mode, backup_stats, backup_capital))
        self.raw_road.append(res)
        self._add_to_big_road(res)
        self.round_num += 1
        self.is_blind_mode = False

        winner_str = "閒贏" if res == 'P' else "莊贏" if res == 'B' else "和局"
        self.last_action_text = f"輸入 [{cards_str}] -> 閒 {p_score} 點 vs 莊 {b_score} 點 ({winner_str}){wl_text}"
        return True

    def process_blind_shortcut(self, cmd):
        res = cmd.upper()
        backup_stats, backup_capital = {k: v.copy() for k, v in self.stats.items()}, self.capital
        wl_text = self._update_stats_and_capital(res)
        self.history.append(('BLIND', res, res, self.counts[:], self.is_blind_mode, backup_stats, backup_capital))
        self.raw_road.append(res)
        self._add_to_big_road(res)
        self.round_num += 1
        self.is_blind_mode = True
        winner_str = "閒贏" if res == 'P' else "莊贏" if res == 'B' else "和局"
        self.last_action_text = f"快捷輸入 [{cmd}] -> {winner_str} (未扣牌){wl_text}"
        return True

    def undo_round(self):
        if not self.history: return False
        last_type, last_data, res, backup_counts, prev_blind_state, backup_stats, backup_capital = self.history.pop()
        self.counts, self.is_blind_mode, self.stats, self.capital = backup_counts, prev_blind_state, backup_stats, backup_capital
        if last_type == 'EXACT': self.total_cards += len(last_data)
        self.raw_road.pop()
        self.big_road = []
        for r in self.raw_road: self._add_to_big_road(r)
        self.round_num -= 1
        self.last_action_text = f"⏪ 已撤銷第 {self.round_num} 局！本金已回溯。"
        return True

    def calculate_bet_strategy(self, math_side, road_side):
        base_bet = max(100, int(self.capital * 0.01))
        if math_side and road_side:
            if math_side == road_side:
                self.current_bet_target = math_side
                self.current_bet_amount = base_bet * 3
                return f"🔥 雙引擎共振！重注押【{'莊' if math_side == 'B' else '閒'}】 ({self.current_bet_amount} 元)"
            else:
                self.current_bet_target, self.current_bet_amount = None, 0
                return f"⚠️ 訊號衝突！強制建議【觀望】 (0 元)"
        elif math_side:
            self.current_bet_target, self.current_bet_amount = math_side, base_bet * 2
            return f"💡 數學優勢！穩健押【{'莊' if math_side == 'B' else '閒'}】 ({self.current_bet_amount} 元)"
        elif road_side:
            self.current_bet_target, self.current_bet_amount = road_side, base_bet * 1
            return f"👉 路單順勢！保守押【{'莊' if road_side == 'B' else '閒'}】 ({self.current_bet_amount} 元)"
        else:
            self.current_bet_target, self.current_bet_amount = None, 0
            return f"⚪ 局勢不明，建議【觀望】 (0 元)"

    def _format_stat(self, eng):
        st = self.stats[eng]
        if st['W'] == 0 and st['L'] == 0: return "無紀錄"
        s = st['streak']
        streak_str = f"🔥{s}連勝" if s > 0 else f"🧊{-s}連敗" if s < 0 else "-"
        return f"{st['W']}勝{st['L']}負 ({streak_str})"


# 初始化全域遊戲物件
game = BaccaratPro(8, 10000)


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/cmd', methods=['POST'])
def handle_command():
    data = request.json
    cmd = data.get('cmd', '').upper()

    # 執行操作
    if cmd == 'R':
        game.reset_game()
        game.last_action_text = "🔄 牌靴已重置，全新 8 副牌準備就緒。"
    elif cmd == 'U':
        if not game.undo_round():
            game.last_action_text = "❌ 已經退到第一局，無法再撤銷！"
    elif cmd in ['B', 'P', 'T']:
        game.process_blind_shortcut(cmd)
    elif cmd.isdigit():
        game.process_exact_cards(cmd)

    # 結算下一局的建議狀態
    math_side, road_side, shift = None, None, 0
    if not game.is_blind_mode and game.total_cards > 0:
        small = sum(game.counts[1:6])
        large = sum(game.counts[6:10]) + game.counts[0]
        ratio = small / game.total_cards
        shift = (ratio - 0.3846) * 100
        if shift > 0.15:
            math_side = 'B'
        elif shift < -0.15:
            math_side = 'P'

    road_recs = game.get_road_recommendation()
    if road_recs['vote_B'] > road_recs['vote_P']:
        road_side = 'B'
    elif road_recs['vote_P'] > road_recs['vote_B']:
        road_side = 'P'

    game.current_advice['math'] = math_side
    game.current_advice['road'] = road_side
    bet_strategy_str = game.calculate_bet_strategy(math_side, road_side)
    stats_str = f"[數學] {game._format_stat('math')} | [路單] {game._format_stat('road')}"

    return jsonify({
        "round": game.round_num,
        "capital": game.capital,
        "bet_advice": bet_strategy_str,
        "stats": stats_str,
        "last_action": game.last_action_text
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)