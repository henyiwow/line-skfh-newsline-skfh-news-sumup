import os
import feedparser
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup
from summa import summarizer

ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
print("✅ Access Token 前 10 碼：", ACCESS_TOKEN[:10] if ACCESS_TOKEN else "未設定")

TW_TZ = timezone(timedelta(hours=8))
now = datetime.now(TW_TZ)
today = now.date()

RSS_URLS = [
    "https://news.google.com/rss/search?q=新光金控+OR+新光人壽+OR+台新金控+OR+台新人壽+OR+壽險+OR+金控+OR+人壽+OR+新壽+OR+台新壽+OR+吳東進+OR+吳東亮&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "https://news.google.com/rss/search?q=新光金控+OR+新光人壽+OR+新壽+OR+吳東進&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "https://news.google.com/rss/search?q=台新金控+OR+台新人壽+OR+台新壽+OR+吳東亮&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "https://news.google.com/rss/search?q=壽險+OR+健康險+OR+意外險+OR+人壽&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "https://news.google.com/rss/search?q=金控+OR+金融控股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
]

EXCLUDED_KEYWORDS = ['保險套', '避孕套', '保險套使用', '太陽人壽', '大西部人壽', '美國海岸保險']
TAIWAN_SOURCES = [
    '工商時報', '中國時報', '經濟日報', '三立新聞網', '自由時報', '聯合新聞網',
    '鏡週刊', '台灣雅虎', '鉅亨網', '中時新聞網', 'Ettoday新聞雲',
    '天下雜誌', '奇摩新聞', '《現代保險》雜誌', '遠見雜誌'
]

def shorten_url(long_url):
    try:
        encoded_url = quote(long_url, safe='')
        res = requests.get(f"http://tinyurl.com/api-create.php?url={encoded_url}", timeout=5)
        return res.text.strip() if res.status_code == 200 else long_url
    except:
        return long_url

def is_taiwan_news(source, link):
    if any(src in source for src in TAIWAN_SOURCES) and "香港經濟日報" not in source:
        return True
    if ".tw" in link:
        return True
    return False

def fetch_article_content(url):
    try:
        res = requests.get(url, timeout=10)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')
        selectors = [
            'article', 'div.article-content', 'div#article-body',
            'div#content', 'div[itemprop="articleBody"]', 'div.story-content',
            'section.article',
        ]
        text = ""
        for sel in selectors:
            content = soup.select_one(sel)
            if content:
                text = content.get_text(separator='\n').strip()
                if len(text) > 200:
                    break
        if not text:
            text = soup.get_text(separator='\n').strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)
    except:
        return ""

def summarize_text(text, max_words=100):
    try:
        return summarizer.summarize(text, words=max_words)
    except:
        return text[:max_words]

def fetch_all_news():
    results = []
    for url in RSS_URLS:
        feed = feedparser.parse(url)
        print(f"✅ RSS: {url} 共 {len(feed.entries)} 筆")
        for entry in feed.entries:
            title = entry.title.strip()
            link = entry.link.strip()
            pub_date = entry.published_parsed
            source = entry.get('source', {}).get('title', '未知來源')
            if not pub_date:
                continue
            pub_dt = datetime(*pub_date[:6], tzinfo=timezone.utc).astimezone(TW_TZ)
            if now - pub_dt > timedelta(hours=24):
                continue
            if any(bad_kw in title for bad_kw in EXCLUDED_KEYWORDS):
                continue
            if not is_taiwan_news(source, link):
                continue
            short_link = shorten_url(link)
            full_text = fetch_article_content(link)
            summary = summarize_text(full_text, max_words=100) or title
            results.append(
                f"📰 {title}\n📌 來源：{source}\n✍️ 摘要：{summary}\n🔗 {short_link}"
            )
    return results

def send_news_message(news_list):
    if not news_list:
        print("⚠️ 無符合條件的新聞，不發送。")
        return
    message = f"【{today} 業企部 今日重點新聞整理】 共{len(news_list)}則\n\n"
    message += "\n\n".join(news_list)
    if len(message) > 4000:
        message = message[:4000]
        print("⚠️ 超出 4000 字元限制，訊息已截斷")
    broadcast_message(message)

def broadcast_message(message):
    if not ACCESS_TOKEN:
        print("⚠️ ACCESS_TOKEN 未設定，無法發送訊息")
        return
    url = 'https://api.line.me/v2/bot/message/broadcast'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {ACCESS_TOKEN}'
    }
    data = {
        "messages": [{"type": "text", "text": message}]
    }
    print(f"📤 發送訊息字數：{len(message)}")
    res = requests.post(url, headers=headers, json=data)
    print(f"📤 LINE 回應狀態碼：{res.status_code}")
    print(f"📤 LINE 回應內容：{res.text}")

if __name__ == "__main__":
    news_items = fetch_all_news()
    send_news_message(news_items)


