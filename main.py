import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import email.utils
from urllib.parse import quote
import requests
from summa import summarizer
import jieba

# 讀 LINE Access Token
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
if not ACCESS_TOKEN:
    print("❌ ERROR: ACCESS_TOKEN 未設定，請在 GitHub Secrets 裡設定 LINE_TOKEN")
    exit(1)
print("✅ Access Token 前 10 碼：", ACCESS_TOKEN[:10])

# 預設來源
PREFERRED_SOURCES = ['工商時報', '中國時報', '經濟日報', 'Ettoday新聞雲', '工商時報網',
                     '中時新聞網', '台灣雅虎奇摩', '經濟日報網', '鉅亨網', '聯合新聞網',
                     '鏡周刊網', '自由財經', '中華日報', '台灣新生報', '旺報', '三立新聞網',
                     '天下雜誌', '奇摩新聞', '《現代保險》雜誌', 'MoneyDJ', '遠見雜誌',
                     '自由時報', 'Ettoday財經雲', '鏡週刊Mirror Media', '匯流新聞網',
                     'Newtalk新聞', '奇摩股市', 'news.cnyes.com', '中央社', '民視新聞網',
                     '風傳媒', 'CMoney', '大紀元']

# 分類關鍵字
CATEGORY_KEYWORDS = {
    "新光金控": ["新光金", "新光人壽", "新壽", "吳東進"],
    "台新金控": ["台新金", "台新人壽", "台新壽", "吳東亮"],
    "金控": ["金控", "金融控股", "中信金", "玉山金", "永豐金", "國泰金", "富邦金", "台灣金"],
    "保險": ["保險", "壽險", "健康險", "意外險", "人壽"],
    "其他": []
}

EXCLUDED_KEYWORDS = ['保險套', '避孕套', '保險套使用', '太陽人壽', '大西部人壽', '美國海岸保險']

TW_TZ = timezone(timedelta(hours=8))
now = datetime.now(TW_TZ)
today = now.strftime("%Y-%m-%d")

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
    title_lower = title.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw.lower() in title_lower for kw in keywords):
            return category
    return "其他"

def is_taiwan_news(source_name, link):
    taiwan_sources = [
        '工商時報', '中國時報', '經濟日報', '三立新聞網', '自由時報', '聯合新聞網',
        '鏡週刊', '台灣雅虎', '鉅亨網', '中時新聞網','Ettoday新聞雲',
        '天下雜誌', '奇摩新聞', '《現代保險》雜誌','遠見雜誌'
    ]
    if any(ts in source_name for ts in taiwan_sources) and "香港經濟日報" not in source_name:
        return True
    if '.tw' in link:
        return True
    return False

def get_summary(text, max_chars=100):
    # 使用 jieba 做斷詞
    words = jieba.cut(text, cut_all=False)
    text_for_sum = " ".join(words)
    try:
        summary = summarizer.summarize(text_for_sum, words=50)  # 約 50 個詞語摘要
        if not summary:
            summary = text[:max_chars]
    except:
        summary = text[:max_chars]
    # 將空白去除，並限制字數
    summary = summary.replace('\n', '').replace(' ', '')[:max_chars]
    return summary

def fetch_news():
    classified_news = {cat: [] for cat in CATEGORY_KEYWORDS}
    processed_links = set()

    for rss_url in RSS_URLS:
        try:
            res = requests.get(rss_url, timeout=10)
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
                description_elem = item.find('description')
                if None in (title_elem, link_elem, pubDate_elem, description_elem):
                    continue
                title = title_elem.text.strip()
                link = link_elem.text.strip()
                pubDate_str = pubDate_elem.text.strip()
                description = description_elem.text.strip()

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
                summary = get_summary(description, max_chars=100)

                formatted = f"📰 {title}\n摘要：{summary}\n📌 來源：{source_name}\n🔗 {short_link}"
                classified_news[category].append(formatted)

        except Exception as e:
            print(f"⚠️ 抓取RSS錯誤：{e}")

    return classified_news

def send_message(full_text):
    url = 'https://api.line.me/v2/bot/message/broadcast'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {ACCESS_TOKEN}'
    }
    data = {
        "messages": [{
            "type": "text",
            "text": full_text
        }]
    }
    print(f"📤 發送訊息總長：{len(full_text)} 字元")
    res = requests.post(url, headers=headers, json=data)
    print(f"📤 LINE 回傳狀態碼：{res.status_code}")
    print("📤 LINE 回傳內容：", res.text)

def main():
    news = fetch_news()

    # 按指定排序組合新聞
    category_order = ["新光金控", "台新金控", "金控", "保險", "其他"]
    final_msgs = []
    for cat in category_order:
        if news.get(cat):
            final_msgs.extend(news[cat])

    if not final_msgs:
        print("⚠️ 無符合條件的新聞，不發送。")
        return

    title = f"【{today} 業企部 今日重點新聞整理】 共{len(final_msgs)}則新聞"
    content = "\n\n".join(final_msgs)
    full_message = f"{title}\n\n{content}"

    # LINE訊息限制 4000 字，超過捨棄
    if len(full_message) > 4000:
        full_message = full_message[:4000]
        print("⚠️ 訊息過長，已自動截斷至4000字以內")

    send_message(full_message)

if __name__ == "__main__":
    main()


