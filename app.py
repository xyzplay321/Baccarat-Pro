"""
Web 伺服器入口 (app.py)
負責將 Baccarat-Pro v3.0 核心邏輯與 Flask 網頁介面串接，以便在 Render 等雲端平台運行。
"""
import os
from flask import Flask, render_template, request, jsonify
from app_v3 import BaccaratProV3

app = Flask(__name__)

# 初始化百家樂預測系統核心
# 這裡會讀取 config.py 中的預設設定
system = BaccaratProV3(
    num_decks=8, 
    eor_source='JACOBSON', 
    bet_strategy='CONSERVATIVE'
)

@app.route('/')
@app.route('/api/cmd', methods=['POST'])
def handle_cmd():
    """
    接收前端終端機傳來的指令，並回傳格式化的純文字
    """
    data = request.json
    cmd = data.get('cmd', '').upper().strip()
    
    # 1. 處理網頁剛載入時的初始連線 (空字串)
    if cmd == '':
        welcome_text = (
            "✅ 系統連線成功！Baccarat-Pro v3.0 已啟動。\n"
            "================================================\n"
            f"目前策略: {system.bet_strategy}\n"
            f"EOR來源: {system.eor_source}\n"
            "================================================\n"
            "等待輸入中..."
        )
        return jsonify({'terminal_text': welcome_text})
        
    # 2. 處理新增遊戲結果 (B, P, T)
    if cmd in ['B', 'P', 'T']:
        analysis = system.add_game_result(cmd)
        
        # 將分析數據排版成前端需要的純文字 (terminal_text)
        result_text = (
            f"\n> 輸入結果: {cmd}\n"
            "------------------------------------------------\n"
            f"📍 莊家勝率: {analysis.get('banker_prob', 0):.2f}%\n"
            f"📍 閒家勝率: {analysis.get('player_prob', 0):.2f}%\n"
            f"📍 真實計數: {analysis.get('true_count', 0):.2f}\n"
            f"📍 信心度:   {analysis.get('confidence', 'NONE')}\n"
        )
        
        # 提取 Kelly 下注建議
        if analysis.get('kelly_advice_banker'):
            advice = analysis['kelly_advice_banker']
            result_text += f"💡 建議 [莊]: {advice['recommendation']} (單位: {advice['bet_units']})\n"
        elif analysis.get('kelly_advice_player'):
            advice = analysis['kelly_advice_player']
            result_text += f"💡 建議 [閒]: {advice['recommendation']} (單位: {advice['bet_units']})\n"
        else:
            result_text += "💡 建議: 觀望\n"
            
        return jsonify({'terminal_text': result_text})
        
    # 3. 處理未知的指令 (防呆)
    return jsonify({'terminal_text': f"\n❌ 尚未支援或無效的指令: {cmd}\n請輸入 B, P 或 T。"})
def index():
    """
    首頁路由：當使用者訪問網站時，回傳 templates/index.html
    """
    # 確保你的專案資料夾內有一個 templates 資料夾，裡面有 index.html
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
def get_status():
    """
    API 路由：獲取目前系統的狀態與設定
    """
    return jsonify(system.get_system_info())

@app.route('/api/add_result', methods=['POST'])
def add_result():
    """
    API 路由：接收前端傳來的新遊戲結果，並回傳分析與下注建議
    """
    data = request.json
    result = data.get('result')
    
    # 驗證輸入格式
    if not result or result.upper() not in ['B', 'P', 'T']:
        return jsonify({'error': '無效的結果，請輸入 B (莊), P (閒) 或 T (和)'}), 400
    
    # 將結果加入核心系統並取得分析
    analysis = system.add_game_result(result.upper())
    
    # 將結果回傳給前端
    return jsonify(analysis)

if __name__ == '__main__':
    # 取得環境變數中的 PORT，這是 Render 部署的必要設定
    # 如果找不到 PORT，則預設使用 5000 (供本地端測試使用)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
