"""
sync_dca.py — v1.0
讀取 dca_data.csv → 產生 dca_sync.json → 注入 dca_tracker.html

流程：
  1. 你每月在 dca_data.csv 填入買入價
  2. 執行 python sync_dca.py
  3. dca_tracker.html 內的資料自動更新

依賴：pip install pandas
"""

import csv
import json
import hashlib
import datetime
from pathlib import Path

# ════════════════════════════════════════════════════
# 設定區
# ════════════════════════════════════════════════════
BASE_DIR   = Path(__file__).resolve().parent
CSV_FILE   = BASE_DIR / "dca_data.csv"
HTML_FILE  = BASE_DIR / "dca_tracker.html"
SYNC_FILE  = BASE_DIR / "dca_sync.json"   # 中間產物，可供除錯

# localStorage key 對應（需與 dca_tracker.html 一致）
PLANS_KEY  = "dca_plans_v2"
REC_PREFIX = "dca_rec_v2_"

# ════════════════════════════════════════════════════
# 核心：讀取 CSV
# ════════════════════════════════════════════════════
def read_csv(path: Path) -> dict:
    """
    回傳結構：
    {
      "0050": {
        "ticker": "0050",
        "name": "元大台灣50",
        "records": [
          {"date":"2023-03-26","price":115.5,"amount":3000,...},
          ...
        ]
      }
    }
    """
    plans = {}
    if not path.exists():
        raise FileNotFoundError(f"找不到 {path}")

    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ticker = row.get("計畫代碼", "").strip()
            name   = row.get("計畫名稱",  "").strip()
            date   = row.get("購入日期",  "").strip()
            price  = row.get("買入價",    "").strip()
            amt    = row.get("本期金額",  "").strip()
            sdate  = row.get("出售日期",  "").strip() or None
            sprice = row.get("出售價格",  "").strip() or None
            note   = row.get("備註",      "").strip()

            if not ticker or not date:
                continue

            # 驗證日期格式
            try:
                datetime.date.fromisoformat(date)
            except ValueError:
                print(f"  ⚠ 日期格式錯誤，跳過：{date}")
                continue

            price_f  = float(price)  if price  else None
            amt_f    = float(amt)    if amt    else 3000.0
            sprice_f = float(sprice) if sprice else None

            # 計算股數與損益
            shares    = round(amt_f / price_f, 6) if price_f else None
            realized  = None
            real_pct  = None
            if price_f and sprice_f:
                realized = round((sprice_f - price_f) * (shares or 0), 2)
                real_pct = round((sprice_f - price_f) / price_f * 100, 2)

            status = "sold" if sdate else "holding"

            if ticker not in plans:
                plans[ticker] = {"ticker": ticker, "name": name, "records": []}
            if name and not plans[ticker]["name"]:
                plans[ticker]["name"] = name

            # 用日期產生穩定 ID（相同日期重複匯入不會產生重複列）
            rec_id = "csv_" + hashlib.md5(f"{ticker}_{date}".encode()).hexdigest()[:10]

            plans[ticker]["records"].append({
                "id":         rec_id,
                "date":       date,
                "price":      price_f,
                "amount":     amt_f,
                "amtVersion": amt_f,
                "shares":     shares,
                "sellDate":   sdate,
                "sellPrice":  sprice_f,
                "realized":   realized,
                "realPct":    real_pct,
                "note":       note or "CSV匯入",
                "status":     status,
            })

    # 每個計畫的紀錄按日期排序
    for p in plans.values():
        p["records"].sort(key=lambda r: r["date"])

    return plans


# ════════════════════════════════════════════════════
# 核心：合併到現有 localStorage 資料
# ════════════════════════════════════════════════════
def extract_ls_data(html_content: str) -> dict:
    """從 HTML 中取出目前 __LS_INIT__ 區塊"""
    marker_s = "/*__LS_INIT_START__*/"
    marker_e = "/*__LS_INIT_END__*/"
    if marker_s not in html_content:
        return {}
    s = html_content.index(marker_s) + len(marker_s)
    e = html_content.index(marker_e)
    block = html_content[s:e].strip()
    try:
        return json.loads(block)
    except Exception:
        return {}


