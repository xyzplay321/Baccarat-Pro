# 引入 Flask 網頁伺服器相關套件，讓 Python 能與網頁溝通
from flask import Flask, render_template, request, jsonify

# 建立一個名為 app 的 Flask 網站伺服器實例
app = Flask(__name__)

# 定義「百家樂專業版」的遊戲引擎類別
class BaccaratPro:
    # 系統初始化的設定（預設使用 8 副牌）
    def __init__(self, num_decks=8):
        self.num_decks = num_decks # 儲存使用的牌靴副數
        # 華爾街等級 EOR (精確牌效應) 矩陣：每一種牌被抽走後，對莊家勝率的微幅影響 (%)
        self.EOR_B = {0: 0.03, 1: -0.08, 2: -0.11, 3: -0.16, 4: -0.29, 5: -0.18, 6: 0.20, 7: 0.13, 8: 0.21, 9: 0.13}
        self.reset_game() # 啟動時自動重置牌局

    # 重置整靴牌與所有統計資料的函式
    def reset_game(self):
        # 建立全新的牌庫：0點(10/J/Q/K)有16張*8副，其餘1~9點各有4張*8副
        self.counts = {i: 4 * self.num_decks if i != 0 else 16 * self.num_decks for i in range(10)}
        self.initial_counts = self.counts.copy() # 備份最一開始的牌庫狀態，用來比對消耗量
        self.total_cards = 52 * self.num_decks # 計算總牌數 (預設 416 張)
        self.round_num = 1 # 局數從第 1 局開始
        self.history = []  # 儲存每一局的詳細狀態，供「悔棋」使用   
        self.raw_road = [] # 儲存純粹的勝負結果陣列 (例如 ['B', 'P', 'B'])  
        self.big_road = [] # 儲存整理成大路格式的二維陣列 (畫圖用)   
        self.is_blind_mode = False # 紀錄上一把是否為盲打模式
        self.session_streak = 0 # 紀錄目前的連勝或連敗次數
        self.current_bet_target = None # 紀錄系統當前建議押注的目標 (B 或 P)
        self.history_log = [] # 儲存給網頁顯示用的「最近 5 手文字日誌」
        
        # 兩段式輸入的狀態記憶變數
        self.pending_stage = False # 標記目前是否正在「等待輸入補牌」
        self.pending_vals = []     # 暫存第一段輸入的 4 張牌
        self.pending_text = ""     # 暫存要在畫面上顯示的等待提示文字

    # 將最新的勝負結果加入「大路」陣列的函式
    def _add_to_big_road(self, res):
        if res not in ['B', 'P']: return # 和局不畫在大路的主圈圈，直接跳過
        # 如果大路是空的，或是這把結果跟上一把不同 (換邊)，就開一個新的「直列」
        if not self.big_road or self.big_road[-1][0] != res: self.big_road.append([res])
        # 如果跟上一把相同 (連贏)，就接在目前最後一個「直列」的下方
        else: self.big_road[-1].append(res)

    # 計算最近 15 局盤勢波動率的過濾器
    def get_volatility(self):
        # 如果打不到 10 把，資料太少不計算波動率
        if len(self.raw_road) < 10: return "數據不足", 1.0 
        # 取出最近 15 把的莊閒結果
        recent = [r for r in self.raw_road if r in ['B', 'P']][-15:]
        if len(recent) < 5: return "數據不足", 1.0
        # 計算這段時間內發生了幾次「換邊」
        switches = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i-1])
        chop_rate = switches / (len(recent) - 1) # 計算換邊頻率
        # 頻率大於 60% 代表盤勢很亂 (單跳多)，回傳係數 0.5 來削弱圖形權重
        if chop_rate > 0.6: return "🔴 高波動 (震盪盤)", 0.5  
        # 頻率小於 40% 代表盤勢穩定 (長龍多)，回傳係數 1.5 來放大圖形權重
        elif chop_rate < 0.4: return "🟢 低波動 (趨勢盤)", 1.5 
        return "🟡 中等波動", 1.0 # 正常狀況，權重不變

    # 全盤掃描大路，尋找經典圖形
    def detect_all_patterns(self, vol_multiplier):
        if len(self.big_road) < 4: return None, 0, "🔍 掃描中..." # 列數不夠不掃描
        lens = [len(col) for col in self.big_road[-6:]] # 取出最近 6 列的長度 (連續顆數)
        cur_side = self.big_road[-1][0] # 目前最後一顆的顏色 (勢力)
        opp_side = 'P' if cur_side == 'B' else 'B' # 算出對立面的顏色
        tw = {'B': '莊', 'P': '閒'} # 中文翻譯對照表
        
        # 根據長度陣列，判斷符合哪種神路，並乘上波動率係數算出加權分數
        if lens[-1] >= 4: return cur_side, 15 * vol_multiplier, f"🐉 {tw[cur_side]}長龍"
        if all(l == 1 for l in lens[-4:]): return opp_side, 12 * vol_multiplier, "⚡ 單跳成路"
        if lens[-4:] == [2, 2, 2, 1]: return cur_side, 10 * vol_multiplier, "✌️ 雙跳補齊"
        if lens[-4:] == [1, 2, 1, 1]: return cur_side, 8 * vol_multiplier, "🏠 一廳兩房"
        return None, 0, "⚪ 無明顯圖形" # 都沒中就回傳無

    # 凱利公式：根據勝率與賠率，計算出最完美的下注比例
    def calculate_kelly_units(self, p_win, is_banker):
        p = p_win / 100 # 將勝率轉換為小數
        q = 1 - p # 計算敗率
        b = 0.95 if is_banker else 1.0 # 莊家抽水 5% 所以賠率是 0.95，閒家是 1.0
        f = (b * p - q) / b # 凱利公式核心數學式
        if f <= 0: return 0 # 如果算出來期望值是負的，建議下注 0
        units = round(f * 100, 1) # 轉換成資金的 % 數 (單位)
        return min(units, 10) # 系統保護機制：單把極限最多下注總本金的 10%

    # 捕捉高賠率邊注 (打和局) 的特殊漏洞
    def check_side_bets(self, true_count_shift):
        zeros_removed = self.initial_counts[0] - self.counts[0] # 算出被抽走多少張 10/J/Q/K
        # 如果 0 點牌已經消耗超過一半，且牌靴來到尾聲，和局機率暴增
        if zeros_removed > (16 * self.num_decks * 0.5) and self.total_cards < 100:
            return "🚨 高能預警：和局 EV 轉正，建議防守打【和】"
        return "" # 沒機會就保持空白

    # 【核心】結算牌面、自動判斷補牌、更新系統資料
    def _finalize_exact_cards(self, vals):
        p_cards, b_cards = [vals[0], vals[1]], [vals[2], vals[3]] # 前兩張給閒，後兩張給莊
        p_score, b_score = sum(p_cards) % 10, sum(b_cards) % 10 # 計算起手點數
        idx = 4 # 設定陣列讀取指標，準備讀第 5 張牌
        
        # 完美還原賭場補牌矩陣 (若雙方起手都不是 8 或 9 點才補牌)
        if p_score < 8 and b_score < 8:
            p_drew = False # 紀錄閒家是否有補牌
            p3 = -1 # 紀錄閒家補到的第三張牌點數
            # 閒家 0~5 點必須補牌
            if p_score <= 5:
                if idx < len(vals): # 如果使用者有輸入第 5 個數字
                    p3 = vals[idx]
                    p_cards.append(p3) # 加入閒家牌組
                    idx += 1
                    p_drew = True
            
            b_draw = False # 紀錄莊家是否需要補牌
            # 莊家補牌判斷邏輯
            if not p_drew:
                if b_score <= 5: b_draw = True # 閒沒補，莊 0~5 補
            else:
                # 閒有補，莊家根據自己的點數與閒補的牌(p3)決定
                if b_score <= 2: b_draw = True
                elif b_score == 3 and p3 != 8: b_draw = True
                elif b_score == 4 and p3 in [2, 3, 4, 5, 6, 7]: b_draw = True
                elif b_score == 5 and p3 in [4, 5, 6, 7]: b_draw = True
                elif b_score == 6 and p3 in [6, 7]: b_draw = True
                
            if b_draw and idx < len(vals):
                b_cards.append(vals[idx]) # 若莊家需補牌，讀取下一個數字加入莊家牌組
                idx += 1

        used_cards = vals[:idx] # 切片：只取真正有發出來的牌 (過濾掉手滑多打的數字)
        valid_cards_str = "".join(map(str, used_cards)) # 轉成字串備份
        final_p, final_b = sum(p_cards) % 10, sum(b_cards) % 10 # 計算最終莊閒點數
        res = 'P' if final_p > final_b else 'B' if final_b > final_p else 'T' # 判斷誰贏
        
        # 如果上一把系統有給出方向，且這把不是和局，就更新連勝負次數
        if res != 'T' and self.current_bet_target:
            self.session_streak += 1 if self.current_bet_target == res else -1 if self.session_streak <= 0 else -(self.session_streak + 1)
                
        backup_counts = self.counts.copy() # 備份當前牌庫供悔棋用
        # 從真實牌庫中扣除剛才發出去的牌
        for val in used_cards:
            if self.counts[val] > 0:
                self.counts[val] -= 1
                self.total_cards -= 1
                
        # 儲存歷史紀錄，並把結果畫進大路
        self.history.append(('EXACT', valid_cards_str, res, backup_counts, self.is_blind_mode, self.session_streak))
        self.raw_road.append(res); self._add_to_big_road(res)
        
        # 組合「閒(4+5=9) 莊(1+2=3)」這種漂亮字串顯示在日誌裡
        p_str, b_str = "+".join(map(str, p_cards)), "+".join(map(str, b_cards))
        self.history_log.insert(0, f"局數 {self.round_num}: 閒({p_str}={final_p}) 莊({b_str}={final_b}) -> {'莊贏' if res=='B' else '閒贏' if res=='P' else '和局'}")
        self.history_log = self.history_log[:5] # 日誌永遠只保留最新 5 筆
        
        self.round_num += 1; self.is_blind_mode = False # 局數加一，結束處理
        return True

    # 處理前端傳來的數字字串 (兩段式輸入大腦)
    def process_exact_cards(self, cards_str):
        vals = [int(d) for d in cards_str] # 把字串拆成數字陣列

        # 情況 A：如果目前系統正在「等待補牌」
        if self.pending_stage:
            full_vals = self.pending_vals + vals # 把第一段的 4 張牌與第二段的補牌合併
            self.pending_stage = False # 解除等待狀態
            self.pending_vals = []
            return self._finalize_exact_cards(full_vals) # 交給結算函式處理

        # 情況 B：第一段輸入 (剛發出 4 張牌)
        if len(vals) == 4:
            p_score, b_score = sum(vals[:2]) % 10, sum(vals[2:4]) % 10
            if p_score >= 8 or b_score >= 8: return self._finalize_exact_cards(vals) # 天牌直接結算

            p_draw = p_score <= 5 # 判斷閒是否要補
            b_draw = b_score <= 5 if not p_draw else True # 判斷莊是否可能要補

            if p_draw or b_draw:
                self.pending_stage = True # 開啟等待補牌狀態
                self.pending_vals = vals  # 記住這 4 張牌
                # 生成黃色提示文字
                self.pending_text = f"⏳ 閒({p_score}點) 莊({b_score}點) ➔ 等待輸入補牌"
                return "PENDING"
            else:
                return self._finalize_exact_cards(vals) # 都不用補牌，直接結算

        # 情況 C：老手盲打直接輸入 5 或 6 個數字
        elif len(vals) > 4:
            return self._finalize_exact_cards(vals)
        return False

    # 處理快捷鍵盲打 (只按了莊/閒/和)
    def process_blind_shortcut(self, cmd):
        res = cmd.upper()
        # 更新連勝負次數
        if res != 'T' and self.current_bet_target:
            self.session_streak += 1 if self.current_bet_target == res else -1 if self.session_streak <= 0 else -(self.session_streak + 1)
        
        self.history.append(('BLIND', res, res, self.counts.copy(), self.is_blind_mode, self.session_streak))
        self.raw_road.append(res); self._add_to_big_road(res)
        
        self.history_log.insert(0, f"局數 {self.round_num}: 快捷錄入 -> {'莊贏' if res=='B' else '閒贏' if res=='P' else '和局'}")
        self.history_log = self.history_log[:5]
        
        self.round_num += 1; self.is_blind_mode = True
        return True

    # 悔棋功能：時光倒流回上一局
    def undo(self):
        # 如果是在等待補牌時按悔棋，就取消等待狀態，不扣局數
        if self.pending_stage:
            self.pending_stage = False
            self.pending_vals = []
            self.history_log.insert(0, "⏪ 已取消輸入，請重新輸入 4 張牌")
            self.history_log = self.history_log[:5]
            return True
            
        if not self.history: return False # 已經退無可退
        h = self.history.pop() # 取出上一局的備份資料
        # 還原牌庫、模式、連勝負狀態
        self.counts, self.is_blind_mode, self.session_streak = h[3], h[4], h[5]
        self.raw_road.pop(); self.big_road = [] # 砍掉最後一個路單
        for r in self.raw_road: self._add_to_big_road(r) # 重新重頭畫一次大路
        if self.history_log: self.history_log.pop(0) # 刪掉最新的一筆日誌
        self.round_num -= 1; return True # 局數扣回

