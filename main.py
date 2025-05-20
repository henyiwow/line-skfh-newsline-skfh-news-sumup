import feedparser
import requests
from datetime import datetime, timedelta
from urllib.parse import quote
from config import LINE_NOTIFY_TOKEN

# 關鍵字排序優先順序
KEYWORDS_ORDER = [
    "新光人壽", "新光金控", "台新人壽", "台新金控",
    "金控", "人壽", "壽險", "健康險", "意外險"
]

# RSS 搜尋格式：Google News + 昨日日期
yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
GOOGLE_NEWS_URL = "https://news.google.com/rss/search?q={query}+after:{date}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"

def fetch_news(keyword):
    query = quote(keyword)
    url = GOOGLE_NEWS_URL.format(query=query, date=yesterday)
    print(f"\n🔍 正在抓取：{keyword}\nRSS網址: {url}")
    feed = feedparser.parse(url)
    print(f"📄 找到 {len(feed.entries)} 則新聞")
    return feed.entries

def send_line_notify(message):
    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"}
    data = {"message": message}
    response = requests.post(url, headers=headers, data=data)
    print(f"\n📬 發送 LINE Notify 狀態碼：{response.status_code}")
    print(f"📨 回應內容：{response.text}")

def clean_summary(summary):
    import re
    # 移除 HTML tag、限制字數 100 字
    text = re.sub('<[^<]+?>', '', summary)
    return text.strip().replace('\n', '').replace('\r', '')[:100]

def main():
    seen_links = set()
    final_message = None

    for keyword in KEYWORDS_ORDER:
        entries = fetch_news(keyword)
        for entry in entries:
            if entry.link in seen_links:
                continue
            seen_links.add(entry.link)

            print(f"\n🔗 新聞標題：{entry.title}")
            print(f"🔗 新聞連結：{entry.link}")

            if hasattr(entry, 'summary'):
                summary = clean_summary(entry.summary)
                if summary:
                    final_message = f"📢【{keyword}】\n{summary}\n👉 {entry.link}"
                    break
        if final_message:
            break

    if final_message:
        print(f"\n🚀 準備發送的 LINE 訊息：\n{final_message}")
        send_line_notify(final_message)
    else:
        print("\n⚠️ 無符合條件新聞，發送預設訊息")
        send_line_notify("📢 今日無符合新聞")

if __name__ == "__main__":
    main()
