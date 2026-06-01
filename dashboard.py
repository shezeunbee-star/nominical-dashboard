"""
NOMINICAL 성과 대시보드
실행: streamlit run dashboard.py
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import gspread
from google.oauth2.service_account import Credentials as SACredentials
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.auth.transport.requests import Request
import json, os
import requests
import time
from datetime import date as _date, timedelta
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest, Dimension, Metric, DateRange,
    FilterExpression, Filter, FilterExpressionList
)

# ── 설정 ───────────────────────────────────────────────────────────
SPREADSHEET_ID      = "1y9mZirj81sR2tkkGV_wTzFvJonPdJU-JuErSRDo_73E"
SHEET_NAME          = "📅 일별 트래킹"
PLATFORM_SHEET_NAME = "🏬 플랫폼 매출"
SA_FILE             = "/Users/kimeunbee/Documents/지표분析/service_account.json"
TOKEN_FILE          = "/Users/kimeunbee/Documents/지표분析/token.json"

COLOR = {
    "primary":    "#1A1A1A",
    "accent":     "#E8FF4D",
    "blue":       "#4F8EF7",
    "green":      "#4ECBA0",
    "orange":     "#F7874F",
    "purple":     "#9B59B6",
    "gray":       "#8C8C8C",
    "bg":         "#F9F9F7",
    "card":       "#FFFFFF",
}

CHANNEL_COLORS = {
    "메타광고":   "#1877F2",
    "공식인스타": "#E1306C",
    "개인인스타": "#F56040",
    "직접방문":   "#1A1A1A",
}

PLATFORM_COLORS = {
    "29CM":       "#E94B3C",   # 레드
    "W컨셉":      "#5B3F9E",   # 딥 퍼플
    "SSF":        "#0077C8",   # 삼성 블루
    "SI Village": "#C8A951",   # 신세계 골드
    "무신사":     "#222222",   # 무신사 블랙
    "Cafe24":     "#4ECBA0",   # 그린
}

st.set_page_config(
    page_title="NOMINICAL 대시보드",
    page_icon="🏃",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── 비밀번호 인증 ────────────────────────────────────────────────────
def check_password():
    correct_pw = st.secrets.get("dashboard_password", "nominical2026")

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.markdown("""
    <div style="max-width:360px;margin:15vh auto 0;text-align:center;">
        <div style="font-size:36px;margin-bottom:8px;">🏃</div>
        <div style="font-size:22px;font-weight:700;color:#1A1A1A;margin-bottom:4px;">NOMINICAL</div>
        <div style="font-size:13px;color:#8C8C8C;margin-bottom:32px;">성과 대시보드</div>
    </div>
    """, unsafe_allow_html=True)

    col = st.columns([1, 2, 1])[1]
    with col:
        pw = st.text_input("비밀번호", type="password", placeholder="비밀번호 입력")
        if st.button("로그인", use_container_width=True):
            if pw == correct_pw:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸어요.")
    return False

if not check_password():
    st.stop()

# ── 커스텀 CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #F9F9F7; }
    .kpi-card {
        background: #FFFFFF;
        border-radius: 16px;
        padding: 24px 20px;
        border: 1px solid #EBEBEB;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .kpi-card-sm {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 16px 16px;
        border: 1px solid #EBEBEB;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .kpi-label { font-size: 12px; color: #8C8C8C; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 6px; }
    .kpi-label-sm { font-size: 11px; color: #8C8C8C; font-weight: 600; letter-spacing: 0.06em; margin-bottom: 4px; }
    .kpi-value { font-size: 28px; font-weight: 700; color: #1A1A1A; line-height: 1; }
    .kpi-value-sm { font-size: 20px; font-weight: 700; color: #1A1A1A; line-height: 1; }
    .kpi-delta-pos { font-size: 13px; font-weight: 600; color: #4ECBA0; margin-top: 6px; }
    .kpi-delta-neg { font-size: 13px; font-weight: 600; color: #F7874F; margin-top: 6px; }
    .kpi-delta-neu { font-size: 13px; font-weight: 500; color: #8C8C8C; margin-top: 6px; }
    .section-title { font-size: 16px; font-weight: 700; color: #1A1A1A; margin-bottom: 4px; }
    .section-sub   { font-size: 12px; color: #8C8C8C; margin-bottom: 16px; }
    div[data-testid="stMetric"] { display: none; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    .platform-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
        color: white;
        margin-bottom: 6px;
    }
</style>
""", unsafe_allow_html=True)


# ── 헬퍼 ───────────────────────────────────────────────────────────
def fmt_num(n, suffix=""):
    if n >= 10000:
        return f"{n/10000:.1f}만{suffix}"
    return f"{int(n):,}{suffix}"

def kpi_card(label, value, delta_str="", delta_pos=None):
    delta_class = "kpi-delta-pos" if delta_pos is True else ("kpi-delta-neg" if delta_pos is False else "kpi-delta-neu")
    delta_html = f'<div class="{delta_class}">{delta_str}</div>' if delta_str else ""
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)

def kpi_card_sm(label, value, badge_color="#1A1A1A", sub=""):
    sub_html = f'<div style="font-size:11px;color:#8C8C8C;margin-top:4px;">{sub}</div>' if sub else ""
    st.markdown(f"""
    <div class="kpi-card-sm">
        <div style="display:inline-block;padding:2px 8px;border-radius:20px;background:{badge_color};
                    font-size:10px;font-weight:700;color:white;margin-bottom:6px;">{label}</div>
        <div class="kpi-value-sm">{value}</div>
        {sub_html}
    </div>
    """, unsafe_allow_html=True)

def chart_container(title, subtitle=""):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-sub">{subtitle}</div>', unsafe_allow_html=True)

def insight_box(lines, color=None):
    bc = color or "#4F8EF7"
    body = "".join(f'<div style="margin-bottom:6px;">{l}</div>' for l in lines)
    st.markdown(f"""
    <div style="background:#FAFAFA;border-left:4px solid {bc};padding:13px 18px;
                border-radius:8px;font-size:13px;color:#1A1A1A;margin:8px 0 20px;
                border:1px solid #EBEBEB;">
    {body}
    </div>""", unsafe_allow_html=True)




# ── OAuth 크레덴셜 헬퍼 ─────────────────────────────────────────────
def _get_oauth_creds():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/analytics.readonly",
    ]
    token_json = None
    try:
        token_json = st.secrets["google_token_json"]
    except Exception:
        pass
    if token_json:
        token_info = json.loads(token_json) if isinstance(token_json, str) else dict(token_json)
        creds = OAuthCredentials.from_authorized_user_info(token_info, scopes)
    else:
        creds = OAuthCredentials.from_authorized_user_file(TOKEN_FILE, scopes)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds

GA4_PROPERTY_ID = "536368183"
AD_ACCOUNT      = "act_1599099620677018"

def update_ga4_yesterday():
    try:
        creds = _get_oauth_creds()
        ga4_client = BetaAnalyticsDataClient(credentials=creds)
        gc_o = gspread.authorize(creds)
        ws_t = gc_o.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

        yesterday = _date.today() - timedelta(days=1)
        date_str  = yesterday.strftime("%Y-%m-%d")
        day_label = f"{yesterday.month}/{yesterday.day}"

        def run_report(dims, mets, filter_expr=None):
            req = RunReportRequest(
                property=f"properties/{GA4_PROPERTY_ID}",
                dimensions=[Dimension(name=d) for d in dims],
                metrics=[Metric(name=m) for m in mets],
                date_ranges=[DateRange(start_date=date_str, end_date=date_str)],
            )
            if filter_expr:
                req.dimension_filter = filter_expr
            return ga4_client.run_report(req)

        res = run_report(["date"], ["sessions","transactions","bounceRate","averagePurchaseRevenue","purchaseRevenue"])
        sessions = transactions = bounce = avg_price = revenue = 0
        if res.rows:
            r = res.rows[0].metric_values
            sessions     = int(float(r[0].value))
            transactions = int(float(r[1].value))
            bounce       = round(float(r[2].value) * 100, 1)
            avg_price    = round(float(r[3].value))
            revenue      = round(float(r[4].value))

        def get_channel(source, medium):
            f = FilterExpression(and_group=FilterExpressionList(expressions=[
                FilterExpression(filter=Filter(field_name="sessionSource",
                    string_filter=Filter.StringFilter(value=source, match_type="EXACT"))),
                FilterExpression(filter=Filter(field_name="sessionMedium",
                    string_filter=Filter.StringFilter(value=medium, match_type="EXACT")))
            ]))
            r = run_report(["sessionSource"], ["sessions"], f)
            return int(float(r.rows[0].metric_values[0].value)) if r.rows else 0

        time.sleep(0.3); ch_meta     = get_channel("meta","paid_feed") + get_channel("ig","paid")
        time.sleep(0.3); ch_official = get_channel("instagram","bio")
        time.sleep(0.3); ch_personal = get_channel("instagram","personal_bio") + get_channel("instagram","personal_story")
        time.sleep(0.3)
        f_direct = FilterExpression(filter=Filter(field_name="sessionMedium",
            string_filter=Filter.StringFilter(value="(none)", match_type="EXACT")))
        r_direct = run_report(["sessionMedium"], ["sessions"], f_direct)
        ch_direct = int(float(r_direct.rows[0].metric_values[0].value)) if r_direct.rows else 0

        res_new = run_report(["newVsReturning"], ["activeUsers"])
        new_users = returning_users = 0
        for row in res_new.rows:
            val = int(float(row.metric_values[0].value))
            if row.dimension_values[0].value == "new":
                new_users = val
            else:
                returning_users = val

        all_dates = ws_t.col_values(1)
        row_idx = next((i+1 for i, d in enumerate(all_dates) if d == day_label), None)
        if not row_idx:
            return False, f"❌ GA4: 시트에 {day_label} 날짜 행 없음"

        ws_t.update(values=[[sessions, transactions]], range_name=f"K{row_idx}:L{row_idx}")
        time.sleep(0.2)
        ws_t.update(values=[[bounce, avg_price, revenue, ch_meta, ch_official, ch_personal, ch_direct]],
                    range_name=f"N{row_idx}:T{row_idx}")
        time.sleep(0.2)
        ws_t.update(values=[[new_users, returning_users]], range_name=f"U{row_idx}:V{row_idx}")
        return True, f"✅ GA4 {day_label} 업데이트 완료 (방문 {sessions}명, 전환 {transactions}건)"
    except Exception as e:
        return False, f"❌ GA4 업데이트 실패: {e}"

