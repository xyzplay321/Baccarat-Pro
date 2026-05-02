"""
═══════════════════════════════════════════════════════════════════════════════
                        澳門路單分析模組 (Road Module)
═══════════════════════════════════════════════════════════════════════════════

此模組實現澳門三種衍生路：大眼仔路、小路、蟑螂路

澳門路單規則說明：
- 大眼仔路：比較大路第C列 vs 第C-1列的高度
- 小路趨勢：比較大路第C列 vs 第C-2列的高度
- 蟑螂路：比較大路第C列 vs 第C-3列的高度

作者：Baccarat-Pro Team
版本：2.0
更新日期：2026-04-30
═══════════════════════════════════════════════════════════════════════════════
"""

from typing import List, Dict, Optional, Tuple
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════════════════════
# 澳門路單分析器
# ═══════════════════════════════════════════════════════════════════════════════

class RoadAnalyzer:
    """
    澳門路單分析器
    
    功能：
    - 維護大路、大眼仔路、小路、蟑螂路
    - 預測下一步結果
    - 統計路單趨勢
    """
    
    def __init__(self):
        """
        初始化路單分析器
        
        大路結構：
        [[col0], [col1], ...]
        其中每個 col 是一列，包含該列的所有結果
        例：[['B', 'P', 'B'], ['P']] 表示：
        第1列：B, P, B（從上到下）
        第2列：P
        """
        self.big_road = []  # 大路
        self.eye_road = []  # 大眼仔路
        self.small_road = []  # 小路
        self.cockroach_road = []  # 蟑螂路
        
        self.statistics = {
            'big_road': defaultdict(int),
            'eye_road': defaultdict(int),
            'small_road': defaultdict(int),
            'cockroach_road': defaultdict(int),
        }
    
    def add_result(self, result: str):
        """
        添加一個遊戲結果到大路
        
        參數：
        - result: 'B' (莊勝), 'P' (閒勝), 'T' (和局)
        
        規則：
        - 如果結果與上一個相同，添加到當前列下方
        - 如果結果與上一個不同，開始新的一列
        """
        if not self.big_road:
            self.big_road.append([result])
        else:
            last_col = self.big_road[-1]
            if last_col[0] == result:
                # 與當前列相同，添加到下方
                last_col.append(result)
            else:
                # 與當前列不同，開始新列
                self.big_road.append([result])
        
        # 更新統計
        self.statistics['big_road'][result] += 1
        
        # 更新衍生路
        self._update_derived_roads()
    
    def _update_derived_roads(self):
        """更新所有衍生路"""
        self.eye_road = self._calculate_derived_road(1)
        self.small_road = self._calculate_derived_road(2)
        self.cockroach_road = self._calculate_derived_road(3)
    
    def _calculate_derived_road(self, comparison_depth: int) -> List:
        """
        計算衍生路
        
        參數：
        - comparison_depth: 1 (大眼仔), 2 (小路), 3 (蟑螂路)
        
        規則（以大眼仔路為例）：
        1. 從第 3 列第 2 個位置開始記錄
        2. 比較當前列高度 vs 前 1 列高度
        3. 高度相同 → 記錄 'R' (紅)
        4. 高度不同 → 記錄 'B' (藍)
        """
        derived = []
        
        # 需要至少 comparison_depth + 1 列才能開始衍生路
        if len(self.big_road) < comparison_depth + 1:
            return derived
        
        # 從第 comparison_depth + 2 列開始
        for col_idx in range(comparison_depth + 1, len(self.big_road)):
            current_height = len(self.big_road[col_idx])
            compare_height = len(self.big_road[col_idx - comparison_depth])
            
            # 判斷同號還是變號
            if current_height > compare_height:
                prediction = 'R'  # 紅（同號）
            elif current_height < compare_height:
                prediction = 'B'  # 藍（變號）
            else:
                prediction = 'E'  # 相等（邊界情況）
            
            # 構建衍生路（類似大路的結構）
            if not derived or derived[-1][0] != prediction:
                derived.append([prediction])
            else:
                derived[-1].append(prediction)
            
            # 更新統計
            road_name = f"road_{comparison_depth}"
            self.statistics[f"{'eyeroad' if comparison_depth == 1 else 'smallroad' if comparison_depth == 2 else 'cockroachroad'}"][prediction] += 1
        
        return derived
    
    def predict_next_result(self) -> Dict[str, any]:
        """
        基於路單預測下一步結果
        
        返回：
        {
            'eye_road_prediction': 'R'/'B'/'?',
            'small_road_prediction': 'R'/'B'/'?',
            'cockroach_road_prediction': 'R'/'B'/'?',
            'consensus': 'R'/'B'/None,  # 三路是否一致
            'confidence': 'HIGH'/'MEDIUM'/'LOW'
        }
        """
        predictions = {}
        
        # 大眼仔路預測
        eye_pred = self._predict_derived_road(self.eye_road)
        predictions['eye_road'] = eye_pred
        
        # 小路預測
        small_pred = self._predict_derived_road(self.small_road)
        predictions['small_road'] = small_pred
        
        # 蟑螂路預測
        roach_pred = self._predict_derived_road(self.cockroach_road)
        predictions['cockroach_road'] = roach_pred
        
        # 計算共識
        valid_predictions = [p for p in [eye_pred, small_pred, roach_pred] if p]
        
        if len(valid_predictions) == 0:
            consensus = None
            confidence = 'LOW'
        elif len(set(valid_predictions)) == 1:
            # 三路一致
            consensus = valid_predictions[0]
            confidence = 'HIGH'
        else:
            # 不一致
            consensus = None
            confidence = 'MEDIUM'
        
        predictions['consensus'] = consensus
        predictions['confidence'] = confidence
        
        return predictions
    
    def _predict_derived_road(self, road: List) -> Optional[str]:
        """
        預測衍生路的下一步
        
        邏輯：
        - 如果路單為空，返回 None
        - 否則根據最後一列的方向預測下一步
        """
        if not road:
            return None
        
        # 獲取最後一列的結果
        last_result = road[-1][0]
        
        # 簡單預測：重複最後一個結果
        return last_result
    
    def get_road_statistics(self) -> Dict:
        """獲取所有路單的統計信息"""
        return {
            'big_road_length': len(self.big_road),
            'eye_road_length': len(self.eye_road),
            'small_road_length': len(self.small_road),
            'cockroach_road_length': len(self.cockroach_road),
            'statistics': dict(self.statistics)
        }
    
    def reset(self):
        """重置所有路單"""
        self.big_road = []
        self.eye_road = []
        self.small_road = []
        self.cockroach_road = []
        self.statistics = {
            'big_road': defaultdict(int),
            'eye_road': defaultdict(int),
            'small_road': defaultdict(int),
            'cockroach_road': defaultdict(int),
        }
    
    def format_road_as_string(self, road: List[List[str]]) -> str:
        """將路單格式化為字符串"""
        if not road:
            return "(空)"
        
        # 構建字符串表示
        rows = []
        max_height = max(len(col) for col in road)
        
        for row_idx in range(max_height):
            row_str = ""
            for col in road:
                if row_idx < len(col):
                    row_str += col[row_idx] + " "
                else:
                    row_str += ". "
            rows.append(row_str)
        
        return "\n".join(rows)
    
    def display_all_roads(self):
        """顯示所有路單"""
        print("\n【大路】")
        print(self.format_road_as_string(self.big_road))
        
        print("\n【大眼仔路】")
        print(self.format_road_as_string(self.eye_road))
        
        print("\n【小路】")
        print(self.format_road_as_string(self.small_road))
        
        print("\n【蟑螂路】")
        print(self.format_road_as_string(self.cockroach_road))

