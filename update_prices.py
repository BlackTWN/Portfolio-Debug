"""
update_prices.py — v3.1
重寫：改為直接更新 HTML 中的大盤錨點 + RSI5_DATA JS 物件
不再依賴靜態 sim-log 結構（已移除）
"""
import datetime, json, re, sys, pytz
from pathlib import Path

import yfinance as yf

# ── 路徑設定 ──────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent.parent   # Portfolio-Debug/
HTML_FILE  = BASE_DIR / "dashboard" / "portfolio_radar_v3.html"
LOG_FILE   = BASE_DIR / "logs" / "price_log.jsonl"
DATA_DIR   = BASE_DIR / "data"

# ── 匯率 ──────────────────────────────────────────────────
USD_TO_TWD = 32.0

# ── 追蹤股票（從 STOCK_DB_DEFAULT 同步） ──────────────────
TW_TICKERS = [
    "0050.TW","0056.TW","00878.TW",
    "2308.TW","2330.TW","2337.TW","2615.TW",
    "2884.TW","2886.TW","2892.TW",
    "3529.TW","3546.TW","5274.TW",
]
US_TICKERS = ["MU","CAT"]

# ── 輔助函式 ──────────────────────────────────────────────
def get_last_close(ticker: str):
    """取最後一個交易日收盤價，回傳 (price, date_str) 或 None"""
    try:
        tz_tw  = pytz.timezone("Asia/Taipei")
        now_tw = datetime.datetime.now(tz_tw)
        hist   = yf.Ticker(ticker).history(period="5d")
        if hist.empty:
            return None
        # 台股 13:30 前、美股 05:00 前視為未收盤
        cutoff = 13 if ".TW" in ticker else 5
        today  = now_tw.strftime("%Y-%m-%d")
        if now_tw.hour < cutoff:
            hist = hist[hist.index.strftime("%Y-%m-%d") < today]
        if hist.empty:
            return None
        price = round(float(hist["Close"].iloc[-1]), 2)
        date  = hist.index[-1].strftime("%m/%d")
        return price, date
    except Exception as e:
        print(f"  ⚠ {ticker}: {e}")
        return None

def get_rsi_5day(ticker: str) -> list[int]:
    """計算近 5 個交易日的 RSI(14)"""
    try:
        hist = yf.Ticker(ticker).history(period="3mo")
        if len(hist) < 15:
            return [50,50,50,50,50]
        closes = hist["Close"].values
        rsi_vals = []
        for i in range(len(closes)-5, len(closes)):
            segment = closes[max(0,i-14):i+1]
            if len(segment) < 2:
                rsi_vals.append(50)
                continue
            diffs  = [segment[j]-segment[j-1] for j in range(1,len(segment))]
            gains  = [d for d in diffs if d > 0]
            losses = [-d for d in diffs if d < 0]
            avg_g  = sum(gains)/14  if gains  else 0
            avg_l  = sum(losses)/14 if losses else 0
            rsi = 100 - (100/(1+avg_g/avg_l)) if avg_l else 100
            rsi_vals.append(round(rsi))
        return rsi_vals if len(rsi_vals)==5 else [50,50,50,50,50]
    except:
        return [50,50,50,50,50]


# ════════════════════════════════════════════════════════════
# 主要更新函式
# ════════════════════════════════════════════════════════════

