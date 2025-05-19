import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import email.utils
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup
import jieba
from summa import summarizer

ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
print("✅ Access Token 前 10 碼：", ACCESS_TOKEN[:10] if ACCESS_TOKEN else "未設定")

# 台灣時區
TW_TZ = timezone(timedelta(hours=8))
now = datetime.now(TW_TZ)
today = now.strftime("%Y-%m-%d")

# 分類關鍵字及排序（你指定順序）
CATEGORY_KEYWORDS = {
    "新光金控": ["新光金", "新光人壽", "新壽", "吳東進"],
    "台新金控": ["台新金", "台新人壽", "台新壽", "吳東亮"],
    "金控": ["金控", "金融控股", "中信金", "玉山金", "永豐金", "國泰金", "富邦金", "台灣金"],
    "保險": ["保險", "壽險", "健康險", "意外險", "人壽"],
    "其他": []
}
CATEGORY_ORDER = ["新光金控", "台新金控", "金控", "保險", "其他"]

EXCLUDED_KEYWORDS = ['保險套', '避孕套', '保險套使用', '太陽人壽', '大西部人壽', '美國海岸保險']

# RSS 來源
RSS_URLS = [
    "https://news.google.com/rss/search?q=新光金控+OR+新光人壽+OR+新壽+OR+吳東進&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "https://news.google.com/rss/search?q=台新金控+OR+台新人壽+OR+台新壽+OR+吳東亮&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "https://news.google.com/rss/search?q=金控+OR+金融控股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "https://news.google.com/rss/search?q=壽險+OR+健康險+OR+意外險+OR+人壽&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
]

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
    title = title.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw.lower() in title for kw in keywords):
            return category
    return "其他"

def is_taiwan_news(source_name, link):
    taiwan_sources = [
        '工商時報', '中國時報', '經濟日報', '三立新聞網', '自由時報', '聯合新聞網',
        '鏡週刊', '台灣雅虎', '鉅亨網', '中時新聞網','Ettoday新聞雲',
        '天下雜誌', '奇摩新聞', '《現代保險》雜誌','遠見雜誌'
    ]
    if any(taiwan_source in source_name for taiwan_source in taiwan_sources) and "香港經濟日報" not in source_name:
        return True
    if '.tw' in link:
        return True
    return False

def extract_text_simple(url):
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')

        article = soup.find('article')
        if article:
            text = article.get_text(separator=' ', strip=True)
        else:
            divs = soup.find_all('div')
            divs = sorted(divs, key=lambda d: len(d.get_text(strip=True)), reverse=True)
            for d in divs:
                if len(d.get_text(strip=True)) > 200:
                    text = d.get_text(separator=' ', strip=True)
                    break
            else:
                for script in soup(['script', 'style']):
                    script.decompose()
                text = soup.get_text(separator=' ', strip=True)

        return text[:5000]
    except Exception as e:
        print(f"⚠️ 讀取全文失敗: {e}")
        return ""

def summarize_text(text, max_chars=100):
    if not text:
        return "無法取得內容摘要"
    try:
        words = jieba.cut(text, cut_all=False)
        text_for_sum = " ".join(words)
        summary = summarizer.summarize(text_for_sum, words=50)
        if not summary:
            summary = text[:max_chars]
    except Exception:
        summary = text[:max_chars]
    return summary.replace('\n', '').replace(' ', '')[:max_chars]

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
            if title_elem is None or link_elem is None or pubDate_elem is None:
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
            processed_links.add(link)

            short_link = shorten_url(link)
            category = classify_news(title)

            # 抓全文+摘要
            full_text = extract_text_simple(link)
            summary = summarize_text(full_text, 100)

            formatted = f"📰 {title}\n摘要：{summary}\n🔗 {short_link}\n來源：{source_name}\n"
            classified_news[category].append(formatted)

    return classified_news

def send_line_message(message):
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

    print(f"📤 發送訊息長度：{len(message)} 字元")
    res = requests.post(url, headers=headers, json=data)
    print(f"📤 LINE 回傳狀態碼：{res.status_code}")
    print(f"📤 LINE 回傳內容：{res.text}")

def main():
    news = fetch_news()
    all_messages = []
    for cat in CATEGORY_ORDER:
        items = news.get(cat, [])
        if items:
            header = f"【{today} 業企部 今日【{cat}】重點新聞整理】 共{len(items)}則新聞\n\n"
            all_messages.append(header + "\n".join(items))

    if not all_messages:
        print("⚠️ 無符合條件的新聞，不發送。")
        return

    final_message = "\n\n".join(all_messages)
    if len(final_message) > 4000:
        print(f"⚠️ 訊息超過4000字，將截斷")
        final_message = final_message[:4000]

    send_line_message(final_message)

if __name__ == "__main__":
    main()


