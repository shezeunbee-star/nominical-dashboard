"""
Cafe24 주문 → 구글 시트 자동 정리
사용법: python3 cafe24_to_sheets.py [YYYY-MM-DD] [YYYY-MM-DD]
  예시: python3 cafe24_to_sheets.py 2026-05-01 2026-05-26
  날짜 생략 시 오늘 기준 최근 30일
"""
import sys, os, json, requests, base64, re, gspread
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE     = os.path.join(BASE_DIR, "cafe24_token.json")
GSHEET_TOKEN   = os.path.join(BASE_DIR, "token.json")
SPREADSHEET_ID = "1y9mZirj81sR2tkkGV_wTzFvJonPdJU-JuErSRDo_73E"
SHEET_NAME     = "🏬 플랫폼 매출"
COMMISSION_DEFAULT = 30
COMMISSION_CAFE24   = 3   # PG 수수료만 (자사몰)
API_VERSION    = "2026-03-01"

# Cafe24 연동 마켓 market_id 매핑
MARKET_PLATFORM_MAP = {
    "musinsa":  "무신사",     # 무신사
    "zigzag":   "지그재그",   # 지그재그 (카카오스타일)
    "shopn":    "스마트스토어", # 옛 네이버 "샵N" 코드명이 그대로 남아있음
                              # (order_place_name="스마트스토어"로 실제 확인됨)
}
# 위 목록 외: self, NCHECKOUT, mobile 등 → 자사몰(Cafe24)

def market_to_platform(market_id):
    mid = (market_id or "").lower().strip()
    if mid in MARKET_PLATFORM_MAP:
        return MARKET_PLATFORM_MAP[mid]
    if "naver" in mid or "smart" in mid:
        return "스마트스토어"
    return "Cafe24"

# ── 토큰 관리 ─────────────────────────────────────────────────────
def get_token():
    with open(TOKEN_FILE) as f:
        t = json.load(f)
    if t.get("expires_at"):
        try:
            exp = datetime.fromisoformat(t["expires_at"].replace(".000", ""))
            if datetime.now() >= exp - timedelta(minutes=10):
                t = _refresh(t)
        except Exception:
            pass
    return t

def _refresh(t):
    cred = base64.b64encode(f"{t['client_id']}:{t['client_secret']}".encode()).decode()
    resp = requests.post(
        f"https://{t['shop_id']}.cafe24api.com/api/v2/oauth/token",
        headers={"Authorization": f"Basic {cred}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "refresh_token", "refresh_token": t["refresh_token"]}
    )
    if resp.status_code == 200:
        new = resp.json()
        t.update({k: new[k] for k in ["access_token","expires_at","refresh_token","refresh_token_expires_at"] if k in new})
        with open(TOKEN_FILE, "w") as f:
            json.dump(t, f, indent=2, ensure_ascii=False)
        print("  🔄 Access Token 갱신 완료")
    else:
        print(f"  ❌ 토큰 갱신 실패: {resp.text}")
        sys.exit(1)
    return t

# ── API 호출 ──────────────────────────────────────────────────────
def get_orders(token, start_date, end_date):
    headers = {
        "Authorization":        f"Bearer {token['access_token']}",
        "Content-Type":         "application/json",
        "X-Cafe24-Api-Version": API_VERSION,
    }
    shop_id    = token["shop_id"]
    all_orders = []
    offset     = 0
    limit      = 100

    while True:
        resp = requests.get(
            f"https://{shop_id}.cafe24api.com/api/v2/admin/orders",
            headers=headers,
            params={"start_date": start_date, "end_date": end_date,
                    "limit": limit, "offset": offset, "embed": "items"}
        )
        if resp.status_code != 200:
            print(f"  ❌ API 오류 ({resp.status_code}): {resp.text[:200]}")
            break
        orders = resp.json().get("orders", [])
        all_orders.extend(orders)
        print(f"  수집 중: {len(all_orders)}건...")
        if len(orders) < limit:
            break
        offset += limit

    return all_orders

# ── 파싱 ─────────────────────────────────────────────────────────
def parse_option(opt_str):
    """'색상=블랙, 사이즈=M' → ('블랙', 'M')"""
    color, size = "-", "-"
    if not opt_str:
        return color, size
    s = str(opt_str)
    m_color = re.search(r'색상=([^,]+)', s)
    m_size  = re.search(r'사이즈=([^,]+)', s)
    if m_color:
        color = m_color.group(1).strip()
    if m_size:
        size = m_size.group(1).strip()
    # 색상/사이즈 태그 없이 단순 '블랙/M' 형태면
    if color == "-" and size == "-" and "/" in s:
        parts = s.split("/", 1)
        color, size = parts[0].strip(), parts[1].strip()
    return color, size

def parse_status(order):
    if order.get("canceled") == "T":
        return "취소"
    if order.get("paid") == "T":
        return "결제완료"
    return "주문접수"

def parse_orders(orders):
    rows = []
    for order in orders:
        platform   = market_to_platform(order.get("market_id", "self"))
        order_date = (order.get("order_date") or "")[:10]
        status     = parse_status(order)

        items = order.get("items", [])
        if not items:
            continue

        for item in items:
            color, size = parse_option(item.get("option_value", ""))
            qty    = int(float(item.get("quantity", 1) or 1))
            price  = int(float(item.get("product_price", 0) or 0))
            total  = price * qty
            comm   = COMMISSION_CAFE24 if platform == "Cafe24" else COMMISSION_DEFAULT
            profit = round(total * (1 - comm / 100))

            rows.append([
                platform, order_date,
                str(item.get("product_name", "-")),
                str(item.get("product_code", "-")),
                color, size, qty, total,
                comm, profit, status
            ])
    return rows

# ── 구글 시트 ─────────────────────────────────────────────────────
def get_sheet():
    creds = Credentials.from_authorized_user_file(GSHEET_TOKEN, [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ])
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return gspread.authorize(creds).open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

def get_existing_keys(ws):
    keys = set()
    for row in ws.get_all_values()[1:]:
        if len(row) >= 6:
            keys.add(f"{row[0]}|{row[1]}|{row[3]}|{row[4]}|{row[5]}")
    return keys

# ── 메인 ─────────────────────────────────────────────────────────
def main():
    start = sys.argv[1] if len(sys.argv) > 1 else (datetime.now()-timedelta(days=30)).strftime("%Y-%m-%d")
    end   = sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime("%Y-%m-%d")
    print(f"🛒 Cafe24 주문 수집: {start} ~ {end}")

    token  = get_token()
    orders = get_orders(token, start, end)
    print(f"  총 {len(orders)}건 수집")

    rows = parse_orders(orders)
    c24  = sum(1 for r in rows if r[0] == "Cafe24")
    mus  = sum(1 for r in rows if r[0] == "무신사")
    print(f"  Cafe24: {c24}건 | 무신사: {mus}건")

    ws       = get_sheet()
    existing = get_existing_keys(ws)
    new_rows = [r for r in rows if f"{r[0]}|{r[1]}|{r[3]}|{r[4]}|{r[5]}" not in existing]

    # 기존 취소 상태 업데이트
    for r in new_rows:
        existing.add(f"{r[0]}|{r[1]}|{r[3]}|{r[4]}|{r[5]}")

    if new_rows:
        ws.append_rows(new_rows, value_input_option="USER_ENTERED")
        print(f"\n🎉 {len(new_rows)}건 추가! ({len(rows)-len(new_rows)}건 중복 스킵)")
    else:
        print("\n새로 추가할 데이터 없음.")

if __name__ == "__main__":
    main()
