import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import email.utils
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup
import jieba
from summa import summarizer

# 從環境變數取得 Access Token（確保名稱與 GitHub Actions 設定一致）
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
if ACCESS_TOKEN:
    print("✅ Access Token 前 10 碼：", ACCESS_TOKEN[:10])
else:
    print("⚠️ Access Token 未設定，無法發送訊息")

TW_TZ = timezone(timedelta(hours=8))
now = datetime.now(TW_TZ)
today = now.date()

RSS_URLS = [
    "https://news.google.com/rss/search?q=新光金控+OR+新光人壽+OR+台新金控+OR+台新人壽+OR+壽險+OR+金控+OR+人壽+OR+新壽+OR+台新壽+OR+吳東進+OR+吳東亮&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
]

KEYWORDS_ORDER = [
    "新光人壽",
    "新光金控",
    "台新金控",
    "台新人壽",
    "金控",
    "人壽",
    "壽險",
    "健康險",
    "意外險",
]

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
    news_list = []
    print("✅ 取得 RSS 中...")
    for rss_url in RSS_URLS:
        try:
            res = requests.get(rss_url, timeout=10)
            if res.status_code != 200:
                print(f"⚠️ 取得 RSS 失敗: {rss_url}")
                continue
            root = ET.fromstring(res.content)
            items = root.findall(".//item")
            print(f"✅ RSS: {rss_url} 共 {len(items)} 筆")
            for item in items:
                title_elem = item.find('title')
                link_elem = item.find('link')
                pubDate_elem = item.find('pubDate')
                source_elem = item.find('source')
                if not title_elem or not link_elem or not pubDate_elem:
                    continue
                title = title_elem.text.strip()
                link = link_elem.text.strip()
                pubDate_str = pubDate_elem.text.strip()
                source_name = source_elem.text.strip() if source_elem is not None else "未標示"
                if not title or any(bad_kw in title for bad_kw in EXCLUDED_KEYWORDS):
                    continue
                pub_datetime = email.utils.parsedate_to_datetime(pubDate_str).astimezone(TW_TZ)
                if now - pub_datetime > timedelta(hours=24):
                    continue
                if not is_taiwan_news(source_name, link):
                    continue
                # 抓文章摘要
                full_text = fetch_article_content(link)
                summary = summarize_text(full_text, max_words=100)
                if not summary:
                    summary = title
                short_link = shorten_url(link)

                # 按關鍵字排序
                keyword_found = None
                for kw in KEYWORDS_ORDER:
                    if kw in title:
                        keyword_found = kw
                        break
                if not keyword_found:
                    keyword_found = "其他"

                news_list.append((KEYWORDS_ORDER.index(keyword_found) if keyword_found in KEYWORDS_ORDER else 999,
                                  f"📰 {title}\n✍️ {summary}\n🔗 {short_link}"))
        except Exception as e:
            print("⚠️ 讀取 RSS 發生錯誤:", e)
            continue

    # 依關鍵字排序
    news_list.sort(key=lambda x: x[0])
    return [n[1] for n in news_list]

def send_message(news_list):
    if not ACCESS_TOKEN:
        print("⚠️ ACCESS_TOKEN 未設定，無法發送訊息")
        return
    if not news_list:
        print("⚠️ 無有效摘要可發送")
        return

    max_length = 4000
    message = f"【{today} 業企部 今日重點新聞整理】 共{len(news_list)}則新聞\n\n"
    message += "\n\n".join(news_list)
    if len(message) > max_length:
        message = message[:max_length]
        print(f"⚠️ 超出 {max_length} 字元限制，訊息已截斷")

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
    print(f"✅ 過濾後的台灣新聞共 {len(news)} 則")
    send_message(news)



