import feedparser
import requests
from datetime import datetime, timedelta
from urllib.parse import quote
from config import LINE_CHANNEL_ACCESS_TOKEN

KEYWORDS_ORDER = [
    "新光人壽", "新光金控", "台新人壽", "台新金控",
    "金控", "人壽", "壽險", "健康險", "意外險"
]

yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
GOOGLE_NEWS_URL = "https://news.google.com/rss/search?q={query}+after:{date}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"

def fetch_news(keyword):
    query = quote(keyword)
    url = GOOGLE_NEWS_URL.format(query=query, date=yesterday)
    print(f"🔍 抓取 {keyword}：{url}")
    feed = feedparser.parse(url)
    print(f"📰 {len(feed.entries)} 筆")
    return feed.entries

def clean_summary(summary):
    import re
    text = re.sub('<[^<]+?>', '', summary)
    return text.strip().replace('\n', '').replace('\r', '')[:100]

def send_line_message(message):
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    payload = {
        "messages": [{
            "type": "text",
            "text": message
        }]
    }
    response = requests.post(url, headers=headers, json=payload)
    print(f"📬 傳送 LINE 回應：{response.status_code} - {response.text}")

def main():
    seen_links = set()
    final_message = None

    for keyword in KEYWORDS_ORDER:
        entries = fetch_news(keyword)
        for entry in entries:
            if entry.link in seen_links:
                continue
            seen_links.add(entry.link)

            if hasattr(entry, 'summary'):
                summary = clean_summary(entry.summary)
                if summary:
                    final_message = f"📢【{keyword}】\n{summary}\n👉 {entry.link}"
                    break
        if final_message:
            break

    if final_message:
        send_line_message(final_message)
    else:
        send_line_message("📢 今日無符合新聞")

if __name__ == "__main__":
    main()