def merge_records(existing_recs: list, csv_recs: list) -> list:
    """
    合併策略：
    - CSV 紀錄以 id（日期 hash）為主鍵
    - 若 existing 中已有相同 id → 保留 existing（避免覆蓋手動修改）
    - 若 existing 中沒有 → 新增
    - 若 existing 中有同 date 但 id 不同（手動新增的）→ 也保留
    """
    existing_by_id   = {r["id"]: r for r in existing_recs}
    existing_by_date = {r["date"]: r for r in existing_recs}

    result = list(existing_recs)  # 先放既有的

    for cr in csv_recs:
        if cr["id"] in existing_by_id:
            # 已存在相同 hash id：若現有價格為 null 則用 CSV 的填入
            ex = existing_by_id[cr["id"]]
            if ex.get("price") is None and cr.get("price") is not None:
                ex.update({
                    "price":     cr["price"],
                    "shares":    cr["shares"],
                    "realized":  cr["realized"],
                    "realPct":   cr["realPct"],
                    "sellDate":  cr["sellDate"],
                    "sellPrice": cr["sellPrice"],
                    "status":    cr["status"],
                })
                print(f"    ↑ 更新空白價格：{cr['date']} → {cr['price']}")
        elif cr["date"] in existing_by_date:
            # 同日期但不同 id（手動新增的）：只更新價格若為空
            ex = existing_by_date[cr["date"]]
            if ex.get("price") is None and cr.get("price") is not None:
                ex.update({
                    "price":    cr["price"],
                    "shares":   cr["shares"],
                    "realized": cr["realized"],
                    "realPct":  cr["realPct"],
                    "status":   cr["status"],
                })
                print(f"    ↑ 填入手動列價格：{cr['date']} → {cr['price']}")
        else:
            # 新紀錄：直接加入
            result.append(cr)
            print(f"    + 新增：{cr['date']} {cr['price'] or '待填'}")

    result.sort(key=lambda r: r["date"])
    return result


# ════════════════════════════════════════════════════
# 核心：產生初始化 Script 注入 HTML
# ════════════════════════════════════════════════════
def build_ls_init_block(ls_data: dict) -> str:
    """產生注入 localStorage 的 JS 初始化區塊"""
    lines = ["// ── localStorage 初始化（由 sync_dca.py 自動產生）──"]
    lines.append("(function(){")
    lines.append("  var _ls = " + json.dumps(ls_data, ensure_ascii=False, separators=(',', ':')) + ";")
    lines.append("  Object.keys(_ls).forEach(function(k){")
    lines.append("    if(!localStorage.getItem(k)) localStorage.setItem(k, _ls[k]);")
    lines.append("  });")
    lines.append("})();")
    return "\n".join(lines)


def inject_ls_to_html(html_content: str, ls_data: dict) -> str:
    """將 localStorage 初始化資料注入 HTML，確保首次開啟即有資料"""
    marker_s = "/*__LS_INIT_START__*/"
    marker_e = "/*__LS_INIT_END__*/"
    init_block = build_ls_init_block(ls_data)

    if marker_s in html_content and marker_e in html_content:
        # 替換既有區塊
        s = html_content.index(marker_s)
        e = html_content.index(marker_e) + len(marker_e)
        new_block = f"{marker_s}\n{init_block}\n{marker_e}"
        return html_content[:s] + new_block + html_content[e:]
    else:
        # 第一次注入：找 </script> 前的 window.addEventListener DOMContentLoaded
        target = "window.addEventListener('DOMContentLoaded',"
        if target in html_content:
            insert_pos = html_content.index(target)
            injection = f"<script>{marker_s}\n{init_block}\n{marker_e}\n</script>\n"
            return html_content[:insert_pos - 0] + injection + html_content[insert_pos:]
        else:
            # fallback：在 </body> 前
            injection = f"\n<script>{marker_s}\n{init_block}\n{marker_e}\n</script>\n"
            return html_content.replace("</body>", injection + "</body>", 1)