# ═══════════════════════════════════════════════════════════════════════════════
# 單元測試
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    """運行澳門路單測試"""
    tests_passed = 0
    tests_failed = 0
    
    # 測試 1: 基本路單構建
    try:
        analyzer = RoadAnalyzer()
        analyzer.add_result('B')
        analyzer.add_result('B')
        analyzer.add_result('P')
        
        assert len(analyzer.big_road) == 2
        assert analyzer.big_road[0] == ['B', 'B']
        assert analyzer.big_road[1] == ['P']
        tests_passed += 1
        print("✅ 測試 1 (基本路單): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 1 (基本路單): 失敗 - {e}")
    
    # 測試 2: 衍生路計算
    try:
        analyzer = RoadAnalyzer()
        # 構建一個足夠長的大路來測試衍生路
        for result in ['B', 'B', 'P', 'P', 'P', 'B']:
            analyzer.add_result(result)
        
        # 應該有衍生路
        assert len(analyzer.eye_road) > 0
        tests_passed += 1
        print("✅ 測試 2 (衍生路): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 2 (衍生路): 失敗 - {e}")
    
    # 測試 3: 預測功能
    try:
        analyzer = RoadAnalyzer()
        for result in ['B', 'B', 'P', 'P', 'P', 'B', 'B']:
            analyzer.add_result(result)
        
        prediction = analyzer.predict_next_result()
        assert 'consensus' in prediction
        assert 'confidence' in prediction
        tests_passed += 1
        print("✅ 測試 3 (預測): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 3 (預測): 失敗 - {e}")
    
    # 測試 4: 統計功能
    try:
        analyzer = RoadAnalyzer()
        analyzer.add_result('B')
        analyzer.add_result('P')
        analyzer.add_result('B')
        
        stats = analyzer.get_road_statistics()
        assert stats['big_road_length'] == 2
        assert stats['statistics']['big_road']['B'] == 2
        assert stats['statistics']['big_road']['P'] == 1
        tests_passed += 1
        print("✅ 測試 4 (統計): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 4 (統計): 失敗 - {e}")
    
    # 測試 5: 重置功能
    try:
        analyzer = RoadAnalyzer()
        analyzer.add_result('B')
        analyzer.add_result('P')
        analyzer.reset()
        
        assert len(analyzer.big_road) == 0
        assert len(analyzer.eye_road) == 0
        tests_passed += 1
        print("✅ 測試 5 (重置): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 5 (重置): 失敗 - {e}")
    
    # 測試 6: 複雜路單
    try:
        analyzer = RoadAnalyzer()
        sequence = ['B', 'B', 'B', 'P', 'P', 'B', 'B', 'P', 'P', 'P']
        for result in sequence:
            analyzer.add_result(result)
        
        stats = analyzer.get_road_statistics()
        assert stats['big_road_length'] > 0
        assert stats['eye_road_length'] > 0
        tests_passed += 1
        print("✅ 測試 6 (複雜路單): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 6 (複雜路單): 失敗 - {e}")
    
    # 測試 7: 格式化輸出
    try:
        analyzer = RoadAnalyzer()
        analyzer.add_result('B')
        analyzer.add_result('P')
        analyzer.add_result('B')
        
        road_str = analyzer.format_road_as_string(analyzer.big_road)
        assert 'B' in road_str
        assert 'P' in road_str
        tests_passed += 1
        print("✅ 測試 7 (格式化): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 7 (格式化): 失敗 - {e}")
    
    # 測試 8: 邊界情況
    try:
        analyzer = RoadAnalyzer()
        
        # 空路單
        prediction = analyzer.predict_next_result()
        assert prediction is not None
        
        # 單個結果
        analyzer.add_result('B')
        prediction = analyzer.predict_next_result()
        assert prediction is not None
        
        tests_passed += 1
        print("✅ 測試 8 (邊界情況): 通過")
    except AssertionError as e:
        tests_failed += 1
        print(f"❌ 測試 8 (邊界情況): 失敗 - {e}")
    
    print(f"\n═══════════════════════════════════════════")
    print(f"✅ Road 測試完成: {tests_passed} 通過, {tests_failed} 失敗")
    print(f"═══════════════════════════════════════════\n")

if __name__ == '__main__':
    run_tests()
