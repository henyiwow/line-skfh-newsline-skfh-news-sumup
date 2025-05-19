import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import email.utils
from urllib.parse import quote
import requests
import hashlib

# 環境變數
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
print("✅ Access Token 前 10 碼：", ACCESS_TOKEN[:10] if ACCESS_TOKEN else "未設定")

# 時區
TW_TZ = timezone(timedelta(hours=8))
now = datetime.now(TW_TZ)
today = now.date()

# 類別排序
CATEGORY_ORDER = ["新光金控", "台新金控", "金控", "保險", "其他"]

# 關鍵字分類
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
            return "line://" + res.text.strip().replace("https://", "").replace("http://", "")
    except Exception as e:
        print("⚠️ 短網址失敗：", e)
    return long_url

def classify_news(title):
    title = title.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw.lower() in title for kw in keywords):
            return category
    return "其他"

def is_taiwan_news(source_name, link):
    tw_sources = ['工商時報', '中國時報', '經濟日報', '三立新聞網', '自由時報', '聯合新聞網',
                  '鏡週刊', '台灣雅虎', '鉅亨網', '中時新聞網','Ettoday新聞雲',
                  '天下雜誌', '奇摩新聞', '《現代保險》雜誌','遠見雜誌']
    if any(src in source_name for src in tw_sources) and "香港經濟日報" not in source_name:
        return True
    if '.tw' in link:
        return True
    return False

def summarize_text(text, max_length=100):
    return text[:max_length] + "..." if len(text) > max_length else text

def fetch_news():
    rss_urls = [
        "https://news.google.com/rss/search?q=新光金控+OR+新光人壽+OR+台新金控+OR+台新人壽+OR+壽險+OR+金控+OR+人壽+OR+新壽+OR+台新壽+OR+吳東進+OR+吳東亮&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    ]

    classified_news = {cat: [] for cat in CATEGORY_KEYWORDS}
    seen = set()

    for rss_url in rss_urls:
        res = requests.get(rss_url)
        if res.status_code != 200:
            continue
        root = ET.fromstring(res.content)
        for item in root.findall(".//item"):
            title_elem = item.find('title')
            link_elem = item.find('link')
            pub_elem = item.find('pubDate')
            if not title_elem or not link_elem or not pub_elem:
                continue
            title = title_elem.text.strip()
            link = link_elem.text.strip()
            pub = email.utils.parsedate_to_datetime(pub_elem.text).astimezone(TW_TZ)

            if not title or title.startswith("Google ニュース"):
                continue
            if now - pub > timedelta(hours=24):
                continue
            if any(kw in title for kw in EXCLUDED_KEYWORDS):
                continue

            source_elem = item.find('source')
            source = source_elem.text.strip() if source_elem is not None else "未標示"
            if not is_taiwan_news(source, link):
                continue
            uid = hashlib.md5(link.encode()).hexdigest()
            if uid in seen:
                continue
            seen.add(uid)

            category = classify_news(title)
            short_link = shorten_url(link)
            summary = summarize_text(title)
            classified_news[category].append(f"📰 {summary}\n📌 來源：{source}\n🔗 {short_link}")

    return classified_news

def send_to_line(messages):
    url = 'https://api.line.me/v2/bot/message/broadcast'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {ACCESS_TOKEN}'
    }
    for msg in messages:
        data = {"messages": [{"type": "text", "text": msg}]}
        res = requests.post(url, headers=headers, json=data)
        print(f"📤 發送中：{len(msg)} 字元；狀態：{res.status_code}")

def format_and_send(news_dict):
    max_len = 4000
    combined = []

    for cat in CATEGORY_ORDER:
        articles = news_dict.get(cat, [])
        if not articles:
            continue
        combined.append(f"\n【{cat}】共{len(articles)}則")
        combined.extend(articles)

    full_text = f"【{today} 業企部 今日新聞整理】\n" + "\n\n".join(combined)
    segments = [full_text[i:i+max_len] for i in range(0, len(full_text), max_len)]
    send_to_line(segments)

if __name__ == "__main__":
    news = fetch_news()
    if any(news.values()):
        format_and_send(news)
    else:
        print("⚠️ 無符合條件的新聞，不發送。")
