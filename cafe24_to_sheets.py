"""
Cafe24 주문 → 구글 시트 자동 정리
사용법: python3 cafe24_to_sheets.py [YYYY-MM-DD] [YYYY-MM-DD]
  예시: python3 cafe24_to_sheets.py 2026-05-01 2026-05-26
  날짜 생략 시 오늘 기준 최근 30일
"""
# ── 자동실행 안전장치: 잠자기 등으로 네트워크가 멈춰도 30분 후 자동 종료 ──
import signal as _signal, socket as _socket
_signal.alarm(1800)
_socket.setdefaulttimeout(120)

import sys, os, json, requests, base64, re, gspread, hashlib
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
    # 무신사 등 마켓 주문: '옵션1=차콜, 옵션2=M' 형식 (순서는 상품마다 다름 —
    # 플리츠는 옵션1=사이즈, 페이크레이어드는 옵션1=컬러) → 값을 보고 판별
    if color == "-" and size == "-":
        SIZE_PAT = re.compile(r'^(XXS|XS|S|M|L|XL|XXL|2XL|3XL|FREE|\d{2,3})$', re.I)
        for m in re.finditer(r'옵션\d+=([^,]+)', s):
            val = m.group(1).strip()
            if SIZE_PAT.match(val):
                size = val
            else:
                color = val
    # 색상/사이즈 태그 없이 단순 '블랙/M' 형태면
    if color == "-" and size == "-" and "/" in s:
        parts = s.split("/", 1)
        color, size = parts[0].strip(), parts[1].strip()
    return color, size

def item_status(item, order):
    """Cafe24 아이템 order_status 접두어로 상태 판별.
    C*=취소, R*=반품, E*=교환, N*=정상. 코드 없으면 order 레벨 canceled 폴백."""
    code = str(item.get("order_status", "") or "").strip().upper()
    if code[:1] == "C":
        return "취소"
    if code[:1] == "R":
        return "반품"
    if code[:1] == "E":
        return "교환"
    if code[:1] == "N":
        return "결제완료"
    return "취소" if order.get("canceled") == "T" else "결제완료"

def parse_orders(orders):
    rows = []
    for order in orders:
        platform   = market_to_platform(order.get("market_id", "self"))
        order_date = (order.get("order_date") or "")[:10]

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
            status = item_status(item, order)

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

# ── GA4 Measurement Protocol (서버사이드 구매 추적) ────────────────
def _load_ga4_secrets():
    secrets_path = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")
    if not os.path.exists(secrets_path):
        return None, None
    with open(secrets_path) as f:
        content = f.read()
    mid = re.search(r'ga4_measurement_id\s*=\s*["\']([^"\']+)["\']', content)
    sec = re.search(r'ga4_api_secret\s*=\s*["\']([^"\']+)["\']', content)
    return (mid.group(1) if mid else None), (sec.group(1) if sec else None)

def send_ga4_purchase_mp(order_id, value, items, measurement_id, api_secret, order_ts=None):
    """결제수단(네이버페이 등 외부결제 포함)과 무관하게 Cafe24 주문 데이터를
    기준으로 GA4에 구매 이벤트를 직접 전송 (클라이언트 gtag 의존 안 함).

    order_ts: 주문 시각 ISO 문자열. timestamp_micros로 전송해 실제 주문일에 기록.
    GA4 MP는 72시간 이전 이벤트를 거부하므로, 그보다 오래된 주문은 전송하지 않고
    "skip"을 반환 (전송 시점 날짜로 잘못 기록되는 것 방지)."""
    try:
        ts_micros = None
        if order_ts:
            try:
                dt = datetime.fromisoformat(str(order_ts).replace("Z", "+09:00"))
                if dt.tzinfo:
                    dt = dt.replace(tzinfo=None)  # KST 로컬 기준
                age = datetime.now() - dt
                if age > timedelta(hours=71):
                    return "skip"
                ts_micros = int(dt.timestamp() * 1_000_000)
            except Exception:
                pass

        client_id = hashlib.md5(f"cafe24-{order_id}".encode()).hexdigest()[:16]
        client_id = f"{client_id[:8]}.{client_id[8:]}"
        payload = {
            "client_id": client_id,
            "events": [{
                "name": "purchase",
                "params": {
                    "transaction_id": str(order_id),
                    "currency": "KRW",
                    "value": float(value),
                    "items": items,
                },
            }],
        }
        if ts_micros:
            payload["timestamp_micros"] = ts_micros
        resp = requests.post(
            f"https://www.google-analytics.com/mp/collect?measurement_id={measurement_id}&api_secret={api_secret}",
            json=payload, timeout=10,
        )
        return resp.status_code in (200, 204)
    except Exception:
        return False

