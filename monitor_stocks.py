import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta, timezone

# --- あなたのURLを貼り付け済み ---
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"

def update_prime_list():
    """JPXの最新Excelからプライム全銘柄を取得して保存"""
    url = "https://www.jpx.co.jp/markets/statistics-banner/quote/01_data_j.xls"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers)
        df_jpx = pd.read_excel(io.BytesIO(resp.content))
        # 市場区分が「プライム」の銘柄を抽出
        prime_df = df_jpx[df_jpx['市場・商品区分'].str.contains('プライム', na=False)]
        save_df = prime_df[['コード', '銘柄名']]
        # ファイルとして保存
        save_df.to_csv('prime_list.csv', index=False)
        return len(save_df)
    except Exception as e:
        return f"エラー: {e}"

if __name__ == "__main__":
    count = update_prime_list()
    message = f"✅ prime_list.csv を更新しました。現在 **{count}** 銘柄がパトロール対象です。"
    requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    print(message)
