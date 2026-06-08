"""
갭 채우기 함수 구현 및 테스트
— 6/2~6/6 자동 감지 & 채우기
"""
import pandas as pd
import gspread
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.auth.transport.requests import Request
from datetime import date, timedelta
import os
import json

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")
SPREADSHEET_ID = "1y9mZirj81sR2tkkGV_wTzFvJonPdJU-JuErSRDo_73E"
SHEET_NAME = "📅 일별 트래킹"

print("=" * 70)
print("🚀 갭 채우기 함수 구현 및 테스트")
print("=" * 70)

# ① Google Sheets 연결
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
creds = OAuthCredentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())

gc = gspread.authorize(creds)
ws = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

# ② 현재 데이터 조회
raw = ws.get("A2:W100", value_render_option="UNFORMATTED_VALUE")
headers = raw[0]
dates_in_sheet = []
for r in raw[1:]:
    if r and r[0]:
        label = str(r[0])
        if "종합" not in label and "날짜" not in label:
            dates_in_sheet.append(str(r[0]).strip())

print(f"\n✅ 현재 Google Sheets 데이터:")
print(f"   첫 날짜: {dates_in_sheet[0]}")
print(f"   마지막 날짜: {dates_in_sheet[-1]}")
print(f"   전체 {len(dates_in_sheet)}개 행")

# ③ 날짜 파싱 함수
def parse_date(s):
    """M/D 형식을 date 객체로 변환"""
    s = str(s).strip()
    # datetime 문자열 처리
    if "-" in s:
        try:
            dt = pd.to_datetime(s)
            return dt.date()
        except:
            pass
    # M/D 형식 처리
    try:
        parts = s.split("/")
        month, day = int(parts[0]), int(parts[1])
        return date(2026, month, day)
    except:
        return None

# ④ 마지막 데이터 날짜 찾기
def get_last_data_date():
    """마지막 데이터 날짜 반환"""
    for d in reversed(dates_in_sheet):
        parsed = parse_date(d)
        if parsed:
            return parsed
    return None

last_date = get_last_data_date()
today = date.today()
yesterday = today - timedelta(days=1)

print(f"\n📅 날짜 정보:")
print(f"   마지막 데이터: {last_date}")
print(f"   어제: {yesterday}")
print(f"   오늘: {today}")

# ⑤ 비어있는 날짜 감지
def find_missing_dates(last_date, until_date):
    """last_date 다음부터 until_date까지 비어있는 날짜 찾기"""
    missing = []
    current = last_date + timedelta(days=1)

    while current <= until_date:
        date_str = f"{current.month}/{current.day}"
        # 정규화된 형식 확인 (데이터에 있는지 체크)
        found = False
        for d in dates_in_sheet:
            if parse_date(d) == current:
                found = True
                break
        if not found:
            missing.append(current)
        current += timedelta(days=1)

    return missing

missing_dates = find_missing_dates(last_date, yesterday)

print(f"\n🔍 감지된 비어있는 날짜:")
if missing_dates:
    print(f"   {[f'{d.month}/{d.day}' for d in missing_dates]}")
    print(f"   총 {len(missing_dates)}개")
else:
    print(f"   없음")

# ⑥ 각 빈 날짜에 대해 어떤 데이터를 추가해야 할지 시뮬레이션
print(f"\n📝 추가할 행 미리보기:")
print(f"   (실제 GA4, Meta, Cafe24 데이터는 API에서 가져옴)")
print()

for d in missing_dates:
    date_str = f"{d.month}/{d.day}"
    day_name = ["월", "화", "수", "목", "금", "토", "일"][d.weekday()]
    print(f"   ✨ {date_str} ({day_name})")
    print(f"      → GA4 데이터 조회")
    print(f"      → Meta 데이터 조회")
    print(f"      → Cafe24 데이터 조회")
    print(f"      → Google Sheets에 새 행 추가")
    print()

print("=" * 70)
print("✅ 테스트 완료!")
print("=" * 70)
print("\n다음 단계:")
print("1️⃣  update_ga4_for_date(date) 함수 구현")
print("2️⃣  update_meta_for_date(date) 함수 구현")
print("3️⃣  update_cafe24_for_date(date) 함수 구현")
print("4️⃣  fill_missing_dates() 메인 함수 구현")
print("5️⃣  대시보드에 통합")