def update_meta_yesterday():
    try:
        meta_token = None
        for key in ("meta_access_token", "META_ACCESS_TOKEN", "meta_token"):
            try:
                meta_token = st.secrets[key]
                if meta_token: break
            except Exception:
                pass
        if not meta_token:
            _tf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "meta_token.txt")
            if os.path.exists(_tf):
                meta_token = open(_tf).read().strip()
        if not meta_token:
            return False, "❌ Meta 토큰 없음. Streamlit secrets에 meta_access_token을 추가해 주세요."

        yesterday = _date.today() - timedelta(days=1)
        date_str  = yesterday.strftime("%Y-%m-%d")
        day_label = f"{yesterday.month}/{yesterday.day}"

        res = requests.get(
            f"https://graph.facebook.com/v25.0/{AD_ACCOUNT}/insights",
            params={
                "fields": "spend,impressions,clicks,ctr,cpc,actions,purchase_roas",
                "time_range": f'{{"since":"{date_str}","until":"{date_str}"}}',
                "access_token": meta_token
            }
        ).json()

        spend = impressions = clicks = purchases = 0
        if res.get("data"):
            d = res["data"][0]
            spend       = round(float(d.get("spend", 0)))
            impressions = int(d.get("impressions", 0))
            clicks      = int(d.get("clicks", 0))
            for action in d.get("actions", []):
                if action["action_type"] in ("purchase","offsite_conversion.fb_pixel_purchase"):
                    purchases = int(float(action["value"]))

        creds = _get_oauth_creds()
        gc_o  = gspread.authorize(creds)
        ws_t  = gc_o.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        all_dates = ws_t.col_values(1)
        row_idx = next((i+1 for i, d in enumerate(all_dates) if d == day_label), None)
        if not row_idx:
            return False, f"❌ Meta: 시트에 {day_label} 날짜 행 없음"

        ws_t.update(values=[[spend, impressions, clicks]], range_name=f"C{row_idx}:E{row_idx}")
        time.sleep(0.2)
        ws_t.update(values=[[purchases]], range_name=f"H{row_idx}")
        return True, f"✅ Meta {day_label} 업데이트 완료 (광고비 {spend:,}원, 전환 {purchases}건)"
    except Exception as e:
        return False, f"❌ Meta 업데이트 실패: {e}"

# ── 데이터 로드: 방문자/광고 ────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data():
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    if "gcp_service_account" in st.secrets:
        creds = SACredentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=SCOPES
        )
    elif os.path.exists(SA_FILE):
        creds = SACredentials.from_service_account_file(SA_FILE, scopes=SCOPES)
    else:
        creds = OAuthCredentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    raw = ws.get("A2:W40", value_render_option="UNFORMATTED_VALUE")

    headers = raw[0]
    rows = []
    for r in raw[1:]:
        if not r or not r[0]: continue
        label = str(r[0])
        if "종합" in label or "날짜" in label: continue
        row = dict(zip(headers, r + [""] * (len(headers) - len(r))))
        rows.append(row)

    df = pd.DataFrame(rows)

    def safe_num(col, default=0):
        return pd.to_numeric(df[col], errors="coerce").fillna(default)

    date_col    = df.iloc[:, 0].apply(lambda x: str(x).strip())
    spend       = safe_num(headers[2])
    impressions = safe_num(headers[3])
    clicks      = safe_num(headers[4])
    ctr         = safe_num(headers[5])
    cpc         = safe_num(headers[6])
    conv_meta   = safe_num(headers[7])
    roas_meta   = safe_num(headers[8])
    visitors    = safe_num(headers[10])
    purchases   = safe_num(headers[11])
    bounce      = safe_num(headers[13])
    avg_price   = safe_num(headers[14])
    revenue     = safe_num(headers[15])
    ch_meta     = safe_num(headers[16])
    ch_off      = safe_num(headers[17])
    ch_per      = safe_num(headers[18])
    ch_dir      = safe_num(headers[19])
    new_users   = safe_num(headers[20])
    ret_users   = safe_num(headers[21])

    result = pd.DataFrame({
        "날짜":       date_col.values,
        "광고비":     spend.values,
        "노출수":     impressions.values,
        "클릭수":     clicks.values,
        "CTR":        ctr.values,
        "CPC":        cpc.values,
        "전환_메타":  conv_meta.values,
        "ROAS_메타":  roas_meta.values,
        "방문자":     visitors.values,
        "구매":       purchases.values,
        "이탈율":     bounce.values,
        "객단가":     avg_price.values,
        "매출":       revenue.values,
        "유입_메타":  ch_meta.values,
        "유입_공식":  ch_off.values,
        "유입_개인":  ch_per.values,
        "유입_직접":  ch_dir.values,
        "신규":       new_users.values,
        "재방문":     ret_users.values,
    })

    result["CPO"] = result.apply(
        lambda r: round(r["광고비"] / r["구매"]) if r["구매"] > 0 and r["광고비"] > 0 else 0, axis=1
    )
    result["전환율"] = result.apply(
        lambda r: round(r["구매"] / r["방문자"] * 100, 2) if r["방문자"] > 0 else 0, axis=1
    )
    result["ROAS"] = result.apply(
        lambda r: round(r["매출"] / r["광고비"], 2) if r["광고비"] > 0 and r["매출"] > 0 else 0, axis=1
    )

    def parse_date(s):
        try:
            parts = str(s).strip().split("/")
            return pd.Timestamp(f"2026-{int(parts[0]):02d}-{int(parts[1]):02d}")
        except:
            return pd.NaT

    result["날짜_dt"] = result["날짜"].apply(parse_date)
    result["주차"] = result["날짜_dt"].apply(
        lambda d: f"{d.month}월 {((d.day - 1) // 7) + 1}주차" if pd.notna(d) else ""
    )
    result = result[result["방문자"] > 0].reset_index(drop=True)
    return result


