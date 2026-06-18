# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

# ==========================================
# 🛠️ 設定：Discord Webhook URL
# ==========================================
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"

def get_kabutan_news():
    """株探の最新ニュースを直接スクレイピングする（最も確実な方法）"""
    url = "https://kabutan.jp/news/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        # 文字化け防止対策
        response.encoding = response.apparent_encoding
        
        soup = BeautifulSoup(response.content, "html.parser")
        news_list = []
        
        # 株探のニュース一覧から上位3件を取得
        for item in soup.select("table.news_list tr")[:3]:
            a_tag = item.select_one("td.news_title a")
            if not a_tag:
                continue
                
            title = a_tag.get_text(strip=True)
            link = "https://kabutan.jp" + a_tag["href"]
            news_list.append({"title": title, "link": link})
            
        return news_list
    except Exception as e:
        print(f"データ取得エラー: {e}")
        return []

def main():
    # 日本時間に変換
    jst_now = datetime.now(timezone(timedelta(hours=9)))
    
    # メッセージの土台作成
    message_content = f"🌅 **【朝7時：日本株影響ニュース】** ({jst_now.strftime('%Y/%m/%d')})\n\n"
    
    # 株探から最新のニュース情報を取得
    news = get_kabutan_news()
    
    if not news:
        message_content += "⚠️ 本日はニュースの取得に失敗しました。サイトのメンテナンスか構造変更の可能性があります。"
    else:
        message_content += "📦 **株探（Kabutan） 最新注目ニュース**\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        for i, item in enumerate(news, 1):
            # 簡易的に読みやすい3行構成にします
            message_content += f"📌 **{item['title']}**\n"
            message_content += f" 📝 ① 概要: 本日の注目材料・市場ニュース\n"
            message_content += f" 📝 ② 影響: 個別銘柄の物色や地合いへの波及に注目\n"
            message_content += f"🔗 リンク: {item['link']}\n\n"

    # Discordに送信
    response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message_content})
    if response.status_code == 204:
        print("✅ Discord送信完了しました！")
    else:
        print(f"❌ Discord送信エラー: {response.status_code}")

if __name__ == "__main__":
    main()
