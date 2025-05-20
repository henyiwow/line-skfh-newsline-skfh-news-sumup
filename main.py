import feedparser
import requests
from newspaper import Article
from datetime import datetime, timedelta
from urllib.parse import quote
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
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

def get_summary_from_url(url, max_sentences=3):
    try:
        print(f"📰 嘗試抓取摘要: {url}")
        article = Article(url)
        article.download()
        article.parse()
        text = article.text

        if not text.strip():
            print("⚠️ 無內文可摘要")
            return None

        parser = PlaintextParser.from_string(text, Tokenizer("chinese"))
        summarizer = LsaSummarizer()
        summary_sentences = summarizer(parser.document, max_sentences)
        summary = " ".join(str(s) for s in summary_sentences)
        trimmed_summary = summary.strip()[:100]
        print(f"✅ 摘要完成: {trimmed_summary}")
        return trimmed_summary
    except Exception as e:
        print(f"❌ 摘要失敗: {e}")
        return None

def send_line_notify(message):
    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"}
    data = {"message": message}
    response = requests.post(url, headers=headers, data=data)
    print(f"\n📬 發送 LINE Notify 狀態碼：{response.status_code}")
    print(f"📨 回應內容：{response.text}")

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

            summary = get_summary_from_url(entry.link)
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


