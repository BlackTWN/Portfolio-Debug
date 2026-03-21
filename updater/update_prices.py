"""
update_prices.py — v1.2
自動抓取台股 + 美股即時/收盤價，更新 portfolio_radar_v3.html 追蹤表格
依賴：pip install yfinance requests beautifulsoup4 pytz
使用：python update_prices.py
"""

import re
import json
import datetime
from pathlib import Path

# ── 安裝確認 ─────────────────────────────────────────
try:
    import yfinance as yf
except ImportError:
    raise SystemExit("❌ 請先執行：pip install yfinance")

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise SystemExit("❌ 請先執行：pip install beautifulsoup4")

# ════════════════════════════════════════════════════
# 設定區（可自行修改）
# ════════════════════════════════════════════════════

# 專案根目錄（自動偵測：updater/ 的上一層）
BASE_DIR    = Path(__file__).resolve().parent.parent
HTML_FILE   = BASE_DIR / "dashboard" / "portfolio_radar_v3.html"
LOG_FILE    = BASE_DIR / "logs" / "price_log.jsonl"

USD_TO_TWD  = 32.1                               # 匯率（手動填或接API）

# 台股清單：{代碼: {name, entry_price, shares, stop, target, currency}}
TW_STOCKS = {
    "0050.TW":  {"name": "元大台灣50",     "entry": 230.0,   "shares": 21,   "stop": None,    "target": None,   "sim": True},
    "0056.TW":  {"name": "元大高股息",     "entry": 41.0,    "shares": 121,  "stop": None,    "target": None,   "sim": True},
    "00878.TW": {"name": "國泰永續高股息", "entry": 23.0,    "shares": 217,  "stop": None,    "target": None,   "sim": True},
    "2308.TW":  {"name": "台達電",         "entry": 1455.0,  "shares": 3,    "stop": 1300.0,  "target": None,   "sim": False},
    "2330.TW":  {"name": "台積電",         "entry": 1840.0,  "shares": 2,    "stop": 1720.0,  "target": 2400.0, "sim": True},
    "2337.TW":  {"name": "旺宏電子",       "entry": 157.0,   "shares": 31,   "stop": 130.5,   "target": 300.0,  "sim": True},
    "2615.TW":  {"name": "萬海航運",       "entry": 88.0,    "shares": 56,   "stop": 80.0,    "target": 105.0,  "sim": True},
    "2884.TW":  {"name": "玉山金",         "entry": 33.35,   "shares": 149,  "stop": None,    "target": None,   "sim": True},
    "2886.TW":  {"name": "兆豐金",         "entry": 45.0,    "shares": 111,  "stop": None,    "target": None,   "sim": True},
    "2892.TW":  {"name": "第一金",         "entry": 36.0,    "shares": 138,  "stop": None,    "target": None,   "sim": True},
    "3529.TW":  {"name": "力旺",           "entry": 1480.0,  "shares": 3,    "stop": None,    "target": None,   "sim": False},
    "3546.TW":  {"name": "宇峻",           "entry": 69.8,    "shares": 71,   "stop": None,    "target": None,   "sim": False},
    "5274.TW":  {"name": "信驊",           "entry": 11750.0, "shares": 0,    "stop": None,    "target": None,   "sim": False},
}

# 美股清單
US_STOCKS = {
    "MU":  {"name": "Micron",       "entry": 444.0,  "shares_frac": 0.35, "stop": 412.0,  "target": 550.0,  "sim": True},
    "CAT": {"name": "Caterpillar",  "entry": 681.0,  "shares_frac": 0.23, "stop": 662.0,  "target": 736.0,  "sim": True},
}

# HTML 內各股票對應的 data-stock-id（我們在 HTML 內用此做定位）
# 格式：yfinance_ticker -> HTML_anchor_id
TICKER_TO_HTML_ID = {
    "0050.TW": "d-0050", "0056.TW": "d-0056", "00878.TW": "d-00878",
    "2308.TW": "d-2308", "2330.TW": "d-2330", "2337.TW": "d-2337",
    "2615.TW": "d-2615", "2884.TW": "d-2884", "2886.TW": "d-2886",
    "2892.TW": "d-2892", "3529.TW": "d-3529", "3546.TW": "d-3546",
    "5274.TW": "d-5274",
    "MU": "d-MU", "CAT": "d-CAT",
}

# ════════════════════════════════════════════════════
# 核心函式
# ════════════════════════════════════════════════════

