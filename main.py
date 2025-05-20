import feedparser
import requests
import re
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
from summa import summarizer

LINE_ACCESS_TOKEN = '你的 LINE Access Token'
EXCLUDED_KEYWORDS = ['徵才', '招聘', '職缺', '兼職', '門市', '培訓', '粗工', '按摩']
CATEGORY_KEYWORDS = {
    '新光金控': ['新光金控', '新光人壽', '新壽', '吳東進'],
    '台新金控': ['台新金控', '台新人壽', '台新壽', '吳東亮'],
    '金控': ['金控', '金融控股'],
    '保險': ['壽險', '健康險', '意外險', '人壽'],
}
CATEGORY_ORDER = ['新光金控', '台新金控', '金控', '保險', '其他']

def is_taiwan_news(source_name, link):
    # 暫時允許所有新聞來源，方便 debug
    return True

def shorten_url(url):
    try:
        resp = requests.post("https://cleanuri.com/api/v1/shorten", data={"url": url}, timeout=10)
        if resp.ok:
            return resp.json().get("result_url")
    except:
        pass
    return url

def resolve_google_news_url(url):
    if 'news.google.com/rss/articles/' in url:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            og_url = soup.find('meta', property='og:url')
            if og_url:
                return og_url['content']
        except:
            pass
    return url

def fetch_news(feed_urls):
    all_news = []
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    processed_links = set()

    for url in feed_urls:
        print(f"✅ 來源: {url}", end=' ')
        resp = requests.get(url)
        print(f"回應狀態：{resp.status_code}")
        d = feedparser.parse(resp.text)
        print(f"✅ 從 {url} 抓到 {len(d.entries)} 筆新聞")

        for entry in d.entries:
            title = entry.title
            link = entry.link
            source_name = entry.get('source', {}).get('title', '')
            pub_date = entry.get('published', '') or entry.get('pubDate', '')
            try:
                pub_datetime = datetime(*entry.published_parsed[:6])
            except:
                pub_datetime = today  # 預設今天

            print(f"📰 標題: {title}")
            print(f"    來源: {source_name}")
            print(f"    發布時間: {pub_datetime}")

            # 檢查來源
            if not is_taiwan_news(source_name, link):
                print(f"    🛑 跳過：非台灣來源 ({source_name})")
                continue

            # 檢查黑名單關鍵字
            if any(bad_kw in title for bad_kw in EXCLUDED_KEYWORDS):
                print(f"    🛑 跳過：包含排除關鍵字")
                continue

            # 檢查時間
            if pub_datetime < yesterday:
                print(f"    🛑 跳過：非近24小時")
                continue

            # 解析原始連結
            original_url = resolve_google_news_url(link)
            if original_url in processed_links:
                print(f"    🛑 跳過：重複新聞")
                continue
            processed_links.add(original_url)

            # 抓取原文摘要
            try:
                resp = requests.get(original_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
                soup = BeautifulSoup(resp.text, 'html.parser')
                paragraphs = [p.get_text() for p in soup.find_all('p')]
                full_text = '\n'.join(paragraphs)
                summary = summarizer.summarize(full_text, words=100)
                if not summary:
                    raise ValueError("空摘要")
                summary = re.sub(r'\s+', ' ', summary.strip())
                short_url = shorten_url(original_url).replace("https://", "line://")  # 防止 preview
                all_news.append((title, summary, short_url))
                print(f"    ✅ 加入：{title}")
            except Exception as e:
                print(f"    ⚠️ 抓取/摘要失敗: {e}")

    return all_news

def classify_news(news_list):
    categories = {cat: [] for cat in CATEGORY_ORDER}
    for title, summary, url in news_list:
        assigned = False
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in title for kw in keywords):
                categories[cat].append((title, summary, url))
                assigned = True
                break
        if not assigned:
            categories['其他'].append((title, summary, url))
    return categories

def format_message(categories):
    date_str = datetime.now().strftime("%Y-%m-%d")
    message_parts = []
    for cat in CATEGORY_ORDER:
        items = categories[cat]
        if not items:
            continue
        header = f"【{date_str} 業企部 今日【{cat}】重點新聞整理】"
        body = '\n\n'.join([f"🔸{title}\n📝{summary}\n👉{url}" for title, summary, url in items])
        message = f"{header}\n\n{body}"
        if len(message) > 4800:
            message = message[:4790] + "\n...(訊息過長已截斷)"
        message_parts.append(message)
    return message_parts

def send_line_message(messages):
    for msg in messages:
        headers = {
            "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        data = {
            "messages": [{"type": "text", "text": msg}]
        }
        response = requests.post("https://api.line.me/v2/bot/message/broadcast", headers=headers, json=data)
        print(f"📤 發送結果：{response.status_code} - {response.text}")

if __name__ == "__main__":
    print(f"✅ Access Token 前 10 碼： {LINE_ACCESS_TOKEN[:10]}")
    RSS_FEEDS = [
        "https://news.google.com/rss/search?q=新光金控+OR+新光人壽+OR+台新金控+OR+台新人壽+OR+壽險+OR+金控+OR+人壽+OR+新壽+OR+台新壽+OR+吳東進+OR+吳東亮&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
        "https://news.google.com/rss/search?q=新光金控+OR+新光人壽+OR+新壽+OR+吳東進&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
        "https://news.google.com/rss/search?q=台新金控+OR+台新人壽+OR+台新壽+OR+吳東亮&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
        "https://news.google.com/rss/search?q=壽險+OR+健康險+OR+意外險+OR+人壽&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
        "https://news.google.com/rss/search?q=金控+OR+金融控股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    ]
    news = fetch_news(RSS_FEEDS)
    if not news:
        print("⚠️ 無符合條件的新聞，不發送。")
    else:
        categories = classify_news(news)
        messages = format_message(categories)
        send_line_message(messages)
