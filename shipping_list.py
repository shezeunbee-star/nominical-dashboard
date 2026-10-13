#!/usr/bin/env python3
"""오늘 발송 리스트 생성 — 모바일 체크리스트 HTML.

자사몰(Cafe24 API, 주문단위·발송대기만) + 외부몰(플랫폼 매출 시트) 취합 →
택배 건수 자동 카운트, 품목별 집품 수량, 취소/중복/품절 자동 플래그.

사용법: python3 shipping_list.py [일수]   # 기본 4일(오늘 포함)
출력:  <스크래치패드 또는 인자>/shipping_list.html
"""
import sys, os, re, json, base64, requests
from datetime import date, datetime, timedelta
from collections import defaultdict

import gspread
from google.oauth2.service_account import Credentials as SACredentials

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
SA_FILE    = os.path.join(BASE_DIR, "service_account.json")
C24_TOKEN  = os.path.join(BASE_DIR, "cafe24_token.json")
SHEET_ID   = "1y9mZirj81sR2tkkGV_wTzFvJonPdJU-JuErSRDo_73E"
PLAT_SHEET = "🏬 플랫폼 매출"
INV_SHEET  = "📦 입고관리"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/private/tmp/claude-501/-Users-kimeunbee-Documents-----/33421354-9ced-4b83-b7bd-9a1d2e3b77f0/scratchpad/shipping_list.html"

DAYS   = int(sys.argv[1]) if len(sys.argv) > 1 else 4
END    = date.today()
START  = END - timedelta(days=DAYS - 1)

# ── 공통 유틸 ──────────────────────────────────────────────
def norm_color(c):
    return re.sub(r"\s+", "", str(c or "")).lower()

def parse_opt(opt):
    """option_value → (색, 사이즈). 대시보드 파서와 동일 규칙."""
    opt = str(opt or "")
    color = re.search(r"색상=([^,)]+)", opt)
    size  = re.search(r"사이즈=([^,)]+)", opt)
    color = color.group(1).strip() if color else "-"
    size  = size.group(1).strip() if size else "-"
    if color == "-" and size == "-":
        SZ = re.compile(r"^(XXS|XS|S|M|L|XL|XXL|2XL|3XL|FREE|\d{2,3})$", re.I)
        for m in re.finditer(r"옵션\d+=([^,]+)", opt):
            v = m.group(1).strip()
            if SZ.match(v): size = v
            else:           color = v
    return color, size

def short_name(name):
    """[RE-ORDER]/[3차리오더]/(남녀공용) 등 군더더기 제거한 짧은 품명."""
    n = re.sub(r"\[[^\]]*\]", "", str(name))
    n = re.sub(r"\([^)]*\)", "", n)
    return re.sub(r"\s+", " ", n).strip()

# ── Cafe24: 발송대기 주문 (주문단위) ────────────────────────
def load_cafe24():
    t = json.load(open(C24_TOKEN))
    # 토큰 갱신
    try:
        exp = datetime.fromisoformat(t["expires_at"].replace(".000", ""))
        if datetime.now() >= exp - timedelta(minutes=10):
            cred = base64.b64encode(f"{t['client_id']}:{t['client_secret']}".encode()).decode()
            r = requests.post(f"https://{t['shop_id']}.cafe24api.com/api/v2/oauth/token",
                              headers={"Authorization": f"Basic {cred}",
                                       "Content-Type": "application/x-www-form-urlencoded"},
                              data={"grant_type": "refresh_token", "refresh_token": t["refresh_token"]}, timeout=10)
            if r.status_code == 200:
                n = r.json(); t["access_token"] = n["access_token"]; t["expires_at"] = n.get("expires_at", "")
                if n.get("refresh_token"): t["refresh_token"] = n["refresh_token"]
                json.dump(t, open(C24_TOKEN, "w"), indent=2)
    except Exception:
        pass
    h = {"Authorization": f"Bearer {t['access_token']}", "X-Cafe24-Api-Version": "2026-03-01"}
    r = requests.get(f"https://{t['shop_id']}.cafe24api.com/api/v2/admin/orders", headers=h,
                     params={"start_date": START.isoformat(), "end_date": END.isoformat(),
                             "limit": 500, "embed": "items"}, timeout=40)
    r.raise_for_status()
    orders, cancels = [], []
    name_count = defaultdict(int)
    for o in r.json().get("orders", []):
        who = o.get("buyer_name") or o.get("billing_name") or "?"
        pend = []
        for it in o.get("items", []):
            st = str(it.get("order_status") or "").strip().upper()
            color, size = parse_opt(it.get("option_value"))
            row = {"name": str(it.get("product_name", "-")), "color": color, "size": size,
                   "qty": int(float(it.get("quantity", 1) or 1))}
            if st.startswith("C") or st.startswith("R"):
                cancels.append({**row, "who": who, "why": "취소/반품"})
            elif st == "N21":
                pend.append(row)  # 배송대기 = 발송 대상 (상품/배송준비중 N10·N20은 아직 제외)
        if pend:
            orders.append({"ch": "자사몰", "who": who, "items": pend})
            name_count[who] += 1
    # 중복주문(같은 고객 2건+) 플래그
    dups = {w for w, c in name_count.items() if c > 1}
    for od in orders:
        od["dup"] = od["who"] in dups
    return orders, cancels, dups

