# -*- coding: utf-8 -*-
import requests
import re  # 💡 認識エラーを防ぐため、一番上に移動しました
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

# ==========================================
# 🛠️ 設定：Discord Webhook URL
# ==========================================
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"

def get_kabutan_news():
    """株探のトップニュースをより確実に検知してスクレイピングする"""
    url = "https://kabutan.jp/news/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = response.apparent_encoding
        
        soup = BeautifulSoup(response.content, "html.parser")
        news_list = []
        
        # サイトの構造変更に強い汎用的なリンク抽出
        links = soup.find_all("a", href=re.compile(r"/news/"))
        
        for a_tag in links:
            title = a_tag.get_text(strip=True)
            href = a_tag.get("href", "")
            
            # 短すぎる文字や、メニュー用のリンクを除外するための安全フィルター
            if len(title) < 10 or "開示情報" in title or "市場ニュース" in title:
                continue
                
            link = "https://kabutan.jp" + href if href.startswith("/") else href
            
            # 重複を排除しながら最新の3件をピックアップ
            if {"title": title, "link": link} not in news_list:
                news_list.append({"title": title, "link": link})
            if len(news_list) >= 3:
                break
                
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
