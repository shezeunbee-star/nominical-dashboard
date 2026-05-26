"""
플랫폼 출고 파일 → 구글 시트 자동 정리
사용법: python3 platform_to_sheets.py [파일경로1] [파일경로2] ...
파일명으로 플랫폼 자동 감지:
  - 29CM_출고관리리스트_*.xlsx → 29CM
  - 상품준비중내역*.xlsx       → W컨셉
  - 배송조회*.xls              → SSF
  - 발송처리목록*.xlsx         → SI Village
"""
import sys, os, re
import openpyxl, xlrd, gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from datetime import datetime

TOKEN_FILE     = "/Users/kimeunbee/Documents/지표분석/token.json"
SPREADSHEET_ID = "1y9mZirj81sR2tkkGV_wTzFvJonPdJU-JuErSRDo_73E"
SHEET_NAME     = "🏬 플랫폼 매출"
COMMISSION     = 30  # 공통 수수료율 (%)

creds = Credentials.from_authorized_user_file(TOKEN_FILE, [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
])
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
gc = gspread.authorize(creds)
ws = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

HEADERS = ["플랫폼", "주문일", "상품명", "상품코드", "컬러", "사이즈", "수량", "판매가", "수수료율(%)", "실수익", "주문상태"]

def ensure_header():
    first = ws.row_values(1)
    if not first or first[0] != "플랫폼":
        ws.update(values=[HEADERS], range_name="A1:K1")
        print("  헤더 작성 완료")

def get_existing_keys():
    """중복 방지용 기존 데이터 키 (플랫폼+주문일+상품코드+컬러+사이즈) 수집"""
    all_rows = ws.get_all_values()
    keys = set()
    for row in all_rows[1:]:
        if len(row) >= 6:
            keys.add(f"{row[0]}|{row[1]}|{row[3]}|{row[4]}|{row[5]}")
    return keys

# ── 컬러/사이즈 파서 ─────────────────────────────────────────────

def parse_color_size_29cm(option):
    """[컬러]블랙 / [사이즈]L 형식"""
    color, size = "-", "-"
    if not option:
        return color, size
    m_color = re.search(r'\[컬러\]([^/\[\]]+)', str(option))
    m_size  = re.search(r'\[사이즈\]([^/\[\]]+)', str(option))
    if m_color: color = m_color.group(1).strip()
    if m_size:  size  = m_size.group(1).strip()
    return color, size

def parse_color_size_slash(option):
    """컬러/사이즈 또는 사이즈만 (SSF, SI Village 공통)"""
    color, size = "-", "-"
    if not option or str(option).strip() == "":
        return color, size
    opt = str(option).strip()
    if "/" in opt:
        parts = opt.split("/", 1)
        color = parts[0].strip()
        size  = parts[1].strip()
    elif opt.upper() == "FREE":
        size = "FREE"
    else:
        size = opt
    return color, size

# ── 날짜 포맷터 ─────────────────────────────────────────────────

def fmt_date(val):
    """일반 날짜 → YYYY-MM-DD (29CM, W컨셉, SSF용)"""
    if not val:
        return ""
    s = str(val)
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    m = re.match(r'(\d{4}-\d{2}-\d{2})', s)
    if m:
        return m.group(1)
    return s[:10]