def fetch_price(ticker: str) -> float | None:
    """
    抓最後一個交易日收盤價（非 today）
    邏輯：取 period=5d 的歷史，拿最後一筆已收盤資料
    台灣時間若 < 14:00，當日未收盤，自動回退到前一交易日
    """
    try:
        data = yf.Ticker(ticker)
        hist = data.history(period="5d")
        if hist.empty:
            return None
        # 去掉 today 尚未收盤的資料
        import datetime, pytz
        tz_tw = pytz.timezone("Asia/Taipei")
        now_tw = datetime.datetime.now(tz_tw)
        today_str = now_tw.strftime("%Y-%m-%d")
        # 台股 13:30 前、美股 05:00 前視為未收盤
        cutoff_hour = 13 if ".TW" in ticker else 5
        if now_tw.hour < cutoff_hour:
            # 排除今日，取前一日
            hist = hist[hist.index.strftime("%Y-%m-%d") < today_str]
        if hist.empty:
            return None
        price = round(float(hist["Close"].iloc[-1]), 2)
        trade_date = hist.index[-1].strftime("%Y/%m/%d")
        return price, trade_date
    except Exception as e:
        print(f"  ⚠ 抓取 {ticker} 失敗：{e}")
        return None


def calc_return(current: float, entry: float) -> tuple[float, float]:
    """回傳 (損益金額NT, 報酬率%)"""
    pct = (current - entry) / entry * 100
    return pct


def fmt_price(price: float, is_usd: bool = False) -> str:
    if is_usd:
        return f"${price:.2f}"
    return f"{price:.2f}"


def signal_text(pct: float, stop: float | None, current: float, target: float | None) -> str:
    """根據報酬率與停損/停利給出訊號文字"""
    if stop and current <= stop:
        return "🔴 觸停損"
    if target and current >= target:
        return "🎯 達目標"
    if pct >= 10:
        return "📈 強勢"
    if pct >= 5:
        return "📊 獲利中"
    if pct >= 0:
        return "🟡 持平"
    if pct >= -5:
        return "🟠 小幅虧損"
    return "🔴 注意虧損"


def color_class(pct: float) -> str:
    if pct > 0:
        return "g"
    if pct < 0:
        return "r"
    return "y"


# ════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════

