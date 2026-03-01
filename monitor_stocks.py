import pandas as pd
import requests
import io
import os

# --- 設定 ---
DISCORD_WEBHOOK_URL = "あなたのDiscordのURL"

def update_prime_list():
    # JPXの最新Excelからプライム全銘柄を取得
    url = "https://www.jpx.co.jp/markets/statistics-banner/quote/01_data_j.xls"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers)
        df = pd.read_excel(io.BytesIO(resp.content))
        # プライム市場のみ抽出
        prime_df = df[df['市場・商品区分'].str.contains('プライム', na=False)]
        save_df = prime_df[['コード', '銘柄名']]
        save_df.to_csv('prime_list.csv', index=False)
        return len(save_df)
    except Exception as e:
        return f"エラー: {e}"

if __name__ == "__main__":
    count = update_prime_list()
    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"✅ prime_list.csv を更新しました。現在 {count} 銘柄が登録されています。"})
