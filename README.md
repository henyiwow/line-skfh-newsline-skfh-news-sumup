# LINE News Broadcast

每日自動抓取台灣金融保險新聞，分類整理並推播至 LINE。

## 特性

- 每則新聞摘要 100 字內
- 類別：新光金控 → 台新金控 → 金控 → 保險 → 其他
- 自動排除非台灣新聞、不良關鍵字
- 自動截斷超過 LINE 限制長度

## 使用方式

1. Fork 本 repo
2. 在 GitHub 儲存庫設定中新增 Secrets：
   - `LINE_TOKEN`：你的 LINE Bot Access Token
3. 自動排程每天執行，無須人工操作