def update_market_index(html: str) -> tuple[str, dict]:
    """更新大盤（台股加權 + 道瓊）"""
    result = {}
    # 診斷：確認 HTML 有正確的錨點
    has_taiex = 'id="taiex-price"' in html
    has_dji   = 'id="dji-price"' in html
    print(f"  HTML 錨點: taiex-price={'✅' if has_taiex else '❌'}  dji-price={'✅' if has_dji else '❌'}")
    if not has_taiex:
        print("  ⚠ 找不到大盤錨點，可能是舊版 HTML，跳過大盤更新")
        return html, result
    for sym, label_tw, label_dji in [("^TWII","taiex",""),("^DJI","","dji")]:
        r = get_last_close(sym)
        if not r: continue
        price, date = r
        try:
            hist = yf.Ticker(sym).history(period="5d")
            prev = round(float(hist["Close"].iloc[-2]),2)
            change = round(price - prev, 2)
        except:
            change = 0
        up = change >= 0
        arrow = "▲" if up else "▼"
        color_up   = "var(--green)" if up else "var(--red)"
        color_dn   = color_up

        if sym == "^TWII":
            # 成交額
            try:
                vol = hist["Volume"].iloc[-1]
                vol_str = f"成交:{vol/1e8:.0f}億" if vol > 1e8 else ""
            except:
                vol_str = ""
            html = re.sub(r'(<div class="sl">加權指數（)[^）]+(）</div>)',
                          f'\\g<1>{date}收盤\\2', html)
            html = re.sub(r'id="taiex-price"[^>]*>[^<]*</div>',
                          f'id="taiex-price" style="color:{color_up};">{price:,.2f}</div>', html)
            html = re.sub(r'id="taiex-change"[^>]*>[^<]*</div>',
                          f'id="taiex-change" style="font-size:.68rem;font-family:\'IBM Plex Mono\',monospace;color:{color_dn};">{arrow}{abs(change):,.2f}</div>', html)
            html = re.sub(r'id="taiex-vol"[^>]*>[^<]*</div>',
                          f'id="taiex-vol" style="font-size:.6rem;color:var(--muted);">{vol_str}</div>', html)
            result["taiex"] = dict(price=f"{price:,.2f}", change=f"{arrow}{abs(change):,.2f}",
                                   date=date, up=up, vol=vol_str)
            print(f"  台股加權: {price:,.2f}  {arrow}{abs(change):.2f}  [{date}]")
        else:
            html = re.sub(r'(<div class="sl">道瓊工業（)[^）]+(）</div>)',
                          f'\\g<1>{date}收盤\\2', html)
            html = re.sub(r'id="dji-price"[^>]*>[^<]*</div>',
                          f'id="dji-price" style="color:{color_up};">{price:,.2f}</div>', html)
            html = re.sub(r'id="dji-change"[^>]*>[^<]*</div>',
                          f'id="dji-change" style="font-size:.68rem;font-family:\'IBM Plex Mono\',monospace;color:{color_dn};">{arrow}{abs(change):,.2f}</div>', html)
            result["dji"] = dict(price=f"{price:,.2f}", change=f"{arrow}{abs(change):,.2f}",
                                 date=date, up=up)
            print(f"  道瓊工業: {price:,.2f}  {arrow}{abs(change):.2f}  [{date}]")
    # 更新 header 副標題的「最後收盤日」文字
    tw_date = result.get('taiex',{}).get('date','')
    if tw_date:
        html = re.sub(
            r'最後收盤日（[^）]*）為準',
            f'最後收盤日（{tw_date}）為準',
            html
        )
    return html, result


def update_rsi5_data(html: str, prices: dict) -> str:
    """更新 HTML 中 RSI5_DATA JS 物件（近5日RSI）"""
    print("\n📊 計算 RSI 近五日走勢...")
    rsi_map = {}
    all_tickers = TW_TICKERS + US_TICKERS
    for t in all_tickers:
        clean = t.replace(".TW","")
        vals  = get_rsi_5day(t)
        rsi_map[clean] = vals
        print(f"  {clean}: {vals}")

    # 建立新的 RSI5_DATA 字串
    lines = ["const RSI5_DATA = {"]
    for clean, vals in rsi_map.items():
        lines.append(f"  '{clean}' :{vals},")
    lines.append("};")
    new_rsi5 = "\n".join(lines)

    # 替換 HTML 中的 RSI5_DATA
    html = re.sub(
        r'const RSI5_DATA\s*=\s*\{.*?\};',
        new_rsi5,
        html,
        flags=re.DOTALL
    )
    print("  ✅ RSI5_DATA 已更新")
    return html


