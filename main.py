import os
import re
import feedparser
import requests
import hashlib
import base64
from datetime import datetime, timedelta
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from summa.summarizer import summarize

# === 設定區 ===
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")  # 記得在 GitHub Actions secrets 設定
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=新光金控+OR+新光人壽+OR+台新金控+OR+台新人壽+OR+壽險+OR+金控+OR+人壽+OR+新壽+OR+台新壽+OR+吳東進+OR+吳東亮&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "https://news.google.com/rss/search?q=新光金控+OR+新光人壽+OR+新壽+OR+吳東進&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "https://news.google.com/rss/search?q=台新金控+OR+台新人壽+OR+台新壽+OR+吳東亮&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "https://news.google.com/rss/search?q=壽險+OR+健康險+OR+意外險+OR+人壽&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "https://news.google.com/rss/search?q=金控+OR+金融控股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
]
EXCLUDED_KEYWORDS = ["保險套", "遊戲", "旅遊", "酒店", "電影"]
CATEGORY_KEYWORDS = {
    "新光金控": ["新光金控", "新光人壽", "新壽", "吳東進"],
    "台新金控": ["台新金控", "台新人壽", "台新壽", "吳東亮"],
    "金控": ["金控", "金融控股"],
    "保險": ["壽險", "健康險", "意外險", "保險", "人壽"],
}
CATEGORY_ORDER = ["新光金控", "台新金控", "金控", "保險", "其他"]
MAX_LINE_MESSAGE_LENGTH = 5000
SUMMARY_CHAR_LIMIT = 100


# === 工具方法 ===
def shorten_url(url):
    try:
        response = requests.post("https://cleanuri.com/api/v1/shorten", data={"url": url})
        return response.json().get("result_url", url)
    except:
        return url


def resolve_google_news_redirect(link):
    try:
        res = requests.get(link, allow_redirects=True, timeout=5)
        return res.url
    except:
        return link


def fetch_full_article(url):
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        paragraphs = soup.find_all("p")
        return " ".join(p.get_text() for p in paragraphs)
    except:
        return ""


def summarize_text(text, limit=SUMMARY_CHAR_LIMIT):
    try:
        summary = summarize(text, ratio=0.1)
        return summary.strip()[:limit] if summary else text[:limit]
    except:
        return text[:limit]


def categorize_news(title, summary):
    combined_text = title + summary
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in combined_text for kw in keywords):
            return category
    return "其他"


def should_exclude(title):
    return any(bad_kw in title for bad_kw in EXCLUDED_KEYWORDS)


# === 主流程 ===
def main():
    print(f"✅ Access Token 前 10 碼： {LINE_ACCESS_TOKEN[:10] if LINE_ACCESS_TOKEN else '未設定'}")
    all_news = []

    for url in RSS_FEEDS:
        print(f"✅ 來源: {url}", end=" ")
        feed = feedparser.parse(url)
        print(f"回應狀態：{feed.get('status', 'N/A')}")
        entries = feed.entries
        print(f"✅ 從 {url} 抓到 {len(entries)} 筆新聞")

        for entry in entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            pub_date = entry.get("published", entry.get("updated", ""))

            if not title or not link:
                continue

            parsed_time = None
            for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%SZ"):
                try:
                    parsed_time = datetime.strptime(pub_date, fmt)
                    break
                except:
                    continue
            if not parsed_time:
                continue

            now = datetime.utcnow()
            if now - parsed_time > timedelta(hours=48):  # 放寬為48小時
                print(f"⏳ 跳過：超過 48 小時 {title}")
                continue

            if should_exclude(title):
                print(f"🚫 排除關鍵字命中：{title}")
                continue

            original_url = resolve_google_news_redirect(link)
            full_article = fetch_full_article(original_url)
            summary = summarize_text(full_article)

            category = categorize_news(title, summary)
            short_url = shorten_url(original_url)
            line_url = short_url.replace("https://", "line://")

            all_news.append({
                "category": category,
                "title": title,
                "summary": summary,
                "url": line_url,
            })

    if not all_news:
        print("⚠️ 無符合條件的新聞，不發送。")
        return

    # 分類、排序
    categorized = {cat: [] for cat in CATEGORY_ORDER}
    for item in all_news:
        categorized[item["category"]].append(item)

    messages = []
    today = datetime.now().strftime("%Y-%m-%d")
    for cat in CATEGORY_ORDER:
        items = categorized[cat]
        if not items:
            continue

        header = f"【{today} 業企部 今日【{cat}】重點新聞整理】"
        lines = [header]
        for news in items:
            lines.append(f"🔹{news['title']}\n摘要：{news['summary']}\n{news['url']}")
        message = "\n\n".join(lines)
        messages.append(message)

    # 自動分段
    final_messages = []
    current = ""
    for msg in messages:
        if len(current) + len(msg) + 2 > MAX_LINE_MESSAGE_LENGTH:
            final_messages.append(current)
            current = msg
        else:
            current += "\n\n" + msg
    if current:
        final_messages.append(current)

    # 傳送
    headers = {
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    for msg in final_messages:
        data = {"messages": [{"type": "text", "text": msg.strip()}]}
        r = requests.post("https://api.line.me/v2/bot/message/broadcast", headers=headers, json=data)
        print(f"✅ 發送狀態：{r.status_code} - {r.text}")


if __name__ == "__main__":
    main()