# ── 외부몰: 시트에서 기간 내 정상 주문 ─────────────────────
def load_external(gc):
    ws = gc.open_by_key(SHEET_ID).worksheet(PLAT_SHEET)
    rows = ws.get_all_values()[1:]
    out = []
    for r in rows:
        cells = (r + [""] * 12)[:12]
        plat, odate, name, code, color, size, qty, price, comm, rev, status, recv = cells
        if plat == "Cafe24" or not (START.isoformat() <= odate <= END.isoformat()):
            continue
        if re.match(r"^(취소|반품|C|R)", str(status)):
            continue
        out.append({"ch": plat, "who": (recv or "").strip() or "-", "dup": False,
                    "items": [{"name": name, "color": color, "size": size, "qty": int(float(qty or 1))}]})
    return out

# ── 재고(입고관리) → 현재고 맵 ─────────────────────────────
def load_stock(gc):
    sh = gc.open_by_key(SHEET_ID)
    inv = sh.worksheet(INV_SHEET).get_all_values()[1:]
    plat = sh.worksheet(PLAT_SHEET).get_all_values()[1:]
    sales = []  # (상품명, color_norm, size, qty, odate)
    for r in plat:
        _, odate, name, code, color, size, qty, *_rest = (r + [""] * 7)[:7]
        status = r[10] if len(r) > 10 else ""
        if re.search(r"취소|반품", str(status)): continue
        sales.append((str(name), norm_color(color), str(size).strip(), int(float(qty or 0)), odate))
    stock = []  # {kw,color_norm,size,current}
    for r in inv:
        if not r or not r[0].strip(): continue
        kw   = r[1].strip() if len(r) > 1 else ""
        col  = norm_color(r[2]) if len(r) > 2 else ""
        size = r[3].strip() if len(r) > 3 else "-"
        try: base = int(float(r[4])) if len(r) > 4 and r[4].strip() else 0
        except ValueError: base = 0
        bdate = r[5].strip() if len(r) > 5 else ""
        sold = 0
        for sname, scol, ssize, sqty, sodate in sales:
            if kw and kw.lower() in sname.lower() and scol == col:
                if "프리오더" not in kw and "프리오더" in sname: continue
                if size and size != "-" and ssize != size: continue
                if bdate and sodate <= bdate: continue
                sold += sqty
        stock.append({"kw": kw, "color": col, "size": size, "current": base - sold})
    return stock

def match_stock(stock, pname, color, size):
    cn, sz = norm_color(color), str(size).strip()
    for s in stock:
        if s["kw"] and s["kw"].lower() in pname.lower() and s["color"] == cn:
            if s["size"] and s["size"] != "-" and sz and s["size"] != sz: continue
            return s["current"]
    return None

# ── 집계 ───────────────────────────────────────────────────
def build():
    gc = gspread.authorize(SACredentials.from_service_account_file(
        SA_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"]))
    c24, cancels, dups = load_cafe24()
    ext = load_external(gc)
    stock = load_stock(gc)
    orders = c24 + ext

    # 품목별 집품 수량
    pick = defaultdict(lambda: {"qty": 0, "name": "", "color": "", "size": ""})
    for od in orders:
        for it in od["items"]:
            key = (short_name(it["name"]), it["color"], it["size"])
            p = pick[key]; p["qty"] += it["qty"]
            p["name"], p["color"], p["size"] = key
    picking, lows = [], []
    for (n, c, s), p in sorted(pick.items(), key=lambda kv: -kv[1]["qty"]):
        cur = match_stock(stock, next(it["name"] for od in orders for it in od["items"]
                                      if short_name(it["name"]) == n), c, s)
        low = cur is not None and cur < p["qty"]
        label = " ".join(x for x in [n, c if c != "-" else "", s if s != "-" else ""] if x)
        row = {"label": label, "qty": p["qty"], "stock": cur, "low": low}
        picking.append(row)
        if low: lows.append(row)

    ch_count = defaultdict(int)
    for od in orders: ch_count[od["ch"]] += 1

    return {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "range": f"{START.month}/{START.day}~{END.month}/{END.day}",
        "total": len(orders),
        "channels": dict(ch_count),
        "orders": orders,
        "picking": picking,
        "cancels": cancels,
        "dups": sorted(dups),
        "lows": lows,
    }

DATA = build()
html = open(os.path.join(BASE_DIR, "shipping_list_template.html")).read()
html = html.replace("/*__DATA__*/null", json.dumps(DATA, ensure_ascii=False))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w").write(html)
print(f"✅ 생성: {OUT}")
print(f"   택배 {DATA['total']}건 | 채널 {DATA['channels']} | 취소 {len(DATA['cancels'])} | 중복 {len(DATA['dups'])} | 품절위험 {len(DATA['lows'])}")