def update_stock_prices_in_js(html: str, prices: dict) -> str:
    """更新 LIVE_PRICES JS 物件"""
    has_live = 'const LIVE_PRICES' in html
    print(f"  HTML 錨點: LIVE_PRICES={'✅' if has_live else '❌（舊版HTML，跳過）'}")
    if not has_live:
        return html
    # 注意：entry 是買入成本，不應覆蓋
    # 改為更新 HTML 中的 <td> 參考價顯示（如果有靜態錨點）
    # v2.0 架構：主表格完全動態，改以 data-price-TICKER 屬性傳值
    # 在 <body> 加入隱藏 data 元素，由 JS 讀取更新顯示
    
    price_data_js = "const LIVE_PRICES = {\n"
    for ticker, (price, date) in prices.items():
        clean = ticker.replace(".TW","")
        price_data_js += f"  '{clean}': {{price:{price}, date:'{date}'}},\n"
    price_data_js += "};\n"

    # 替換 HTML 中的 LIVE_PRICES（若存在）或加入
    if "const LIVE_PRICES" in html:
        html = re.sub(r'const LIVE_PRICES\s*=\s*\{.*?\};',
                      price_data_js.rstrip(), html, flags=re.DOTALL)
    else:
        # 在 STOCK_DB_DEFAULT 前插入
        html = html.replace(
            "const STOCK_DB_DEFAULT",
            price_data_js + "const STOCK_DB_DEFAULT"
        )
    print("  ✅ LIVE_PRICES 已更新")
    return html


def update_kline_data(prices: dict):
    """抓取 K 線資料存 JSON"""
    print("\n📈 抓取 K 線資料...")
    kline = {}
    all_tickers = TW_TICKERS + US_TICKERS
    for t in all_tickers:
        clean = t.replace(".TW","")
        try:
            tk = yf.Ticker(t)
            day  = tk.history(period="3mo",  interval="1d")
            week = tk.history(period="1y",   interval="1wk")
            mon  = tk.history(period="2y",   interval="1mo")
            def to_list(h, n):
                rows = []
                for dt, row in h.tail(n).iterrows():
                    rows.append({"t": dt.strftime("%Y-%m-%d"),
                                 "o": round(float(row.Open),2),
                                 "h": round(float(row.High),2),
                                 "l": round(float(row.Low),2),
                                 "c": round(float(row.Close),2)})
                return rows
            kline[clean] = {"1d": to_list(day,60), "1wk": to_list(week,26), "1mo": to_list(mon,24)}
            print(f"  {clean}: {len(kline[clean]['1d'])} 日K")
        except Exception as e:
            print(f"  ⚠ {clean}: {e}")
    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / "kline_data.json"
    out.write_text(json.dumps(kline, ensure_ascii=False, separators=(",",":")), encoding="utf-8")
    print(f"  ✅ K線存至 {out.name}")



# ════════════════════════════════════════════════════════
# AI 推薦分析（每日由 GitHub Actions 執行）
# 依據：技術面(RSI/KD) + 基本面(殖利率/EPS) + 新聞情緒
# ════════════════════════════════════════════════════════
import os, json as _json, urllib.request as _req

def call_gemini(prompt: str, system: str = "") -> str:
    """呼叫 Google Gemini API"""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("❌ 未設定 GEMINI_API_KEY，請在 GitHub Secrets 中新增")

    # 合併 system prompt 和 user prompt
    full_prompt = f"{system}\n\n{prompt}" if system else prompt

    payload = _json.dumps({
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 2000,
            "temperature": 0.3,
        }
    }).encode("utf-8")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={api_key}"
    )
    request = _req.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"}
    )
    with _req.urlopen(request, timeout=60) as resp:
        data = _json.loads(resp.read())
    return data["candidates"][0]["content"]["parts"][0]["text"]


