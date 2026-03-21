# 📋 Portfolio 雲端自動化 — 完整設定步驟
# 適用：已有 GitHub 帳號 · 數字密碼保護 · 2026/03/21

---

## 🗂 上傳前先在電腦整理好資料夾結構

```
Portfolio/                            ← Repository 根目錄
├── index.html                        ← 密碼保護登入頁
├── sync_dca.py                       ← DCA 同步腳本
│
├── .github/
│   └── workflows/
│       └── update.yml                ← 自動排程（路徑固定）
│
├── dashboard/
│   ├── portfolio_radar_v3.html       ← 主儀表板
│   └── dca_tracker.html             ← 定期定額追蹤
│
├── updater/
│   ├── update_prices.py
│   └── run_update.bat
│
├── data/
│   └── dca_data.csv                  ← ★ 你每月填這個 ★
│
└── logs/
    └── .gitkeep                      ← 空檔，讓資料夾存在用
```

---

## 📝 STEP 1：設定你的數字密碼

開啟 index.html，找到第 43 行：
```javascript
const HASH = '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4';
```

**換成你的密碼：**
1. 瀏覽器開啟 https://emn178.github.io/online-tools/sha256.html
2. 輸入你的 4–6 位數字密碼（如 `888888`）
3. 複製下方 64 字元的雜湊值
4. 貼回 HASH = '...' 中，儲存

> ✅ 密碼本身不會被上傳，只有雜湊值，安全無虞

---

## 📤 STEP 2：建立 GitHub Repository

1. 登入 https://github.com
2. 右上角 ＋ → **New repository**
3. 填寫：
   - Name：`Portfolio`
   - **選 Private**（⚠ 保護持倉資料）
   - 不勾選 Initialize README
4. **Create repository**

---

## 📤 STEP 3：上傳檔案（建議用 GitHub Desktop）

**下載 GitHub Desktop：** https://desktop.github.com

1. 安裝後登入你的 GitHub 帳號
2. File → **Add local repository**
3. 選擇你電腦上的 `Portfolio/` 資料夾
4. 若提示不是 git repository → 點「**create a repository**」
5. 右上角 **Publish repository**
   - 確認名稱是 `Portfolio`
   - 確認勾選 **Keep this code private**（保持私有）
6. 點 **Publish Repository** → 上傳完成

---

## ⚙️ STEP 4：啟用 GitHub Pages

1. 進入 GitHub → 你的 Portfolio repository
2. 上方 **Settings** → 左側 **Pages**
3. Source 選 **GitHub Actions**
4. 儲存

你的網址：`https://你的帳號.github.io/Portfolio/`

---

## ▶️ STEP 5：手動執行第一次更新

1. Repository → 上方 **Actions**
2. 左側「**Portfolio 每日自動更新**」
3. 右側 **Run workflow** → 綠色 **Run workflow**
4. 等待 2–3 分鐘看到 ✅ 代表成功

---

## 📱 STEP 6：手機加入書籤

1. 手機瀏覽器開啟網址
2. 輸入你設定的數字密碼進入
3. iOS：分享 → 加入主畫面
4. Android：右上選單 → 加至主畫面

---

## 📅 設定完成後的日常操作

### 每月一次（3 分鐘）：
1. 用 Excel 開啟 `Portfolio/data/dca_data.csv`
2. 新增一列填入本月買入資料：
   `0050, 元大台灣50, 2026-04-26, 252.5, 3000`
3. 儲存
4. GitHub Desktop → Commit → Push
5. 完成，系統自動同步

### 完全不需操作：
- 每個工作日 14:30（台灣時間）自動抓最新股價
- 手機書籤開啟即是最新

---

## 📂 檔案放置位置對照

| 下載的檔案 | GitHub 路徑 |
|-----------|------------|
| `index.html` | `Portfolio/index.html` |
| `update.yml` | `Portfolio/.github/workflows/update.yml` |
| `portfolio_radar_v3.html` | `Portfolio/dashboard/portfolio_radar_v3.html` |
| `dca_tracker.html` | `Portfolio/dashboard/dca_tracker.html` |
| `update_prices.py` | `Portfolio/updater/update_prices.py` |
| `run_update.bat` | `Portfolio/updater/run_update.bat` |
| `sync_dca.py` | `Portfolio/sync_dca.py` |
| `dca_data.csv` | `Portfolio/data/dca_data.csv` |

---

## 🆘 問題排除

| 問題 | 解決方式 |
|------|---------|
| Actions 紅色 ✕ | Actions 頁籤看 log，截圖回報 |
| 開啟 404 | 重新確認 STEP 4 Pages 設定 |
| 密碼錯誤 | 重新計算 SHA-256 確認無空格 |
| 股價沒更新 | 手動 Run workflow 一次 |
| CSV 同步失敗 | 確認 dca_data.csv 放在 data/ 資料夾 |
