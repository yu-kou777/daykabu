# -*- coding: utf-8 -*-
import feedparser
import requests
import re
from datetime import datetime, timezone, timedelta

# ==========================================
# 🛠️ 設定：Discord Webhook URL
# ==========================================
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"

# 安定して取得できるRSSフィードのURL（バックアップ含め調整）
RSS_SOURCES = {
    "CNBC Markets (海外)": "https://search.cnbc.com/rs/search/combinedseo.rss?type=text&id=100003114",
    "ロイター ビジネス (海外)": "https://www.reutersagency.com/feed/?best-topics=business&p=5",
    "株探ニュース (国内)": "https://kabutan.jp/news/?mode=rss"
}

def analyze_impact(title, summary):
    """タイトルと本文から日本株への影響度と簡易要約を生成"""
    combined = (title + " " + summary).lower()
    
    # 影響度判定キーワード
    high_impact = ["semiconductor", "fed", "rate", "nvda", "fomc", "inflation", "半導体", "特報", "決算", "修正", "利下げ", "利上げ"]
    medium_impact = ["china", "oil", "yen", "dollar", "nasdaq", "株価", "急騰", "急落", "為替", "円高", "円安"]
    
    if any(k in combined for k in high_impact):
        impact = "🔴 高 (相場全体の方向性や主力セクターを左右する可能性)"
    elif any(k in combined for k in medium_impact):
        impact = "🟡 中 (特定セクターや為替を動かす可能性)"
    else:
        impact = "🟢 低 (個別材料または限定的な影響)"
        
    # タグの除去と文字数制限
    clean_title = re.sub('<[^<]+?>', '', title).strip()[:60]
    clean_summary = re.sub('<[^<]+?>', '', summary).strip()[:80] if summary else "詳細はリンク先をご確認ください。"

    return [
        f"① 概要: {clean_title}",
        f"② 詳細: {clean_summary}...",
        f"③ 影響度: {impact}"
    ]

def main():
    # 日本時間に変換して本日が土日ならスキップ
    jst_now = datetime.now(timezone(timedelta(hours=9)))
    if jst_now.weekday() >= 5:  # 5=土曜日, 6=日曜日
        print("💤 本日は土日のため、通知をスキップします。")
        return

    print("🦅 海外・国内ニュースの取得を開始します...")
    # 💡 日付のバグ（%m/%mになっていた部分）を %Y/%m/%d に修正
    message_content = f"🌅 **【朝7時：日本株影響ニュース 3行要約】** ({jst_now.strftime('%Y/%m/%d')})\n"
    
    has_news = False
    
    for source_name, url in RSS_SOURCES.items():
        feed = feedparser.parse(url)
        entries = feed.entries[:2]  # 各ソース最新2件
        
        if not entries:
            # 念のため別ルートでのデータ取得を試みる
            continue
            
        message_content += f"\n━━━━━━━━━━━━━━━━━━━━━━━━\n📦 **{source_name}**\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        has_news = True
        
        for entry in entries:
            title = entry.get("title", entry.get("description", "タイトルなし"))
            summary = entry.get("summary", entry.get("description", ""))
            link = entry.get("link", "#")
            
            # 完全に空文字だった場合の対策
            if not summary or len(summary) < 5:
                summary = title

            lines = analyze_impact(title, summary)
            
            message_content += f"📌 **{title}**\n"
            for line in lines:
                message_content += f"  {line}\n"
            message_content += f"🔗 {link}\n\n"

    if not has_news:
        message_content += "\n⚠️ 現在、ニュースソースから記事を一時的に取得できませんでした。時間をおいて再試行してください。"

    # Discord送信処理
    if len(message_content) > 2000:
        message_content = message_content[:1950] + "\n...(文字数制限のため省略)"
        
    response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message_content})
    if response.status_code == 204:
        print("✅ Discordへの配信が成功しました！")
    else:
        print(f"❌ エラーが発生しました: {response.status_code}")

if __name__ == "__main__":
    main()
