import os
"""
GA4 → 구글 시트 일별 자동 기록 스크립트
매일 실행하면 어제 데이터를 자사몰 성과 컬럼(K~T)에 자동 입력
"""
import os
import gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest, Dimension, Metric, DateRange,
    FilterExpression, Filter, FilterExpressionList
)
from datetime import date, timedelta
import time

TOKEN_FILE      = os.environ.get("GOOGLE_TOKEN_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")
SPREADSHEET_ID  = "1y9mZirj81sR2tkkGV_wTzFvJonPdJU-JuErSRDo_73E"
GA4_PROPERTY_ID = "536368183"
SHEET_NAME      = "📅 일별 트래킹"

creds = Credentials.from_authorized_user_file(TOKEN_FILE, [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/analytics.readonly"
])
if creds.expired and creds.refresh_token:
    creds.refresh(Request())

ga4 = BetaAnalyticsDataClient(credentials=creds)
gc  = gspread.authorize(creds)
ws  = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

yesterday = date.today() - timedelta(days=1)
date_str  = yesterday.strftime("%Y-%m-%d")
day_label = f"{yesterday.month}/{yesterday.day}"
print(f"📅 {day_label} 데이터 수집 중...")

def run_report(dimensions, metrics, filter_expr=None):
    req = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[Dimension(name=d) for d in dimensions],
        metrics=[Metric(name=m) for m in metrics],
        date_ranges=[DateRange(start_date=date_str, end_date=date_str)],
    )
    if filter_expr:
        req.dimension_filter = filter_expr
    return ga4.run_report(req)

# 전체 지표
res = run_report(
    ["date"],
    ["sessions", "transactions", "bounceRate", "averagePurchaseRevenue", "purchaseRevenue"]
)
sessions = transactions = bounce = avg_price = revenue = 0
if res.rows:
    r = res.rows[0].metric_values
    sessions     = int(float(r[0].value))
    transactions = int(float(r[1].value))
    bounce       = round(float(r[2].value) * 100, 1)
    avg_price    = round(float(r[3].value))
    revenue      = round(float(r[4].value))
print(f"   방문자: {sessions}, 구매: {transactions}, 이탈율: {bounce}%")

def get_channel(source, medium):
    f = FilterExpression(and_group=FilterExpressionList(expressions=[
        FilterExpression(filter=Filter(field_name="sessionSource",
            string_filter=Filter.StringFilter(value=source, match_type="EXACT"))),
        FilterExpression(filter=Filter(field_name="sessionMedium",
            string_filter=Filter.StringFilter(value=medium, match_type="EXACT")))
    ]))
    r = run_report(["sessionSource"], ["sessions"], f)
    return int(float(r.rows[0].metric_values[0].value)) if r.rows else 0

time.sleep(0.3); ch_meta     = get_channel("meta", "paid_feed") + get_channel("ig", "paid")
time.sleep(0.3); ch_official = get_channel("instagram", "bio")
time.sleep(0.3); ch_personal = get_channel("instagram", "personal_bio") + get_channel("instagram", "personal_story")
time.sleep(0.3)

f_direct = FilterExpression(filter=Filter(field_name="sessionMedium",
    string_filter=Filter.StringFilter(value="(none)", match_type="EXACT")))
r_direct = run_report(["sessionMedium"], ["sessions"], f_direct)
ch_direct = int(float(r_direct.rows[0].metric_values[0].value)) if r_direct.rows else 0

print(f"   유입 → 메타:{ch_meta} 공식:{ch_official} 개인:{ch_personal} 직접:{ch_direct}")

# 신규/재방문
res_new = run_report(["newVsReturning"], ["activeUsers"])
new_users = returning_users = 0
for row in res_new.rows:
    val = int(float(row.metric_values[0].value))
    if row.dimension_values[0].value == "new":
        new_users = val
    else:
        returning_users = val
print(f"   신규: {new_users}, 재방문: {returning_users}")

all_dates = ws.col_values(1)
row_idx = next((i+1 for i, d in enumerate(all_dates) if d == day_label), None)

if not row_idx:
    print(f"❌ '{day_label}' 날짜를 시트에서 찾을 수 없어요!")
else:
    ws.update(values=[[sessions, transactions]], range_name=f"K{row_idx}:L{row_idx}")
    time.sleep(0.2)
    ws.update(
        values=[[bounce, avg_price, revenue, ch_meta, ch_official, ch_personal, ch_direct]],
        range_name=f"N{row_idx}:T{row_idx}"
    )
    time.sleep(0.3)
    ws.update(values=[[new_users, returning_users]], range_name=f"U{row_idx}:V{row_idx}")
    print(f"✅ {day_label} 데이터 입력 완료! (행 {row_idx})")
