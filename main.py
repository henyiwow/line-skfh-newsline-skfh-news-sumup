import os
import feedparser
import requests
from datetime import datetime, timedelta
from urllib.parse import quote
from bs4 import BeautifulSoup
from summa.summarizer import summarize
import re

LINE_TOKEN = os.getenv("ACCESS_TOKEN", "")
KEYWORDS = [
    "新光人壽", "新光金控", "台新金控", "台新人壽",
    "金控", "人壽", "壽險", "健康險", "意外險"
]

GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?q=" +
    quote(" OR ".join(KEYWORDS)) +
    "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
)

def fetch_articles(rss_url):
    feed = feedparser.parse(rss_url)
    articles = []
    for entry in feed.entries:
        published = entry.get("published_parsed")
        if not published:
            continue
        pub_time = datetime(*published[:6])
        if datetime.utcnow() - pub_time > timedelta(days=1):
            continue
        link = re.sub(r"^https://news\.google\.com/.*?&url=", "", entry.link)
        link = requests.utils.unquote(link)
        articles.append({
            "title": entry.title,
            "link": link,
            "published": pub_time,
        })
    return articles

def fetch_and_summarize_content(url, max_sentences=3):
    try:
        resp = requests.get(url, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        texts = soup.stripped_strings
        raw_text = " ".join(texts)
        summary = summarize(raw_text, words=100)
        summary = re.sub(r"\s+", " ", summary).strip()
        return summary[:100] if summary else None
    except Exception:
        return None

def classify_by_priority(article):
    text = f"{article['title']}"
    for keyword in KEYWORDS:
        if keyword in text:
            return KEYWORDS.index(keyword)
    return len(KEYWORDS)

def format_message(articles):
    sorted_articles = sorted(articles, key=classify_by_priority)
    lines = []
    for article in sorted_articles:
        summary = fetch_and_summarize_content(article["link"])
        if summary:
            line = f"【{article['title']}】\n{summary}\n👉 {article['link']}\n"
            lines.append(line)
    message = "\n".join(lines)
    return message[:3900] if len(message) > 3900 else message

def send_line_message(message):
    if not LINE_TOKEN:
        print("⚠️ ACCESS_TOKEN 未設定，無法發送訊息")
        return
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messages": [{"type": "text", "text": message}]
    }
    res = requests.post("https://api.line.me/v2/bot/message/broadcast", headers=headers, json=payload)
    print("✅ 發送狀態:", res.status_code, res.text)

def main():
    print("✅ 取得 RSS 中...")
    articles = fetch_articles(GOOGLE_NEWS_RSS)
    print(f"✅ 過濾後的台灣新聞共 {len(articles)} 則")
    if not articles:
        print("⚠️ 沒有新聞可供發送")
        return
    message = format_message(articles)
    if message:
        send_line_message(message)
    else:
        print("⚠️ 無有效摘要可發送")

if __name__ == "__main__":
    main()


