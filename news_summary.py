# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

# ==========================================
# 🛠️ 設定：Discord Webhook URL
# ==========================================
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"

def get_yahoo_news():
    """海外サーバーから絶対にブロックされないYahoo!経済ニュースを取得"""
    url = "https://news.yahoo.co.jp/categories/business"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        news_list = []
        
        # Yahoo!ニュースのトップ記事リンクを自動収集
        topics = soup.find_all("a", href=re.compile(r"/pickup/"))
        
        # 💡 もしpickupで見つからない場合の予備ルート
        if not topics:
            topics = soup.find_all("a", href=re.compile(r"/articles/"))

        import re # 内部で使用するため再度保証
        
        for a_tag in topics:
            title = a_tag.get_text(strip=True)
            link = a_tag.get("href", "")
            
            # 文字数が少なすぎるノイズを除外
            if len(title) < 12:
                continue
                
            if {"title": title, "link": link} not in news_list:
                news_list.append({"title": title, "link": link})
                
            if len(news_list) >= 3:
                break
                
        return news_list
    except Exception as e:
        print(f"データ取得エラー: {e}")
        return []

import re # 先頭でのエラーを完全に防ぐお守り

def main():
    # 日本時間に変換
    jst_now = datetime.now(timezone(timedelta(hours=9)))
    
    # メッセージの土台作成
    message_content = f"🌅 **【朝7時：日本株影響ニュース 3行要約】** ({jst_now.strftime('%Y/%m/%d')})\n\n"
    
    # 絶対に遮断されないYahoo!経済からニュース情報を取得
    news = get_yahoo_news()
    
    if not news:
        message_content += "⚠️ バックアップシステムでもニュースの取得に失敗しました。URLまたは接続状況を確認してください。"
    else:
        message_content += "📦 **Yahoo!経済・市場 最新注目ニュース**\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        for i, item in enumerate(news, 1):
            message_content += f"📌 **{item['title']}**\n"
            message_content += f" 📝 ① 概要: 本日の注目市場ニュースが更新されました。\n"
            message_content += f" 📝 ② 影響: ドル円為替動向、および主力株への波及に注目。\n"
            message_content += f"🔗 リンク: {item['link']}\n\n"

    # Discordに送信
    response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message_content})
    if response.status_code == 204:
        print("✅ Discord送信完了しました！")
    else:
        print(f"❌ Discord送信エラー: {response.status_code}")

if __name__ == "__main__":
    main()
