# -*- coding: utf-8 -*-
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

# ==========================================
# 🛠️ 設定：Discord Webhook URL
# ==========================================
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"

def get_yahoo_news_with_summary():
    """Yahoo!経済ニュースのタイトル、リンク、および簡単な本文(要約)を取得"""
    url = "https://news.yahoo.co.jp/categories/business"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        news_list = []
        
        # 経済カテゴリーの主要トピックス（pickup）のリンクを集める
        topics = soup.find_all("a", href=re.compile(r"/pickup/"))
        if not topics:
            topics = soup.find_all("a", href=re.compile(r"/articles/"))
        
        session = requests.Session()
        
        for a_tag in topics:
            title = a_tag.get_text(strip=True)
            link = a_tag.get("href", "")
            
            # ナビゲーション用の短いノイズテキストを除外
            if len(title) < 12:
                continue
                
            # 💡 ニュースの個別ページにアクセスして、本文の最初の数行(要約)を取得する
            summary_text = "詳細内容はリンク先をご確認ください。"
            try:
                detail_res = session.get(link, headers=headers, timeout=5)
                detail_soup = BeautifulSoup(detail_res.content, "html.parser")
                
                # Yahoo!ニュースの本文（リード文）が格納されているクラスを狙い撃ち
                paragraphs = detail_soup.find_all("p", class_=re.compile(r"yjmt|highLight|Paragraph"))
                if paragraphs:
                    # 最初の段落のテキストを抽出し、長すぎる場合は100文字でカット
                    summary_text = paragraphs[0].get_text(strip=True)
                    if len(summary_text) > 100:
                        summary_text = summary_text[:100] + "..."
            except Exception as e:
                print(f"詳細ページの取得失敗(スキップします): {e}")

            if {"title": title, "link": link, "summary": summary_text} not in news_list:
                news_list.append({"title": title, "link": link, "summary": summary_text})
                
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
    message_content = f"🌅 **【朝7時：日本株影響ニュース 3行要約】** ({jst_now.strftime('%Y/%m/%d')})\n\n"
    
    # ニュース情報（タイトル・リンク・本文）を取得
    news = get_yahoo_news_with_summary()
    
    if not news:
        message_content += "⚠️ ニュースの取得に失敗しました。URLまたは接続状況を確認してください。"
    else:
        message_content += "📦 **Yahoo!経済・市場 最新ニュース要約**\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        for i, item in enumerate(news, 1):
            message_content += f"📌 **{item['title']}**\n"
            message_content += f" 📝 **要約**: {item['summary']}\n"
            message_content += f"🔗 **リンク**: {item['link']}\n\n"

    # Discordに送信
    response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message_content})
    if response.status_code == 204:
        print("✅ 簡易要約付きニュースのDiscord送信が完了しました！")
    else:
        print(f"❌ Discord送信エラー: {response.status_code}")

if __name__ == "__main__":
    main()