def main():
    today = datetime.date.today().strftime("%Y/%m/%d")
    print(f"\n{'='*52}")
    print(f"  台美股投資組合價格更新  {today}")
    print(f"{'='*52}\n")

    if not HTML_FILE.exists():
        raise SystemExit(f"❌ 找不到 {HTML_FILE}，請確認路徑")

    html_text = HTML_FILE.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_text, "html.parser")

    results = {}  # ticker -> {price, pct, ...}

    # ── 抓台股 ─────────────────────────────────────
    print("📡 抓取台股價格...")
    for ticker, cfg in TW_STOCKS.items():
        result = fetch_price(ticker)
        if result is None:
            print(f"  ✗ {ticker} ({cfg['name']}) 無法取得")
            continue
        price, trade_date = result
        pct = calc_return(price, cfg["entry"])
        cc  = color_class(pct)
        sig = signal_text(pct, cfg.get("stop"), price, cfg.get("target"))
        results[ticker] = {"price": price, "pct": pct, "cc": cc, "sig": sig, "cfg": cfg, "usd": False}
        mark = "🔴" if (cfg.get("stop") and price <= cfg["stop"]) else ("🟢" if pct > 0 else "🔴" if pct < 0 else "⚪")
        print(f"  {mark} {ticker:12s} {cfg['name']:10s}  {price:>10.2f} 元  {pct:+.2f}%  [{trade_date}]  {sig}")

    # ── 抓美股 ─────────────────────────────────────
    print("\n📡 抓取美股價格...")
    for ticker, cfg in US_STOCKS.items():
        result = fetch_price(ticker)
        if result is None:
            print(f"  ✗ {ticker} ({cfg['name']}) 無法取得")
            continue
        price, trade_date = result
        pct = calc_return(price, cfg["entry"])
        cc  = color_class(pct)
        sig = signal_text(pct, cfg.get("stop"), price, cfg.get("target"))
        results[ticker] = {"price": price, "pct": pct, "cc": cc, "sig": sig, "cfg": cfg, "usd": True}
        mark = "🔴" if (cfg.get("stop") and price <= cfg["stop"]) else ("🟢" if pct > 0 else "🔴" if pct < 0 else "⚪")
        pnl_nt = (price - cfg["entry"]) * cfg["shares_frac"] * USD_TO_TWD
        print(f"  {mark} {ticker:6s} {cfg['name']:14s}  ${price:>8.2f}   {pct:+.2f}%  NT損益 {pnl_nt:+.0f}  {sig}")

    # ── 寫入 HTML ──────────────────────────────────
    print(f"\n✏️  更新 HTML 追蹤表格...")
    modified = False

    for ticker, data in results.items():
        html_id = TICKER_TO_HTML_ID.get(ticker)
        if not html_id:
            continue
        cfg   = data["cfg"]
        price = data["price"]
        pct   = data["pct"]
        cc    = data["cc"]
        sig   = data["sig"]
        is_usd = data["usd"]

        # 找到對應的 detail-row
        detail_div = soup.find(id=html_id)
        if not detail_div:
            continue

        sim_log = detail_div.find(class_="sim-log")
        if not sim_log:
            continue

        # 找第一個「—」（未填入）的 sim-row
        rows = sim_log.find_all(class_="sim-row")
        target_row = None
        for row in rows:
            spans = row.find_all("span")
            # 第二個 span 是價格欄，若為 "—" 則填入
            if len(spans) >= 4 and spans[1].get_text().strip() == "—":
                target_row = row
                break

        if not target_row:
            print(f"  ℹ  {ticker} 所有追蹤列已填滿，無需更新")
            continue

        spans = target_row.find_all("span")

        # ── 日期 span[0]：若為空補上今日 ──
        if spans[0].get_text().strip() in ["", "—"]:
            spans[0].string = today

        # ── 價格 span[1] ──
        price_str = fmt_price(price, is_usd)
        spans[1].string = price_str
        spans[1]["class"] = spans[1].get("class", [])  # 保留 class

        # ── 損益 span[2] ──
        if is_usd:
            pnl = (price - cfg["entry"]) * cfg["shares_frac"] * USD_TO_TWD
            pnl_str = f"NT{pnl:+.0f}"
        else:
            pnl = (price - cfg["entry"]) * cfg.get("shares", 0)
            pnl_str = f"{pnl:+.0f}"
        spans[2].string = pnl_str
        spans[2]["class"] = [cc]

        # ── 報酬率 span[3] ──
        spans[3].string = f"{pct:+.2f}%"
        spans[3]["class"] = [cc]

        # ── 訊號 span[4] ──
        inner = spans[4].find("span")
        if inner:
            inner.string = sig
            if "🔴" in sig:
                inner["style"] = "display:inline-block;padding:1px 6px;border-radius:3px;font-size:.58rem;background:rgba(240,48,96,.15);color:#f03060;border:1px solid rgba(240,48,96,.3);"
            elif "🎯" in sig:
                inner["style"] = "display:inline-block;padding:1px 6px;border-radius:3px;font-size:.58rem;background:rgba(240,192,64,.15);color:#f0c040;border:1px solid rgba(240,192,64,.3);"
            elif "📈" in sig:
                inner["style"] = "display:inline-block;padding:1px 6px;border-radius:3px;font-size:.58rem;background:rgba(40,224,144,.15);color:#28e090;border:1px solid rgba(40,224,144,.3);"
        else:
            spans[4].string = sig

        # 移除半透明樣式
        if "opacity" in target_row.get("style", ""):
            del target_row["style"]

        print(f"  ✅ {ticker} → {price_str}  {pct:+.2f}%  {sig}")
        modified = True

    # ── 同步更新表頭價格欄 (第4欄) ─────────────────
    print(f"\n✏️  同步更新主表格即時價格欄...")
    rows_main = soup.select("tr.row-hold, tr.row-new")
    ticker_list = list(TW_STOCKS.keys()) + list(US_STOCKS.keys())

    for tr in rows_main:
        onclick = tr.get("onclick", "")
        matched_id = re.search(r"'(d-[^']+)'", onclick)
        if not matched_id:
            continue
        html_id = matched_id.group(1)
        ticker  = next((t for t, h in TICKER_TO_HTML_ID.items() if h == html_id), None)
        if not ticker or ticker not in results:
            continue

        tds = tr.find_all("td")
        if len(tds) < 5:
            continue

        price  = results[ticker]["price"]
        pct    = results[ticker]["pct"]
        cc     = results[ticker]["cc"]
        is_usd = results[ticker]["usd"]

        # td[3] = 參考價
        tds[3].string = fmt_price(price, is_usd)
        tds[3]["style"] = "font-family:'IBM Plex Mono',monospace;"

        # td[4] = 近三日表現 → 改為即時漲跌幅
        arrow = "▲" if pct >= 0 else "▼"
        tds[4].string = f"{arrow} {abs(pct):.2f}%（{today}）"
        tds[4]["class"] = [cc]
        modified = True

    # ── 更新頁首日期標籤 ──────────────────────────
    date_bdg = soup.find(class_="bdg-date")
    if date_bdg:
        date_bdg.string = f"更新：{today}"

    # ── 存回 HTML ──────────────────────────────────
    if modified:
        HTML_FILE.write_text(str(soup), encoding="utf-8")
        print(f"\n💾 已儲存 → {HTML_FILE}")
    else:
        print("\nℹ️  無需更新")

    # ── 寫入 JSON 紀錄 ─────────────────────────────
    log_entry = {
        "date": today,
        "prices": {
            t: {"price": d["price"], "pct": round(d["pct"], 2), "signal": d["sig"]}
            for t, d in results.items()
        }
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    print(f"📒 價格紀錄已寫入 → {LOG_FILE}")

    # ── 終端摘要 ───────────────────────────────────
    print(f"\n{'─'*52}")
    print(f"  更新完成  共 {len(results)} 檔  {today}")
    stops = [(t, d) for t, d in results.items() if d["cfg"].get("stop") and d["price"] <= d["cfg"]["stop"]]
    if stops:
        print(f"\n  🔴 停損警示：")
        for t, d in stops:
            print(f"     {t} {d['cfg']['name']}  現價 {d['price']}  停損位 {d['cfg']['stop']}")
    print(f"{'─'*52}\n")


if __name__ == "__main__":
    main()