def generate_ai_recommendations(prices: dict, rsi5_map: dict) -> list:
    """
    呼叫 Claude 產生每日推薦清單
    綜合：技術面(RSI/KD) + 基本面 + 新聞情緒
    """
    print("\n🤖 呼叫 Claude AI 產生推薦...")

    # 組建技術面摘要
    tech_lines = []
    for ticker_raw, (price, date) in prices.items():
        clean = ticker_raw.replace(".TW", "")
        rsi5  = rsi5_map.get(clean, [50, 50, 50, 50, 50])
        rsi   = rsi5[-1]
        trend = "↑上升" if rsi5[-1] > rsi5[0] else "↓下降"
        mkt   = "美股" if "." not in ticker_raw else "台股"
        tech_lines.append(
            f"{clean} [{mkt}] 現價:{price} RSI14:{rsi}({trend}) "
            f"RSI5日:{','.join(str(v) for v in rsi5)}"
        )

    tech_summary = "\n".join(tech_lines)
    today_str = __import__("datetime").date.today().strftime("%Y/%m/%d")

    SYSTEM = """你是專業股票分析師，每日提供台灣與美國股市的綜合推薦。
分析依據：技術面(RSI/KD均線)、基本面(殖利率/成長性)、市場情緒與新聞。
嚴格回傳 JSON 陣列，不加任何說明文字或 markdown。"""

    PROMPT = f"""今日（{today_str}）請綜合分析以下股票，挑選 2-5 檔值得推薦的個股：

技術指標摘要：
{tech_summary}

分析原則：
1. 技術面：RSI<30超賣反彈、KD低檔黃金交叉、均線支撐
2. 基本面：高殖利率防禦、EPS成長動能、護城河優勢
3. 新聞情緒：AI/半導體產業趨勢、法說會利多、法人買超

推薦條件（至少符合兩項）：
- RSI < 35 且趨勢開始回升
- RSI 在 40-60 且技術面健康
- 近期有基本面利多
- 市場情緒偏正面

回傳 JSON 陣列（只含值得推薦的個股，2-5 檔）：
[{{
  "ticker": "代碼",
  "name": "公司名稱",
  "mkt": "tw或us",
  "tag": "類別(etf/semi/mem/ai/fin/mfg/other)",
  "price": 參考價格(數字),
  "recDate": "{today_str}",
  "reason": "推薦原因(繁體中文,20字內)",
  "rsi": RSI數值(整數),
  "kd": "KD訊號說明",
  "action": "操作建議(可布局/可小買/可分批買/謹慎小買)",
  "risk": "低/中/高",
  "url": "Yahoo Finance連結",
  "stop": 建議停損價(數字或null),
  "target": 建議目標價(數字或null),
  "note": "詳細分析(繁體中文,40字內)"
}}]"""

    try:
        raw     = call_gemini(PROMPT, SYSTEM)
        clean   = raw.strip().replace("```json", "").replace("```", "").strip()
        results = _json.loads(clean)
        print(f"  ✅ AI 產生 {len(results)} 筆推薦")
        for r in results:
            print(f"     {r.get('ticker','?')} {r.get('name','?')} - {r.get('reason','')}")
        return results
    except Exception as e:
        print(f"  ❌ AI 推薦失敗: {e}")
        return []


