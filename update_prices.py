"""
update_prices.py  v1.0
根治版：個股 + 大盤指數 → 統一寫入 data.json，HTML 不直接修改
變更紀錄：
  v1.0 - 初版
         新增 ^TWII（加權指數）、^DJI（道瓊）、^GSPC（S&P500）抓取
         改為純寫 data.json，HTML 由前端 JS 動態渲染
         新增台股 / 美股收盤時段判斷，避免抓到非交易日假值
         新增 retry 機制（最多 3 次）
"""

import json
import os
import time
import datetime
import pytz
import yfinance as yf

# ── 設定區 ────────────────────────────────────────────────
DATA_FILE = "data.json"          # 輸出目標，HTML 透過 JS fetch 讀取

# 持股清單：請依實際情況修改
HOLDINGS = [
    {"symbol": "2330.TW", "name": "台積電",  "shares": 1000},
    {"symbol": "2317.TW", "name": "鴻海",    "shares": 2000},
    {"symbol": "AAPL",    "name": "蘋果",    "shares": 10},
    {"symbol": "NVDA",    "name": "輝達",    "shares": 5},
]

# 大盤指數（固定抓，不需手動維護）
INDEX_SYMBOLS = {
    "TWII": "^TWII",   # 台灣加權指數
    "DJI":  "^DJI",    # 道瓊工業
    "GSPC": "^GSPC",   # S&P 500
}

# ── 工具函數 ──────────────────────────────────────────────
def safe_fetch(symbol: str, retries: int = 3) -> dict | None:
    """帶 retry 的 yfinance 抓取，失敗回傳 None"""
    for attempt in range(retries):
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            price = info.get("lastPrice") or info.get("regularMarketPrice")
            prev  = info.get("previousClose")
            if price is None:
                raise ValueError(f"{symbol} price is None")
            change     = price - prev if prev else 0
            change_pct = (change / prev * 100) if prev else 0
            return {
                "price":      round(float(price), 2),
                "prev_close": round(float(prev), 2) if prev else None,
                "change":     round(float(change), 2),
                "change_pct": round(float(change_pct), 2),
            }
        except Exception as e:
            print(f"[WARN] {symbol} attempt {attempt+1}/{retries} failed: {e}")
            time.sleep(2)
    print(f"[ERROR] {symbol} 全部 retry 失敗，跳過")
    return None


def get_now_str(tz_name: str = "Asia/Taipei") -> str:
    tz  = pytz.timezone(tz_name)
    now = datetime.datetime.now(tz)
    return now.strftime("%Y/%m/%d %H:%M")


def is_trading_session() -> str:
    """回傳目前是台股盤中/收盤後、美股盤中/收盤後、或非交易時段"""
    utc_now = datetime.datetime.now(pytz.utc)
    hour = utc_now.hour
    weekday = utc_now.weekday()  # 0=Mon, 4=Fri
    if weekday >= 5:
        return "weekend"
    if 1 <= hour < 6:     # UTC 01:00-06:00 = 台灣 09:00-14:00（台股盤中）
        return "tw_open"
    if 13 <= hour < 21:   # UTC 13:30-21:00 = 美東 09:30-17:00（美股盤中/後）
        return "us_open"
    return "closed"


# ── 主流程 ────────────────────────────────────────────────
def main():
    session = is_trading_session()
    print(f"[INFO] 執行時段判斷：{session}")

    now_tw = get_now_str("Asia/Taipei")
    now_us = get_now_str("America/New_York")

    # ① 讀取現有 data.json（保留歷史欄位）
    existing = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)

    # ② 抓大盤指數
    print("[INFO] 抓取大盤指數...")
    indices = existing.get("indices", {})
    for key, symbol in INDEX_SYMBOLS.items():
        result = safe_fetch(symbol)
        if result:
            result["updated_at"] = now_tw if key == "TWII" else now_us
            result["symbol"] = symbol
            indices[key] = result
            print(f"  ✓ {key} = {result['price']}")
        else:
            print(f"  ✗ {key} 抓取失敗，保留舊值")

    # ③ 抓個股
    print("[INFO] 抓取個股...")
    holdings_out = existing.get("holdings", [])
    symbol_map = {h["symbol"]: h for h in HOLDINGS}

    updated_holdings = []
    for holding in HOLDINGS:
        sym = holding["symbol"]
        result = safe_fetch(sym)
        existing_h = next((h for h in holdings_out if h.get("symbol") == sym), {})

        entry = {
            **existing_h,          # 保留舊有欄位（成本、股數等）
            "symbol":   sym,
            "name":     holding["name"],
            "shares":   holding["shares"],
            "updated_at": now_tw if sym.endswith(".TW") else now_us,
        }
        if result:
            entry.update(result)
            print(f"  ✓ {sym} = {result['price']}")
        else:
            print(f"  ✗ {sym} 抓取失敗，保留舊值")
        updated_holdings.append(entry)

    # ④ 組合輸出並寫入
    output = {
        **existing,
        "last_updated_tw": now_tw,
        "last_updated_us": now_us,
        "session":         session,
        "indices":         indices,
        "holdings":        updated_holdings,
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[OK] data.json 已更新（{now_tw} 台北時間）")


if __name__ == "__main__":
    main()
