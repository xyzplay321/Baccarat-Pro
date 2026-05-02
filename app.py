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