def build_ga4_events(orders, existing_keys_before):
    """orders 원본에서 신규(미동기화)+정상 상태인 주문만 모아 GA4 전송용으로 집계."""
    events = []
    for order in orders:
        platform   = market_to_platform(order.get("market_id", "self"))
        order_date = (order.get("order_date") or "")[:10]
        status     = parse_status(order)
        order_id   = order.get("order_id", "")
        items      = order.get("items", [])
        if not items:
            continue
        total = 0
        ga4_items = []
        has_new = False
        for item in items:
            color, size = parse_option(item.get("option_value", ""))
            qty   = int(float(item.get("quantity", 1) or 1))
            price = int(float(item.get("product_price", 0) or 0))
            total += price * qty
            ga4_items.append({
                "item_id": str(item.get("product_code", "-")),
                "item_name": str(item.get("product_name", "-")),
                "quantity": qty, "price": price,
            })
            key = f"{platform}|{order_date}|{item.get('product_code','-')}|{color}|{size}"
            if key not in existing_keys_before:
                has_new = True
        if has_new and status != "취소" and total > 0:
            events.append((order_id or f"{platform}-{order_date}-{len(events)}",
                           total, ga4_items, order.get("order_date", "")))
    return events

# ── 메인 ─────────────────────────────────────────────────────────
def main():
    # end 기본값 = 어제. 오늘(마감 안 된 날)을 수집하면 부분 데이터가 먼저 들어가고,
    # 이후 같은 날 동일 상품·컬러·사이즈 주문이 중복으로 오인되어 누락되는 문제 발생.
    start = sys.argv[1] if len(sys.argv) > 1 else (datetime.now()-timedelta(days=30)).strftime("%Y-%m-%d")
    end   = sys.argv[2] if len(sys.argv) > 2 else (datetime.now()-timedelta(days=1)).strftime("%Y-%m-%d")
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
    existing_before = set(existing)  # GA4 이벤트 판단용 — append 전 상태 보존
    new_rows = [r for r in rows if f"{r[0]}|{r[1]}|{r[3]}|{r[4]}|{r[5]}" not in existing]

    # 기존 취소 상태 업데이트
    for r in new_rows:
        existing.add(f"{r[0]}|{r[1]}|{r[3]}|{r[4]}|{r[5]}")

    if new_rows:
        ws.append_rows(new_rows, value_input_option="USER_ENTERED")
        print(f"\n🎉 {len(new_rows)}건 추가! ({len(rows)-len(new_rows)}건 중복 스킵)")
    else:
        print("\n새로 추가할 데이터 없음.")

    # GA4 Measurement Protocol — 결제수단 무관 서버사이드 구매 추적
    ga4_mid, ga4_secret = _load_ga4_secrets()
    if ga4_mid and ga4_secret:
        ga4_events = build_ga4_events(orders, existing_before)
        sent = skipped = 0
        for oid, val, its, ots in ga4_events:
            r = send_ga4_purchase_mp(oid, val, its, ga4_mid, ga4_secret, order_ts=ots)
            if r == "skip":
                skipped += 1
            elif r:
                sent += 1
        msg = f"📊 GA4 전송: {sent}/{len(ga4_events)}건"
        if skipped:
            msg += f" (72시간 초과 {skipped}건 스킵 — GA4가 과거 이벤트를 받지 않음)"
        print(msg)
    else:
        print("⚠️  GA4 secrets 없음 — Measurement Protocol 전송 스킵")

if __name__ == "__main__":
    main()
