# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone, timedelta

# ==========================================
# 🛠️ 設定
# ==========================================
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"

def get_kabutan_news():
    """株探の最新ニュースを直接スクレイピングする（RSSより確実）"""
    url = "https://kabutan.jp/news/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        news_list = []
        # 株探のニュースリスト構造を解析
        for item in soup.select("ul.news_list li")[:3]:
            title = item.select_one("a").get_text(strip=True)
            link = "https://kabutan.jp" + item.select_one("a")["href"]
            news_list.append({"title": title, "link": link})
        return news_list
    except:
        return []

def main():
    jst_now = datetime.now(timezone(timedelta(hours=9)))
    
    # メッセージ構築
    message_content = f"🌅 **【朝7時：日本株影響ニュース】** ({jst_now.strftime('%Y/%m/%d')})\n\n"
    
    # ニュース取得
    news = get_kabutan_news()
    
    if not news:
        message_content += "⚠️ 本日はニュースの取得に失敗しました。サイトの構造が変更された可能性があります。"
    else:
        message_content += "📦 **株探 最新ニュース**\n"
        for item in news:
            message_content += f"📌 **{item['title']}**\n🔗 {item['link']}\n\n"

    # Discord送信
    requests.post(DISCORD_WEBHOOK_URL, json={"content": message_content})
    print("✅ Discord送信完了")

if __name__ == "__main__":
    main()