# 創建一個全域的遊戲引擎實體
game = BaccaratPro(8)

# 定義網頁的首頁路由，回傳 index.html 畫面
@app.route('/')
def home(): return render_template('index.html')

# 定義 API 路由，用來接收網頁按鈕傳來的指令
@app.route('/api/cmd', methods=['POST'])
def handle_command():
    cmd = request.json.get('cmd', '').upper() # 取得前端傳來的指令 (轉大寫)
    
    # 根據指令呼叫大腦對應的函式
    if cmd == 'R': game.reset_game()
    elif cmd == 'U': game.undo()
    elif cmd in ['B', 'P', 'T']:
        if game.pending_stage: game.pending_stage, game.pending_vals = False, [] # 盲打強制中斷補牌
        game.process_blind_shortcut(cmd)
    elif cmd.isdigit():
        if game.pending_stage:
            if len(cmd) > 2: game.pending_text = "⚠️ 補牌最多 2 張，請重新輸入"
            else: game.process_exact_cards(cmd)
        else:
            if len(cmd) < 4:
                game.history_log.insert(0, "⚠️ 第一段請輸入 4 個數字 (閒2莊2)")
                game.history_log = game.history_log[:5]
            else:
                game.process_exact_cards(cmd)
            
    # 【量化引擎運算區】
    # 1. 根據目前牌庫與 EOR 矩陣，精算出數學優勢偏移值
    eor_shift_total = 0
    if game.total_cards > 0:
        for card, eor_val in game.EOR_B.items():
            removed = game.initial_counts[card] - game.counts[card] # 算出每種牌被抽走幾張
            eor_shift_total += removed * eor_val # 乘上權重並加總
            
    # 2. 計算「真數 (True Count)」 (偏移值 ÷ 剩餘牌副數)
    remaining_decks = max(0.5, game.total_cards / 52.0) # 預防除以零
    true_count_shift = eor_shift_total / remaining_decks

    # 3. 取得市場波動率與符合的經典圖形
    vol_status, vol_mult = game.get_volatility()
    pat_side, pat_weight, pat_name = game.detect_all_patterns(vol_mult)

    # 4. 綜合所有數據，結算最終莊閒機率 (%)
    b_prob, p_prob = 50.68, 49.32 # 基準起跑點
    b_prob += true_count_shift # 加上真數偏移
    p_prob -= true_count_shift
    if pat_side == 'B': b_prob += pat_weight # 加上圖形權重
    elif pat_side == 'P': p_prob += pat_weight
    
    # 數值歸一化，確保相加為 100%
    total = b_prob + p_prob
    b_pct, p_pct = round((b_prob/total)*100, 1), round((p_prob/total)*100, 1)

    # 5. 輸出決策與凱利注碼建議
    game.current_bet_target = None
    advice = "⚪ 局勢膠著，建議【觀望】"
    units = 0
    
    # 依據剩餘牌副數，動態調整進場門檻 (牌越少，信心越高，門檻越低)
    threshold = 52.0 if remaining_decks > 4 else 51.5 if remaining_decks > 2 else 51.0

    # 判斷是否突破門檻
    if b_pct >= threshold:
        game.current_bet_target = 'B'
        units = game.calculate_kelly_units(b_pct, True)
        advice = f"🔥 訊號成立！押【莊】"
    elif p_pct >= threshold:
        game.current_bet_target = 'P'
        units = game.calculate_kelly_units(p_pct, False)
        advice = f"🔥 訊號成立！押【閒】"

    # 如果正在兩段式輸入的等待期，覆蓋掉所有建議，顯示等待文字
    if game.pending_stage:
        advice = game.pending_text
        units = 0

    side_bet_alert = game.check_side_bets(true_count_shift) # 檢查邊注警報
    # 組合連勝負火焰文字
    streak_text = f"🔥 {game.session_streak} 連勝" if game.session_streak > 0 else f"🧊 {abs(game.session_streak)} 連敗" if game.session_streak < 0 else "---"

    # 將所有結果打包成 JSON 格式，送回給前端網頁
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
        "big_road": game.big_road[-12:] # 擷取大路的最後 12 列給前端畫圖
    })

# 啟動伺服器的語法
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