# ════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════
def main():
    today = datetime.date.today().strftime("%Y/%m/%d")
    print(f"\n{'='*52}")
    print(f"  DCA 資料同步  {today}")
    print(f"{'='*52}\n")

    # ── 讀 CSV ──────────────────────────────────────
    print(f"📖 讀取 {CSV_FILE.name} ...")
    csv_plans = read_csv(CSV_FILE)
    print(f"   找到 {len(csv_plans)} 個計畫，"
          f"{sum(len(p['records']) for p in csv_plans.values())} 筆紀錄\n")

    # ── 讀現有 HTML ──────────────────────────────────
    if not HTML_FILE.exists():
        raise FileNotFoundError(f"找不到 {HTML_FILE}")
    html = HTML_FILE.read_text(encoding="utf-8")

    # ── 取出現有 localStorage 資料 ───────────────────
    existing_ls = extract_ls_data(html)
    existing_plans: list = json.loads(existing_ls.get(PLANS_KEY, "[]"))

    # ── 合併各計畫 ───────────────────────────────────
    new_ls = dict(existing_ls)
    plan_ids_by_ticker = {p["ticker"]: p["id"] for p in existing_plans}

    for ticker, csv_plan in csv_plans.items():
        print(f"📊 處理計畫：{ticker} {csv_plan['name']}")

        if ticker in plan_ids_by_ticker:
            # 計畫已存在
            plan_id = plan_ids_by_ticker[ticker]
            existing_recs = json.loads(existing_ls.get(REC_PREFIX + plan_id, "[]"))
            merged = merge_records(existing_recs, csv_plan["records"])
            new_ls[REC_PREFIX + plan_id] = json.dumps(merged, ensure_ascii=False)
            print(f"   已存在計畫 id={plan_id[:12]}，合併後 {len(merged)} 筆")
        else:
            # 建立新計畫
            plan_id = "plan_csv_" + hashlib.md5(ticker.encode()).hexdigest()[:8]
            new_plan = {
                "id":             plan_id,
                "ticker":         ticker,
                "name":           csv_plan["name"],
                "mkt":            "tw" if ticker.isdigit() else "us",
                "tag":            "etf" if ticker.startswith("00") else "other",
                "cycle":          "monthly",
                "cycleDay":       26,
                "initialAmount":  csv_plan["records"][0]["amount"] if csv_plan["records"] else 3000,
                "amountHistory":  [{
                    "effectiveDate": csv_plan["records"][0]["date"] if csv_plan["records"] else "2023-01-01",
                    "amount":        csv_plan["records"][0]["amount"] if csv_plan["records"] else 3000,
                    "note":          "CSV匯入建立"
                }],
                "start":          csv_plan["records"][0]["date"] if csv_plan["records"] else "2023-01-01",
                "createdAt":      today,
            }
            existing_plans.append(new_plan)
            new_ls[REC_PREFIX + plan_id] = json.dumps(csv_plan["records"], ensure_ascii=False)
            print(f"   新建計畫 id={plan_id}，共 {len(csv_plan['records'])} 筆")
        print()

    # 更新計畫清單
    new_ls[PLANS_KEY] = json.dumps(existing_plans, ensure_ascii=False)

    # ── 存 sync JSON（除錯用）────────────────────────
    SYNC_FILE.write_text(
        json.dumps(new_ls, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"💾 同步資料已存至 {SYNC_FILE.name}")

    # ── 注入 HTML ────────────────────────────────────
    new_html = inject_ls_to_html(html, new_ls)
    HTML_FILE.write_text(new_html, encoding="utf-8")
    print(f"✅ 已更新 {HTML_FILE.name}")

    # ── 摘要 ─────────────────────────────────────────
    total_recs = sum(
        len(json.loads(new_ls.get(REC_PREFIX + p["id"], "[]")))
        for p in existing_plans
    )
    print(f"\n{'─'*52}")
    print(f"  完成！共 {len(existing_plans)} 個計畫，{total_recs} 筆紀錄已同步")
    print(f"  開啟 {HTML_FILE.name} 即可看到最新資料")
    print(f"{'─'*52}\n")


if __name__ == "__main__":
    main()
