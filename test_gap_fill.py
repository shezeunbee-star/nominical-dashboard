"""
갭 채우기 함수 테스트 스크립트
— 대시보드에 통합하기 전에 로컬에서만 테스트
"""
import pandas as pd
import gspread
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.auth.transport.requests import Request
from datetime import date, timedelta
import os

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")
SPREADSHEET_ID = "1y9mZirj81sR2tkkGV_wTzFvJonPdJU-JuErSRDo_73E"
SHEET_NAME = "📅 일별 트래킹"

print("=" * 60)
print("🧪 갭 채우기 테스트")
print("=" * 60)

# ① Google Sheets에서 현재 데이터 조회
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
    raw = ws.get("A2:W100", value_render_option="UNFORMATTED_VALUE")

    print("\n✅ Google Sheets 연결 성공!")

    # 현재 데이터의 날짜 추출
    headers = raw[0]
    dates_in_sheet = []
    for r in raw[1:]:
        if r and r[0]:
            label = str(r[0])
            if "종합" not in label and "날짜" not in label:
                dates_in_sheet.append(str(r[0]).strip())

    print(f"\n현재 Google Sheets 데이터:")
    print(f"  행 수: {len(dates_in_sheet)}")
    print(f"  첫 날짜: {dates_in_sheet[0] if dates_in_sheet else 'N/A'}")
    print(f"  마지막 날짜: {dates_in_sheet[-1] if dates_in_sheet else 'N/A'}")
    print(f"  전체 날짜: {dates_in_sheet}")

    # ② 마지막 데이터 날짜와 어제 날짜 확인
    def parse_simple_date(s):
        """M/D 형식을 datetime으로 변환"""
        s = str(s).strip()
        # datetime 문자열 형식 처리
        if "-" in s:
            try:
                return pd.to_datetime(s)
            except:
                pass
        # M/D 형식 처리
        try:
            parts = s.split("/")
            month, day = int(parts[0]), int(parts[1])
            return pd.Timestamp(f"2026-{month:02d}-{day:02d}")
        except:
            return None

    if dates_in_sheet:
        # 마지막 유효한 날짜 찾기
        last_date = None
        for d in reversed(dates_in_sheet):
            parsed = parse_simple_date(d)
            if parsed is not None:
                last_date = parsed
                break
        yesterday = date.today() - timedelta(days=1)
        print(f"\n마지막 데이터 날짜: {last_date.date()}")
        print(f"어제 날짜: {yesterday}")

        # ③ 비어있는 날짜 감지
        missing_dates = []
        current = last_date
        while current.date() < yesterday:
            current = current + timedelta(days=1)
            date_str = f"{current.month}/{current.day}"
            if date_str not in dates_in_sheet:
                missing_dates.append(date_str)

        print(f"\n🔍 감지된 비어있는 날짜:")
        if missing_dates:
            print(f"  {missing_dates}")
            print(f"  총 {len(missing_dates)}개 날짜")
        else:
            print(f"  없음 (모든 날짜가 채워짐)")

except Exception as e:
    print(f"❌ 에러: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("테스트 완료!")
print("=" * 60)
