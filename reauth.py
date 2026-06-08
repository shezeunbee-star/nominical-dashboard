"""
Google OAuth 재인증 스크립트
실행: python3 reauth.py
브라우저 열림 → 로그인 → 새 token.json 저장
"""
import json, os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(DIR, "token.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/analytics.readonly",
]

# 기존 토큰에서 client_id/secret 읽기
with open(TOKEN_FILE) as f:
    old = json.load(f)

client_config = {
    "installed": {
        "client_id":     old["client_id"],
        "client_secret": old["client_secret"],
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
        "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
        "token_uri":     "https://oauth2.googleapis.com/token",
    }
}

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
creds = flow.run_local_server(port=0)

# token.json 저장
token_data = {
    "token":         creds.token,
    "refresh_token": creds.refresh_token,
    "token_uri":     creds.token_uri,
    "client_id":     creds.client_id,
    "client_secret": creds.client_secret,
    "scopes":        list(creds.scopes),
}
with open(TOKEN_FILE, "w") as f:
    json.dump(token_data, f, indent=2)

print("\n✅ 새 token.json 저장 완료!")
print("\n아래 내용을 복사해서 Streamlit secrets의 google_token_json 값으로 교체하세요:\n")
print(f"google_token_json = '{json.dumps(token_data)}'")