# ── 데이터 로드: 플랫폼 매출 ────────────────────────────────────────
@st.cache_data(ttl=60)
def load_platform_data():
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    if "gcp_service_account" in st.secrets:
        creds = SACredentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=SCOPES
        )
    elif os.path.exists(SA_FILE):
        creds = SACredentials.from_service_account_file(SA_FILE, scopes=SCOPES)
    else:
        creds = OAuthCredentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SPREADSHEET_ID).worksheet(PLATFORM_SHEET_NAME)
    raw = ws.get_all_values()

    if len(raw) <= 1:
        return pd.DataFrame()

    headers = raw[0]
    rows = [dict(zip(headers, r + [""] * (len(headers) - len(r)))) for r in raw[1:] if r and r[0]]
    df = pd.DataFrame(rows)

    for col in ["수량", "판매가", "수수료율(%)", "실수익"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce").fillna(0)

    if "주문일" in df.columns:
        def _safe_dt(s):
            s = str(s).strip()
            if s in ('', 'None', 'nan', '-', 'NaT'):
                return pd.NaT
            try:
                return pd.to_datetime(s, format="%Y-%m-%d")
            except Exception:
                pass
            try:
                return pd.to_datetime(s)
            except Exception:
                return pd.NaT

        df["주문일_dt"] = df["주문일"].apply(_safe_dt)
        # 날짜 없는 행 제거 (빈 행 방지)
        df = df[df["주문일_dt"].notna()].reset_index(drop=True)
        df["주차"] = df["주문일_dt"].apply(
            lambda d: f"{d.month}월 {((d.day - 1) // 7) + 1}주차" if pd.notna(d) else ""
        )
        df["주문월"] = df["주문일_dt"].apply(
            lambda d: f"{d.month}월" if pd.notna(d) else ""
        )

    return df


# ══════════════════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════════════════
df_all          = load_data()
df_platform_all = load_platform_data()

# 헤더
col_logo, col_refresh = st.columns([6, 1])
with col_logo:
    st.markdown("## 🏃 NOMINICAL 성과 대시보드")
with col_refresh:
    if st.button("🔄 새로고침"):
        with st.spinner("전일자 데이터 업데이트 중..."):
            ok1, msg1 = update_ga4_yesterday()
            ok2, msg2 = update_meta_yesterday()
        if ok1:
            st.toast(msg1, icon="✅")
        else:
            st.toast(msg1, icon="⚠️")
        if ok2:
            st.toast(msg2, icon="✅")
        else:
            st.toast(msg2, icon="⚠️")
        # 각 캐시 함수 명시적으로 개별 초기화 (st.cache_data.clear()만으론 Cloud에서 불안정)
        load_data.clear()
        load_platform_data.clear()
        st.rerun()

st.markdown("---")

# ── 탭 분기 ──────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 방문자 · 광고 성과", "🏬 플랫폼별 매출", "📅 기간별 매출 조회"])


# ════════════════════════════════════════════════════════════════
# TAB 1: 방문자 & 광고 성과 (기존 대시보드)
# ════════════════════════════════════════════════════════════════
with tab1:

    # 기간 필터
    weeks = ["전체 기간"] + sorted(df_all["주차"].unique().tolist(),
                key=lambda x: df_all[df_all["주차"]==x]["날짜_dt"].iloc[0])
    col_f1, col_f2, col_f3 = st.columns([2, 2, 4])
    with col_f1:
        preset = st.selectbox("📅 조회 기간",
            ["전체 기간", "최근 7일", "최근 14일"] + [w for w in weeks if "주차" in w],
            label_visibility="collapsed", key="tab1_preset")
    with col_f2:
        if preset == "전체 기간":
            period_label = f"전체 {len(df_all)}일"
        elif "주차" in preset:
            period_label = f"📆 {preset}"
        else:
            n = int(preset.replace("최근 ", "").replace("일", ""))
            period_label = f"최근 {n}일"
        st.markdown(f'<div style="padding:8px 0;color:#8C8C8C;font-size:13px;">{period_label} 기준</div>',
                    unsafe_allow_html=True)

    if preset == "전체 기간":
        df = df_all.copy()
    elif "주차" in preset:
        df = df_all[df_all["주차"] == preset].copy()
    else:
        n = int(preset.replace("최근 ", "").replace("일", ""))
        df = df_all.tail(n).copy()
    df = df.reset_index(drop=True)

    st.markdown("---")

    # KPI 카드
    ad_days   = df[df["광고비"] > 0]
    conv_days = df[df["구매"] > 0]

    total_visitors  = int(df["방문자"].sum())
    total_purchases = int(df["구매"].sum())
    total_spend     = int(df["광고비"].sum())
    total_revenue   = int(df["매출"].sum())
    avg_cpo         = int(total_spend / total_purchases) if total_purchases > 0 else 0
    overall_roas    = round(total_revenue / total_spend, 1) if total_spend > 0 else 0
    overall_cvr     = round(total_purchases / total_visitors * 100, 2) if total_visitors > 0 else 0
    new_sum         = df["신규"].sum()
    ret_sum         = df["재방문"].sum()
    avg_new_rate    = int(new_sum / (new_sum + ret_sum) * 100) if (new_sum + ret_sum) > 0 else 0

    recent = df.tail(7)
    prior  = df.iloc[max(0, len(df)-14):len(df)-7]
    vis_delta = ""
    vis_pos = None
    if len(prior) > 0 and prior["방문자"].sum() > 0:
        pct = round((recent["방문자"].sum() - prior["방문자"].sum()) / prior["방문자"].sum() * 100)
        vis_delta = f"{'▲' if pct >= 0 else '▼'} {abs(pct)}% vs 이전 7일"
        vis_pos = pct >= 0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: kpi_card("총 방문자", fmt_num(total_visitors, "명"), vis_delta, vis_pos)
    with c2: kpi_card("총 전환", f"{total_purchases}건", f"전환율 {overall_cvr}%")
    with c3: kpi_card("누적 광고비", fmt_num(total_spend, "원"))
    with c4: kpi_card("누적 매출", fmt_num(total_revenue, "원"), f"ROAS {overall_roas}배", overall_roas >= 3)
    with c5: kpi_card("평균 CPO", f"{avg_cpo:,}원" if avg_cpo else "—", f"전환일 {len(conv_days)}일")
    with c6: kpi_card("신규방문 비율", f"{avg_new_rate}%", f"재방문 {100-avg_new_rate}%")

    # KPI 인사이트
    _kpi_lines = []
    if len(df) >= 7:
        _r7  = df.tail(7); _p7 = df.iloc[-14:-7] if len(df) >= 14 else df.head(max(1,len(df)-7))
        _v_r = int(_r7["방문자"].sum()); _v_p = int(_p7["방문자"].sum())
        _s_r = int(_r7["광고비"].sum()); _s_p = int(_p7["광고비"].sum())
        _c_r = int(_r7["구매"].sum());   _c_p = int(_p7["구매"].sum())
        _rev_r = _r7["매출"].sum(); _rev_p = _p7["매출"].sum()
        _vd = round((_v_r-_v_p)/_v_p*100) if _v_p>0 else 0
        _sd = round((_s_r-_s_p)/_s_p*100) if _s_p>0 else 0
        _cd = _c_r - _c_p
        _arrow = lambda x: ("▲" if x>0 else "▼") + f"{abs(x)}%"
        _vis_comment = (
            f"방문자가 {abs(_vd)}% 증가했는데 전환이 {'함께 늘었어요' if _cd>0 else '늘지 않았다면 랜딩 경험이나 상품 설득력 점검이 필요해요'}." if _vd>0 else
            f"방문자가 {abs(_vd)}% 감소했어요. {'광고비도 줄었다면 예산 축소 영향이며,' if _sd<0 else '광고비는 유지됐으므로 소재 반응이 떨어진 것으로'} 새 소재 테스트가 필요해요." if _vd<0 else
            "방문자 수 큰 변동 없이 안정적이에요."
        )
        _kpi_lines.append(f"📊 지난 7일 vs 이전 7일 — 방문자 {_arrow(_vd)} ({_v_r:,}명) · 광고비 {_arrow(_sd)} ({_s_r:,}원) · 전환 {_c_r}건({'▲' if _cd>0 else ('▼' if _cd<0 else '±')}{abs(_cd)}건). {_vis_comment}")
    # ROAS: 전체 매출/전체 광고비로 정확 계산
    _roas_v = overall_roas
    _new_pct = avg_new_rate
    _ret_pct = 100 - _new_pct
    if total_purchases > 0 and total_spend > 0:
        if _roas_v >= 3:
            _kpi_lines.append(f"💰 ROAS {_roas_v}배 — 광고비 대비 수익이 나는 구간이에요. 단, 플랫폼 수수료(약 30%)와 원가를 고려한 실수익률도 함께 체크하세요. 현재 소재·타겟 조합을 유지하면서 일예산 10~20% 증액 테스트를 권장해요.")
        elif _roas_v >= 2:
            _kpi_lines.append(f"💰 ROAS {_roas_v}배 — 손익분기(3배)에 근접했지만 아직 미달이에요. 클릭 후 구매까지 이어지지 않는 구간(장바구니 이탈, 결제 직전 이탈)을 GA4 퍼널로 확인하고, 이탈 시점에 맞는 리타게팅 메시지를 추가하면 전환율을 높일 수 있어요.")
        else:
            _kpi_lines.append(f"💰 ROAS {_roas_v}배 — 광고비 대비 매출 회수가 낮아요. 타겟 오디언스가 실제 구매층과 일치하는지 점검하고, 현재 소재를 구매 전환에 특화된 메시지(한정 수량·할인 종료 임박)로 교체해보세요.")
    if _new_pct > 85:
        _kpi_lines.append(f"👥 신규 {_new_pct}% · 재방문 {_ret_pct}% — 신규 방문 비중이 압도적으로 높아요. 이는 브랜드 인지가 아직 쌓이지 않았다는 의미로, 재방문율을 높이려면 팔로우 유도 콘텐츠, 첫 구매 쿠폰, 카카오채널 추가 등 락인 장치가 필요해요.")
    elif _ret_pct >= 20:
        _kpi_lines.append(f"👥 신규 {_new_pct}% · 재방문 {_ret_pct}% — 재방문 비중이 {_ret_pct}%로 양호해요. 재방문자는 구매 의향이 높은 잠재 고객이에요. 이 그룹에게 '한정 재고', '오늘만 혜택' 메시지로 전환을 유도하면 CPO를 크게 낮출 수 있어요.")
    else:
        _kpi_lines.append(f"👥 신규 {_new_pct}% · 재방문 {_ret_pct}% — 재방문자가 적어 브랜드 충성도 형성이 초기 단계예요. 인스타그램 스토리 리타게팅과 메타 맞춤 타겟(웹사이트 방문자)을 활용하면 재방문율을 끌어올릴 수 있어요.")
    if _kpi_lines:
        insight_box(_kpi_lines, "#4F8EF7")

    st.markdown("<br>", unsafe_allow_html=True)

    # 차트 1: 일별 방문자 & 전환 추이
    chart_container("일별 방문자 · 전환 추이", "바이럴 스파이크, 광고 집행일, 전환 발생 패턴을 한눈에")

    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    fig1.add_trace(go.Scatter(
        x=df["날짜"], y=df["방문자"],
        name="방문자",
        fill="tozeroy",
        fillcolor="rgba(79,142,247,0.12)",
        line=dict(color=COLOR["blue"], width=2),
        hovertemplate="<b>%{x}</b><br>방문자: %{y:,}명<extra></extra>",
    ), secondary_y=False)
    fig1.add_trace(go.Bar(
        x=df["날짜"], y=df["광고비"],
        name="광고비",
        marker_color="rgba(232,255,77,0.7)",
        marker_line_color=COLOR["accent"],
        marker_line_width=1,
        hovertemplate="<b>%{x}</b><br>광고비: %{y:,}원<extra></extra>",
        yaxis="y3",
    ), secondary_y=False)
    conv_df = df[df["구매"] > 0]
    fig1.add_trace(go.Scatter(
        x=conv_df["날짜"], y=conv_df["방문자"],
        name="전환 발생",
        mode="markers",
        marker=dict(symbol="circle", size=12, color=COLOR["green"],
                    line=dict(color="white", width=2)),
        hovertemplate="<b>%{x}</b><br>전환 %{customdata}건<extra></extra>",
        customdata=conv_df["구매"].astype(int),
    ), secondary_y=False)
    fig1.update_layout(
        height=320, margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(showgrid=False, tickfont=dict(size=11)),
        yaxis=dict(showgrid=True, gridcolor="#F0F0F0", tickfont=dict(size=11), title="방문자수"),
        hovermode="x unified", barmode="overlay",
    )
    fig1.update_layout(yaxis2=dict(overlaying="y", visible=False))
    st.plotly_chart(fig1, use_container_width=True)

    # 방문자/전환 추이 인사이트
    _vis_lines = []
    _ad_days_cnt = len(df[df["광고비"]>0])
    _conv_days_cnt = len(df[df["구매"]>0])
    if total_spend > 0:
        _spend_per_day = round(total_spend / max(_ad_days_cnt, 1))
        _conv_hit_rate = round(_conv_days_cnt / max(_ad_days_cnt, 1) * 100)
        _vis_lines.append(
            f"💸 광고 집행일 <b>{_ad_days_cnt}일</b> · 일평균 <b>{_spend_per_day:,}원</b> 집행 "
            f"→ 전환 발생일 <b>{_conv_days_cnt}일</b> ({_conv_hit_rate}%)"
        )
        if _conv_days_cnt == 0:
            _vis_lines.append(
                f"⚠️ <b>전환 0건</b> — 광고비 {total_spend:,}원을 쓰고 있는데 구매가 한 건도 없어요. "
                f"원인을 단계별로 체크하세요: "
                f"① <b>소재↔랜딩 불일치</b>: 광고 이미지와 상품페이지 첫 화면이 다르면 즉시 이탈 — 소재와 동일한 착용컷을 랜딩 최상단에 배치하세요. "
                f"② <b>결제 마찰</b>: 배송비·회원가입 강제가 결제 직전 이탈을 만들어요 — 게스트 결제 허용 또는 배송비를 상품가에 포함하는 방식을 검토하세요. "
                f"③ <b>타겟 불일치</b>: 메타 광고 관리자에서 '링크 클릭 → 장바구니 추가 → 구매' 퍼널 이탈율을 확인해 병목 구간을 특정하세요."
            )
        elif total_purchases > 0:
            _cvr = round(total_purchases / max(total_visitors, 1) * 100, 2)
            _cpo = round(total_spend / total_purchases)
            if _cvr >= 2.0:
                _cvr_msg = (
                    f"전환율 <b style='color:#27AE60'>{_cvr}%</b> — 패션 이커머스 평균(1~2%)을 상회하는 우수한 수치예요. "
                    f"소재·상품페이지 조합이 잘 맞고 있어요. 지금이 트래픽을 늘릴 타이밍이에요 — 일예산을 주 단위로 20~30%씩 점진적으로 증액해보세요."
                )
            elif _cvr >= 1.0:
                _cvr_msg = (
                    f"전환율 <b style='color:#F39C12'>{_cvr}%</b> — 패션 이커머스 평균(1~2%) 범위예요. "
                    f"리뷰 수·별점 강화, 상세페이지 상단에 광고 소재와 동일한 착용컷 배치, 사이즈 가이드 접근성 개선으로 "
                    f"전환율을 1~2%p 더 끌어올릴 수 있어요."
                )
            else:
                _cvr_msg = (
                    f"전환율 <b style='color:#E74C3C'>{_cvr}%</b> — 패션 이커머스 평균(1~2%) 미달이에요. "
                    f"방문자는 들어오지만 구매로 이어지지 않는 상황이에요. "
                    f"GA4에서 '상품 조회 → 장바구니 → 결제 완료' 퍼널 이탈율을 확인하고, "
                    f"가장 이탈이 큰 단계에 집중 개선이 필요해요."
                )
            _vis_lines.append(f"🎯 {_cvr_msg}")
            if _cpo < 30000:
                _cpo_label = f"<b style='color:#27AE60'>{_cpo:,}원</b> — 효율 좋은 구간이에요. 이 소재·타겟 조합을 메인으로 유지하면서 예산 증액을 검토하세요."
            elif _cpo < 70000:
                _cpo_label = (
                    f"<b style='color:#F39C12'>{_cpo:,}원</b> — 상품 평균 객단가를 기준으로 손익분기 CPO를 설정해보세요. "
                    f"객단가의 20~30% 이하가 일반적인 목표 CPO 범위예요. 리타게팅 비중을 높이면 CPO를 낮출 수 있어요."
                )
            else:
                _cpo_label = (
                    f"<b style='color:#E74C3C'>{_cpo:,}원</b> — CPO가 높아요. 광범위 신규 타겟보다 "
                    f"'웹사이트 방문자' 맞춤 타겟 리타게팅 캠페인으로 전환하면 CPO를 30~50% 낮출 수 있어요."
                )
            _vis_lines.append(f"💡 CPO {_cpo_label}")
    elif total_visitors > 0:
        _avg_vis = df["방문자"].mean()
        _max_vis = df["방문자"].max()
        if _max_vis > _avg_vis * 2:
            _vis_lines.append(
                f"📌 광고 미집행 기간 — 방문자 {total_visitors:,}명 순수 오가닉 유입. "
                f"최대 {int(_max_vis):,}명 스파이크(평균 대비 {round(_max_vis/_avg_vis, 1)}배)가 있었어요. "
                f"이 날 어떤 콘텐츠가 확산됐는지 분석해 같은 포맷을 반복 생산하면 오가닉 트래픽 기반을 구조적으로 늘릴 수 있어요."
            )
        else:
            _vis_lines.append(
                f"📌 광고 미집행 기간 — 방문자 {total_visitors:,}명 오가닉 유입. "
                f"꾸준한 콘텐츠 발행으로 유기 트래픽 기반을 쌓는 중이에요."
            )
    if len(df) > 3:
        _mx = df.loc[df["방문자"].idxmax()]
        _avg_v = df["방문자"].mean()
        if _mx["방문자"] > _avg_v * 2.5 and total_spend > 0:
            _ch_map = {"메타광고": _mx["유입_메타"], "공식인스타": _mx["유입_공식"], "개인인스타": _mx["유입_개인"], "직접방문": _mx["유입_직접"]}
            _top_ch = max(_ch_map, key=_ch_map.get)
            _vis_lines.append(
                f"📈 <b>{_mx['날짜']} 트래픽 스파이크</b> — 평균 대비 {round(_mx['방문자']/_avg_v, 1)}배 급등, "
                f"주요 유입: {_top_ch}. 이 날 집행 소재·콘텐츠를 분석해 같은 패턴으로 재활용하세요."
            )
    if _vis_lines:
        insight_box(_vis_lines, "#4ECBA0")

    st.markdown("<br>", unsafe_allow_html=True)

    # 차트 2+3: 광고 효율 & 채널 유입
    col_left, col_right = st.columns([3, 2])

    with col_left:
        chart_container("광고 효율 추이", "광고비·CTR 항상 표시 / CPO·ROAS는 전환 발생 시")
        ad_df = df[df["광고비"] > 0].copy()
        if not ad_df.empty:
            fig2 = make_subplots(specs=[[{"secondary_y": True}]])
            # 광고비 막대 (항상)
            fig2.add_trace(go.Bar(
                x=ad_df["날짜"], y=ad_df["광고비"],
                name="광고비 (원)",
                marker_color=COLOR["blue"], opacity=0.5,
                hovertemplate="<b>%{x}</b><br>광고비: %{y:,}원<extra></extra>",
            ), secondary_y=False)
            # CTR 라인 (항상)
            ctr_df = ad_df[ad_df["CTR"] > 0]
            if not ctr_df.empty:
                fig2.add_trace(go.Scatter(
                    x=ctr_df["날짜"], y=ctr_df["CTR"],
                    name="CTR (%)",
                    mode="lines+markers",
                    line=dict(color=COLOR["orange"], width=2),
                    marker=dict(size=6, color=COLOR["orange"]),
                    hovertemplate="<b>%{x}</b><br>CTR: %{y:.2f}%<extra></extra>",
                ), secondary_y=True)
            # CPO 라인 (전환 있을 때)
            cpo_df = ad_df[ad_df["CPO"] > 0]
            if not cpo_df.empty:
                fig2.add_trace(go.Scatter(
                    x=cpo_df["날짜"], y=cpo_df["CPO"],
                    name="CPO (원)",
                    mode="lines+markers",
                    line=dict(color=COLOR["purple"], width=2, dash="dot"),
                    marker=dict(size=6, color=COLOR["purple"]),
                    hovertemplate="<b>%{x}</b><br>CPO: %{y:,}원<extra></extra>",
                ), secondary_y=False)
            # ROAS 라인 (전환 있을 때)
            roas_df = ad_df[ad_df["ROAS"] > 0]
            if not roas_df.empty:
                fig2.add_trace(go.Scatter(
                    x=roas_df["날짜"], y=roas_df["ROAS"],
                    name="ROAS (배)",
                    mode="lines+markers",
                    line=dict(color=COLOR["green"], width=2.5),
                    marker=dict(size=7, color=COLOR["green"]),
                    hovertemplate="<b>%{x}</b><br>ROAS: %{y:.1f}배<extra></extra>",
                ), secondary_y=True)
            fig2.update_layout(
                height=300, margin=dict(l=0, r=0, t=10, b=0),
                plot_bgcolor="white", paper_bgcolor="white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                xaxis=dict(showgrid=False, tickfont=dict(size=11)),
                yaxis=dict(showgrid=True, gridcolor="#F0F0F0", tickfont=dict(size=11), title="광고비 (원)"),
                yaxis2=dict(showgrid=False, tickfont=dict(size=11), title="CTR (%) / ROAS (배)"),
                hovermode="x unified",
            )
            st.plotly_chart(fig2, use_container_width=True)
            # 광고효율 인사이트
            _ae_lines = []
            _avg_ctr = ctr_df["CTR"].mean() if not ctr_df.empty else 0
            _recent_ctr = ctr_df["CTR"].iloc[-3:].mean() if len(ctr_df) >= 3 else _avg_ctr
            if _avg_ctr > 0:
                if _avg_ctr >= 2.0:
                    _ctr_level = f"<b style='color:#27AE60'>{_avg_ctr:.2f}%</b> — 패션 광고 CTR 우수 구간(2%+)이에요. 이 소재·타겟 조합을 메인으로 고정하고 예산을 집중하세요."
                elif _avg_ctr >= 1.0:
                    _ctr_level = (
                        f"<b style='color:#F39C12'>{_avg_ctr:.2f}%</b> — CTR 보통 수준이에요. "
                        f"썸네일 첫 1초 임팩트를 강화하거나 후크(Hook) 문구를 변경해 클릭률을 끌어올릴 여지가 있어요."
                    )
                else:
                    _ctr_level = (
                        f"<b style='color:#E74C3C'>{_avg_ctr:.2f}%</b> — CTR 낮아요. "
                        f"노출 대비 클릭이 적은 상태예요. 소재 이미지가 피드에서 멈춰 세울 만큼 강렬한지, "
                        f"카피가 타겟의 언어로 쓰였는지 점검하세요. "
                        f"3~5개 소재를 동시 집행하는 A/B 테스트로 최적 소재를 찾는 것을 권장해요."
                    )
                if len(ctr_df) >= 3:
                    if _recent_ctr < _avg_ctr * 0.8:
                        _ctr_trend_msg = (
                            f"최근 3일 CTR <b style='color:#E74C3C'>하락 중 ({_recent_ctr:.2f}%)</b> — 소재 피로 신호예요. "
                            f"동일 타겟에게 같은 소재를 반복 노출하면 CTR이 점점 떨어져요. "
                            f"소재 교체 주기를 2~3주로 설정하고 새 크리에이티브를 미리 준비하세요."
                        )
                    elif _recent_ctr > _avg_ctr * 1.2:
                        _ctr_trend_msg = (
                            f"최근 3일 CTR <b style='color:#27AE60'>상승 중 ({_recent_ctr:.2f}%)</b> — 좋은 신호예요. "
                            f"현재 소재가 잘 먹히고 있어요. 일예산 10~20% 증액으로 모멘텀을 살려보세요."
                        )
                    else:
                        _ctr_trend_msg = f"최근 3일 CTR {_recent_ctr:.2f}% — 안정적으로 유지 중이에요."
                    _ae_lines.append(f"📣 CTR {_ctr_level} / {_ctr_trend_msg}")
                else:
                    _ae_lines.append(f"📣 CTR {_ctr_level}")
            # ROAS: total_revenue/total_spend 기준 (일별 평균 아님)
            if total_spend > 0 and total_purchases > 0:
                _real_roas = overall_roas
                if _real_roas >= 5:
                    _roas_detail = (
                        f"<b style='color:#27AE60'>{_real_roas}배</b> — 매우 우수해요. "
                        f"원가+플랫폼 수수료(약 30~40%)를 제해도 수익 구간이에요. "
                        f"이 소재·타겟 조합을 스케일업할 최적 타이밍이에요 — 예산을 주 단위로 20~30%씩 점진적으로 늘려보세요."
                    )
                elif _real_roas >= 3:
                    _roas_detail = (
                        f"<b style='color:#27AE60'>{_real_roas}배</b> — 수익 구간이에요. "
                        f"단, 플랫폼 수수료+원가(약 30~40%)를 제한 <b>실수익 ROAS</b>도 함께 계산해보세요. "
                        f"현재 세팅 유지하면서 예산 증액 테스트 가능해요."
                    )
                elif _real_roas >= 2:
                    _roas_detail = (
                        f"<b style='color:#F39C12'>{_real_roas}배</b> — 손익분기(3배) 미달이에요. "
                        f"전환 의향이 높은 재방문자 리타게팅 비중을 높이거나, "
                        f"번들·세트 구성으로 객단가를 올려 ROAS를 개선해보세요."
                    )
                else:
                    _roas_detail = (
                        f"<b style='color:#E74C3C'>{_real_roas}배</b> — 광고비 대비 매출 회수가 낮아요. "
                        f"지금 세팅으로 예산을 늘리면 적자가 심화돼요. "
                        f"타겟을 구매 이력 유사 타겟(LLA)으로 좁히거나, "
                        f"'신규 고객 첫 구매 혜택'을 소재에 노출해 전환 트리거를 만드세요."
                    )
                _ae_lines.append(f"💰 ROAS {_roas_detail}")
            elif total_spend > 0:
                _ae_lines.append(
                    f"⚠️ <b>전환 미발생</b> — 클릭→구매 전환 병목 구간을 점검하세요. "
                    f"확인 순서: ① 메타 픽셀 이벤트 정상 수신 여부 → ② GA4 랜딩 페이지 이탈율 → "
                    f"③ 상품페이지 구매 마찰 요소(배송비 노출 시점·리뷰 수·CTA 버튼). "
                    f"전환 캠페인보다 트래픽 캠페인으로 먼저 모수를 쌓은 뒤 "
                    f"리타게팅 전환 캠페인으로 전환하는 2단계 전략을 고려해보세요."
                )
            if _ae_lines:
                insight_box(_ae_lines, COLOR["orange"])
        else:
            st.info("광고 집행 데이터 없음")

    with col_right:
        chart_container("채널별 누적 유입", "어디서 온 사람들이 가장 많은지")
        ch_totals = {
            "메타광고":   int(df["유입_메타"].sum()),
            "공식인스타": int(df["유입_공식"].sum()),
            "개인인스타": int(df["유입_개인"].sum()),
            "직접방문":   int(df["유입_직접"].sum()),
        }
        ch_totals = {k: v for k, v in ch_totals.items() if v > 0}
        if ch_totals:
            fig3 = go.Figure(go.Pie(
                labels=list(ch_totals.keys()),
                values=list(ch_totals.values()),
                hole=0.52,
                marker=dict(colors=[CHANNEL_COLORS[k] for k in ch_totals.keys()],
                            line=dict(color="white", width=2)),
                textinfo="label+percent",
                textfont=dict(size=12),
                hovertemplate="<b>%{label}</b><br>%{value:,}명 (%{percent})<extra></extra>",
            ))
            fig3.update_layout(
                height=300, margin=dict(l=0, r=0, t=10, b=10),
                showlegend=False,
                annotations=[dict(text=f"총<br>{fmt_num(sum(ch_totals.values()))}명",
                                  x=0.5, y=0.5, font_size=14, font_color="#1A1A1A",
                                  showarrow=False)]
            )
            st.plotly_chart(fig3, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 차트 4: 신규 vs 재방문자
    chart_container("신규 vs 재방문자 · 픽셀 모수 누적", "신규 유입이 리타게팅 모수로 쌓이는 흐름")
    nvr_df = df[(df["신규"] > 0) | (df["재방문"] > 0)].copy()
    if not nvr_df.empty:
        nvr_df["누적_신규"] = nvr_df["신규"].cumsum()
        fig4 = make_subplots(specs=[[{"secondary_y": True}]])
        fig4.add_trace(go.Bar(x=nvr_df["날짜"], y=nvr_df["신규"], name="신규방문자",
            marker_color=COLOR["blue"], opacity=0.85,
            hovertemplate="<b>%{x}</b><br>신규: %{y:,}명<extra></extra>",
        ), secondary_y=False)
        fig4.add_trace(go.Bar(x=nvr_df["날짜"], y=nvr_df["재방문"], name="재방문자",
            marker_color=COLOR["green"], opacity=0.85,
            hovertemplate="<b>%{x}</b><br>재방문: %{y:,}명<extra></extra>",
        ), secondary_y=False)
        fig4.add_trace(go.Scatter(x=nvr_df["날짜"], y=nvr_df["누적_신규"],
            name="누적 픽셀 모수", mode="lines",
            line=dict(color=COLOR["orange"], width=2, dash="dot"),
            hovertemplate="<b>%{x}</b><br>누적 픽셀 모수: %{y:,}명<extra></extra>",
        ), secondary_y=True)
        for _, row in nvr_df[nvr_df["구매"] > 0].iterrows():
            fig4.add_vline(x=row["날짜"], line_width=1, line_dash="dot",
                           line_color=COLOR["green"], opacity=0.4)
        fig4.update_layout(
            height=300, margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="white", paper_bgcolor="white", barmode="stack",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            xaxis=dict(showgrid=False, tickfont=dict(size=11)),
            yaxis=dict(showgrid=True, gridcolor="#F0F0F0", tickfont=dict(size=11), title="방문자수"),
            yaxis2=dict(showgrid=False, tickfont=dict(size=11), title="누적 모수"),
            hovermode="x unified",
        )
        st.plotly_chart(fig4, use_container_width=True)

        pixel_total = int(nvr_df["신규"].sum())
        latest_ret  = nvr_df["재방문"].iloc[-3:].mean()
        early_ret   = nvr_df["재방문"].iloc[:max(1, len(nvr_df)-7)].mean()
        _nr_lines   = []
        if pixel_total >= 1000:
            _nr_lines.append(
                f"🎯 <b>누적 픽셀 모수 {pixel_total:,}명</b> — 리타게팅 캠페인을 집행할 충분한 모수가 쌓였어요. "
                f"메타 광고에서 '웹사이트 방문자(최근 30일)' 맞춤 타겟으로 리타게팅 캠페인을 별도 집행하면 "
                f"cold 오디언스 대비 전환율이 3~5배 높아요."
            )
        elif pixel_total >= 300:
            _nr_lines.append(
                f"🎯 <b>누적 픽셀 모수 {pixel_total:,}명</b> — 리타게팅 캠페인 최소 기준(300명)에 도달했어요. "
                f"신규 방문 후 3~7일 이내 리타게팅이 전환율이 가장 높아요. "
                f"지금 바로 '웹사이트 방문자' 맞춤 타겟 광고를 설정하세요."
            )
        else:
            _nr_lines.append(
                f"🎯 <b>누적 픽셀 모수 {pixel_total:,}명</b> — 아직 리타게팅 캠페인 효과가 나기엔 모수가 부족해요(최소 300명 권장). "
                f"지금은 신규 트래픽 유입에 집중해 모수를 먼저 쌓는 게 중요해요."
            )
        if latest_ret > early_ret * 1.2:
            _nr_lines.append(
                f"📈 <b>재방문자 증가 추세</b> — 브랜드 인지도가 쌓이는 중이에요. "
                f"재방문자는 구매 의향이 높은 따뜻한 오디언스예요. "
                f"이 그룹에게 '한정 재고', '오늘만 혜택' 메시지로 전환을 유도하면 CPO를 크게 낮출 수 있어요."
            )
        elif latest_ret < early_ret * 0.8:
            _nr_lines.append(
                f"📉 <b>재방문자 감소 추세</b> — 신규 방문 후 재방문으로 이어지지 않는 상황이에요. "
                f"인스타그램 팔로우 유도, 카카오채널 추가, 이메일 수집 후 뉴스레터 발송 등 "
                f"재방문을 유도할 락인(Lock-in) 장치가 필요해요."
            )
        else:
            _nr_lines.append(
                f"➡️ 재방문자 비율 <b>안정적</b> — 꾸준히 돌아오는 방문자가 있어요. "
                f"이 그룹에게 리타게팅 광고 또는 DM 팔로업으로 첫 구매를 유도해보세요."
            )
        if total_purchases == 0 and pixel_total >= 100:
            _nr_lines.append(
                f"💡 전환 미발생이지만 모수 {pixel_total:,}명 확보 — "
                f"'재고 한정·마감 임박' 긴박감 메시지로 지금 리타게팅 집행할 최적 타이밍이에요."
            )
        insight_box(_nr_lines, COLOR["purple"])

    st.markdown("<br>", unsafe_allow_html=True)

    # 차트 5: 채널 유입 스택 바 (접기)
    with st.expander("📊 일별 채널 유입 상세 보기"):
        chart_container("일별 채널별 유입 구성", "어떤 날 어떤 채널이 트래픽을 이끌었는지")
        ch_df = df[(df["유입_메타"] + df["유입_공식"] + df["유입_개인"] + df["유입_직접"]) > 0]
        if not ch_df.empty:
            fig5 = go.Figure()
            for ch, col_key, color in [
                ("메타광고",   "유입_메타",  "#1877F2"),
                ("공식인스타", "유입_공식",  "#E1306C"),
                ("개인인스타", "유입_개인",  "#F56040"),
                ("직접방문",   "유입_직접",  "#1A1A1A"),
            ]:
                fig5.add_trace(go.Bar(x=ch_df["날짜"], y=ch_df[col_key],
                    name=ch, marker_color=color,
                    hovertemplate=f"<b>%{{x}}</b><br>{ch}: %{{y}}명<extra></extra>"))
            fig5.update_layout(
                height=260, barmode="stack",
                margin=dict(l=0, r=0, t=10, b=0),
                plot_bgcolor="white", paper_bgcolor="white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                xaxis=dict(showgrid=False, tickfont=dict(size=11)),
                yaxis=dict(showgrid=True, gridcolor="#F0F0F0", tickfont=dict(size=11)),
                hovermode="x unified",
            )
            st.plotly_chart(fig5, use_container_width=True)

    # 기간 인사이트
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")
    chart_container("🔍 기간 종합 인사이트",
                    f"{df['날짜'].iloc[0]} ~ {df['날짜'].iloc[-1]} | {len(df)}일 분석")

    def generate_period_insight(df):
        insights = []
        if df.empty or df["방문자"].sum() == 0:
            return ["데이터가 없어요."]

        total_vis   = int(df["방문자"].sum())
        total_conv  = int(df["구매"].sum())
        total_spend = int(df["광고비"].sum())
        total_rev   = int(df["매출"].sum())
        total_new   = int(df["신규"].sum())
        total_ret   = int(df["재방문"].sum())
        conv_days   = df[df["구매"] > 0]
        ad_df       = df[df["광고비"] > 0]

        cvr  = round(total_conv / total_vis * 100, 2) if total_vis > 0 else 0
        roas = round(total_rev / total_spend, 1) if total_spend > 0 else 0
        cpo  = round(total_spend / total_conv) if total_conv > 0 else 0
        insights.append(
            f"**📊 기간 성과 요약**\n"
            f"방문자 {total_vis:,}명에서 {total_conv}건 전환 (전환율 {cvr}%). "
            f"{'광고비 ' + str(f'{total_spend:,}원') + ' 투입, ROAS ' + str(roas) + '배 달성.' if total_spend > 0 else '광고 미집행 기간.'}"
        )

        if len(df) > 1:
            max_day = df.loc[df["방문자"].idxmax()]
            avg_vis = df["방문자"].mean()
            if max_day["방문자"] > avg_vis * 2.5:
                top_ch = max({"메타광고": max_day["유입_메타"], "공식인스타": max_day["유입_공식"],
                              "개인인스타": max_day["유입_개인"], "직접방문": max_day["유입_직접"]},
                             key=lambda k: {"메타광고": max_day["유입_메타"], "공식인스타": max_day["유입_공식"],
                                            "개인인스타": max_day["유입_개인"], "직접방문": max_day["유입_직접"]}[k])
                new_pct = round(max_day["신규"] / max_day["방문자"] * 100) if max_day["방문자"] > 0 else 0
                insights.append(
                    f"**📈 최대 트래픽 스파이크: {max_day['날짜']}**\n"
                    f"평균({int(avg_vis):,}명) 대비 {round(max_day['방문자']/avg_vis, 1)}배 급등. "
                    f"주요 유입: {top_ch}. 신규 비중 {new_pct}% — "
                    f"{'바이럴/콘텐츠 확산으로 신규 유입이 대부분. cold audience라 당일 전환은 낮지만 픽셀 모수 대거 확충.' if new_pct >= 80 else '기존 팔로워 + 신규 혼합 유입. 전환 가능성 상대적으로 높은 날.'}"
                )

        if total_conv > 0 and not conv_days.empty:
            best_conv    = conv_days.loc[conv_days["구매"].idxmax()]
            ret_on_conv  = conv_days["재방문"].mean()
            ret_overall  = df["재방문"].mean()
            insights.append(
                f"**🛍 전환 패턴**\n"
                f"총 {total_conv}건 전환, {len(conv_days)}일에 분산 발생. "
                f"최다 전환일: {best_conv['날짜']} ({int(best_conv['구매'])}건). "
                + (f"전환 발생일의 재방문자 평균({ret_on_conv:.0f}명)이 전체 평균({ret_overall:.0f}명)보다 높음 → "
                   f"한 번 본 후 재방문해서 결제하는 패턴 확인. 리타게팅 효과 작동 중."
                   if ret_on_conv > ret_overall * 1.1 else
                   f"신규 방문자가 전환까지 바로 이어지는 케이스도 포함 — 콘텐츠/프로모션 직접 구매 설득력 있음.")
            )
        elif total_conv == 0 and total_spend > 0:
            avg_bounce = df["이탈율"].mean()
            insights.append(
                f"**⚠️ 전환 0건 구간**\n"
                f"광고비 {total_spend:,}원 집행했으나 전환 없음. "
                f"평균 이탈율 {avg_bounce:.0f}% — "
                + (f"이탈율이 높아 랜딩 직후 이탈이 주요 원인. 소재와 상품페이지 메시지 일관성 점검 필요."
                   if avg_bounce >= 60
                   else f"이탈율은 양호하나 결제 미전환 — 가격 저항, 배송비, 리뷰 부족 등 결제 직전 장벽 점검 필요.")
            )

        ch_totals = {
            "메타광고":   int(df["유입_메타"].sum()),
            "공식인스타": int(df["유입_공식"].sum()),
            "개인인스타": int(df["유입_개인"].sum()),
            "직접방문":   int(df["유입_직접"].sum()),
        }
        top_ch    = max(ch_totals, key=ch_totals.get)
        ch_str    = " | ".join([f"{k} {v:,}명" for k, v in sorted(ch_totals.items(), key=lambda x: -x[1]) if v > 0])
        direct_ok = "직접방문이 꾸준히 유입되는 것은 브랜드 인지도가 쌓이고 있는 긍정 신호." if ch_totals["직접방문"] >= 50 else ""
        insights.append(
            f"**🔀 채널 기여 분석**\n"
            f"{ch_str}. 이 기간 {top_ch}이 유입 1위. "
            + (f"메타 광고 UTM 포착률 확인 필요 — 광고 클릭 대비 GA4 메타 유입 세션이 낮으면 UTM 파라미터 누락."
               if top_ch != "메타광고" and total_spend > 0 else "")
            + (" " + direct_ok if direct_ok else "")
        )

        if total_new >= 100:
            insights.append(
                f"**🎯 리타게팅 액션플랜**\n"
                f"이 기간 신규 유입 {total_new:,}명으로 픽셀 모수 확충. "
                f"재방문율 {round(total_ret/(total_new+total_ret)*100) if (total_new+total_ret)>0 else 0}% — "
                f"나머지 {total_new - total_ret:,}명은 아직 재방문 안 함. "
                f"이 모수를 대상으로 '프리오더 마감 임박' 또는 '재고 한정' 메시지로 리타게팅 집행 시 전환율 3~5배 기대 가능."
            )
        return insights

    period_insights = generate_period_insight(df)
    for i, insight in enumerate(period_insights):
        border_colors = [COLOR["blue"], COLOR["accent"], COLOR["green"], COLOR["orange"], COLOR["purple"]]
        bc = border_colors[i % len(border_colors)]
        st.markdown(f"""
        <div style="background:#FFFFFF;border-left:4px solid {bc};padding:16px 20px;border-radius:8px;
                    font-size:13px;color:#1A1A1A;margin-bottom:12px;border:1px solid #EBEBEB;
                    box-shadow:0 1px 3px rgba(0,0,0,0.04);">
        {insight.replace(chr(10), "<br>")}
        </div>
        """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# TAB 2: 플랫폼별 매출 대시보드
# ════════════════════════════════════════════════════════════════
with tab2:

    if df_platform_all.empty:
        st.info("🏬 플랫폼 매출 데이터가 없어요. platform_to_sheets.py로 데이터를 먼저 업로드해 주세요.")
        st.stop()

    # 마지막 갱신 시간 표시
    from datetime import datetime as _dt
    st.caption(f"🕐 데이터 기준: {_dt.now().strftime('%Y-%m-%d %H:%M')} 로드 | 🔄 버튼으로 최신 데이터 반영")

    # ── 기간 필터 ─────────────────────────────────────────────────
    # 주차 목록 (주차별 필터 옵션)
    _valid_weeks = df_platform_all[df_platform_all["주차"].str.strip() != ""]["주차"].dropna().unique().tolist()
    pf_weeks = sorted(
        _valid_weeks,
        key=lambda x: df_platform_all[df_platform_all["주차"]==x]["주문일_dt"].min()
    )
    _preset_options = ["전체 기간", "최근 7일", "최근 30일"] + pf_weeks

    col_pf1, col_pf2, col_pf3 = st.columns([2, 2, 4])
    with col_pf1:
        pf_preset = st.selectbox(
            "📅 조회 기간",
            _preset_options,
            label_visibility="collapsed",
            key="tab2_preset",
            help="주차별 선택 시 해당 주 데이터만 표시"
        )
    with col_pf2:
        order_count = len(df_platform_all)
        st.markdown(
            f'<div style="padding:8px 0;color:#8C8C8C;font-size:13px;">📦 전체 {order_count}건 중 {pf_preset}</div>',
            unsafe_allow_html=True
        )

    now = pd.Timestamp.now()
    if pf_preset == "전체 기간":
        pf = df_platform_all.copy()
    elif pf_preset in pf_weeks:
        pf = df_platform_all[df_platform_all["주차"] == pf_preset].copy()
    elif pf_preset == "최근 7일":
        cutoff = now - pd.Timedelta(days=7)
        pf = df_platform_all[df_platform_all["주문일_dt"] >= cutoff].copy()
    else:
        cutoff = now - pd.Timedelta(days=30)
        pf = df_platform_all[df_platform_all["주문일_dt"] >= cutoff].copy()

    pf = pf.reset_index(drop=True)

    # 주문상태 필터 (취소 포함)
    pf_valid   = pf                                    # 전체 (취소 포함)
    pf_normal  = pf[~pf["주문상태"].str.contains("취소", na=False)]  # 취소 제외

    st.markdown("---")

    # ── KPI 카드 ──────────────────────────────────────────────────
    total_sales   = int(pf_normal["판매가"].sum())
    total_profit  = int(pf_normal["실수익"].sum())
    total_orders  = len(pf_normal)
    avg_price_pf  = int(total_sales / total_orders) if total_orders > 0 else 0
    profit_rate   = round(total_profit / total_sales * 100, 1) if total_sales > 0 else 0
    cancel_cnt    = len(pf[pf["주문상태"].str.contains("취소", na=False)])

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: kpi_card("총 매출액", fmt_num(total_sales, "원"))
    with c2: kpi_card("총 실수익", fmt_num(total_profit, "원"), f"수익률 {profit_rate}%", profit_rate >= 65)
    with c3: kpi_card("총 주문 건수", f"{total_orders:,}건", f"취소 {cancel_cnt}건")
    with c4: kpi_card("평균 객단가", f"{avg_price_pf:,}원")
    with c5: kpi_card("취소율", f"{round(cancel_cnt/(total_orders+cancel_cnt)*100) if (total_orders+cancel_cnt)>0 else 0}%",
                      f"취소 {cancel_cnt}건")
    with c6: kpi_card("수익률", f"{profit_rate}%",
                      "목표 70% 이상" if profit_rate < 70 else "✓ 목표 달성",
                      profit_rate >= 70)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 플랫폼별 미니 카드 ────────────────────────────────────────
    platforms_avail = [p for p in ["29CM", "W컨셉", "SSF", "SI Village", "무신사", "Cafe24"]
                       if p in pf_normal["플랫폼"].values]
    if platforms_avail:
        pf_cols = st.columns(len(platforms_avail))
        for i, pname in enumerate(platforms_avail):
            sub = pf_normal[pf_normal["플랫폼"] == pname]
            s   = int(sub["판매가"].sum())
            pr  = int(sub["실수익"].sum())
            cnt = len(sub)
            rate= round(pr/s*100, 1) if s > 0 else 0
            with pf_cols[i]:
                kpi_card_sm(
                    pname,
                    fmt_num(s, "원"),
                    badge_color=PLATFORM_COLORS.get(pname, "#888"),
                    sub=f"{cnt}건 | 실수익 {fmt_num(pr)}원 | 수익률 {rate}%"
                )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 차트 A: 도넛 + 일별 매출 트렌드 ──────────────────────────
    col_a, col_b = st.columns([2, 3])

    with col_a:
        chart_container("플랫폼별 매출 비중", "어느 채널이 가장 많이 팔리는지")
        pf_sales = pf_normal.groupby("플랫폼")["판매가"].sum().reset_index()
        pf_sales = pf_sales[pf_sales["판매가"] > 0]
        if not pf_sales.empty:
            colors_donut = [PLATFORM_COLORS.get(p, "#888") for p in pf_sales["플랫폼"]]
            fig_d = go.Figure(go.Pie(
                labels=pf_sales["플랫폼"],
                values=pf_sales["판매가"],
                hole=0.52,
                marker=dict(colors=colors_donut, line=dict(color="white", width=2)),
                textinfo="label+percent",
                textfont=dict(size=12),
                hovertemplate="<b>%{label}</b><br>%{value:,}원 (%{percent})<extra></extra>",
            ))
            fig_d.update_layout(
                height=300, margin=dict(l=0, r=0, t=10, b=10),
                showlegend=False,
                annotations=[dict(text=f"총<br>{fmt_num(total_sales)}원",
                                  x=0.5, y=0.5, font_size=13, font_color="#1A1A1A",
                                  showarrow=False)]
            )
            st.plotly_chart(fig_d, use_container_width=True)

    with col_b:
        chart_container("일별 플랫폼별 매출 트렌드", "날짜별로 어느 플랫폼에서 매출이 발생했는지")
        # 핵심 fix: 주문일_dt(datetime) 기준으로 그룹핑 → Jan 2000 버그 해결
        pf_trend_src = pf_normal.dropna(subset=["주문일_dt"]).copy()
        pf_daily = (pf_trend_src
                    .groupby(["주문일_dt", "플랫폼"])["판매가"]
                    .sum().reset_index()
                    .sort_values("주문일_dt"))
        if not pf_daily.empty:
            fig_t = go.Figure()
            for pname in pf_daily["플랫폼"].unique():
                sub_t = pf_daily[pf_daily["플랫폼"] == pname].copy()
                _mode = "lines+markers" if len(sub_t) > 1 else "markers"
                _msize = 8 if len(sub_t) == 1 else 6
                fig_t.add_trace(go.Scatter(
                    x=sub_t["주문일_dt"],
                    y=sub_t["판매가"],
                    name=pname,
                    mode=_mode,
                    line=dict(color=PLATFORM_COLORS.get(pname, "#888"), width=2.5),
                    marker=dict(size=_msize, color=PLATFORM_COLORS.get(pname, "#888"),
                                line=dict(color="white", width=1.5)),
                    hovertemplate=(
                        f"<b>%{{x|%Y-%m-%d}}</b><br>{pname}: %{{y:,}}원<extra></extra>"
                    ),
                ))
            fig_t.update_layout(
                height=300, margin=dict(l=0, r=0, t=10, b=0),
                plot_bgcolor="white", paper_bgcolor="white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                xaxis=dict(
                    type="date",               # 명시적 date 타입 지정 — Jan 2000 버그 방지
                    showgrid=False,
                    tickfont=dict(size=11),
                    tickformat="%m/%d",        # MM/DD 형식 표기
                ),
                yaxis=dict(showgrid=True, gridcolor="#F0F0F0", tickfont=dict(size=11),
                           tickformat=",", title="매출액 (원)"),
                hovermode="x unified",
            )
            st.plotly_chart(fig_t, use_container_width=True)
        else:
            st.info("선택 기간에 날짜 데이터가 없어요.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 차트 B: 플랫폼별 실수익 누적 바 ──────────────────────────
    chart_container("플랫폼별 실수익 비교", "수수료 차감 후 실제로 남는 금액")
    pf_profit = pf_normal.groupby("플랫폼").agg(
        매출=("판매가", "sum"),
        실수익=("실수익", "sum"),
        주문수=("판매가", "count")
    ).reset_index().sort_values("매출", ascending=False)

    if not pf_profit.empty:
        fig_p = go.Figure()
        fig_p.add_trace(go.Bar(
            x=pf_profit["플랫폼"], y=pf_profit["매출"],
            name="총 매출",
            marker_color=[PLATFORM_COLORS.get(p, "#888") for p in pf_profit["플랫폼"]],
            opacity=0.4,
            hovertemplate="<b>%{x}</b><br>총 매출: %{y:,}원<extra></extra>",
        ))
        fig_p.add_trace(go.Bar(
            x=pf_profit["플랫폼"], y=pf_profit["실수익"],
            name="실수익",
            marker_color=[PLATFORM_COLORS.get(p, "#888") for p in pf_profit["플랫폼"]],
            opacity=1.0,
            hovertemplate="<b>%{x}</b><br>실수익: %{y:,}원<extra></extra>",
        ))
        fig_p.update_layout(
            height=280, margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="white", paper_bgcolor="white",
            barmode="overlay",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            xaxis=dict(showgrid=False, tickfont=dict(size=13, color="#1A1A1A")),
            yaxis=dict(showgrid=True, gridcolor="#F0F0F0", tickfont=dict(size=11), tickformat=","),
        )
        st.plotly_chart(fig_p, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 차트 C: 상품 TOP 10 ───────────────────────────────────────
    chart_container("베스트셀러 TOP 10", "매출 기준 인기 상품 순위")
    top10 = (pf_normal.groupby("상품명")
             .agg(매출=("판매가", "sum"), 수량=("수량", "sum"), 주문수=("판매가", "count"))
             .reset_index()
             .sort_values("매출", ascending=False)
             .head(10))

    if not top10.empty:
        top10_sorted = top10.sort_values("매출", ascending=True)
        # 상품명 짧게 자르기
        top10_sorted["상품명_short"] = top10_sorted["상품명"].apply(
            lambda x: x[:22] + "…" if len(str(x)) > 22 else str(x)
        )
        fig_top = go.Figure(go.Bar(
            x=top10_sorted["매출"],
            y=top10_sorted["상품명_short"],
            orientation="h",
            marker_color=COLOR["blue"],
            marker_line_width=0,
            text=top10_sorted["매출"].apply(lambda v: fmt_num(v, "원")),
            textposition="outside",
            customdata=top10_sorted[["수량", "주문수"]].values,
            hovertemplate="<b>%{y}</b><br>매출: %{x:,}원<br>수량: %{customdata[0]}개 | 주문: %{customdata[1]}건<extra></extra>",
        ))
        fig_top.update_layout(
            height=max(300, len(top10) * 38),
            margin=dict(l=0, r=80, t=10, b=0),
            plot_bgcolor="white", paper_bgcolor="white",
            xaxis=dict(showgrid=True, gridcolor="#F0F0F0", tickfont=dict(size=11), tickformat=","),
            yaxis=dict(showgrid=False, tickfont=dict(size=12)),
        )
        st.plotly_chart(fig_top, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 상세 주문 테이블 (접기) ────────────────────────────────────
    with st.expander("📋 전체 주문 내역 보기"):
        display_cols = [c for c in ["플랫폼", "주문일", "상품명", "컬러", "사이즈", "수량", "판매가", "수수료율(%)", "실수익", "주문상태"]
                        if c in pf.columns]
        pf_display = pf[display_cols].copy()
        pf_display["판매가"] = pf_display["판매가"].apply(lambda x: f"{int(x):,}")
        pf_display["실수익"] = pf_display["실수익"].apply(lambda x: f"{int(x):,}")
        st.dataframe(pf_display, use_container_width=True, hide_index=True)

    # ── 플랫폼 인사이트 ────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")
    chart_container("🔍 플랫폼 매출 인사이트", f"선택 기간 {pf_preset} | 취소 제외 {total_orders}건 기준")

    def generate_platform_insight(pf_normal, pf_all):
        insights = []
        if pf_normal.empty:
            return ["데이터가 없어요."]

        total_s  = int(pf_normal["판매가"].sum())
        total_p  = int(pf_normal["실수익"].sum())
        total_o  = len(pf_normal)
        cancel_c = len(pf_all[pf_all["주문상태"].str.contains("취소", na=False)])
        cancel_r = round(cancel_c / (total_o + cancel_c) * 100) if (total_o + cancel_c) > 0 else 0
        p_rate   = round(total_p / total_s * 100, 1) if total_s > 0 else 0
        avg_pr   = int(total_s / total_o) if total_o > 0 else 0

        # ① 전체 요약
        insights.append(
            f"**📊 플랫폼 통합 성과**\n"
            f"총 매출 {total_s:,}원 | 실수익 {total_p:,}원 (수익률 {p_rate}%). "
            f"총 {total_o}건 주문, 취소율 {cancel_r}%. 평균 객단가 {avg_pr:,}원. "
            f"{'수익률이 목표(70%) 미달 — 수수료율 재협상 또는 고마진 상품 비중 확대 검토.' if p_rate < 70 else '수익률 목표(70%) 달성 ✓ — 현재 플랫폼 믹스 유지.'}"
        )

        # ② 플랫폼별 효율 비교
        pf_stats = pf_normal.groupby("플랫폼").agg(
            매출=("판매가", "sum"), 실수익=("실수익", "sum"), 주문수=("판매가", "count")
        ).reset_index()
        if len(pf_stats) > 1:
            best_p  = pf_stats.loc[pf_stats["매출"].idxmax(), "플랫폼"]
            best_s  = int(pf_stats.loc[pf_stats["매출"].idxmax(), "매출"])
            worst_p = pf_stats.loc[pf_stats["매출"].idxmin(), "플랫폼"]
            # 수익률 기준 최고
            pf_stats["수익률"] = pf_stats["실수익"] / pf_stats["매출"] * 100
            best_rate_p = pf_stats.loc[pf_stats["수익률"].idxmax(), "플랫폼"]
            best_rate   = round(pf_stats["수익률"].max(), 1)
            insights.append(
                f"**🏆 플랫폼 효율 비교**\n"
                f"매출 1위: {best_p} ({best_s:,}원). "
                f"수익률 1위: {best_rate_p} ({best_rate}%). "
                f"{worst_p}는 이 기간 매출 최소 — 상품 노출 방식이나 등록 상품 수를 점검하거나, 해당 플랫폼 고객층에 맞는 상품을 추가 입점 검토."
            )

        # ③ 취소율 진단
        if cancel_r >= 15:
            top_cancel_pf = (pf_all[pf_all["주문상태"].str.contains("취소", na=False)]
                             .groupby("플랫폼").size().idxmax()
                             if cancel_c > 0 else "—")
            insights.append(
                f"**⚠️ 취소율 {cancel_r}% — 높음**\n"
                f"취소 {cancel_c}건 발생. 집중 플랫폼: {top_cancel_pf}. "
                f"취소 원인 상위는 ①배송 지연 ②사이즈 불만 ③단순 변심. "
                f"상품 상세페이지에 사이즈 가이드 강화 + 빠른 출고 메시지 노출로 취소율 낮출 수 있음."
            )
        elif cancel_r > 0:
            insights.append(
                f"**✅ 취소율 {cancel_r}% — 양호**\n"
                f"취소 {cancel_c}건으로 관리 가능한 수준. 취소 사유 모니터링 유지."
            )

        # ④ 베스트셀러 분석
        if not pf_normal.empty:
            top1 = (pf_normal.groupby("상품명")["판매가"].sum().idxmax())
            top1_sales = int(pf_normal.groupby("상품명")["판매가"].sum().max())
            top1_qty   = int(pf_normal[pf_normal["상품명"]==top1]["수량"].sum())
            top1_share = round(top1_sales / total_s * 100) if total_s > 0 else 0
            insights.append(
                f"**🔥 베스트셀러 집중도**\n"
                f"1위 상품 '{top1[:20]}{'...' if len(top1)>20 else ''}' — {top1_qty}개 판매, 매출 {top1_sales:,}원 (전체의 {top1_share}%). "
                f"{'1위 집중도가 높음 — 해당 상품 재고 관리를 최우선으로 하고, 유사 스타일 신상품 입점을 통해 의존도 분산 필요.' if top1_share >= 40 else '매출이 여러 상품에 분산되어 있음 — 안정적인 구조. 베스트 상품군 중심으로 광고 소재 제작 시 전환율 개선 효과 기대.'}"
            )

        # ⑤ 액션플랜
        insights.append(
            f"**🎯 다음 스텝 액션플랜**\n"
            f"① 수익률 {p_rate}% {'→ 고마진 상품 추가 등록으로 70%대 목표.' if p_rate < 70 else '유지 — OK.'} "
            f"② 취소율 {'관리 필요 — 상품설명 보강.' if cancel_r >= 15 else '양호 — 모니터링 유지.'} "
            f"③ 베스트셀러 중심으로 플랫폼 광고(셀렉티드/기획전) 신청 검토. "
            f"④ 월별 플랫폼 매출 비교로 성장 채널 집중 투자."
        )

        return insights

    pf_insights = generate_platform_insight(pf_normal, pf)
    for i, insight in enumerate(pf_insights):
        border_colors = [COLOR["blue"], COLOR["purple"], COLOR["orange"], COLOR["green"], COLOR["accent"]]
        bc = border_colors[i % len(border_colors)]
        st.markdown(f"""
        <div style="background:#FFFFFF;border-left:4px solid {bc};padding:16px 20px;border-radius:8px;
                    font-size:13px;color:#1A1A1A;margin-bottom:12px;border:1px solid #EBEBEB;
                    box-shadow:0 1px 3px rgba(0,0,0,0.04);">
        {insight.replace(chr(10), "<br>")}
        </div>
        """, unsafe_allow_html=True)



with tab3:
    if df_platform_all.empty:
        st.info("🏬 플랫폼 매출 데이터가 없어요. platform_to_sheets.py로 데이터를 먼저 업로드해 주세요.")
    else:
        import datetime as _dt

        st.markdown("### 📅 기간별 매출 조회")

        t3_min_date = df_platform_all["주문일_dt"].min().date()
        t3_max_date = df_platform_all["주문일_dt"].max().date()
        t3_today    = pd.Timestamp.now().date()

        # ── 빠른 기간 선택 버튼 ──────────────────────────────────
        b1, b2, b3, b4, b5 = st.columns(5)
        with b1:
            if st.button("오늘", use_container_width=True, key="t3_today"):
                st.session_state["t3_s"] = t3_today
                st.session_state["t3_e"] = t3_today
        with b2:
            if st.button("최근 7일", use_container_width=True, key="t3_7d"):
                st.session_state["t3_s"] = max(t3_today - _dt.timedelta(days=6), t3_min_date)
                st.session_state["t3_e"] = t3_today
        with b3:
            if st.button("최근 30일", use_container_width=True, key="t3_30d"):
                st.session_state["t3_s"] = max(t3_today - _dt.timedelta(days=29), t3_min_date)
                st.session_state["t3_e"] = t3_today
        with b4:
            if st.button("이번 달", use_container_width=True, key="t3_month"):
                st.session_state["t3_s"] = t3_today.replace(day=1)
                st.session_state["t3_e"] = t3_today
        with b5:
            if st.button("전체 기간", use_container_width=True, key="t3_all"):
                st.session_state["t3_s"] = t3_min_date
                st.session_state["t3_e"] = t3_max_date

        # ── 날짜 직접 선택 ────────────────────────────────────────
        col_d1, col_d2, col_d3 = st.columns([2, 2, 4])
        with col_d1:
            t3_start = st.date_input(
                "📅 시작일",
                value=st.session_state.get("t3_s", t3_min_date),
                min_value=t3_min_date,
                max_value=t3_max_date,
                key="t3_s",
            )
        with col_d2:
            t3_end = st.date_input(
                "📅 종료일",
                value=st.session_state.get("t3_e", t3_max_date),
                min_value=t3_min_date,
                max_value=t3_max_date,
                key="t3_e",
            )
        with col_d3:
            days_range = (t3_end - t3_start).days + 1 if t3_end >= t3_start else 0
            st.markdown(
                f'<div style="padding-top:30px;color:#8C8C8C;font-size:13px;">'
                f'📌 <b>{t3_start}</b> ~ <b>{t3_end}</b> | {days_range}일</div>',
                unsafe_allow_html=True
            )

        if t3_start > t3_end:
            st.warning("⚠️ 시작일이 종료일보다 늦어요.")
        else:
            # ── 데이터 필터 ───────────────────────────────────────
            t3_mask   = (
                (df_platform_all["주문일_dt"].dt.date >= t3_start) &
                (df_platform_all["주문일_dt"].dt.date <= t3_end)
            )
            t3_df     = df_platform_all[t3_mask].copy()
            t3_normal = t3_df[~t3_df["주문상태"].str.contains("취소", na=False)]
            t3_cancel = t3_df[t3_df["주문상태"].str.contains("취소", na=False)]

            st.markdown(
                f'<div style="color:#8C8C8C;font-size:13px;margin:4px 0 12px;">'
                f'정상 {len(t3_normal)}건 · 취소 {len(t3_cancel)}건</div>',
                unsafe_allow_html=True
            )
            st.markdown("---")

            # ── KPI 카드 ──────────────────────────────────────────
            t3_sales  = int(t3_normal["판매가"].sum())
            t3_profit = int(t3_normal["실수익"].sum())
            t3_orders = len(t3_normal)
            t3_avg    = int(t3_sales / t3_orders) if t3_orders > 0 else 0
            t3_prate  = round(t3_profit / t3_sales * 100, 1) if t3_sales > 0 else 0
            t3_daily  = int(t3_sales / days_range) if days_range > 0 else 0

            c1, c2, c3, c4, c5, c6 = st.columns(6)
            with c1: kpi_card("기간 총 매출", fmt_num(t3_sales, "원"))
            with c2: kpi_card("기간 실수익", fmt_num(t3_profit, "원"), f"수익률 {t3_prate}%", t3_prate >= 65)
            with c3: kpi_card("총 주문수", f"{t3_orders:,}건", f"취소 {len(t3_cancel)}건")
            with c4: kpi_card("평균 객단가", f"{t3_avg:,}원")
            with c5: kpi_card("일평균 매출", fmt_num(t3_daily, "원"), f"{days_range}일 기준")
            with c6: kpi_card("수익률", f"{t3_prate}%",
                              "목표 70% 미달" if t3_prate < 70 else "✓ 목표 달성",
                              t3_prate >= 70)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── 플랫폼별 요약 테이블 + 도넛 ─────────────────────
            col_ta, col_tb = st.columns([3, 2])

            with col_ta:
                chart_container("플랫폼별 매출 요약", f"{t3_start} ~ {t3_end}")
                if not t3_normal.empty:
                    t3_pf = t3_normal.groupby("플랫폼").agg(
                        매출=("판매가", "sum"),
                        실수익=("실수익", "sum"),
                        주문수=("판매가", "count"),
                    ).reset_index().sort_values("매출", ascending=False)
                    t3_pf["수익률(%)"] = (t3_pf["실수익"] / t3_pf["매출"] * 100).round(1)
                    t3_pf["객단가"]    = (t3_pf["매출"] / t3_pf["주문수"]).astype(int)
                    comm_map = {"Cafe24": "3% (PG)", "무신사": "30%", "29CM": "30%",
                                "W컨셉": "30%", "SSF": "30%", "SI Village": "30%"}
                    t3_pf["수수료"]    = t3_pf["플랫폼"].map(lambda x: comm_map.get(x, "30%"))
                    t3_pf["매출"]      = t3_pf["매출"].apply(lambda x: f"{int(x):,}원")
                    t3_pf["실수익"]    = t3_pf["실수익"].apply(lambda x: f"{int(x):,}원")
                    t3_pf["객단가"]    = t3_pf["객단가"].apply(lambda x: f"{int(x):,}원")
                    st.dataframe(
                        t3_pf[["플랫폼", "매출", "실수익", "수익률(%)", "주문수", "객단가", "수수료"]],
                        use_container_width=True, hide_index=True
                    )
                else:
                    st.info("해당 기간 데이터 없음")

            with col_tb:
                chart_container("플랫폼 비중", "")
                if not t3_normal.empty:
                    t3_pie = t3_normal.groupby("플랫폼")["판매가"].sum().reset_index()
                    t3_pie = t3_pie[t3_pie["판매가"] > 0]
                    if not t3_pie.empty:
                        fig_t3d = go.Figure(go.Pie(
                            labels=t3_pie["플랫폼"], values=t3_pie["판매가"],
                            hole=0.5,
                            marker=dict(
                                colors=[PLATFORM_COLORS.get(p, "#888") for p in t3_pie["플랫폼"]],
                                line=dict(color="white", width=2)
                            ),
                            textinfo="label+percent", textfont=dict(size=12),
                            hovertemplate="<b>%{label}</b><br>%{value:,}원 (%{percent})<extra></extra>",
                        ))
                        fig_t3d.update_layout(
                            height=280, margin=dict(l=0, r=0, t=10, b=10),
                            showlegend=False,
                        )
                        st.plotly_chart(fig_t3d, use_container_width=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── 일별 매출 트렌드 ──────────────────────────────────
            chart_container("일별 매출 추이", f"{days_range}일")
            if not t3_normal.empty:
                t3_daily_df = (
                    t3_normal.dropna(subset=["주문일_dt"])
                    .groupby(["주문일_dt", "플랫폼"])["판매가"]
                    .sum().reset_index().sort_values("주문일_dt")
                )
                if not t3_daily_df.empty:
                    fig_t3t = go.Figure()
                    for pname in t3_daily_df["플랫폼"].unique():
                        sub = t3_daily_df[t3_daily_df["플랫폼"] == pname]
                        _mode = "lines+markers" if len(sub) > 1 else "markers"
                        fig_t3t.add_trace(go.Scatter(
                            x=sub["주문일_dt"], y=sub["판매가"],
                            name=pname, mode=_mode,
                            line=dict(color=PLATFORM_COLORS.get(pname, "#888"), width=2.5),
                            marker=dict(size=7, color=PLATFORM_COLORS.get(pname, "#888"),
                                        line=dict(color="white", width=1.5)),
                            hovertemplate=f"<b>%{{x|%Y-%m-%d}}</b><br>{pname}: %{{y:,}}원<extra></extra>",
                        ))
                    fig_t3t.update_layout(
                        height=300, margin=dict(l=0, r=0, t=10, b=0),
                        plot_bgcolor="white", paper_bgcolor="white",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                        xaxis=dict(type="date", showgrid=False, tickformat="%m/%d",
                                   tickfont=dict(size=11)),
                        yaxis=dict(showgrid=True, gridcolor="#F0F0F0",
                                   tickfont=dict(size=11), tickformat=","),
                        hovermode="x unified",
                    )
                    st.plotly_chart(fig_t3t, use_container_width=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── 베스트셀러 TOP 10 ─────────────────────────────────
            chart_container("베스트셀러 TOP 10", f"{t3_start} ~ {t3_end}")
            if not t3_normal.empty:
                t3_top = (
                    t3_normal.groupby("상품명")
                    .agg(매출=("판매가", "sum"), 수량=("수량", "sum"), 주문수=("판매가", "count"))
                    .reset_index().sort_values("매출", ascending=False).head(10)
                )
                t3_top_s = t3_top.sort_values("매출", ascending=True).copy()
                t3_top_s["상품명_s"] = t3_top_s["상품명"].apply(
                    lambda x: x[:24] + "…" if len(str(x)) > 24 else str(x)
                )
                fig_t3top = go.Figure(go.Bar(
                    x=t3_top_s["매출"], y=t3_top_s["상품명_s"],
                    orientation="h",
                    marker_color=COLOR["blue"], marker_line_width=0,
                    text=t3_top_s["매출"].apply(lambda v: fmt_num(v, "원")),
                    textposition="outside",
                    customdata=t3_top_s[["수량", "주문수"]].values,
                    hovertemplate="<b>%{y}</b><br>%{x:,}원 | 수량 %{customdata[0]}개 | %{customdata[1]}건<extra></extra>",
                ))
                fig_t3top.update_layout(
                    height=max(280, len(t3_top) * 38),
                    margin=dict(l=0, r=90, t=10, b=0),
                    plot_bgcolor="white", paper_bgcolor="white",
                    xaxis=dict(showgrid=True, gridcolor="#F0F0F0", tickformat=","),
                    yaxis=dict(showgrid=False, tickfont=dict(size=12)),
                )
                st.plotly_chart(fig_t3top, use_container_width=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── 상세 주문 내역 ─────────────────────────────────────
            with st.expander("📋 상세 주문 내역 보기"):
                col_f1, col_f2 = st.columns([2, 4])
                with col_f1:
                    t3_pf_filter = st.multiselect(
                        "플랫폼",
                        options=sorted(t3_df["플랫폼"].unique().tolist()),
                        default=sorted(t3_df["플랫폼"].unique().tolist()),
                        key="t3_pf_filter",
                    )
                with col_f2:
                    t3_status_filter = st.multiselect(
                        "주문상태",
                        options=sorted(t3_df["주문상태"].unique().tolist()),
                        default=[s for s in sorted(t3_df["주문상태"].unique()) if "취소" not in str(s)],
                        key="t3_status_filter",
                    )
                t3_filtered = t3_df[
                    t3_df["플랫폼"].isin(t3_pf_filter) &
                    t3_df["주문상태"].isin(t3_status_filter)
                ].copy()
                detail_cols = [c for c in ["플랫폼", "주문일", "상품명", "컬러", "사이즈",
                                            "수량", "판매가", "수수료율(%)", "실수익", "주문상태"]
                               if c in t3_filtered.columns]
                t3_display = t3_filtered[detail_cols].copy()
                t3_display["판매가"] = t3_display["판매가"].apply(lambda x: f"{int(x):,}")
                t3_display["실수익"] = t3_display["실수익"].apply(lambda x: f"{int(x):,}")
                st.markdown(f"**{len(t3_display)}건** 조회됨")
                st.dataframe(
                    t3_display.sort_values("주문일", ascending=False),
                    use_container_width=True, hide_index=True
                )


# ── 푸터 ───────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<div style="text-align:center;color:#BDBDBD;font-size:12px;">NOMINICAL · 지표 자동화 대시보드 · 5분마다 캐시 갱신</div>',
    unsafe_allow_html=True
)