def fmt_date_sivillage(val):
    """SI Village 날짜: '20260525061821' → '2026-05-25'"""
    if not val:
        return ""
    s = str(val).strip()
    if len(s) >= 8 and s.isdigit():
        try:
            return datetime.strptime(s[:8], "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            pass
    return fmt_date(val)

# ── 플랫폼별 파서 ───────────────────────────────────────────────

def parse_29cm(filepath):
    print(f"  📦 29CM 파싱: {os.path.basename(filepath)}")
    wb = openpyxl.load_workbook(filepath)
    ws_f = wb.active
    rows = []
    for i, row in enumerate(ws_f.iter_rows(values_only=True)):
        if i == 0: continue
        if not row[8]: continue
        color, size = parse_color_size_29cm(row[10])
        qty    = int(row[11]) if row[11] else 1
        price  = int(row[20]) if row[20] else 0
        total  = price * qty
        profit = round(total * (1 - COMMISSION / 100))
        status = str(row[33]) if row[33] else ""
        rows.append([
            "29CM", fmt_date(row[28]),
            str(row[8]), str(row[7]),
            color, size, qty, total,
            COMMISSION, profit, status
        ])
    return rows

def parse_wconcept(filepath):
    print(f"  📦 W컨셉 파싱: {os.path.basename(filepath)}")
    wb = openpyxl.load_workbook(filepath)
    ws_f = wb.active
    rows = []
    for i, row in enumerate(ws_f.iter_rows(values_only=True)):
        if i == 0: continue
        if not row[11]: continue
        color  = str(row[12]) if row[12] else "-"
        size   = str(row[13]) if row[13] else "-"
        qty    = int(row[15]) if row[15] else 1
        price  = int(row[18]) if row[18] else 0
        total  = price * qty
        profit = round(total * (1 - COMMISSION / 100))
        status = "취소" if row[23] else "정상"
        code   = str(row[29]) if row[29] else str(row[10])
        rows.append([
            "W컨셉", fmt_date(row[0]),
            str(row[11]), code,
            color, size, qty, total,
            COMMISSION, profit, status
        ])
    return rows

def parse_ssf(filepath):
    print(f"  📦 SSF 파싱: {os.path.basename(filepath)}")
    wb = xlrd.open_workbook(filepath)
    ws_f = wb.sheet_by_index(0)
    rows = []
    for i in range(1, ws_f.nrows):
        row = ws_f.row_values(i)
        if not row[21]: continue
        color, size = parse_color_size_slash(row[22])
        qty    = int(row[23]) if row[23] else 1
        price  = int(row[28]) if row[28] else 0
        comm   = int(row[29]) if row[29] else COMMISSION
        total  = price * qty
        profit = round(total * (1 - comm / 100))
        status = str(row[25]) if row[25] else ""
        rows.append([
            "SSF", fmt_date(row[0]),
            str(row[21]), str(row[20]),
            color, size, qty, total,
            comm, profit, status
        ])
    return rows

def parse_sivillage(filepath):
    """
    SI Village 발송처리목록 파싱
    컬럼 매핑:
      [2]  배송진행상태 → 주문상태
      [7]  업체상품번호 → 상품코드
      [8]  상품명
      [9]  상품옵션(SKU) → 컬러/사이즈 (예: '더스트핑크/FREE')
      [10] 수량
      [11] 판매금액 → 판매가 (총액)
      [18] 결제완료일시 → 주문일 (예: '20260525061821')
    """
    print(f"  📦 SI Village 파싱: {os.path.basename(filepath)}")
    wb = openpyxl.load_workbook(filepath)
    ws_f = wb.active
    rows = []
    for i, row in enumerate(ws_f.iter_rows(values_only=True)):
        if i == 0: continue          # 헤더 스킵
        if not row[8]: continue      # 상품명 없으면 스킵

        color, size = parse_color_size_slash(row[9])
        qty    = int(row[10]) if row[10] else 1
        total  = int(row[11]) if row[11] else 0   # 판매금액 (총액)
        profit = round(total * (1 - COMMISSION / 100))
        status = str(row[2]) if row[2] else "정상"
        code   = str(row[7]) if row[7] else "-"
        date   = fmt_date_sivillage(row[18])

        rows.append([
            "SI Village", date,
            str(row[8]), code,
            color, size, qty, total,
            COMMISSION, profit, status
        ])
    return rows

# ── 플랫폼 감지 ─────────────────────────────────────────────────

def detect_platform(filepath):
    name = os.path.basename(filepath).lower()
    if "29cm" in name:        return "29cm"
    if "상품준비중" in name:   return "wconcept"
    if "배송조회" in name:     return "ssf"
    if "발송처리목록" in name: return "sivillage"
    return None

# ── 메인 ────────────────────────────────────────────────────────

def main(files):
    ensure_header()
    existing = get_existing_keys()
    all_new = []

    for filepath in files:
        platform = detect_platform(filepath)
        if not platform:
            print(f"  ⚠️ 플랫폼 감지 실패: {filepath}")
            continue

        if platform == "29cm":         rows = parse_29cm(filepath)
        elif platform == "wconcept":   rows = parse_wconcept(filepath)
        elif platform == "ssf":        rows = parse_ssf(filepath)
        elif platform == "sivillage":  rows = parse_sivillage(filepath)
        else:
            rows = []

        added = 0
        for row in rows:
            key = f"{row[0]}|{row[1]}|{row[3]}|{row[4]}|{row[5]}"
            if key not in existing:
                all_new.append(row)
                existing.add(key)
                added += 1
        print(f"  ✅ {added}건 추가 ({len(rows)-added}건 중복 스킵)")

    if all_new:
        ws.append_rows(all_new, value_input_option="USER_ENTERED")
        print(f"\n🎉 총 {len(all_new)}건 시트에 저장 완료!")
    else:
        print("\n새로 추가할 데이터 없음.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python3 platform_to_sheets.py [파일경로1] [파일경로2] ...")
        print("지원 플랫폼:")
        print("  29CM       → 파일명에 '29cm' 포함")
        print("  W컨셉      → 파일명에 '상품준비중' 포함")
        print("  SSF        → 파일명에 '배송조회' 포함")
        print("  SI Village → 파일명에 '발송처리목록' 포함")
    else:
        main(sys.argv[1:])