def write_rec_db_to_html(html: str, recs: list) -> str:
    """將 AI 推薦結果寫入 HTML 的 REC_DB_DEFAULT"""
    if not recs:
        return html

    lines = ["const REC_DB_DEFAULT = ["]
    for r in recs:
        # 確保必填欄位存在
        r.setdefault("mkt",     "tw")
        r.setdefault("tag",     "other")
        r.setdefault("recDate", __import__("datetime").date.today().strftime("%Y/%m/%d"))
        r.setdefault("rsi",     50)
        r.setdefault("kd",      "—")
        r.setdefault("action",  "觀察等待")
        r.setdefault("risk",    "中")
        r.setdefault("stop",    None)
        r.setdefault("target",  None)
        r.setdefault("note",    "")
        r.setdefault("url",     f"https://tw.stock.yahoo.com/quote/{r['ticker']}.TW"
                               if r.get("mkt") != "us"
                               else f"https://finance.yahoo.com/quote/{r['ticker']}/")

        def js_val(v):
            if v is None:    return "null"
            if isinstance(v, bool):  return "true" if v else "false"
            if isinstance(v, (int, float)): return str(v)
            # 字串：跳脫單引號
            return "'" + str(v).replace("'", "\'") + "'"

        lines.append(
            f"  {{ ticker:{js_val(r['ticker'])}, name:{js_val(r['name'])}, "
            f"mkt:{js_val(r['mkt'])}, tag:{js_val(r['tag'])}, "
            f"price:{js_val(r.get('price', 0))}, recDate:{js_val(r['recDate'])}, "
            f"reason:{js_val(r.get('reason',''))}, rsi:{js_val(r['rsi'])}, "
            f"kd:{js_val(r['kd'])}, action:{js_val(r['action'])}, "
            f"risk:{js_val(r['risk'])}, url:{js_val(r['url'])}, "
            f"stop:{js_val(r['stop'])}, target:{js_val(r['target'])}, "
            f"note:{js_val(r.get('note',''))} }},"
        )
    lines.append("];")
    new_rec_db = "\n".join(lines)

    # 替換 HTML 中的 REC_DB_DEFAULT
    updated = re.sub(
        r"const REC_DB_DEFAULT\s*=\s*\[.*?\];",
        new_rec_db,
        html,
        flags=re.DOTALL
    )
    if updated == html:
        print("  ⚠ REC_DB_DEFAULT 未找到，跳過更新")
    else:
        print(f"  ✅ REC_DB_DEFAULT 已更新（{len(recs)} 筆）")
    return updated

def main():
    tz     = pytz.timezone("Asia/Taipei")
    today  = datetime.datetime.now(tz).strftime("%Y/%m/%d")
    print(f"\n{'='*52}")
    print(f"  投資組合自動更新  {today}")
    print(f"{'='*52}\n")

    if not HTML_FILE.exists():
        raise SystemExit(f"❌ 找不到 {HTML_FILE}")

    html = HTML_FILE.read_text(encoding="utf-8")

    # 1. 大盤指數
    print("📡 更新大盤指數...")
    html, mkt = update_market_index(html)

    # 2. 個股價格（收集供 LIVE_PRICES 和日誌）
    print("\n📡 抓取個股價格...")
    prices = {}
    for t in TW_TICKERS + US_TICKERS:
        r = get_last_close(t)
        clean = t.replace(".TW","")
        if r:
            prices[t] = r
            print(f"  ✅ {clean}: {r[0]} ({r[1]})")
        else:
            print(f"  ❌ {clean}: 無法取得")

    # 3. 更新 LIVE_PRICES（讓 JS 可讀取現價）
    html = update_stock_prices_in_js(html, prices)

    # 4. 更新 RSI 近五日
    html = update_rsi5_data(html, prices)

    # 5. 更新日期標示
    html = re.sub(r"(id=\"sysDate\"[^>]*>)[^<]*(</span>)",
                  f'\\g<1>{today}\\2', html)

    # 6. AI 每日推薦（綜合技術面 + 基本面 + 新聞情緒）
    rsi5_for_ai = {}
    for t in TW_TICKERS + US_TICKERS:
        clean = t.replace(".TW", "")
        rsi5_for_ai[clean] = get_rsi_5day(t)
    ai_recs = generate_ai_recommendations(prices, rsi5_for_ai)
    if ai_recs:
        html = write_rec_db_to_html(html, ai_recs)

    # 7. 存回 HTML
    HTML_FILE.write_text(html, encoding="utf-8")
    print(f"\n💾 已儲存 → {HTML_FILE}")

    # 7. K 線資料
    update_kline_data(prices)

    # 8. 寫入日誌
    LOG_FILE.parent.mkdir(exist_ok=True)
    log = {"date": today, "market": mkt,
           "prices": {t.replace(".TW",""): {"price":p,"date":d} for t,(p,d) in prices.items()}}
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(log, ensure_ascii=False) + "\n")
    print(f"📒 日誌 → {LOG_FILE.name}")
    print(f"\n{'─'*52}")
    print(f"  完成！共 {len(prices)} 檔  {today}")
    print(f"{'─'*52}\n")


if __name__ == "__main__":
    main()
