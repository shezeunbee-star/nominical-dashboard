"""
Meta 데이터 직접 테스트
— 6/2 날짜에 Meta API 호출 & Google Sheets 쓰기
"""
import sys
import os
sys.path.insert(0, '/Users/kimeunbee/Documents/nominical-dashboard')

from datetime import date
import gspread
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.auth.transport.requests import Request
import json
import re

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")
SPREADSHEET_ID = "1y9mZirj81sR2tkkGV_wTzFvJonPdJU-JuErSRDo_73E"
SHEET_NAME = "📅 일별 트래킹"

print("=" * 70)
print("🧪 Meta 직접 테스트 (6/2 날짜)")
print("=" * 70)

# ① Meta 토큰 읽기
print("\n1️⃣  Meta 토큰 읽기...")
meta_token = None

secrets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit", "secrets.toml")
print(f"   📁 secrets.toml 경로: {secrets_path}")
print(f"   ✓ 파일 존재: {os.path.exists(secrets_path)}")

if os.path.exists(secrets_path):
    with open(secrets_path, 'r') as f:
        content = f.read()
        print(f"   ✓ 파일 크기: {len(content)} bytes")
        match = re.search(r'meta_access_token\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            meta_token = match.group(1)
            print(f"   ✅ 토큰 발견! (길이: {len(meta_token)})")
        else:
            print(f"   ❌ 토큰을 찾을 수 없음")

if not meta_token:
    print("❌ Meta 토큰 없음!")
    sys.exit(1)

# ② Google Sheets 연결
print("\n2️⃣  Google Sheets 연결...")
try:
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = OAuthCredentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    print("   ✅ Google Sheets 연결 성공!")
except Exception as e:
    print(f"   ❌ 에러: {e}")
    sys.exit(1)

# ③ Meta API 호출
print("\n3️⃣  Meta API 호출 (6/2)...")
import requests
target_date = date(2026, 6, 2)
date_str = target_date.strftime("%Y-%m-%d")

try:
    # Meta Graph API 호출
    url = "https://graph.instagram.com/v25.0/me/insights"
    params = {
        "metric": "impressions,reach,profile_visits,website_clicks,follower_count,get_directions_clicks",
        "period": "day",
        "date_preset": "today",
        "access_token": meta_token,
    }

    # 날짜 기반 호출
    meta_url = "https://graph.instagram.com/v25.0/278649477896928/insights"
    meta_params = {
        "metric": "impressions,reach,profile_visits,website_clicks,follower_count,engagement",
        "date_preset": "yesterday",
        "access_token": meta_token,
    }

    print(f"   🌐 URL: {meta_url}")
    response = requests.get(meta_url, params=meta_params)
    print(f"   📊 상태 코드: {response.status_code}")
    print(f"   📝 응답: {response.text[:200]}")

    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Meta API 호출 성공!")
        print(f"   📊 데이터: {data}")
    else:
        print(f"   ❌ Meta API 호출 실패!")

except Exception as e:
    print(f"   ❌ 에러: {e}")
    import traceback
    traceback.print_exc()

# ④ 6/2 행 찾기
print("\n4️⃣  6/2 행 찾기...")
try:
    raw = ws.get("A2:E100", value_render_option="UNFORMATTED_VALUE")
    target_row = None

    for idx, row in enumerate(raw, start=2):
        if row and row[0]:
            cell_value = str(row[0]).strip()
            if "6/2" in cell_value:
                target_row = idx
                print(f"   ✅ 찾음! 행 {idx}: {cell_value}")
                print(f"      현재 C열(광고비): {row[2] if len(row) > 2 else '없음'}")
                break

    if not target_row:
        print(f"   ⚠️  6/2 행을 찾지 못함")
        print(f"   📋 전체 행 목록:")
        for idx, row in enumerate(raw, start=2):
            if row and row[0]:
                print(f"      행 {idx}: {row[0]}")

except Exception as e:
    print(f"   ❌ 에러: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("테스트 완료!")
print("=" * 70)
