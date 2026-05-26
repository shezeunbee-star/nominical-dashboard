import requests, json, base64, getpass, os

SHOP_ID      = "nominical"
CLIENT_ID    = "1f58ZYA3e0hPmPDD42jHGH"
AUTH_CODE    = "Eao7jUevHqHDdfIlf7B7ZY"
REDIRECT_URI = "https://nominical-dashboard-aasgyx3hnlqter7v4zgkfd.streamlit.app"
TOKEN_FILE   = os.path.expanduser("~/Downloads/cafe24_token.json")

client_secret = getpass.getpass("Client Secret 입력: ").strip()
credentials   = base64.b64encode(f"{CLIENT_ID}:{client_secret}".encode()).decode()

resp = requests.post(
    f"https://{SHOP_ID}.cafe24api.com/api/v2/oauth/token",
    headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/x-www-form-urlencoded"},
    data={"grant_type": "authorization_code", "code": AUTH_CODE, "redirect_uri": REDIRECT_URI}
)
if resp.status_code == 200:
    d = resp.json()
    d.update({"client_id": CLIENT_ID, "client_secret": client_secret, "shop_id": SHOP_ID})
    with open(TOKEN_FILE, "w") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    print(f"✅ 성공! ~/Downloads/cafe24_token.json 저장됨")
    print(f"   만료: {d.get('expires_at','')}")
else:
    print(f"❌ 실패: {resp.text}")
