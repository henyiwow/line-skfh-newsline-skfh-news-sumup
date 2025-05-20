import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import email.utils
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup
from summa import summarizer

# 設定 ACCESS_TOKEN
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
print("✅ Access Token 前 10 碼：", ACCESS_TOKEN[:10] if ACCESS_TOKEN else "未設定")

TW_TZ = timezone(timedelta(hours=8))
now = datetime.now(TW_TZ)
today = now.date()

# RSS 來源
RSS_URLS = [
    "https://news.google.com/rss/search?q=新光金控+OR+新光人壽+OR+台新金控+OR+台新人壽+OR+壽險+OR+金控+OR+人壽+OR+新壽+OR+台新壽+OR+吳東進+OR+吳東亮&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "https://news.google.com/rss/search?q=新光金控+OR+新光人壽+OR+新壽+OR+吳東進&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "https://news.google.com/rss/search?q=台新金控+OR+台新人壽+OR+台新壽+OR+吳東亮&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "https://news.google.com/rss/search?q=壽險+OR+健康險+OR+意外險+OR+人壽&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "https://news.google.com/rss/search?q=金控+OR+金融控股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
]

CATEGORY_ORDER = ["新光金控", "台新金控", "金控", "保險", "其他"]
CATEGORY_KEYWORDS = {
    "新光金控": ["新光金", "新光人壽", "新壽", "吳東進"],
    "台新金控": ["台新金", "台新人壽", "台新壽", "吳東亮"],
    "金控": ["金控", "金融控股", "中信金", "玉山金", "永豐金", "國泰金", "富邦金", "台灣金"],
    "保險": ["保險", "壽險", "健康險", "意外險", "人壽"],
    "其他": []
}

EXCLUDED_KEYWORDS = ['保險套', '避孕套', '保險套使用', '太陽人壽', '大西部人壽', '美國海岸保險']

def shorten_url(long_url):
    try:
        encoded_url = quote(long_url, safe='')
        api_url = f"http://tinyurl.com/api-create.php?url={encoded_url}"
        res = requests.get(api_url, timeout=5)
        if res.status_code == 200:
            return res.text.strip()
    except Exception as e:
        print("⚠️ 短網址失敗：", e)
    return long_url

def classify_news(title):
    title_lower = title.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw.lower() in title_lower for kw in keywords):
            return category
    return "其他"

def is_taiwan_news(source_name, link):
    taiwan_sources = [
        '工商時報', '中國時報', '經濟日報', '三立新聞網', '自由時報', '聯合新聞網',
        '鏡週刊', '台灣雅虎', '鉅亨網', '中時新聞網', 'Ettoday新聞雲',
        '天下雜誌', '奇摩新聞', '《現代保險》雜誌', '遠見雜誌'
    ]
    if any(src in source_name for src in taiwan_sources) and "香港經濟日報" not in source_name:
        return True
    if '.tw' in link:
        return True
    return False

def resolve_redirect_url(url):
    try:
        res = requests.head(url, allow_redirects=True, timeout=5)
        return res.url
    except Exception as e:
        print(f"⚠️ 解析跳轉連結失敗: {e}")
        return url

def fetch_article_content(url):
    try:
        res = requests.get(url, timeout=10)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')

        selectors = [
            'article',
            'div.article-content',
            'div#article-body',
            'div#content',
            'div[itemprop="articleBody"]',
            'div.story-content',
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
        cleaned_text = "\n".join(lines)
        return cleaned_text
    except Exception as e:
        print(f"⚠️ 抓取文章內容失敗: {e}")
        return ""

def summarize_text(text, max_words=100):
    try:
        return summarizer.summarize(text, words=max_words)
    except Exception as e:
        print(f"⚠️ 摘要失敗: {e}")
        return text[:max_words]

def fetch_news():
    classified_news = {cat: [] for cat in CATEGORY_KEYWORDS}
    processed_links = set()

    for rss_url in RSS_URLS:
        res = requests.get(rss_url)
        print(f"✅ 來源: {rss_url} 回應狀態：{res.status_code}")
        if res.status_code != 200:
            continue

        root = ET.fromstring(res.content)
        items = root.findall(".//item")
        print(f"✅ 從 {rss_url} 抓到 {len(items)} 筆新聞")

        for item in items:
            title_elem = item.find('title')
            link_elem = item.find('link')
            pubDate_elem = item.find('pubDate')
            if not title_elem or not link_elem or not pubDate_elem:
                continue

            title = title_elem.text.strip()
            link = link_elem.text.strip()
            pubDate_str = pubDate_elem.text.strip()
            if not title or title.startswith("Google ニュース"):
                continue

            source_elem = item.find('source')
            source_name = source_elem.text.strip() if source_elem is not None else "未標示"
            pub_datetime = email.utils.parsedate_to_datetime(pubDate_str).astimezone(TW_TZ)

            if now - pub_datetime > timedelta(hours=24):
                continue

            if any(bad_kw in title for bad_kw in EXCLUDED_KEYWORDS):
                continue
            if not is_taiwan_news(source_name, link):
                continue
            if link in processed_links:
                continue

            # 處理 Google News 跳轉連結
            if "news.google.com/rss/articles" in link:
                original_link = resolve_redirect_url(link)
                if original_link != link:
                    print(f"🔗 已解析原始連結：{original_link}")
                    link = original_link

            processed_links.add(link)

            short_link = shorten_url(link)
            full_text = fetch_article_content(link)
            summary = summarize_text(full_text, max_words=100)
            if not summary:
                summary = title

            category = classify_news(title)
            formatted = (
                f"📰 {title}\n"
                f"📌 來源：{source_name}\n"
                f"✍️ 摘要：{summary}\n"
                f"🔗 {short_link}"
            )
            classified_news[category].append(formatted)

    return classified_news

def send_message(news_by_category):
    max_length = 4000
    ordered_news = []
    for cat in CATEGORY_ORDER:
        ordered_news.extend(news_by_category.get(cat, []))

    if not ordered_news:
        print("⚠️ 無符合條件的新聞，不發送。")
        return

    message = f"【{today} 業企部 今日重點新聞整理】 共{len(ordered_news)}則新聞\n\n"
    message += "\n\n".join(ordered_news)
    if len(message) > max_length:
        message = message[:max_length]
        print(f"⚠️ 訊息超過 {max_length} 字，已截斷")

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
        "messages": [{
            "type": "text",
            "text": message
        }]
    }
    print(f"📤 發送訊息總長：{len(message)} 字元")
    res = requests.post(url, headers=headers, json=data)
    print(f"📤 LINE 回傳狀態碼：{res.status_code}")
    print("📤 LINE 回傳內容：", res.text)

if __name__ == "__main__":
    news = fetch_news()
    send_message(news)
