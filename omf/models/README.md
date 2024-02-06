# 使用流程介紹
1. 下載可用的程式碼
```git clone -b dev https://github.com/efef31016/omf.git```
2. 進到獨立的需求響應模型程式碼
```cd omf/omf/models```
3. 開啟名為 DemandResponse_dev.py 的程式碼即可了解 PRISM 的輸入
4. 對於需求響應的總輸出，後續會完成



# 補充1: 淨現值（NPV）與 numpy_financial.npv 函數

## 什麼是淨現值（NPV）？
淨現值（Net Present Value, NPV）是評估投資效益的一種方法。它計算未來現金流入與現金流出的現值（以開始投資時為基準）之差。若NPV大於0，則表示投資預計能帶來正收益；若NPV小於0，則表示投資可能會虧損。

## numpy_financial.npv 函數
numpy_financial 是一個基於 NumPy 的財務函數庫，提供了計算 NPV 的函數。numpy_financial.npv 函數需要兩個參數：**貼現率**和**一系列現金流**。

## 範例
from numpy_financial import npv

rate = 0.05  # 貼現率
cashflows = [-1000, 300, 400, 500, 600]  # 現金流

npv = npv(rate, cashflows)
print(f"NPV: {npv}")
輸出為投資的淨現值。