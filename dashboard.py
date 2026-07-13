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
import json, os, time
import requests as _requests

# ── GA4 API imports (lazy-safe) ────────────────────────────────────
try:
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        RunReportRequest, Dimension, Metric, DateRange,
        FilterExpression, Filter, FilterExpressionList, OrderBy,
    )
    _GA4_AVAILABLE = True
except ImportError:
    _GA4_AVAILABLE = False

# ── 설정 ───────────────────────────────────────────────────────────
SPREADSHEET_ID      = "1y9mZirj81sR2tkkGV_wTzFvJonPdJU-JuErSRDo_73E"
SHEET_NAME          = "📅 일별 트래킹"
PLATFORM_SHEET_NAME = "🏬 플랫폼 매출"
SA_FILE             = "/Users/kimeunbee/Documents/지표분析/service_account.json"
TOKEN_FILE          = os.path.expanduser("~/.nominical_token.json")

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
    "메타 유료광고":     "#1877F2",
    "인스타그램 오가닉": "#C13584",
    "공식인스타 바이오": "#E1306C",
    "개인인스타 바이오": "#F56040",
    "직접방문":          "#1A1A1A",
    # 구버전 키 호환 (혹시 다른 곳에서 참조 시 KeyError 방지)
    "메타광고":   "#1877F2",
    "공식인스타": "#E1306C",
    "개인인스타": "#F56040",
}

PLATFORM_COLORS = {
    "29CM":       "#E94B3C",   # 레드
    "W컨셉":      "#5B3F9E",   # 딥 퍼플
    "SSF":        "#0077C8",   # 삼성 블루
    "SI Village": "#C8A951",   # 신세계 골드
    "무신사":     "#222222",   # 무신사 블랙
    "Cafe24":     "#4ECBA0",   # 그린
    "지그재그":   "#FF9900",   # 지그재그 오렌지
    "스마트스토어": "#03C75A", # 네이버 그린
}

st.set_page_config(
    page_title="NOMINICAL 대시보드",
    page_icon="🏃",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── 비밀번호 인증 ────────────────────────────────────────────────────
def _auth_token(pw: str) -> str:
    import hashlib
    return hashlib.sha256(pw.encode()).hexdigest()[:24]

def check_password():
    correct_pw = st.secrets.get("dashboard_password", "nominical2026")

    # 1) 세션 state (같은 WebSocket 세션 내 빠른 체크)
    if st.session_state.get("authenticated"):
        return True

    # 2) URL 토큰 — 서버 재시작/세션 리셋 후에도 자동 재인증
    if st.query_params.get("_t") == _auth_token(correct_pw):
        st.session_state.authenticated = True
        return True

    # 3) 로그인 폼
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
                st.query_params["_t"] = _auth_token(correct_pw)
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


def _refresh_creds(creds):
    import time as _time
    from google.auth.transport.requests import Request as _Request
    for _attempt in range(3):
        try:
            creds.refresh(_Request())
            return
        except Exception as _e:
            if _attempt == 2:
                raise
            _time.sleep(2 ** _attempt)


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
            _refresh_creds(creds)

    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    raw = ws.get("A2:X200", value_render_option="UNFORMATTED_VALUE")

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

    # 날짜 칼럼을 M/D 형식으로 통일 (datetime 객체도 처리)
    def normalize_date(x):
        s = str(x).strip()
        try:
            # datetime 객체인 경우
            if hasattr(x, 'month'):
                return f"{x.month}/{x.day}"
            # "5/1" 같은 문자열이면 그대로 반환
            elif "/" in s:
                return s
            # 다른 형식 시도
            else:
                import pandas as pd
                dt = pd.to_datetime(s, errors='coerce')
                if pd.notna(dt):
                    return f"{dt.month}/{dt.day}"
        except:
            pass
        return s
    date_col    = df.iloc[:, 0].apply(normalize_date)
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
    ch_ig_org   = safe_num(headers[23]) if len(headers) > 23 else pd.Series([0]*len(df))

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
        "유입_인스타오가닉": ch_ig_org.values if hasattr(ch_ig_org, "values") else ch_ig_org,
    })

    # CPO: 광고비 / Meta 전환수 (Meta 기준)
    result["CPO"] = result.apply(
        lambda r: round(r["광고비"] / r["전환_메타"]) if r["전환_메타"] > 0 and r["광고비"] > 0 else 0, axis=1
    )
    result["전환율"] = result.apply(
        lambda r: round(r["구매"] / r["방문자"] * 100, 2) if r["방문자"] > 0 else 0, axis=1
    )
    # ROAS: 광고 효율 지표이므로 Meta 자체 귀속 데이터만 사용 (GA4 매출과 섞지 않음)
    # GA4는 추적 누락 이슈가 있어 실제 매출보다 적게 잡힐 수 있으므로,
    # ROAS/CPO는 순수 Meta 기준 — 진짜 매출 확인은 "구매 전환 채널 상세" 또는
    # 플랫폼별 매출 탭(Cafe24 실데이터)을 봐야 함
    result["ROAS"] = result.apply(
        lambda r: round(float(r["ROAS_메타"]), 2) if r.get("ROAS_메타", 0) > 0 else 0,
        axis=1
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


@st.cache_data(ttl=3600)
def load_meta_ad_insights(date_preset="last_30d"):
    """Meta 광고 소재(Ad)별 성과 데이터 로드. TTL=1시간."""
    try:
        meta_token = None
        for key in ("meta_access_token", "META_ACCESS_TOKEN", "meta_token"):
            try:
                meta_token = st.secrets[key]
                if meta_token: break
            except Exception: pass
        if not meta_token:
            _tf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "meta_token.txt")
            if os.path.exists(_tf):
                meta_token = open(_tf).read().strip()
        if not meta_token:
            return pd.DataFrame()

        AD_ACCOUNT = "act_1599099620677018"

        # ① Ad 레벨 인사이트
        resp = _requests.get(
            f"https://graph.facebook.com/v25.0/{AD_ACCOUNT}/insights",
            params={
                "level": "ad",
                "fields": "ad_id,ad_name,adset_name,campaign_name,spend,impressions,clicks,ctr,actions,purchase_roas",
                "date_preset": date_preset,
                "limit": 100,
                "access_token": meta_token,
            },
            timeout=20,
        ).json()

        if not resp.get("data"):
            return pd.DataFrame()

        rows = []
        ad_ids = []
        for d in resp["data"]:
            purchases = revenue = 0
            # omni_purchase = Meta 권장 통합 구매 지표 (중복 없음)
            # 없으면 offsite_conversion.fb_pixel_purchase 로 폴백
            _actions = {a["action_type"]: int(float(a["value"])) for a in d.get("actions", [])}
            purchases = (
                _actions.get("omni_purchase")
                or _actions.get("offsite_conversion.fb_pixel_purchase")
                or _actions.get("purchase")
                or 0
            )
            for r in d.get("purchase_roas", []):
                spend_val = float(d.get("spend", 0))
                revenue = round(spend_val * float(r.get("value", 0)))

            spend  = round(float(d.get("spend", 0)))
            clicks = int(d.get("clicks", 0))
            imps   = int(d.get("impressions", 0))
            ctr    = round(float(d.get("ctr", 0)), 2)   # Meta API: 이미 % 값
            cpo    = round(spend / purchases) if purchases > 0 else 0
            roas   = round(revenue / spend, 1) if spend > 0 else 0

            _campaign = d.get("campaign_name", "")
            _adset    = d.get("adset_name", "")
            _adname   = d.get("ad_name", "-")
            _full_name = f"{_campaign} > {_adset} > {_adname}"

            rows.append({
                "ad_id":    d.get("ad_id", ""),
                "캠페인":   _campaign,
                "광고세트": _adset,
                "소재명":   _adname,
                "전체경로": _full_name,
                "광고비":   spend,
                "노출수":  imps,
                "클릭수":  clicks,
                "CTR":    ctr,
                "전환수":  purchases,
                "CPO":    cpo,
                "ROAS":   roas,
                "매출":    revenue,
            })
            ad_ids.append(d.get("ad_id", ""))

        df_ads = pd.DataFrame(rows)

        # ② 썸네일 가져오기 (상위 20개 광고)
        thumbnails = {}
        for ad_id in ad_ids[:20]:
            try:
                cr = _requests.get(
                    f"https://graph.facebook.com/v25.0/{ad_id}/adcreatives",
                    params={"fields": "thumbnail_url", "access_token": meta_token},
                    timeout=8,
                ).json()
                if cr.get("data"):
                    thumbnails[ad_id] = cr["data"][0].get("thumbnail_url", "")
            except Exception:
                pass

        df_ads["thumbnail"] = df_ads["ad_id"].map(thumbnails).fillna("")
        return df_ads.sort_values("전환수", ascending=False).reset_index(drop=True)

    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
@st.cache_data(ttl=3600)
def load_meta_creative_fatigue(date_preset="last_14d"):
    """소재별 CTR 추이로 피로도 분석. 교체 필요 소재 목록 반환.
    date_preset: '광고 소재별 성과' 섹션의 기간 선택과 동일한 값을 받아 동기화."""
    try:
        import re as _re
        meta_token = None
        for key in ("meta_access_token", "META_ACCESS_TOKEN", "meta_token"):
            try:
                meta_token = st.secrets[key]
                if meta_token: break
            except Exception: pass
        if not meta_token:
            _tf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "meta_token.txt")
            if os.path.exists(_tf):
                meta_token = open(_tf).read().strip()
        if not meta_token:
            return []

        resp = _requests.get(
            "https://graph.facebook.com/v25.0/act_1599099620677018/insights",
            params={
                "level": "ad",
                "fields": "ad_name,campaign_name,spend,impressions,clicks,ctr",
                "date_preset": date_preset,
                "time_increment": 1,
                "limit": 500,
                "access_token": meta_token,
            }, timeout=20,
        ).json()

        # 소재별 일별 CTR 수집
        ad_daily = {}
        for d in resp.get("data", []):
            name  = d.get("ad_name", "-")
            spend = float(d.get("spend", 0))
            ctr   = float(d.get("ctr", 0))
            date  = d.get("date_start", "")
            if spend < 100: continue  # 소액 집행일 제외
            if name not in ad_daily:
                ad_daily[name] = {"days": [], "campaign": d.get("campaign_name","")}
            ad_daily[name]["days"].append({"date": date, "ctr": ctr, "spend": spend})

        # 소재별 피로도 판단
        fatigued = []
        for name, info in ad_daily.items():
            days = sorted(info["days"], key=lambda x: x["date"])
            if len(days) < 3: continue
            ctrs = [d["ctr"] for d in days]
            peak = max(ctrs)
            last = ctrs[-1]
            last3_avg = sum(ctrs[-3:]) / 3
            first3_avg = sum(ctrs[:3]) / 3
            drop_from_peak = (peak - last) / peak * 100 if peak > 0 else 0
            trend_drop = first3_avg > 0 and last3_avg < first3_avg * 0.8

            level = None
            reason = ""
            if last < 3.0 or drop_from_peak >= 50:
                level = "critical"
                reason = f"CTR {last:.1f}% (피크 {peak:.1f}% 대비 {drop_from_peak:.0f}%↓)"
            elif drop_from_peak >= 30 or trend_drop:
                level = "warning"
                reason = f"CTR {last:.1f}% (피크 {peak:.1f}% 대비 {drop_from_peak:.0f}%↓)"

            if level:
                fatigued.append({
                    "소재명": name,
                    "캠페인": info["campaign"],
                    "level": level,
                    "reason": reason,
                    "집행일수": len(days),
                })

        # critical 먼저, 그 다음 warning 순
        fatigued.sort(key=lambda x: 0 if x["level"] == "critical" else 1)
        return fatigued
    except Exception:
        return []


@st.cache_data(ttl=600)
def load_purchase_channel_detail(start_date, end_date):
    """날짜별 source/medium 단위로 실제 구매가 발생한 채널 상세 조회.
    GA4 Data API는 개별 거래ID까지는 못 주지만, 날짜+채널 단위로 어떤 구매가
    어디서 발생했는지는 정확히 구분 가능. (bool, DataFrame) 반환."""
    if not _GA4_AVAILABLE:
        return False, pd.DataFrame()
    try:
        creds = _get_oauth_creds()
        ga4 = BetaAnalyticsDataClient(credentials=creds)
        res = ga4.run_report(RunReportRequest(
            property="properties/536368183",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimensions=[Dimension(name="date"), Dimension(name="sessionSource"), Dimension(name="sessionMedium")],
            metrics=[Metric(name="transactions"), Metric(name="purchaseRevenue")],
        ))

        def _label_channel(src, med):
            src, med = src.lower(), med.lower()
            if src == "meta" and med == "paid_feed": return "메타 유료광고"
            if src == "ig" and med == "paid":         return "메타 유료광고(IG)"
            if src == "ig" and med == "social":        return "인스타그램 오가닉"
            if src == "igshopping":                    return "인스타그램 오가닉(샵)"
            if src == "instagram" and med == "personal_bio":   return "개인 인스타 바이오"
            if src == "instagram" and med == "personal_story": return "개인 인스타 스토리"
            if src == "instagram" and med == "bio":     return "공식 인스타 바이오"
            if src == "(direct)":                       return "직접 방문"
            return f"{src}/{med}"

        rows = []
        for row in res.rows:
            trans = int(float(row.metric_values[0].value))
            if trans <= 0:
                continue
            d   = row.dimension_values[0].value  # YYYYMMDD
            src = row.dimension_values[1].value
            med = row.dimension_values[2].value
            rev = round(float(row.metric_values[1].value))
            date_label = f"{int(d[4:6])}/{int(d[6:8])}"
            rows.append({
                "날짜": date_label, "_정렬용": d,
                "유입채널": _label_channel(src, med),
                "원본": f"{src}/{med}",
                "구매건수": trans, "매출": rev,
            })
        df_out = pd.DataFrame(rows).sort_values("_정렬용", ascending=False).drop(columns="_정렬용") if rows else pd.DataFrame()
        return True, df_out
    except Exception as e:
        return False, pd.DataFrame()


def load_meta_daily_creative(date_preset="last_30d"):
    """날짜별 소재(Ad) 전환 데이터. 차트 annotation용. TTL=1시간."""
    try:
        meta_token = None
        for key in ("meta_access_token", "META_ACCESS_TOKEN", "meta_token"):
            try:
                meta_token = st.secrets[key]
                if meta_token: break
            except Exception: pass
        if not meta_token:
            _tf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "meta_token.txt")
            if os.path.exists(_tf):
                meta_token = open(_tf).read().strip()
        if not meta_token:
            return pd.DataFrame()

        resp = _requests.get(
            f"https://graph.facebook.com/v25.0/act_1599099620677018/insights",
            params={
                "level": "ad",
                "fields": "ad_name,actions,spend",
                "date_preset": date_preset,
                "time_increment": 1,   # 일별 분해
                "limit": 500,
                "access_token": meta_token,
            },
            timeout=20,
        ).json()

        rows = []
        for d in resp.get("data", []):
            _actions = {a["action_type"]: int(float(a["value"])) for a in d.get("actions", [])}
            purchases = (
                _actions.get("omni_purchase")
                or _actions.get("offsite_conversion.fb_pixel_purchase")
                or _actions.get("purchase") or 0
            )
            if purchases > 0:
                rows.append({
                    "날짜":   d.get("date_start", ""),
                    "소재명": d.get("ad_name", "-"),
                    "전환수": purchases,
                    "광고비": round(float(d.get("spend", 0))),
                })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


# ── Instagram 계정 설정 ───────────────────────────────────────────────
IG_ACCOUNTS = {
    "beeunkim (개인)": {
        "token": "IGAAfKtJZBiU09BZAFkyY3V3TUxXMFY1V1A1cHdiRXljMjV0LTQ5TmZA4RnUtODhSaVhIT0pPQXY1a3pNNk9NVWRoR3BUUnJITG1OTUUySjVicHZAMUDZAVN18wQ1hRQTJSMVpPdmJVRUdHelpMRkpqQkpJRHlFN2ZAzdDZA1ckRCaGlGcwZDZD",
        "ig_id": "17841401409070018",
        "color": "#C13584",
    },
    "nominical_official (공식)": {
        "token": "IGAAfKtJZBiU09BZAFlOVHhQSWxnS1UwdDRweVFOSWMzcVU0eHdNV29EX0tadkZACeXlFNFlKUVpkcGZABMllnQVNQRzd5NEFYSXFXS2VWZAXJXMG1sajRQZAGN0YlhvalNfNmJ2UVVWSVlPYU5YUmFoQU40OXZAtblVsN0VIYmFiWU0zbwZDZD",
        "ig_id": "17841465777820020",
        "color": "#1A1A2E",
    },
}

@st.cache_data(ttl=3600)
def load_ig_profile(account_name: str):
    """Instagram 프로필 + 최근 미디어 + 인사이트 로드. TTL=1시간."""
    cfg = IG_ACCOUNTS.get(account_name, {})
    token = cfg.get("token", "")
    ig_id = cfg.get("ig_id", "")
    if not token or not ig_id:
        return {}, []
    try:
        base = "https://graph.instagram.com/v25.0"

        # 프로필
        prof = _requests.get(f"{base}/me", params={
            "fields": "id,username,followers_count,media_count,profile_picture_url,biography,website",
            "access_token": token,
        }, timeout=10).json()
        if "error" in prof:
            return prof, []

        # 미디어 (최근 20개)
        med = _requests.get(f"{base}/{ig_id}/media", params={
            "fields": "id,caption,media_type,timestamp,like_count,comments_count,permalink,thumbnail_url,media_url",
            "limit": 20,
            "access_token": token,
        }, timeout=10).json()

        rows = []
        for item in med.get("data", []):
            mid   = item["id"]
            mtype = item.get("media_type", "")

            # 미디어 타입별 인사이트 지표
            if mtype in ("VIDEO", "REEL"):
                metrics = "reach,saved,total_interactions,shares,views,ig_reels_avg_watch_time"
            else:
                metrics = "reach,saved,total_interactions,shares"

            ins_r = _requests.get(f"{base}/{mid}/insights", params={
                "metric": metrics, "access_token": token,
            }, timeout=8).json()

            ins = {d["name"]: d["values"][0]["value"] for d in ins_r.get("data", [])}

            rows.append({
                "id":          mid,
                "타입":        mtype,
                "날짜":        item.get("timestamp", "")[:10],
                "캡션":        (item.get("caption") or "")[:80],
                "좋아요":      item.get("like_count", 0),
                "댓글":        item.get("comments_count", 0),
                "도달":        ins.get("reach", 0),
                "저장":        ins.get("saved", 0),
                "공유":        ins.get("shares", 0),
                "반응":        ins.get("total_interactions", 0),
                "조회수":      ins.get("views", 0),
                "평균시청(s)": round(ins.get("ig_reels_avg_watch_time", 0) / 1000, 1) if ins.get("ig_reels_avg_watch_time") else 0,
                "썸네일":      item.get("thumbnail_url") or item.get("media_url", ""),
                "링크":        item.get("permalink", ""),
                "ER":          round((item.get("like_count", 0) + item.get("comments_count", 0)) / max(ins.get("reach", 1), 1) * 100, 2),
            })

        return prof, rows
    except Exception as e:
        return {"error": str(e)}, []


# ── 데이터 로드: 플랫폼 매출 ────────────────────────────────────────
@st.cache_data(ttl=300)
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
            _refresh_creds(creds)

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


# ── 데이터 로드: 입고/재고 ──────────────────────────────────────────
INVENTORY_SHEET_NAME = "📦 입고관리"

def _normalize_color(c):
    """컬러 표기 차이 흡수 (공백 제거 + 알려진 동의어 통일)."""
    c = str(c).strip().replace(" ", "")
    synonyms = {
        "레몬옐로우": "옐로우",
        "멜란지그레이": "멜란지그레이",  # 이미 공백없음 기준
    }
    return synonyms.get(c, c)

@st.cache_data(ttl=300)
def load_inventory_data():
    """입고관리 시트(품번/매칭키워드/컬러/사이즈/기준재고/기준일자) + 플랫폼
    매출 시트를 매칭해서 현재 재고를 계산.
    기준일자 이후 발생한 판매(취소·반품 제외)만 기준재고에서 차감함
    — 기준재고 자체가 그 시점까지의 판매를 이미 반영한 스냅샷이기 때문."""
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
            _refresh_creds(creds)

    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)

    try:
        ws_inv = sh.worksheet(INVENTORY_SHEET_NAME)
    except Exception:
        return pd.DataFrame()

    inv_raw = ws_inv.get_all_values()
    if len(inv_raw) <= 1:
        return pd.DataFrame()

    inv_rows = []
    for r in inv_raw[1:]:
        if not r or not r[0].strip():
            continue
        style_no   = r[0].strip()
        keyword    = r[1].strip() if len(r) > 1 else ""
        color      = r[2].strip() if len(r) > 2 else "-"
        size       = r[3].strip() if len(r) > 3 else "-"
        try:
            baseline = int(float(r[4])) if len(r) > 4 and r[4].strip() else 0
        except ValueError:
            baseline = 0
        baseline_date = r[5].strip() if len(r) > 5 else ""
        memo          = r[6].strip() if len(r) > 6 else ""
        full_name     = r[7].strip() if len(r) > 7 and r[7].strip() else keyword
        inv_rows.append({
            "품번": style_no, "매칭키워드": keyword, "상품명": full_name,
            "컬러": color, "사이즈": size,
            "기준재고": baseline, "기준일자": baseline_date, "비고": memo,
        })

    if not inv_rows:
        return pd.DataFrame()

    df_plat = load_platform_data()
    if df_plat.empty:
        for r in inv_rows:
            r["판매수량(기준일 이후)"] = 0
            r["매칭건수"] = 0
            r["최근7일판매"] = 0
            r["최근3일판매"] = 0
            r["일평균판매"] = 0.0
    else:
        normal = df_plat[~df_plat["주문상태"].str.contains("취소|반품", na=False, regex=True)].copy()
        normal["_컬러norm"] = normal["컬러"].apply(_normalize_color)
        for r in inv_rows:
            kw = r["매칭키워드"]
            color_norm = _normalize_color(r["컬러"])
            size = r["사이즈"]

            m = normal[normal["상품명"].str.contains(kw, case=False, na=False, regex=False)]
            # "(프리오더 ...)" 표기 상품은 별도 생산 배치(다른 재고 풀)이므로
            # 매칭키워드 자체가 프리오더를 명시하지 않는 한 제외
            if "프리오더" not in kw:
                m = m[~m["상품명"].str.contains("프리오더", case=False, na=False, regex=False)]
            m = m[m["_컬러norm"] == color_norm]
            if size and size != "-":
                m = m[m["사이즈"].astype(str).str.strip() == size]
            try:
                cutoff = pd.Timestamp(r["기준일자"]) if r["기준일자"] else None
            except Exception:
                cutoff = None
            if cutoff is not None and "주문일_dt" in m.columns:
                m = m[m["주문일_dt"] > cutoff]

            r["판매수량(기준일 이후)"] = int(m["수량"].sum())
            r["매칭건수"] = len(m)

            # 최근 3일/7일 평균 일판매량 — 둘 중 더 빠른(위험한) 쪽을 리오더 판단에 사용
            # (7일 평균만 쓰면 최근 며칠 급증한 판매 속도가 희석되어 늦게 잡힘)
            now_ts = pd.Timestamp.now()
            cutoff7 = now_ts - pd.Timedelta(days=7)
            cutoff3 = now_ts - pd.Timedelta(days=3)
            m7 = m[m["주문일_dt"] > cutoff7] if "주문일_dt" in m.columns else m.iloc[0:0]
            m3 = m[m["주문일_dt"] > cutoff3] if "주문일_dt" in m.columns else m.iloc[0:0]
            r["최근7일판매"] = int(m7["수량"].sum())
            r["최근3일판매"] = int(m3["수량"].sum())
            avg7 = r["최근7일판매"] / 7
            avg3 = r["최근3일판매"] / 3
            r["일평균판매"] = round(max(avg7, avg3), 2)

    df = pd.DataFrame(inv_rows)
    df["재고"] = df["기준재고"] - df["판매수량(기준일 이후)"]

    # 소진예상일수 = 재고 / 일평균판매 (생산 리드타임 14일 감안해 리오더 필요 여부 판단)
    PRODUCTION_LEAD_DAYS = 14
    def _days_to_stockout(row):
        if row["일평균판매"] <= 0:
            return None  # 최근 판매 없음 → 소진 임박 아님
        return round(row["재고"] / row["일평균판매"], 1)
    df["소진예상일"] = df.apply(_days_to_stockout, axis=1)
    df["리오더필요"] = df["소진예상일"].apply(lambda d: pd.notna(d) and d <= PRODUCTION_LEAD_DAYS)
    return df


# ══════════════════════════════════════════════════════════════════
# 자동 업데이트 함수 (새로고침 버튼에서 호출)
# ══════════════════════════════════════════════════════════════════

def _get_sheet_creds(extra_scopes=None):
    """SA(시크릿) 또는 OAuth(로컬 token.json) 인증 반환 — Sheets 전용"""
    scopes = ["https://www.googleapis.com/auth/spreadsheets"] + (extra_scopes or [])
    if "gcp_service_account" in st.secrets:
        return SACredentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]), scopes=scopes
        )
    token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")
    creds = OAuthCredentials.from_authorized_user_file(token_path, scopes)
    if creds.expired and creds.refresh_token:
        _refresh_creds(creds)
    return creds


def _get_oauth_creds():
    """OAuth 자격증명 반환 — GA4 + Sheets 동시 접근용.
    Streamlit secrets의 google_token_json 또는 로컬 token.json 사용."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
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
        token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")
        creds = OAuthCredentials.from_authorized_user_file(token_path, scopes)
    if creds.expired and creds.refresh_token:
        _refresh_creds(creds)
    return creds


def update_ga4_yesterday():
    """어제 GA4 데이터를 시트 K~V열에 업데이트. (bool, str) 반환."""
    if not _GA4_AVAILABLE:
        return False, "google-analytics-data 패키지가 설치되어 있지 않아요."
    try:
        from datetime import date, timedelta

        GA4_PROPERTY_ID = "536368183"
        creds           = _get_oauth_creds()   # OAuth: Sheets + GA4 동시 접근
        ga4             = BetaAnalyticsDataClient(credentials=creds)
        gc              = gspread.authorize(creds)
        ws              = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

        yesterday = date.today() - timedelta(days=1)
        date_str  = yesterday.strftime("%Y-%m-%d")
        day_label = f"{yesterday.month}/{yesterday.day}"

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
            ["sessions", "transactions", "bounceRate", "averagePurchaseRevenue", "purchaseRevenue"],
        )
        sessions = transactions = bounce = avg_price = revenue = 0
        if res.rows:
            r            = res.rows[0].metric_values
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
                    string_filter=Filter.StringFilter(value=medium, match_type="EXACT"))),
            ]))
            r2 = run_report(["sessionSource"], ["sessions"], f)
            return int(float(r2.rows[0].metric_values[0].value)) if r2.rows else 0

        time.sleep(0.3)
        # 메타 유료광고 (paid만 — meta/paid_feed, ig/paid)
        ch_meta     = get_channel("meta", "paid_feed") + get_channel("ig", "paid")
        time.sleep(0.3)
        ch_official = get_channel("instagram", "bio")
        time.sleep(0.3)
        ch_personal = get_channel("instagram", "personal_bio") + get_channel("instagram", "personal_story")
        time.sleep(0.3)
        # 인스타그램 오가닉 (ig/social, IGShopping/Social) — 개인/공식 계정 구분 불가
        # (UTM 파라미터 없이는 어느 계정 콘텐츠인지 GA4가 알 수 없음)
        ch_ig_organic = get_channel("ig", "social") + get_channel("IGShopping", "Social")
        time.sleep(0.3)

        f_direct  = FilterExpression(filter=Filter(field_name="sessionMedium",
            string_filter=Filter.StringFilter(value="(none)", match_type="EXACT")))
        r_direct  = run_report(["sessionMedium"], ["sessions"], f_direct)
        ch_direct = int(float(r_direct.rows[0].metric_values[0].value)) if r_direct.rows else 0

        res_new        = run_report(["newVsReturning"], ["activeUsers"])
        new_users = returning_users = 0
        for row in res_new.rows:
            val = int(float(row.metric_values[0].value))
            if row.dimension_values[0].value == "new":
                new_users = val
            else:
                returning_users = val

        all_dates = ws.col_values(1)
        row_idx   = next((i + 1 for i, d in enumerate(all_dates) if d == day_label), None)
        if not row_idx:
            # 날짜 행이 없으면 새 행 추가
            ws.append_row([day_label], value_input_option="RAW")
            all_dates = ws.col_values(1)
            row_idx = next((i + 1 for i, d in enumerate(all_dates) if d == day_label), None)
        if not row_idx:
            return False, f"'{day_label}' 행 생성 실패"

        ws.update(values=[[sessions, transactions]], range_name=f"K{row_idx}:L{row_idx}")
        time.sleep(0.2)
        ws.update(
            values=[[bounce, avg_price, revenue, ch_meta, ch_official, ch_personal, ch_direct]],
            range_name=f"N{row_idx}:T{row_idx}",
        )
        time.sleep(0.2)
        ws.update(values=[[new_users, returning_users]], range_name=f"U{row_idx}:V{row_idx}")
        time.sleep(0.2)
        ws.update(values=[[ch_ig_organic]], range_name=f"X{row_idx}")

        return True, f"✅ GA4 {day_label} 완료 — 방문자 {sessions:,}명 · 구매 {transactions}건"

    except Exception as e:
        return False, f"❌ GA4 업데이트 실패: {e}"


def update_ga4_for_date(target_date):
    """특정 날짜 GA4 데이터를 시트에 업데이트. (bool, str) 반환."""
    if not _GA4_AVAILABLE:
        return False, "google-analytics-data 패키지가 설치되어 있지 않아요."
    try:
        from datetime import date, timedelta

        GA4_PROPERTY_ID = "536368183"
        creds           = _get_oauth_creds()
        ga4             = BetaAnalyticsDataClient(credentials=creds)
        gc              = gspread.authorize(creds)
        ws              = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

        # target_date가 date 객체가 아니면 변환
        if isinstance(target_date, str):
            parts = target_date.split("/")
            target_date = date(2026, int(parts[0]), int(parts[1]))

        date_str  = target_date.strftime("%Y-%m-%d")
        day_label = f"{target_date.month}/{target_date.day}"

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
            ["sessions", "transactions", "bounceRate", "averagePurchaseRevenue", "purchaseRevenue"],
        )
        sessions = transactions = bounce = avg_price = revenue = 0
        if res.rows:
            r            = res.rows[0].metric_values
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
                    string_filter=Filter.StringFilter(value=medium, match_type="EXACT"))),
            ]))
            r2 = run_report(["sessionSource"], ["sessions"], f)
            return int(float(r2.rows[0].metric_values[0].value)) if r2.rows else 0

        time.sleep(0.3)
        ch_meta     = get_channel("meta", "paid_feed") + get_channel("ig", "paid")
        time.sleep(0.3)
        ch_official = get_channel("instagram", "bio")
        time.sleep(0.3)
        ch_personal = get_channel("instagram", "personal_bio") + get_channel("instagram", "personal_story")
        time.sleep(0.3)
        # 인스타그램 오가닉 (ig/social, IGShopping/Social) — 개인/공식 계정 구분 불가
        ch_ig_organic = get_channel("ig", "social") + get_channel("IGShopping", "Social")
        time.sleep(0.3)

        f_direct  = FilterExpression(filter=Filter(field_name="sessionMedium",
            string_filter=Filter.StringFilter(value="(none)", match_type="EXACT")))
        r_direct  = run_report(["sessionMedium"], ["sessions"], f_direct)
        ch_direct = int(float(r_direct.rows[0].metric_values[0].value)) if r_direct.rows else 0

        res_new        = run_report(["newVsReturning"], ["activeUsers"])
        new_users = returning_users = 0
        for row in res_new.rows:
            val = int(float(row.metric_values[0].value))
            if row.dimension_values[0].value == "new":
                new_users = val
            else:
                returning_users = val

        all_dates = ws.col_values(1)
        row_idx   = None
        for i, d in enumerate(all_dates):
            if str(d).strip() == day_label:
                row_idx = i + 1
                break

        if not row_idx:
            # 날짜 행이 없으면 새 행 추가
            ws.append_row([day_label], value_input_option="RAW")
            all_dates = ws.col_values(1)
            for i, d in enumerate(all_dates):
                if str(d).strip() == day_label:
                    row_idx = i + 1
                    break

        # 대시보드 읽기 코드 기준 정확한 인덱스 매핑
        # (load_data에서 headers[10]=방문자, [11]=구매, [13]=이탈율, [14]=객단가, [15]=매출...)
        ws.update_cell(row_idx, 11, sessions)          # K(idx10): 방문자수
        ws.update_cell(row_idx, 12, transactions)      # L(idx11): 구매자수
        # M(idx12): 전환율 — 대시보드가 읽지 않음 (skip)
        ws.update_cell(row_idx, 14, bounce)            # N(idx13): 이탈율
        ws.update_cell(row_idx, 15, avg_price)         # O(idx14): 객단가(원)
        ws.update_cell(row_idx, 16, revenue)           # P(idx15): 자사몰매출(원)
        ws.update_cell(row_idx, 17, ch_meta)           # Q(idx16): 유입_메타광고
        ws.update_cell(row_idx, 18, ch_official)       # R(idx17): 유입_공식인스타
        ws.update_cell(row_idx, 19, ch_personal)       # S(idx18): 유입_개인인스타
        ws.update_cell(row_idx, 20, ch_direct)         # T(idx19): 유입_직접
        ws.update_cell(row_idx, 21, new_users)         # U(idx20): 신규방문자
        ws.update_cell(row_idx, 22, returning_users)   # V(idx21): 재방문자
        ws.update_cell(row_idx, 24, ch_ig_organic)     # X(idx23): 유입_인스타오가닉

        return True, f"✅ GA4 {day_label} 완료 — 방문자 {sessions:,}명 · 구매 {transactions}건"

    except Exception as e:
        return False, f"❌ GA4 업데이트 실패 ({target_date}): {e}"


def get_last_data_date():
    """마지막 데이터 날짜 반환 (date 객체)."""
    from datetime import date
    try:
        gc = gspread.authorize(_get_oauth_creds())
        ws = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        all_dates = ws.col_values(1)

        for d in reversed(all_dates[1:]):  # 헤더 제외
            d_str = str(d).strip()
            if not d_str or "종합" in d_str or "날짜" in d_str:
                continue
            try:
                parts = d_str.split("/")
                if len(parts) == 2:
                    month, day = int(parts[0]), int(parts[1])
                    return date(2026, month, day)
            except:
                continue
        return None
    except Exception as e:
        print(f"❌ 마지막 날짜 조회 실패: {e}")
        return None


def add_empty_rows_for_gaps():
    """6/1과 6/7 사이같이 갭이 있으면 빈 행들을 자동으로 추가."""
    from datetime import date, timedelta

    try:
        gc = gspread.authorize(_get_oauth_creds())
        ws = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        all_dates = ws.col_values(1)

        print("\n🔍 갭이 있는지 확인 중...")

        # 모든 날짜를 date 객체로 변환
        date_objects = []
        date_to_row = {}
        for i, d in enumerate(all_dates[1:], start=2):  # 헤더 제외
            d_str = str(d).strip()
            if not d_str or "종합" in d_str or "날짜" in d_str:
                continue
            try:
                parts = d_str.split("/")
                if len(parts) == 2:
                    month, day = int(parts[0]), int(parts[1])
                    dt = date(2026, month, day)
                    date_objects.append(dt)
                    date_to_row[dt] = i
            except:
                continue

        if not date_objects:
            return False, "데이터가 없어요."

        # 갭 찾기 (기존 범위 내 갭 + 어제까지 신규 날짜)
        dates_needed = set()
        min_date = min(date_objects)
        yesterday = date.today() - timedelta(days=1)
        max_date  = max(max(date_objects), yesterday)  # 어제까지 체크

        current = min_date
        while current <= max_date:
            if current not in date_to_row:
                dates_needed.add(current)
            current += timedelta(days=1)

        if not dates_needed:
            return True, "갭이 없어요 (이미 모든 날짜가 있음)."

        print(f"   추가할 날짜: {sorted([f'{d.month}/{d.day}' for d in dates_needed])}")

        # 날짜별로 정렬해서 올바른 위치에 행 삽입/추가
        sorted_dates = sorted(dates_needed)
        max_existing = max(date_to_row.keys()) if date_to_row else None

        for insert_date in sorted_dates:
            date_label = f"{insert_date.month}/{insert_date.day}"

            # 기존 날짜보다 뒤면 append, 중간이면 insert
            insert_row = None
            for check_date in sorted(date_to_row.keys()):
                if check_date > insert_date:
                    insert_row = date_to_row[check_date]
                    break

            if insert_row is None:
                # 맨 뒤에 append
                ws.append_row([date_label], value_input_option="RAW")
                # append 후 실제 행번호 파악
                new_all = ws.col_values(1)
                for i, v in enumerate(new_all, start=1):
                    if str(v).strip() == date_label:
                        date_to_row[insert_date] = i
            else:
                # 중간에 insert
                ws.insert_row([date_label], index=insert_row)
                for d in list(date_to_row.keys()):
                    if date_to_row[d] >= insert_row:
                        date_to_row[d] += 1
                date_to_row[insert_date] = insert_row

            time.sleep(0.5)

        return True, f"✅ {len(sorted_dates)}개 빈 행 추가 완료!"

    except Exception as e:
        return False, f"❌ 빈 행 추가 실패: {e}"


def update_meta_for_date(target_date):
    """특정 날짜 Meta 광고 데이터를 시트에 업데이트. (bool, str) 반환."""
    try:
        from datetime import date

        # Meta 토큰 읽기: secrets.toml → 로컬 파일
        meta_token = None

        # 방법 1: secrets.toml에서 읽기
        import re
        try:
            secrets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit", "secrets.toml")
            if os.path.exists(secrets_path):
                with open(secrets_path, 'r') as f:
                    content = f.read()
                match = re.search(r'meta_access_token\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    meta_token = match.group(1)
        except Exception:
            pass

        # 방법 2: meta_token.txt에서 읽기
        if not meta_token:
            _tf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "meta_token.txt")
            if os.path.exists(_tf):
                meta_token = open(_tf).read().strip()

        if not meta_token:
            return False, "Meta 토큰 없음"

        AD_ACCOUNT = "act_1599099620677018"

        creds = _get_oauth_creds()
        gc    = gspread.authorize(creds)
        ws    = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

        # target_date가 date 객체가 아니면 변환
        if isinstance(target_date, str):
            parts = target_date.split("/")
            target_date = date(2026, int(parts[0]), int(parts[1]))

        date_str  = target_date.strftime("%Y-%m-%d")
        day_label = f"{target_date.month}/{target_date.day}"

        res = _requests.get(
            f"https://graph.facebook.com/v25.0/{AD_ACCOUNT}/insights",
            params={
                "fields":     "spend,impressions,clicks,ctr,cpc,actions,purchase_roas",
                "time_range": f'{{"since":"{date_str}","until":"{date_str}"}}',
                "access_token": meta_token,
            },
            timeout=15,
        ).json()

        spend = impressions = clicks = purchases = ctr = cpc = roas = cpa = 0
        if res.get("data"):
            d           = res["data"][0]
            spend       = round(float(d.get("spend", 0)))
            impressions = int(d.get("impressions", 0))
            clicks      = int(d.get("clicks", 0))
            ctr         = round(float(d.get("ctr", 0)), 2)
            cpc         = round(float(d.get("cpc", 0)))
            for action in d.get("actions", []):
                if action["action_type"] in ("purchase", "offsite_conversion.fb_pixel_purchase"):
                    purchases = int(float(action["value"]))
            for roas_data in d.get("purchase_roas", []):
                roas = round(float(roas_data.get("value", 0)), 2)
            cpa = round(spend / purchases) if purchases > 0 else 0

        # Google Sheets에서 행 찾기
        all_dates = ws.col_values(1)
        row_idx = None
        for i, d in enumerate(all_dates):
            if str(d).strip() == day_label:
                row_idx = i + 1
                break

        if not row_idx:
            return False, f"'{day_label}' 행을 찾을 수 없음"

        # C~J 칼럼 한 번에 쓰기 (광고비, 노출, 클릭, CTR, CPC, 전환, ROAS, CPA)
        ws.update(
            values=[[spend, impressions, clicks, ctr, cpc, purchases, roas, cpa]],
            range_name=f"C{row_idx}:J{row_idx}"
        )

        return True, f"✅ Meta {day_label} 완료 — 광고비 {spend:,}원 · 전환 {purchases}건"

    except Exception as e:
        return False, f"❌ Meta 업데이트 실패 ({target_date}): {e}"


def fill_missing_dates():
    """비어있는 날짜들을 자동 감지하고 GA4 + Meta 데이터로 채우기."""
    from datetime import date, timedelta
    import re as _re

    try:
        creds = _get_oauth_creds()
        gc = gspread.authorize(creds)
        ws = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

        yesterday = date.today() - timedelta(days=1)

        # 시트 전체 데이터 읽기 (A~V 칼럼)
        all_rows = ws.get("A2:V200", value_render_option="UNFORMATTED_VALUE")

        # 날짜 파싱 함수 (M/D 형식)
        def parse_md(s):
            s = str(s).strip()
            try:
                parts = s.split("/")
                if len(parts) == 2:
                    return date(2026, int(parts[0]), int(parts[1]))
            except:
                pass
            return None

        # 시트에 있는 날짜와 해당 행 데이터 매핑
        sheet_map = {}  # date → row_data
        for row in all_rows:
            if not row or not row[0]:
                continue
            d = parse_md(row[0])
            if d:
                sheet_map[d] = row

        # 가장 오래된 날짜부터 어제까지 빠진 날짜 + 데이터 없는 날짜 모두 감지
        if not sheet_map:
            return False, "시트에 데이터가 없어요."

        start_date = min(sheet_map.keys())
        missing_dates = []

        check_date = start_date
        while check_date <= yesterday:
            row_data = sheet_map.get(check_date)

            if row_data is None:
                # 날짜 자체가 없음
                missing_dates.append(check_date)
            else:
                # 날짜는 있지만 GA4 또는 Meta 데이터가 비어있는지 확인
                # GA4: K칼럼 = index 10 (방문자)
                ga4_empty = len(row_data) < 11 or not str(row_data[10]).strip()
                # Meta: C칼럼 = index 2 (광고비)
                meta_empty = len(row_data) < 3 or not str(row_data[2]).strip()

                if ga4_empty or meta_empty:
                    missing_dates.append(check_date)

            check_date += timedelta(days=1)

        if not missing_dates:
            return True, "✅ 갭이 없어요 (이미 모든 날짜가 있음)."

        # 각 날짜에 GA4 + Meta 데이터 추가
        errors = []
        for d in missing_dates:
            # GA4 데이터
            ok_ga4, msg_ga4 = update_ga4_for_date(d)
            if not ok_ga4:
                errors.append(f"GA4 {d.month}/{d.day}: {msg_ga4}")

            # Meta 데이터
            ok_meta, msg_meta = update_meta_for_date(d)
            if not ok_meta:
                errors.append(f"Meta {d.month}/{d.day}: {msg_meta}")

            time.sleep(0.5)

        if errors:
            return True, f"✅ {len(missing_dates)}개 날짜 처리 완료\n⚠️ 에러: {chr(10).join(errors)}"
        return True, f"✅ {len(missing_dates)}개 날짜 데이터 추가 완료!"

    except Exception as e:
        return False, f"❌ 갭 채우기 실패: {e}"


def update_meta_yesterday():
    """어제 메타 광고 데이터를 시트 C~J열에 업데이트. (bool, str) 반환."""
    from datetime import date, timedelta
    yesterday = date.today() - timedelta(days=1)
    return update_meta_for_date(yesterday)


def _send_ga4_purchase_mp(order_id, value, items, order_ts=None):
    """GA4 Measurement Protocol로 purchase 이벤트 서버사이드 전송.
    네이버페이 등 외부 결제는 nominical.co.kr 주문완료 페이지로 안 돌아오기 때문에
    클라이언트 gtag 스크립트가 실행될 기회 자체가 없음 — Cafe24 주문 데이터를
    기준으로 직접 GA4에 구매 이벤트를 쏘아 결제수단 무관하게 100% 추적되게 함.
    (단, 실제 세션의 client_id가 없어 채널 귀속(source/medium)은 비어있을 수 있음 —
    이건 전체 매출/전환수 정확도를 위한 보완이며 채널 분석은 별도 트래킹에 의존)
    """
    try:
        measurement_id = st.secrets.get("ga4_measurement_id", "")
        api_secret      = st.secrets.get("ga4_api_secret", "")
        if not measurement_id or not api_secret:
            return False

        # 주문 시각을 timestamp_micros로 전송 — 없으면 전송 시점 날짜로 기록되어
        # 밀린 주문을 나중에 보내면 전부 엉뚱한 날짜에 집계되는 버그가 생김.
        # GA4 MP는 72시간 이전 이벤트를 거부하므로 그보다 오래된 주문은 스킵.
        ts_micros = None
        if order_ts:
            try:
                from datetime import datetime as _dtt, timedelta as _tdd
                _dt = _dtt.fromisoformat(str(order_ts).replace("Z", "+09:00"))
                if _dt.tzinfo:
                    _dt = _dt.replace(tzinfo=None)
                if _dtt.now() - _dt > _tdd(hours=71):
                    return "skip"
                ts_micros = int(_dt.timestamp() * 1_000_000)
            except Exception:
                pass

        # order_id 기반 결정론적 client_id (같은 주문 재시도해도 동일 id 유지)
        import hashlib
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
        resp = _requests.post(
            f"https://www.google-analytics.com/mp/collect?measurement_id={measurement_id}&api_secret={api_secret}",
            json=payload, timeout=10,
        )
        return resp.status_code in (200, 204)
    except Exception:
        return False


def update_cafe24_yesterday():
    """어제 Cafe24(자사몰+무신사+지그재그) 주문을 플랫폼 매출 시트에 추가. (bool, str) 반환."""
    try:
        import base64, json as _json
        from datetime import date, timedelta

        yesterday = date.today() - timedelta(days=1)
        date_str  = yesterday.strftime("%Y-%m-%d")

        # ── Cafe24 토큰 로드 & 갱신 ──────────────────────────────
        BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
        TOKEN_FILE = os.path.join(BASE_DIR, "cafe24_token.json")
        if not os.path.exists(TOKEN_FILE):
            return False, "❌ cafe24_token.json 없음"

        with open(TOKEN_FILE) as f:
            t = _json.load(f)

        # 토큰 만료 확인 및 갱신
        from datetime import datetime as _dt
        if t.get("expires_at"):
            try:
                exp = _dt.fromisoformat(t["expires_at"].replace(".000", ""))
                if _dt.now() >= exp - timedelta(minutes=10):
                    cred = base64.b64encode(f"{t['client_id']}:{t['client_secret']}".encode()).decode()
                    resp = _requests.post(
                        f"https://{t['shop_id']}.cafe24api.com/api/v2/oauth/token",
                        headers={"Authorization": f"Basic {cred}",
                                 "Content-Type": "application/x-www-form-urlencoded"},
                        data={"grant_type": "refresh_token", "refresh_token": t["refresh_token"]},
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        new = resp.json()
                        t["access_token"] = new["access_token"]
                        t["expires_at"]   = new.get("expires_at", "")
                        if new.get("refresh_token"):
                            t["refresh_token"] = new["refresh_token"]
                        with open(TOKEN_FILE, "w") as f2:
                            _json.dump(t, f2, indent=2)
            except Exception:
                pass

        # ── 주문 조회 ────────────────────────────────────────────
        # shopn = 스마트스토어 (옛 네이버 "샵N" 서비스 시절 코드명이 그대로 남아있음.
        # order_place_name 필드로 실제 확인됨: order_place_id="shopn" → "스마트스토어")
        MARKET_MAP = {"musinsa": "무신사", "zigzag": "지그재그", "shopn": "스마트스토어"}
        COMM_CAFE24 = 3
        COMM_DEFAULT = 30

        def _market_to_platform(market_id):
            mid = (market_id or "").lower().strip()
            if mid in MARKET_MAP:
                return MARKET_MAP[mid]
            if "naver" in mid or "smart" in mid:
                return "스마트스토어"
            return "Cafe24"

        headers = {
            "Authorization": f"Bearer {t['access_token']}",
            "X-Cafe24-Api-Version": "2026-03-01",
        }
        # 정확한 엔드포인트: /api/v2/admin/orders (admin 빠지면 404)
        resp = _requests.get(
            f"https://{t['shop_id']}.cafe24api.com/api/v2/admin/orders",
            headers=headers,
            params={"start_date": date_str, "end_date": date_str,
                    "limit": 100, "embed": "items"},
            timeout=15,
        )
        if resp.status_code != 200:
            return False, f"❌ Cafe24 API 오류: {resp.status_code}"

        orders = resp.json().get("orders", [])

        # ── 시트에 추가 ──────────────────────────────────────────
        creds = _get_sheet_creds()
        gc    = gspread.authorize(creds)
        ws    = gc.open_by_key(SPREADSHEET_ID).worksheet(PLATFORM_SHEET_NAME)

        existing_raw = ws.get_all_values()
        existing_keys = set()
        for row in existing_raw[1:]:
            if len(row) >= 6:
                existing_keys.add(f"{row[0]}|{row[1]}|{row[3]}|{row[4]}|{row[5]}")

        new_rows = []
        ga4_events = []  # (order_id, total_revenue, items) — 신규+정상 주문만 모아서 나중에 전송
        for order in orders:
            platform = _market_to_platform(order.get("market_id"))
            order_date = (order.get("order_date") or "")[:10]
            # Cafe24 API의 canceled 필드로 취소/반품 상태 판별
            # (order_place_name="스마트스토어" 주문 확인 시 canceled="T"인 건이 실제 존재함)
            status = "취소" if str(order.get("canceled", "")).upper() == "T" else "정상"
            order_id_c24 = order.get("order_id", "")
            items = order.get("items", [])
            order_total = 0
            order_ga4_items = []
            order_has_new = False
            for item in items:
                name    = str(item.get("product_name", "-"))
                code    = str(item.get("product_code", "-"))
                opt     = str(item.get("option_value", "") or "")
                import re as _re
                color = _re.search(r'색상=([^,)]+)', opt)
                size  = _re.search(r'사이즈=([^,)]+)', opt)
                color = color.group(1).strip() if color else "-"
                size  = size.group(1).strip()  if size  else "-"
                qty   = int(float(item.get("quantity", 1) or 1))
                price = int(float(item.get("product_price", 0) or 0))
                total = price * qty
                comm  = COMM_CAFE24 if platform == "Cafe24" else COMM_DEFAULT
                profit = round(total * (1 - comm / 100))
                key = f"{platform}|{order_date}|{code}|{color}|{size}"
                if key not in existing_keys:
                    new_rows.append([platform, order_date, name, code,
                                     color, size, qty, total, comm, profit, status])
                    existing_keys.add(key)
                    order_has_new = True
                order_total += total
                order_ga4_items.append({"item_id": code, "item_name": name, "quantity": qty, "price": price})

            # 신규(처음 동기화)이고 취소가 아닌 주문만 GA4로 구매 이벤트 전송
            # — 결제수단(네이버페이 등)과 무관하게 Cafe24 주문 데이터 기준으로 100% 추적
            if order_has_new and status != "취소" and order_total > 0:
                ga4_events.append((order_id_c24 or f"{platform}-{order_date}-{len(ga4_events)}",
                                    order_total, order_ga4_items, order.get("order_date", "")))

        if new_rows:
            # 날짜순 정렬 후 append
            all_data = [r for r in existing_raw[1:] if r] + new_rows
            all_data.sort(key=lambda r: r[1] if len(r) > 1 else "")
            ws.resize(rows=1)
            ws.append_rows([existing_raw[0]] + all_data, value_input_option="USER_ENTERED")

        # GA4에 구매 이벤트 서버사이드 전송 (네이버페이 등 외부결제도 100% 추적)
        ga4_sent = sum(1 for oid, val, its, ots in ga4_events
                       if _send_ga4_purchase_mp(oid, val, its, order_ts=ots) is True)

        return True, f"✅ Cafe24 {date_str} 완료 — {len(new_rows)}건 추가 (GA4 전송 {ga4_sent}/{len(ga4_events)})"

    except Exception as e:
        return False, f"❌ Cafe24 업데이트 실패: {e}"


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
        with st.spinner("🚀 데이터 업데이트 중... 잠시만 기다려주세요."):
            # Step 1: 빈 날짜 행 추가
            ok_gap, msg_gap = add_empty_rows_for_gaps()

            # Step 2: 비어있는 날짜 데이터 채우기
            ok_fill, msg_fill = fill_missing_dates()

            # Step 3: 어제 데이터 업데이트
            ok1, msg1 = update_ga4_yesterday()
            ok2, msg2 = update_meta_yesterday()
            # Step 4: 자사몰(Cafe24+무신사+지그재그+스마트스토어) 어제 주문 업데이트
            ok3, msg3 = update_cafe24_yesterday()

        # 결과 요약 — 성공/실패만 1회 표시
        errors = []
        if not ok_gap:  errors.append(msg_gap)
        if not ok_fill: errors.append(msg_fill)
        if not ok1:     errors.append(msg1)
        if not ok2:     errors.append(msg2)
        if not ok3:     errors.append(msg3)

        if errors:
            st.toast("\n".join(errors), icon="⚠️")
        else:
            st.toast("✅ 업데이트 완료!", icon="✅")

        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# ── 탭 분기 ──────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 방문자 · 광고 성과", "🏬 플랫폼별 매출", "📅 기간별 매출 조회",
    "📱 인스타그램 콘텐츠", "📖 플레이북", "📦 입고·재고",
])


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

    # ── 인사이트 박스 헬퍼 ────────────────────────────────────────
    def insight_box(lines, color=None):
        bc = color or COLOR["blue"]
        body = "".join(f'<div style="margin-bottom:5px;">{l}</div>' for l in lines)
        st.markdown(f"""
        <div style="background:#FAFAFA;border-left:4px solid {bc};padding:13px 18px;
                    border-radius:8px;font-size:13px;color:#1A1A1A;margin:8px 0 20px;
                    border:1px solid #EBEBEB;">
        {body}
        </div>""", unsafe_allow_html=True)

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

    # ── KPI 인사이트 ──────────────────────────────────────────────
    _kpi_lines = []
    if len(prior) > 0 and prior["방문자"].sum() > 0:
        _v  = round((recent["방문자"].sum() - prior["방문자"].sum()) / prior["방문자"].sum() * 100)
        _sp = round((recent["광고비"].sum()  - prior["광고비"].sum())  / prior["광고비"].sum()  * 100) if prior["광고비"].sum() > 0 else None
        _c  = int(recent["구매"].sum() - prior["구매"].sum())
        _vc = f"<b style='color:{'#27AE60' if _v>=0 else '#E74C3C'}'>{'▲' if _v>=0 else '▼'}{abs(_v)}%</b>"
        _sc = (f"<b style='color:{'#E74C3C' if _sp>=0 else '#27AE60'}'>{'▲' if _sp>=0 else '▼'}{abs(_sp)}%</b>") if _sp is not None else "—"
        _cc = f"<b style='color:{'#27AE60' if _c>=0 else '#E74C3C'}'>{'▲' if _c>=0 else '▼'}{abs(_c)}건</b>"
        _kpi_lines.append(f"📊 <b>지난 7일 vs 이전 7일</b> — 방문자 {_vc} · 광고비 {_sc} · 전환 {_cc}")
    _nr_msg = "신규 비중이 높아 재방문 리타게팅 여지 큼." if avg_new_rate >= 70 else "재방문 비중이 올라오고 있음 — 구매 결정 장벽(가격·배송비·리뷰) 점검 권장."
    _kpi_lines.append(f"👥 신규 <b>{avg_new_rate}%</b> / 재방문 <b>{100-avg_new_rate}%</b> — {_nr_msg}")
    if total_spend > 0:
        _rc = "#27AE60" if overall_roas >= 3 else ("#F39C12" if overall_roas >= 1.5 else "#E74C3C")
        _rm = ("목표 ROAS 달성 — 예산 증액 검토 가능." if overall_roas >= 3
               else "손익분기 근접 — 소재·타겟 최적화 후 증액 판단." if overall_roas >= 1.5
               else "ROAS 1.5 미달 — 현 세팅으로 증액 시 손실. 타겟·소재 전면 점검 필요.")
        _kpi_lines.append(f"💰 ROAS <b style='color:{_rc}'>{overall_roas}배</b> — {_rm}")
    insight_box(_kpi_lines, COLOR["blue"])

    st.markdown("<br>", unsafe_allow_html=True)

    # 차트 1: 일별 방문자 & 전환 추이
    chart_container("일별 방문자 · 전환 추이", "바이럴 스파이크, 광고 집행일, 전환 발생 패턴을 한눈에")

    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    # 중요: Plotly는 트레이스 추가 순서가 아니라 "축이 언제 등록됐는지"로 레이어를 쌓음.
    # make_subplots가 처음에 만든 y/y2는 기본 레이어, update_layout()으로 나중에
    # 추가하는 y3는 항상 그 위 레이어에 그려짐(트레이스 순서 무관).
    # → 광고비는 처음부터 등록된 y2(secondary_y=True)에 둬서 기본 레이어에 머물게 하고,
    #   전환수는 나중에 등록할 y3에 둬서 항상 위에 보이게 함
    fig1.add_trace(go.Bar(
        x=df["날짜"], y=df["광고비"],
        name="광고비",
        marker_color="rgba(232,255,77,0.7)",
        marker_line_color=COLOR["accent"],
        marker_line_width=1,
        hovertemplate="<b>%{x}</b><br>광고비: %{y:,}원<extra></extra>",
    ), secondary_y=True)
    fig1.add_trace(go.Scatter(
        x=df["날짜"], y=df["방문자"],
        name="방문자",
        fill="tozeroy",
        fillcolor="rgba(79,142,247,0.12)",
        line=dict(color=COLOR["blue"], width=2),
        hovertemplate="<b>%{x}</b><br>방문자: %{y:,}명<extra></extra>",
    ), secondary_y=False)
    # 전환 발생일: Meta 전환수 OR GA4 구매 중 하나라도 있으면 표시
    conv_df = df[(df["전환_메타"] > 0) | (df["구매"] > 0)].copy()
    conv_df["날짜_key"] = conv_df["날짜_dt"].dt.strftime("%Y-%m-%d")

    # ── 전환 발생일 소재 annotation ─────────────────────────────
    _daily_cr = load_meta_daily_creative("last_30d")
    # 날짜별 소재 그룹핑 (키: YYYY-MM-DD)
    _cr_by_date = {}
    if not _daily_cr.empty:
        for _d, _grp in _daily_cr.groupby("날짜"):
            _cr_by_date[_d] = _grp.sort_values("전환수", ascending=False)

    # 실제 구매 채널(GA4 세션 source/medium 기준) — Meta 귀속과 별개로
    # 인스타그램 오가닉 등에서 실제 발생한 구매를 명확히 구분하기 위함
    _pcd_by_date = {}
    if len(df) > 0:
        _ok_pcd, _df_pcd_all = load_purchase_channel_detail(
            df["날짜_dt"].min().strftime("%Y-%m-%d"), df["날짜_dt"].max().strftime("%Y-%m-%d")
        )
        if _ok_pcd and not _df_pcd_all.empty:
            for _d, _grp in _df_pcd_all.groupby("날짜"):
                _pcd_by_date[_d] = _grp.sort_values("구매건수", ascending=False)

    # 전환 발생일별 호버 텍스트 및 annotation 라벨 구성
    _hover_texts = []
    for _, _row in conv_df.iterrows():
        _date_key = str(_row["날짜_key"])  # YYYY-MM-DD
        _date_label = str(_row["날짜"])     # M/D — 실제 구매 채널 조회용 키
        _total_conv = int(_row["전환_메타"]) if _row["전환_메타"] > 0 else int(_row["구매"])

        # ① 유입 경로 (GA4 세션 전체 — 그날 방문자 기준)
        _ch_lines = []
        _ch_pairs = [
            ("메타 유료광고", _row.get("유입_메타", 0)),
            ("인스타그램 오가닉(개인/공식 구분불가)", _row.get("유입_인스타오가닉", 0)),
            ("공식 인스타 바이오", _row.get("유입_공식", 0)),
            ("개인 인스타 바이오", _row.get("유입_개인", 0)),
            ("직접 방문", _row.get("유입_직접", 0)),
        ]
        for _ch, _v in sorted(_ch_pairs, key=lambda x: -x[1]):
            if _v > 0:
                _ch_lines.append(f"  {_ch}: {int(_v)}명")

        # ② 실제 구매 채널 (GA4 트랜잭션 기준 — Meta 귀속과 무관하게 진짜 구매 발생 채널)
        _pcd_lines = []
        if _date_label in _pcd_by_date:
            for _, _pc in _pcd_by_date[_date_label].iterrows():
                _pcd_lines.append(f"  {_pc['유입채널']}: {int(_pc['구매건수'])}건 ({int(_pc['매출']):,}원)")

        # ③ 전환 소재 (Meta daily breakdown — Meta 유료광고가 직접 기여한 경우만)
        _cr_lines = []
        if _date_key in _cr_by_date:
            for _i, (_, _cr) in enumerate(_cr_by_date[_date_key].head(5).iterrows(), 1):
                _cr_lines.append(f"  {_i}위. {str(_cr['소재명'])[:30]} ({int(_cr['전환수'])}건)")

        # 호버 HTML 조립
        _ht = f"<b>📅 {_date_key} · 전환 {_total_conv}건</b>"
        if _ch_lines:
            _ht += "<br><br><b>유입 경로 (방문자 기준)</b><br>" + "<br>".join(_ch_lines)
        if _pcd_lines:
            _ht += "<br><br><b>✅ 실제 구매 채널 (GA4 트랜잭션)</b><br>" + "<br>".join(_pcd_lines)
        if _cr_lines:
            _ht += "<br><br><b>Meta 전환 소재</b><br>" + "<br>".join(_cr_lines)
        elif not _pcd_lines and not _cr_lines:
            _ht += "<br><br><i style='color:#999'>구매 채널 데이터 없음</i>"
        _hover_texts.append(_ht)

    # 전환수 막대 (보조축) — 전체 날짜 기준, 0건인 날도 포함해서 표시
    _hover_map = dict(zip(conv_df["날짜"], _hover_texts))
    _conv_vals_full = df.apply(
        lambda r: int(r["전환_메타"]) if r["전환_메타"] > 0 else int(r["구매"]), axis=1
    )
    _hover_texts_full = [
        _hover_map.get(label, f"<b>📅 {label}</b><br>전환 없음")
        for label in df["날짜"]
    ]
    # secondary_y 없이 yaxis="y3"로 직접 지정해서 나중에 등록되는 위쪽 레이어에 배치
    fig1.add_trace(go.Bar(
        x=df["날짜"], y=_conv_vals_full,
        name="전환수",
        marker_color=COLOR["green"],
        opacity=0.85,
        width=0.4,
        text=_hover_texts_full,
        hovertemplate="%{text}<extra></extra>",
        yaxis="y3",
    ))

    # annotation 라벨 (막대 위 텍스트, 보조축 기준)
    if not conv_df.empty:
        for _, _row in conv_df.iterrows():
            _date_key  = str(_row["날짜_key"])  # YYYY-MM-DD — Meta 조회용
            _date_label = str(_row["날짜"])      # M/D — 차트 x축 좌표용
            _conv_n_for_y = int(_row["전환_메타"]) if _row["전환_메타"] > 0 else int(_row["구매"])
            if _date_key in _cr_by_date:
                _top = _cr_by_date[_date_key].iloc[0]
                _n_others = len(_cr_by_date[_date_key]) - 1
                _label = f"Meta · {str(_top['소재명'])[:18]}{'…' if len(str(_top['소재명']))>18 else ''}"
                if _n_others > 0:
                    _label += f" 외 {_n_others}개"
                _label += f" ({int(_top['전환수'])}건)"
            else:
                _label = f"전환 {_conv_n_for_y}건"
            fig1.add_annotation(
                x=_date_label, y=_conv_n_for_y, yref="y3",  # 전환수 축(y3) 기준
                text=_label,
                showarrow=True,
                arrowhead=0, arrowwidth=1, arrowcolor="#27AE60",
                ax=0, ay=-30,
                font=dict(size=10, color="#1A6B35"),
                bgcolor="rgba(39,174,96,0.08)",
                bordercolor="#27AE60",
                borderwidth=1, borderpad=3,
                align="center",
            )

    # 방문자수 y축 범위 — 단순 min/max는 바이럴 스파이크 같은 극단값 하나에
    # 전체 스케일이 눌려버림(5/20 같은 평균 10배 급등일). 90th 퍼센타일 기준으로
    # 대다수 날짜의 변동을 잘 보이게 하고, 스파이크는 차트 위로 잘려 보이게 함
    _vis_min = float(df["방문자"].min())
    _vis_p90 = float(df["방문자"].quantile(0.90))
    _vis_pad = max((_vis_p90 - _vis_min) * 0.2, 1)
    _vis_range = [max(0, _vis_min - _vis_pad), _vis_p90 + _vis_pad]

    # 전환수 보조축 범위 — 작은 정수 단위로 깔끔하게
    _conv_max = int(_conv_vals_full.max()) if len(_conv_vals_full) else 0
    _conv_range = [0, max(_conv_max * 1.5, 2)]

    # 광고비 전용 축 범위 — 방문자/전환수와 분리된 독립 스케일 (숨김 축)
    _spend_max = float(df["광고비"].max()) if len(df) else 0
    _spend_range = [0, max(_spend_max * 1.3, 1)]

    fig1.update_layout(
        height=360, margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(type="category", showgrid=False, tickfont=dict(size=11)),
        yaxis=dict(showgrid=True, gridcolor="#F0F0F0", tickfont=dict(size=11),
                   title="방문자수", range=_vis_range),
        hovermode="x unified", barmode="overlay",
    )
    # 광고비: make_subplots가 처음부터 만든 y2(기본 레이어)에 배치 → 숨김
    fig1.update_layout(yaxis2=dict(
        overlaying="y", side="right", visible=False, showgrid=False,
        range=_spend_range,
    ))
    # 전환수: update_layout으로 나중에 등록하는 y3(항상 위쪽 레이어) → 표시
    fig1.update_layout(yaxis3=dict(
        overlaying="y", side="right", visible=True, showgrid=False,
        title="전환수", range=_conv_range,
        dtick=1 if _conv_max <= 6 else None,
        tickfont=dict(size=11), anchor="x",
    ))
    st.plotly_chart(fig1, use_container_width=True)

    # ── 방문자·전환 추이 인사이트 ─────────────────────────────────
    _t1_lines = []
    if len(df) > 1:
        _max_day = df.loc[df["방문자"].idxmax()]
        _avg_vis = df["방문자"].mean()
        if _max_day["방문자"] > _avg_vis * 2:
            _ch_map = {"메타 유료광고": _max_day["유입_메타"], "인스타그램 오가닉": _max_day.get("유입_인스타오가닉", 0),
                       "공식인스타 바이오": _max_day["유입_공식"], "개인인스타 바이오": _max_day["유입_개인"],
                       "직접방문": _max_day["유입_직접"]}
            _top_ch = max(_ch_map, key=_ch_map.get)
            _t1_lines.append(f"📈 <b>{_max_day['날짜']} 트래픽 스파이크</b> — 평균 대비 {round(_max_day['방문자']/_avg_vis,1)}배 급등, 주요 유입: {_top_ch}.")
    if total_purchases == 0 and total_spend > 0:
        _avg_b = df["이탈율"].replace(0, float("nan")).mean()
        if _avg_b and _avg_b >= 60:
            _t1_lines.append(f"⚠️ <b>전환 0건</b> — 광고비 {total_spend:,}원 집행했으나 이탈율 평균 {_avg_b:.0f}%로 높음. <b>액션플랜:</b> 소재 이미지와 상품페이지 메시지 일관성 점검, 랜딩 상품 직링크로 교체.")
        else:
            _t1_lines.append(f"⚠️ <b>전환 0건</b> — 클릭은 유입되나 결제 미전환. <b>액션플랜:</b> 결제 페이지 내 배송비 노출 시점·리뷰 수·CTA 버튼 위치 점검 필요.")
    elif total_purchases > 0:
        _conv_rate_ok = overall_cvr >= 1.0
        _cr_color = "#27AE60" if _conv_rate_ok else "#F39C12"
        _t1_lines.append(f"🛍 전환율 <b style='color:{_cr_color}'>{overall_cvr}%</b> — {'양호. 트래픽 증가 시 전환 비례 상승 기대.' if _conv_rate_ok else '전환율 1% 미달. 방문자 대비 구매가 적음 — 상품 상세 페이지 설득력 강화 필요.'}")
    if total_spend > 0 and len(ad_days) > 0:
        _spend_trend = "증가" if ad_days["광고비"].iloc[-1] > ad_days["광고비"].mean() else "감소"
        _t1_lines.append(f"💸 최근 광고비 {_spend_trend} 추세 — {'전환율 개선 없이 증액은 CPO 악화로 이어짐. 소재 교체 후 증액 순서 권장.' if _spend_trend == '증가' and total_purchases == 0 else '광고비와 전환이 함께 움직이는지 추이를 지속 모니터링.'}")
    if _t1_lines:
        insight_box(_t1_lines, COLOR["orange"])

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 소재 피로도 알림 배너 ────────────────────────────────────────
    # '광고 소재별 성과' 섹션의 기간 선택(아래쪽)과 동일한 값으로 동기화
    _fatigue_preset_map = {"최근 7일": "last_7d", "최근 14일": "last_14d", "최근 30일": "last_30d"}
    _fatigue_period_label = st.session_state.get("creative_preset", "최근 7일")
    _fatigued_ads = load_meta_creative_fatigue(_fatigue_preset_map.get(_fatigue_period_label, "last_14d"))
    if _fatigued_ads:
        _critical_ads = [a for a in _fatigued_ads if a["level"] == "critical"]
        _warning_ads  = [a for a in _fatigued_ads if a["level"] == "warning"]

        if _critical_ads:
            _rows_html = "".join([
                f"<div style='margin-top:6px;'>"
                f"<span style='background:#E74C3C;color:white;font-size:11px;font-weight:700;"
                f"padding:2px 7px;border-radius:3px;margin-right:8px;'>교체 필요</span>"
                f"<span style='font-size:13px;font-weight:600;color:#1A1A1A;'>{a['소재명'][:40]}</span>"
                f"<span style='font-size:12px;color:#888;margin-left:8px;'>{a['reason']} · {a['집행일수']}일 집행</span>"
                f"</div>"
                for a in _critical_ads
            ])
            st.markdown(f"""
            <div style='background:#FFF0F0;border-left:4px solid #E74C3C;border-radius:6px;
                        padding:14px 18px;margin-bottom:12px;'>
                <div style='display:flex;justify-content:space-between;align-items:flex-start;'>
                    <div>
                        <span style='font-size:15px;font-weight:700;color:#C0392B;'>🚨 소재 교체 필요</span>
                        <span style='font-size:12px;color:#888;margin-left:10px;'>아래 소재의 CTR이 급락했어요 ({_fatigue_period_label} 기준). 즉시 교체를 권장합니다.</span>
                    </div>
                    <a href='https://business.facebook.com/adsmanager' target='_blank'
                       style='background:#E74C3C;color:white;padding:7px 14px;border-radius:5px;
                              font-size:12px;font-weight:600;text-decoration:none;white-space:nowrap;flex-shrink:0;margin-left:16px;'>
                       🔄 광고 관리자 열기
                    </a>
                </div>
                {_rows_html}
            </div>""", unsafe_allow_html=True)

        if _warning_ads:
            _rows_html = "".join([
                f"<div style='margin-top:6px;'>"
                f"<span style='background:#F39C12;color:white;font-size:11px;font-weight:700;"
                f"padding:2px 7px;border-radius:3px;margin-right:8px;'>주의</span>"
                f"<span style='font-size:13px;font-weight:600;color:#1A1A1A;'>{a['소재명'][:40]}</span>"
                f"<span style='font-size:12px;color:#888;margin-left:8px;'>{a['reason']} · {a['집행일수']}일 집행</span>"
                f"</div>"
                for a in _warning_ads
            ])
            st.markdown(f"""
            <div style='background:#FFFBF0;border-left:4px solid #F39C12;border-radius:6px;
                        padding:14px 18px;margin-bottom:12px;'>
                <div style='display:flex;justify-content:space-between;align-items:flex-start;'>
                    <div>
                        <span style='font-size:15px;font-weight:700;color:#D35400;'>⚠️ 소재 피로도 감지</span>
                        <span style='font-size:12px;color:#888;margin-left:10px;'>{_fatigue_period_label} 기준 · 3~5일 내 소재 교체를 준비하세요.</span>
                    </div>
                    <a href='https://business.facebook.com/adsmanager' target='_blank'
                       style='background:#F39C12;color:white;padding:7px 14px;border-radius:5px;
                              font-size:12px;font-weight:600;text-decoration:none;white-space:nowrap;flex-shrink:0;margin-left:16px;'>
                       🔄 광고 관리자 열기
                    </a>
                </div>
                {_rows_html}
            </div>""", unsafe_allow_html=True)

    # 차트 2+3: 광고 효율 & 채널 유입
    col_left, col_right = st.columns([3, 2])

    with col_left:
        chart_container("광고 효율 추이", "광고비·CTR 항상 표시 / CPO·ROAS는 전환 발생 시")
        ad_df = df[df["광고비"] > 0].copy()
        if not ad_df.empty:
            fig2 = make_subplots(specs=[[{"secondary_y": True}]])
            # 광고비 막대 (항상 표시)
            fig2.add_trace(go.Bar(
                x=ad_df["날짜"], y=ad_df["광고비"],
                name="광고비 (원)",
                marker_color=COLOR["blue"],
                opacity=0.5,
                hovertemplate="<b>%{x}</b><br>광고비: %{y:,}원<extra></extra>",
            ), secondary_y=False)
            # CTR 라인 (항상 표시)
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
            # CPO 라인 (전환 있을 때만)
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
            # ROAS 라인 — 전환 없는 날은 None으로 처리해서 선 연결 유지
            if not ad_df.empty:
                roas_y = ad_df["ROAS"].apply(lambda v: v if v > 0 else None)
                fig2.add_trace(go.Scatter(
                    x=ad_df["날짜"], y=roas_y,
                    name="ROAS (배)",
                    mode="lines+markers",
                    connectgaps=True,
                    line=dict(color=COLOR["green"], width=2.5),
                    marker=dict(size=7, color=COLOR["green"]),
                    hovertemplate="<b>%{x}</b><br>ROAS: %{y:.1f}배<extra></extra>",
                ), secondary_y=True)
            fig2.update_layout(
                height=300, margin=dict(l=0, r=0, t=10, b=0),
                plot_bgcolor="white", paper_bgcolor="white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                xaxis=dict(type="category", showgrid=False, tickfont=dict(size=11)),
                yaxis=dict(showgrid=True, gridcolor="#F0F0F0", tickfont=dict(size=11), tickformat=","),
                yaxis2=dict(showgrid=False, tickfont=dict(size=11)),
                hovermode="x unified",
            )
            st.plotly_chart(fig2, use_container_width=True)
            # ── 광고 효율 인사이트 ────────────────────────────────
            _ae_lines = []
            _ctr_vals = ad_df[ad_df["CTR"] > 0]["CTR"]
            if len(_ctr_vals) >= 3:
                _ctr_avg   = _ctr_vals.mean()
                _ctr_last  = _ctr_vals.iloc[-1]
                _ctr_color = "#27AE60" if _ctr_last >= _ctr_avg else "#E74C3C"
                _ctr_msg   = ("현재 소재 반응 양호. 예산 증액 고려 가능." if _ctr_last >= _ctr_avg * 1.1
                              else "CTR이 평균 대비 하락 — 소재 피로 신호. 이미지·문구 교체 시점." if _ctr_last < _ctr_avg * 0.8
                              else "CTR 안정적 유지 중.")
                _ae_lines.append(f"📣 CTR <b style='color:{_ctr_color}'>{_ctr_last:.2f}%</b> (평균 {_ctr_avg:.2f}%) — {_ctr_msg}")
            _roas_vals = ad_df[ad_df["ROAS"] > 0]["ROAS"]
            if not _roas_vals.empty:
                _roas_last  = _roas_vals.iloc[-1]
                _roas_color = "#27AE60" if _roas_last >= 3 else ("#F39C12" if _roas_last >= 1.5 else "#E74C3C")
                _ae_lines.append(f"💰 최근 ROAS <b style='color:{_roas_color}'>{_roas_last:.1f}배</b> — {'수익 구간. 소재·타겟 유지하며 예산 확대.' if _roas_last >= 3 else '손익분기 근처. 전환 소재 추가 테스트 권장.' if _roas_last >= 1.5 else 'ROAS 손실 구간. 현 캠페인 일시 중단 후 소재·타겟 재설정 필요.'}")
            _cpo_vals = ad_df[ad_df["CPO"] > 0]["CPO"]
            if len(_cpo_vals) >= 2:
                _cpo_trend = "개선" if _cpo_vals.iloc[-1] < _cpo_vals.mean() else "악화"
                _ae_lines.append(f"🎯 CPO 추이 <b>{'↓ ' if _cpo_trend=='개선' else '↑ '}{int(_cpo_vals.iloc[-1]):,}원</b> (평균 {int(_cpo_vals.mean()):,}원) — {'전환 효율 개선 중. 지금 타겟·소재 조합 유지 권장.' if _cpo_trend=='개선' else 'CPO 상승 중 — 타겟 오디언스 포화 또는 소재 피로. 유사 타겟 전환 또는 소재 A/B 테스트 시작.'}")
            elif total_spend > 0 and total_purchases == 0:
                _ae_lines.append(f"⚠️ 전환 미발생 — 광고비 집행 중이나 CPO·ROAS 산출 불가. <b>조치:</b> 픽셀 이벤트 정상 수신 여부 확인 후, 전환 캠페인 대신 트래픽 캠페인으로 모수 확보 후 리타게팅 전환 집행 고려.")
            if _ae_lines:
                insight_box(_ae_lines, COLOR["green"])
        else:
            st.info("광고 집행 데이터 없음")

    with col_right:
        chart_container("채널별 누적 유입", "어디서 온 사람들이 가장 많은지")
        ch_totals = {
            "메타 유료광고":     int(df["유입_메타"].sum()),
            "인스타그램 오가닉": int(df.get("유입_인스타오가닉", pd.Series([0])).sum()),
            "공식인스타 바이오": int(df["유입_공식"].sum()),
            "개인인스타 바이오": int(df["유입_개인"].sum()),
            "직접방문":          int(df["유입_직접"].sum()),
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
            xaxis=dict(type="category", showgrid=False, tickfont=dict(size=11)),
            yaxis=dict(showgrid=True, gridcolor="#F0F0F0", tickfont=dict(size=11), title="방문자수"),
            yaxis2=dict(showgrid=False, tickfont=dict(size=11), title="누적 모수"),
            hovermode="x unified",
        )
        st.plotly_chart(fig4, use_container_width=True)

        _pixel_total = int(nvr_df["신규"].sum())
        _latest_ret  = nvr_df["재방문"].iloc[-3:].mean()
        _early_ret   = nvr_df["재방문"].iloc[:max(1, len(nvr_df)-7)].mean()
        _ret_up      = _latest_ret > _early_ret * 1.2
        _nr4_lines   = []
        _nr4_lines.append(f"🎯 <b>누적 픽셀 모수 {_pixel_total:,}명</b> — 리타게팅 캠페인이 이 모수 전체를 커버하도록 설정됐는지 확인. 신규 방문 후 3~7일 내 리타게팅 시 전환율 cold 대비 3~5배 높음.")
        if _ret_up:
            _nr4_lines.append(f"📈 재방문자 최근 증가 추세 — 브랜드 인지도 누적 중. <b>액션플랜:</b> 재방문자 전용 '첫 구매 혜택' 리타게팅 광고 집행 타이밍.")
        else:
            _nr4_lines.append(f"📉 재방문 비율 정체 — 신규 방문자가 재방문으로 이어지지 않는 상황. <b>액션플랜:</b> 카카오 알림톡 또는 인스타 DM 팔로업, '장바구니 담기' 리마인드 광고 설정.")
        if total_purchases == 0 and _pixel_total >= 100:
            _nr4_lines.append(f"💡 전환 미발생이지만 모수 {_pixel_total:,}명 확보됨 — 지금이 '재고 한정·마감 임박' 메시지로 리타게팅 집행할 최적 타이밍.")
        insight_box(_nr4_lines, COLOR["purple"])

    st.markdown("<br>", unsafe_allow_html=True)

    # 차트 5: 채널 유입 스택 바 (접기)
    with st.expander("📊 일별 채널 유입 상세 보기"):
        chart_container("일별 채널별 유입 구성", "어떤 날 어떤 채널이 트래픽을 이끌었는지")
        _ig_org_col = df.get("유입_인스타오가닉", pd.Series([0]*len(df)))
        ch_df = df[(df["유입_메타"] + _ig_org_col + df["유입_공식"] + df["유입_개인"] + df["유입_직접"]) > 0]
        if not ch_df.empty:
            fig5 = go.Figure()
            for ch, col_key, color in [
                ("메타 유료광고",     "유입_메타",         "#1877F2"),
                ("인스타그램 오가닉", "유입_인스타오가닉", "#C13584"),
                ("공식인스타 바이오", "유입_공식",         "#E1306C"),
                ("개인인스타 바이오", "유입_개인",         "#F56040"),
                ("직접방문",          "유입_직접",         "#1A1A1A"),
            ]:
                fig5.add_trace(go.Bar(x=ch_df["날짜"], y=ch_df[col_key],
                    name=ch, marker_color=color,
                    hovertemplate=f"<b>%{{x}}</b><br>{ch}: %{{y}}명<extra></extra>"))
            fig5.update_layout(
                height=260, barmode="stack",
                margin=dict(l=0, r=0, t=10, b=0),
                plot_bgcolor="white", paper_bgcolor="white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                xaxis=dict(type="category", showgrid=False, tickfont=dict(size=11)),
                yaxis=dict(showgrid=True, gridcolor="#F0F0F0", tickfont=dict(size=11)),
                hovermode="x unified",
            )
            st.plotly_chart(fig5, use_container_width=True)

    # 구매 전환 채널 상세 — "이 구매가 어디서 왔는지" 날짜+채널 단위로 추적
    with st.expander("🛍️ 구매 전환 채널 상세 — 어떤 구매가 어디서 발생했는지"):
        chart_container("구매 발생 채널 트래킹", "GA4 세션 source/medium 기준, 날짜별 실제 구매 내역")
        if len(df) > 0:
            _pcd_start = df["날짜_dt"].min().strftime("%Y-%m-%d")
            _pcd_end   = df["날짜_dt"].max().strftime("%Y-%m-%d")
            _ok_pcd, _df_pcd = load_purchase_channel_detail(_pcd_start, _pcd_end)
            if _ok_pcd and not _df_pcd.empty:
                st.dataframe(
                    _df_pcd.rename(columns={"매출": "매출(원)"}),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "매출(원)": st.column_config.NumberColumn(format="%,d"),
                    },
                )
                _ch_summary = _df_pcd.groupby("유입채널").agg(
                    구매건수=("구매건수", "sum"), 매출=("매출", "sum")
                ).reset_index().sort_values("구매건수", ascending=False)
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("**채널별 구매 합계**")
                st.dataframe(
                    _ch_summary.rename(columns={"매출": "매출(원)"}),
                    use_container_width=True, hide_index=True,
                    column_config={"매출(원)": st.column_config.NumberColumn(format="%,d")},
                )
            else:
                st.info("이 기간 구매 데이터가 없어요.")

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
                _top_ch_map = {"메타 유료광고": max_day["유입_메타"], "인스타그램 오가닉": max_day.get("유입_인스타오가닉", 0),
                               "공식인스타 바이오": max_day["유입_공식"], "개인인스타 바이오": max_day["유입_개인"],
                               "직접방문": max_day["유입_직접"]}
                top_ch = max(_top_ch_map, key=_top_ch_map.get)
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
            "메타 유료광고":     int(df["유입_메타"].sum()),
            "인스타그램 오가닉": int(df.get("유입_인스타오가닉", pd.Series([0])).sum()),
            "공식인스타 바이오": int(df["유입_공식"].sum()),
            "개인인스타 바이오": int(df["유입_개인"].sum()),
            "직접방문":          int(df["유입_직접"].sum()),
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

    # (기간 종합 인사이트는 각 차트 아래로 이동됨)

    # ════════════════════════════════════════════════════════════
    # 광고 소재별 성과 섹션
    # ════════════════════════════════════════════════════════════
    st.markdown("---")
    chart_container("📱 광고 소재별 성과", "Meta 광고 소재(Ad) 단위 전환·CPO·ROAS·CTR")

    _col_pr, _ = st.columns([2, 5])
    with _col_pr:
        _creative_preset = st.selectbox(
            "기간", ["최근 7일", "최근 14일", "최근 30일"],
            key="creative_preset", label_visibility="collapsed"
        )
    _preset_map = {"최근 7일": "last_7d", "최근 14일": "last_14d", "최근 30일": "last_30d"}

    with st.spinner("소재 데이터 불러오는 중..."):
        df_ads = load_meta_ad_insights(_preset_map[_creative_preset])

    if df_ads.empty:
        st.info("Meta 광고 소재 데이터를 불러올 수 없어요. Meta 토큰을 확인해 주세요.")
    else:
        # ── 요약 KPI ────────────────────────────────────────────
        _total_spend = int(df_ads["광고비"].sum())
        _total_conv  = int(df_ads["전환수"].sum())
        _total_rev   = int(df_ads["매출"].sum())
        _avg_cpo     = round(_total_spend / _total_conv) if _total_conv > 0 else 0
        _avg_roas    = round(_total_rev / _total_spend, 1) if _total_spend > 0 else 0
        _active_ads  = len(df_ads[df_ads["광고비"] > 0])

        _kc1, _kc2, _kc3, _kc4, _kc5 = st.columns(5)
        with _kc1: kpi_card("집행 소재 수", f"{_active_ads}개")
        with _kc2: kpi_card("총 광고비", fmt_num(_total_spend, "원"))
        with _kc3: kpi_card("총 전환수", f"{_total_conv}건")
        with _kc4: kpi_card("평균 CPO", f"{_avg_cpo:,}원" if _avg_cpo else "—")
        with _kc5: kpi_card("전체 ROAS", f"{_avg_roas}배", "목표 3배 이상", _avg_roas >= 3)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── 전환수 TOP 차트 ──────────────────────────────────────
        _top_chart = df_ads[df_ads["전환수"] > 0].head(10).copy()
        _top_chart["소재명_short"] = _top_chart["소재명"].apply(lambda x: x[:25] + "…" if len(str(x)) > 25 else str(x))

        if not _top_chart.empty:
            chart_container("전환 발생 소재 TOP 10", "전환수 기준 상위 소재")
            _top_sorted = _top_chart.sort_values("전환수")
            _fig_cr = go.Figure(go.Bar(
                x=_top_sorted["전환수"],
                y=_top_sorted["소재명_short"],
                orientation="h",
                marker_color=COLOR["green"],
                text=_top_sorted["전환수"].astype(str) + "건",
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>전환: %{x}건<extra></extra>",
            ))
            _fig_cr.update_layout(
                height=max(220, len(_top_chart) * 34),
                margin=dict(l=0, r=60, t=10, b=0),
                plot_bgcolor="white", paper_bgcolor="white",
                xaxis=dict(showgrid=True, gridcolor="#F0F0F0"),
                yaxis=dict(showgrid=False, tickfont=dict(size=11)),
            )
            st.plotly_chart(_fig_cr, use_container_width=True)

        # ── 전체 소재 상세 지표 테이블 (썸네일 인라인) ─────────────
        st.markdown("<br>", unsafe_allow_html=True)
        chart_container("전체 소재 상세 지표", "라이브 중인 모든 소재 — 캠페인 > 광고세트 > 소재명")

        _thumb_map = dict(zip(df_ads["ad_id"], df_ads["thumbnail"]))

        _th = lambda t: f"<th style='padding:8px 10px;background:#F7F7F7;font-size:12px;font-weight:600;color:#555;border-bottom:2px solid #E8E8E8;white-space:nowrap;text-align:left;'>{t}</th>"
        _td = lambda v, align="right": f"<td style='padding:7px 10px;font-size:12px;color:#1A1A1A;border-bottom:1px solid #F0F0F0;text-align:{align};white-space:nowrap;'>{v}</td>"

        _rows_html = ""
        for _, _r in df_ads.iterrows():
            _thumb_html = (
                f"<img src='{_r['thumbnail']}' style='width:44px;height:44px;object-fit:cover;border-radius:5px;display:block;' onerror=\"this.replaceWith(document.createTextNode('—'))\">"
                if _r["thumbnail"] else "<span style='color:#CCC;font-size:11px;'>—</span>"
            )
            _conv_c = "#27AE60" if _r["전환수"] > 0 else "#999"
            _full   = str(_r["전체경로"])
            _rows_html += f"""<tr>
                <td style='padding:6px 10px;border-bottom:1px solid #F0F0F0;'>{_thumb_html}</td>
                <td style='padding:7px 10px;font-size:11px;color:#333;border-bottom:1px solid #F0F0F0;max-width:300px;line-height:1.4;'>{_full}</td>
                {_td(f"{int(_r['광고비']):,}원")}
                {_td(f"{int(_r['노출수']):,}")}
                {_td(f"{int(_r['클릭수']):,}")}
                {_td(f"{_r['CTR']:.2f}%")}
                <td style='padding:7px 10px;font-size:12px;font-weight:700;color:{_conv_c};border-bottom:1px solid #F0F0F0;text-align:right;'>{int(_r['전환수'])}건</td>
                {_td(f"{int(_r['CPO']):,}원" if _r['CPO'] > 0 else "—")}
                {_td(f"{_r['ROAS']}배" if _r['ROAS'] > 0 else "—")}
                {_td(f"{int(_r['매출']):,}원")}
            </tr>"""

        _table_html = f"""
        <div style='overflow-x:auto;'>
        <table style='width:100%;border-collapse:collapse;'>
            <thead><tr>
                {_th('썸네일')}{_th('캠페인 > 광고세트 > 소재명')}
                {_th('광고비')}{_th('노출')}{_th('클릭')}{_th('CTR')}
                {_th('전환')}{_th('CPO')}{_th('ROAS')}{_th('매출')}
            </tr></thead>
            <tbody>{_rows_html}</tbody>
        </table>
        </div>"""
        st.markdown(_table_html, unsafe_allow_html=True)

        # ── 소재 인사이트 ────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        if not df_ads.empty and _total_conv > 0:
            _best = df_ads[df_ads["전환수"] == df_ads["전환수"].max()].iloc[0]
            _best_name = str(_best["소재명"])[:35]
            _worst_spend = df_ads[(df_ads["광고비"] > 0) & (df_ads["전환수"] == 0)]
            _insight_lines = [
                f"🏆 <b>전환 1위 소재</b>: {_best_name} — 전환 {int(_best['전환수'])}건 · CPO {int(_best['CPO']):,}원 · ROAS {_best['ROAS']}배. "
                f"{'예산 증액 및 유사 타겟 확장(Lookalike) 적용 권장.' if _best['ROAS'] >= 3 else '전환은 발생하나 ROAS 3배 미달 — 랜딩 페이지 최적화 후 증액 검토.'}",
            ]
            if not _worst_spend.empty:
                _waste = int(_worst_spend["광고비"].sum())
                _insight_lines.append(
                    f"⚠️ <b>전환 0건 소재 {len(_worst_spend)}개</b> — 합산 광고비 {_waste:,}원 소진 중. "
                    f"소재 교체 또는 일시 중단 검토. 이 예산을 전환 1위 소재에 재배분하면 CPO 개선 가능."
                )
            _high_ctr_no_conv = df_ads[(df_ads["CTR"] >= 1.5) & (df_ads["전환수"] == 0)]
            if not _high_ctr_no_conv.empty:
                _insight_lines.append(
                    f"💡 <b>CTR 높으나 전환 0건 소재 {len(_high_ctr_no_conv)}개</b> — 클릭 유입은 있으나 랜딩 후 이탈. "
                    f"소재·랜딩 메시지 불일치 가능성. 랜딩 URL 및 상품 페이지 구성 점검 필요."
                )
            for line in _insight_lines:
                st.markdown(f"<div style='font-size:13px;line-height:1.8;padding:4px 0'>{line}</div>",
                            unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════
    # 상품 페이지별 전환율 섹션
    # ════════════════════════════════════════════════════════════
    st.markdown("---")
    chart_container("🛍️ 상품 페이지별 유입 vs 전환율", "어느 상품에서 이탈이 많은지 — GA4 페이지 경로 기준")

    @st.cache_data(ttl=3600)
    def load_product_page_stats(days: int = 14):
        if not _GA4_AVAILABLE:
            return None, "GA4 패키지 없음"
        try:
            from datetime import date, timedelta
            GA4_PROPERTY_ID = "536368183"
            creds = _get_oauth_creds()
            ga4   = BetaAnalyticsDataClient(credentials=creds)
            end   = date.today() - timedelta(days=1)
            start = end - timedelta(days=days - 1)
            res = ga4.run_report(RunReportRequest(
                property=f"properties/{GA4_PROPERTY_ID}",
                dimensions=[Dimension(name="pagePath")],
                metrics=[
                    Metric(name="screenPageViews"),
                    Metric(name="bounceRate"),
                    Metric(name="conversions"),
                    Metric(name="averageSessionDuration"),
                ],
                date_ranges=[DateRange(
                    start_date=start.strftime("%Y-%m-%d"),
                    end_date=end.strftime("%Y-%m-%d"),
                )],
                order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"), desc=True)],
                limit=50,
            ))
            rows = []
            for row in res.rows:
                path = row.dimension_values[0].value
                if not any(kw in path for kw in ["/product/", "/goods/", "/item/"]):
                    continue
                views   = int(row.metric_values[0].value)
                bounce  = round(float(row.metric_values[1].value) * 100, 1)
                conv    = int(float(row.metric_values[2].value))
                dur     = int(float(row.metric_values[3].value))
                cvr     = round(conv / views * 100, 2) if views > 0 else 0
                # 경로에서 상품명 추출 (Cafe24: /product/상품명/코드/)
                parts = [p for p in path.split("/") if p]
                name  = parts[1] if len(parts) >= 2 else path
                name  = name.replace("-", " ").replace("%20", " ")[:40]
                rows.append({
                    "상품명": name,
                    "경로": path,
                    "조회수": views,
                    "이탈률(%)": bounce,
                    "전환수": conv,
                    "전환율(%)": cvr,
                    "평균체류(초)": dur,
                })
            import pandas as _pd
            return _pd.DataFrame(rows), None
        except Exception as e:
            return None, str(e)

    _pp_col1, _pp_col2 = st.columns([1, 5])
    with _pp_col1:
        _pp_days = st.selectbox("기간", [7, 14, 30], format_func=lambda x: f"최근 {x}일",
                                key="pp_days_sel", label_visibility="collapsed")

    df_pp, _pp_err = load_product_page_stats(_pp_days)

    if _pp_err:
        st.warning(f"데이터 로드 실패: {_pp_err}")
    elif df_pp is None or df_pp.empty:
        st.info("상품 페이지 방문 데이터가 없어요. GA4에 `/product/` 경로 데이터가 쌓이면 자동으로 표시됩니다.")
    else:
        # 차트: 조회수 vs 전환율 산점도
        import plotly.express as _px
        _fig_pp = _px.scatter(
            df_pp,
            x="조회수", y="전환율(%)",
            size="조회수", color="이탈률(%)",
            hover_name="상품명",
            hover_data={"전환수": True, "평균체류(초)": True, "경로": False},
            color_continuous_scale=[[0, "#27AE60"], [0.5, "#F39C12"], [1, "#E74C3C"]],
            labels={"조회수": "페이지 조회수", "전환율(%)": "전환율 (%)"},
            height=380,
        )
        _fig_pp.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=10, r=10, t=20, b=10),
            coloraxis_colorbar=dict(title="이탈률%", thickness=12),
            font=dict(family="Pretendard, sans-serif", size=12),
        )
        _fig_pp.add_hline(y=df_pp["전환율(%)"].mean(), line_dash="dot",
                          line_color="#8C8C8C", annotation_text="평균 전환율")
        st.plotly_chart(_fig_pp, use_container_width=True)

        # 테이블
        _df_pp_disp = df_pp[["상품명","조회수","이탈률(%)","전환수","전환율(%)","평균체류(초)"]].copy()
        _df_pp_disp = _df_pp_disp.sort_values("조회수", ascending=False).reset_index(drop=True)

        def _color_bounce(val):
            if val >= 70: return "color:#E74C3C;font-weight:700"
            if val >= 50: return "color:#F39C12;font-weight:600"
            return "color:#27AE60"

        def _color_cvr(val):
            if val >= 3: return "color:#27AE60;font-weight:700"
            if val >= 1: return "color:#F39C12"
            return "color:#E74C3C;font-weight:700"

        rows_html = ""
        for _, r in _df_pp_disp.iterrows():
            _bc = _color_bounce(r["이탈률(%)"])
            _cc = _color_cvr(r["전환율(%)"])
            rows_html += (
                f"<tr>"
                f"<td style='padding:7px 10px;font-size:12px;max-width:220px;overflow:hidden;'>{r['상품명']}</td>"
                f"<td style='padding:7px 10px;text-align:right;'>{r['조회수']:,}</td>"
                f"<td style='padding:7px 10px;text-align:right;{_bc}'>{r['이탈률(%)']:.1f}%</td>"
                f"<td style='padding:7px 10px;text-align:right;'>{int(r['전환수'])}</td>"
                f"<td style='padding:7px 10px;text-align:right;{_cc}'>{r['전환율(%)']:.2f}%</td>"
                f"<td style='padding:7px 10px;text-align:right;color:#8C8C8C;'>{int(r['평균체류(초)'])}초</td>"
                f"</tr>"
            )
        st.markdown(f"""
<table style='width:100%;border-collapse:collapse;font-size:13px;'>
<thead><tr style='background:#F7F7F7;border-bottom:2px solid #E8E8E8;'>
<th style='padding:8px 10px;text-align:left;'>상품명</th>
<th style='padding:8px 10px;text-align:right;'>조회수</th>
<th style='padding:8px 10px;text-align:right;'>이탈률</th>
<th style='padding:8px 10px;text-align:right;'>전환수</th>
<th style='padding:8px 10px;text-align:right;'>전환율</th>
<th style='padding:8px 10px;text-align:right;'>평균체류</th>
</tr></thead>
<tbody>{rows_html}</tbody>
</table>""", unsafe_allow_html=True)

        # 인사이트
        _high_bounce = df_pp[df_pp["이탈률(%)"] >= 70].sort_values("조회수", ascending=False)
        _low_cvr     = df_pp[(df_pp["전환율(%)"] < 1) & (df_pp["조회수"] >= 30)].sort_values("조회수", ascending=False)
        _pp_lines = []
        if not _high_bounce.empty:
            top = _high_bounce.iloc[0]
            _pp_lines.append(
                f"⚠️ <b>이탈률 70% 이상 상품 {len(_high_bounce)}개</b> — "
                f"'{top['상품명']}' 조회수 {top['조회수']:,}회·이탈률 {top['이탈률(%)']:.0f}%. "
                f"착용샷·리뷰·가격 설득력 점검 필요."
            )
        if not _low_cvr.empty:
            top2 = _low_cvr.iloc[0]
            _pp_lines.append(
                f"💡 <b>조회수 있으나 전환율 1% 미만 상품 {len(_low_cvr)}개</b> — "
                f"'{top2['상품명']}' {top2['조회수']:,}회 방문 중 전환 {int(top2['전환수'])}건. "
                f"상세페이지 개선 우선순위 상품."
            )
        best = df_pp.sort_values("전환율(%)", ascending=False).iloc[0]
        if best["전환율(%)"] > 0:
            _pp_lines.append(
                f"✅ <b>전환율 1위</b>: '{best['상품명']}' — {best['전환율(%)']:.2f}% "
                f"(조회 {best['조회수']:,}회·전환 {int(best['전환수'])}건). 이 상품 광고 소재 우선 활용."
            )
        if _pp_lines:
            st.markdown("<br>", unsafe_allow_html=True)
            insight_box(_pp_lines, COLOR.get("orange", "#F39C12"))


# ════════════════════════════════════════════════════════════════
# TAB 2: 플랫폼별 매출 대시보드
# ════════════════════════════════════════════════════════════════
with tab2:

    if df_platform_all.empty:
        st.info("🏬 플랫폼 매출 데이터가 없어요. platform_to_sheets.py로 데이터를 먼저 업로드해 주세요.")
        st.stop()

    # ── 기간 필터 ─────────────────────────────────────────────────
    # 월별 목록
    _valid_months = df_platform_all[df_platform_all["주문월"].str.strip() != ""]["주문월"].dropna().unique().tolist()
    pf_months = sorted(
        _valid_months,
        key=lambda x: df_platform_all[df_platform_all["주문월"]==x]["주문일_dt"].min()
    )
    # 주차 목록 (주차별 필터 옵션)
    _valid_weeks = df_platform_all[df_platform_all["주차"].str.strip() != ""]["주차"].dropna().unique().tolist()
    pf_weeks = sorted(
        _valid_weeks,
        key=lambda x: df_platform_all[df_platform_all["주차"]==x]["주문일_dt"].min()
    )
    _preset_options = ["전체 기간", "최근 7일", "최근 30일"] + pf_months + pf_weeks

    col_pf1, col_pf2, col_pf3 = st.columns([2, 2, 4])
    with col_pf1:
        pf_preset = st.selectbox(
            "📅 조회 기간",
            _preset_options,
            label_visibility="collapsed",
            key="tab2_preset",
            help="월별/주차별 선택 시 해당 기간 데이터만 표시"
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
    elif pf_preset in pf_months:
        pf = df_platform_all[df_platform_all["주문월"] == pf_preset].copy()
    elif pf_preset in pf_weeks:
        pf = df_platform_all[df_platform_all["주차"] == pf_preset].copy()
    elif pf_preset == "최근 7일":
        cutoff = now - pd.Timedelta(days=7)
        pf = df_platform_all[df_platform_all["주문일_dt"] >= cutoff].copy()
    else:
        cutoff = now - pd.Timedelta(days=30)
        pf = df_platform_all[df_platform_all["주문일_dt"] >= cutoff].copy()

    pf = pf.reset_index(drop=True)

    # 주문상태 필터 (취소·반품 포함)
    pf_valid   = pf                                    # 전체 (취소·반품 포함)
    pf_normal  = pf[
        ~pf["주문상태"].str.contains("취소", na=False) &
        ~pf["주문상태"].str.contains("반품", na=False)
    ]  # 취소·반품 제외

    st.markdown("---")

    # ── KPI 카드 ──────────────────────────────────────────────────
    total_sales   = int(pf_normal["판매가"].sum())
    total_profit  = int(pf_normal["실수익"].sum())
    total_orders  = len(pf_normal)
    avg_price_pf  = int(total_sales / total_orders) if total_orders > 0 else 0
    profit_rate   = round(total_profit / total_sales * 100, 1) if total_sales > 0 else 0
    # 취소와 반품을 분리해서 집계 ("반품"이 포함되면 취소가 아닌 반품으로 분류)
    cancel_cnt    = len(pf[pf["주문상태"].str.contains("취소", na=False) & ~pf["주문상태"].str.contains("반품", na=False)])
    return_cnt    = len(pf[pf["주문상태"].str.contains("반품", na=False)])
    _total_with_cr = total_orders + cancel_cnt + return_cnt

    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    with c1: kpi_card("총 매출액", fmt_num(total_sales, "원"))
    with c2: kpi_card("총 실수익", fmt_num(total_profit, "원"), f"수익률 {profit_rate}%", profit_rate >= 65)
    with c3: kpi_card("총 주문 건수", f"{total_orders:,}건", f"취소 {cancel_cnt}건 · 반품 {return_cnt}건")
    with c4: kpi_card("평균 객단가", f"{avg_price_pf:,}원")
    with c5: kpi_card("취소율", f"{round(cancel_cnt/_total_with_cr*100) if _total_with_cr>0 else 0}%",
                      f"취소 {cancel_cnt}건")
    with c6: kpi_card("반품율", f"{round(return_cnt/_total_with_cr*100) if _total_with_cr>0 else 0}%",
                      f"반품 {return_cnt}건")
    with c7: kpi_card("수익률", f"{profit_rate}%",
                      "목표 70% 이상" if profit_rate < 70 else "✓ 목표 달성",
                      profit_rate >= 70)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 플랫폼별 미니 카드 ────────────────────────────────────────
    platforms_avail = [p for p in ["29CM", "W컨셉", "SSF", "SI Village", "무신사", "지그재그", "스마트스토어", "Cafe24"]
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
        chart_container("일별 매출 트렌드", "플랫폼별 일별 추이 · 총합계")
        # 핵심 fix: 주문일_dt(datetime) 기준으로 그룹핑 → Jan 2000 버그 해결
        pf_trend_src = pf_normal.dropna(subset=["주문일_dt"]).copy()
        pf_daily = (pf_trend_src
                    .groupby(["주문일_dt", "플랫폼"])["판매가"]
                    .sum().reset_index()
                    .sort_values("주문일_dt"))
        # 총합계 (플랫폼 전체 합산) — 날짜별
        pf_total_by_date = (pf_trend_src
                            .groupby("주문일_dt")["판매가"]
                            .sum().reset_index()
                            .sort_values("주문일_dt"))
        if not pf_daily.empty:
            fig_t = go.Figure()
            # 플랫폼별 라인 — 모두 실선, 색상으로만 구분
            for pname in pf_daily["플랫폼"].unique():
                sub_t = pf_daily[pf_daily["플랫폼"] == pname].copy()
                _mode = "lines+markers" if len(sub_t) > 1 else "markers"
                _msize = 8 if len(sub_t) == 1 else 5
                fig_t.add_trace(go.Scatter(
                    x=sub_t["주문일_dt"],
                    y=sub_t["판매가"],
                    name=pname,
                    mode=_mode,
                    line=dict(color=PLATFORM_COLORS.get(pname, "#888"), width=1.8),
                    marker=dict(size=_msize, color=PLATFORM_COLORS.get(pname, "#888"),
                                line=dict(color="white", width=1)),
                    hovertemplate=f"<b>%{{x|%Y-%m-%d}}</b><br>{pname}: %{{y:,}}원<extra></extra>",
                ))
            # 총합계 라인 — 굵은 실선 + 연한 면적
            fig_t.add_trace(go.Scatter(
                x=pf_total_by_date["주문일_dt"],
                y=pf_total_by_date["판매가"],
                name="총합계",
                mode="lines+markers",
                line=dict(color="#FF6B35", width=3),
                marker=dict(size=6, color="#FF6B35", line=dict(color="white", width=1.5)),
                fill="tozeroy",
                fillcolor="rgba(255,107,53,0.05)",
                hovertemplate="<b>%{x|%Y-%m-%d}</b><br>총합계: %{y:,}원<extra></extra>",
            ))
            fig_t.update_layout(
                height=320, margin=dict(l=0, r=0, t=10, b=0),
                plot_bgcolor="white", paper_bgcolor="white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                            font=dict(size=11)),
                xaxis=dict(
                    type="date",
                    showgrid=False,
                    tickfont=dict(size=11),
                    tickformat="%m/%d",
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
        t3_today    = pd.Timestamp.now().date()
        t3_max_date = max(df_platform_all["주문일_dt"].max().date(), t3_today)  # 오늘 이후도 허용

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
            t3_cancel = t3_df[t3_df["주문상태"].str.contains("취소", na=False) & ~t3_df["주문상태"].str.contains("반품", na=False)]
            t3_return = t3_df[t3_df["주문상태"].str.contains("반품", na=False)]
            t3_normal = t3_df[
                ~t3_df["주문상태"].str.contains("취소", na=False) &
                ~t3_df["주문상태"].str.contains("반품", na=False)
            ]

            st.markdown(
                f'<div style="color:#8C8C8C;font-size:13px;margin:4px 0 12px;">'
                f'정상 {len(t3_normal)}건 · 취소 {len(t3_cancel)}건 · 반품 {len(t3_return)}건</div>',
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
                    comm_map = {"Cafe24": "3% (PG)", "무신사": "30%", "지그재그": "30%",
                                "29CM": "30%", "W컨셉": "30%", "SSF": "30%", "SI Village": "30%"}
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
                t3_top_s = t3_top.sort_values("매출", ascending=True)
                t3_top_s = t3_top_s.copy()
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


# ════════════════════════════════════════════════════════════════
# TAB 4: 인스타그램 콘텐츠 분석
# ════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("---")

    _ig_account_list = list(IG_ACCOUNTS.keys())
    _ig_sel = st.radio("계정 선택", _ig_account_list, horizontal=True, key="ig_account_sel")
    _ig_cfg = IG_ACCOUNTS[_ig_sel]

    if not _ig_cfg["token"]:
        st.warning(f"⚠️ {_ig_sel} 토큰이 아직 설정되지 않았습니다.")
        st.stop()

    with st.spinner("인스타그램 데이터 불러오는 중..."):
        _prof, _media_rows = load_ig_profile(_ig_sel)

    if "error" in _prof:
        st.error(f"API 오류: {_prof}")
        st.stop()

    _df_ig = pd.DataFrame(_media_rows) if _media_rows else pd.DataFrame()

    # ── 프로필 헤더 ─────────────────────────────────────────────
    _col_pic, _col_info = st.columns([1, 6])
    with _col_pic:
        if _prof.get("profile_picture_url"):
            st.markdown(
                f'<img src="{_prof["profile_picture_url"]}" style="width:80px;height:80px;border-radius:50%;border:2px solid {_ig_cfg["color"]};">',
                unsafe_allow_html=True
            )
    with _col_info:
        st.markdown(f"### @{_prof.get('username', '')}")
        _bio = _prof.get("biography", "")
        if _bio:
            st.caption(_bio.replace("\n", " "))

    st.markdown("<br>", unsafe_allow_html=True)

    # ── KPI 카드 ────────────────────────────────────────────────
    _k1, _k2, _k3, _k4, _k5 = st.columns(5)
    with _k1: kpi_card("팔로워", fmt_num(_prof.get("followers_count", 0), "명"))
    with _k2: kpi_card("게시물", f"{_prof.get('media_count', 0)}개")
    if not _df_ig.empty:
        _avg_reach = int(_df_ig["도달"].mean())
        _avg_er    = round(_df_ig["ER"].mean(), 2)
        _avg_save  = int(_df_ig["저장"].mean())
        _total_int = int(_df_ig["반응"].sum())
        with _k3: kpi_card("평균 도달", fmt_num(_avg_reach, "명"))
        with _k4: kpi_card("평균 ER", f"{_avg_er}%", "좋아요+댓글/도달")
        with _k5: kpi_card("평균 저장", fmt_num(_avg_save, "회"))

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")

    if _df_ig.empty:
        st.info("콘텐츠 데이터가 없어요.")
    else:
        # ── 차트: 콘텐츠별 도달 TOP ─────────────────────────────
        _col_ca, _col_cb = st.columns([3, 2])

        with _col_ca:
            chart_container("콘텐츠별 도달 TOP 10", "최근 게시물 도달 기준 순위")
            _top_reach = _df_ig.nlargest(10, "도달").copy()
            _top_reach["캡션_short"] = _top_reach["날짜"] + " · " + _top_reach["캡션"].apply(lambda x: x[:20] + "…" if len(x) > 20 else x)
            _top_sorted = _top_reach.sort_values("도달")
            _fig_ig = go.Figure(go.Bar(
                x=_top_sorted["도달"], y=_top_sorted["캡션_short"],
                orientation="h",
                marker_color=_ig_cfg["color"],
                text=_top_sorted["도달"].apply(lambda x: f"{x:,}"),
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>도달: %{x:,}명<extra></extra>",
            ))
            _fig_ig.update_layout(
                height=max(280, len(_top_reach) * 34),
                margin=dict(l=0, r=60, t=10, b=0),
                plot_bgcolor="white", paper_bgcolor="white",
                xaxis=dict(showgrid=True, gridcolor="#F0F0F0"),
                yaxis=dict(showgrid=False, tickfont=dict(size=10)),
            )
            st.plotly_chart(_fig_ig, use_container_width=True)

        with _col_cb:
            chart_container("타입별 평균 성과", "게시물 유형별 비교")
            _type_stats = _df_ig.groupby("타입").agg(
                도달=("도달", "mean"), 저장=("저장", "mean"),
                ER=("ER", "mean"), 건수=("id", "count")
            ).reset_index()
            _type_stats["타입"] = _type_stats["타입"].map(
                {"IMAGE": "📷 이미지", "VIDEO": "🎬 릴스", "CAROUSEL_ALBUM": "🖼 캐러셀"}
            ).fillna(_type_stats["타입"])
            st.dataframe(
                _type_stats.rename(columns={"건수": "게시물수", "도달": "평균도달", "저장": "평균저장"}),
                use_container_width=True, hide_index=True
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── 일별 도달 트렌드 ─────────────────────────────────────
        chart_container("일별 도달 트렌드", "게시 날짜 기준 도달 추이")
        _df_trend = _df_ig.groupby("날짜").agg(도달=("도달", "sum"), 반응=("반응", "sum")).reset_index().sort_values("날짜")
        _fig_tr = go.Figure()
        _fig_tr.add_trace(go.Bar(x=_df_trend["날짜"], y=_df_trend["도달"], name="도달",
            marker_color=f"rgba({int(_ig_cfg['color'][1:3],16)},{int(_ig_cfg['color'][3:5],16)},{int(_ig_cfg['color'][5:7],16)},0.7)"))
        _fig_tr.add_trace(go.Scatter(x=_df_trend["날짜"], y=_df_trend["반응"], name="반응(우)",
            mode="lines+markers", line=dict(color=COLOR["green"], width=2),
            yaxis="y2"))
        _fig_tr.update_layout(
            height=260, margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="white", paper_bgcolor="white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            xaxis=dict(type="category", showgrid=False, tickfont=dict(size=11)),
            yaxis=dict(showgrid=True, gridcolor="#F0F0F0", title="도달"),
            yaxis2=dict(overlaying="y", side="right", showgrid=False, title="반응"),
            hovermode="x unified",
        )
        st.plotly_chart(_fig_tr, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── 콘텐츠 상세 테이블 (썸네일 포함) ────────────────────
        chart_container("콘텐츠 상세", "최근 20개 게시물 · 썸네일 · 전체 지표")

        _th2 = lambda t: f"<th style='padding:8px 10px;background:#F7F7F7;font-size:12px;font-weight:600;color:#555;border-bottom:2px solid #E8E8E8;white-space:nowrap;'>{t}</th>"
        _td2 = lambda v, c="#1A1A1A": f"<td style='padding:7px 10px;font-size:12px;color:{c};border-bottom:1px solid #F0F0F0;text-align:right;white-space:nowrap;'>{v}</td>"

        _rows_html2 = ""
        for _, _r in _df_ig.iterrows():
            _thumb = _r["썸네일"]
            _img_html = f"<a href='{_r['링크']}' target='_blank'><img src='{_thumb}' style='width:48px;height:48px;object-fit:cover;border-radius:5px;display:block;' onerror=\"this.style.display='none'\"></a>" if _thumb else "—"
            _cap = str(_r["캡션"])[:30] + ("…" if len(str(_r["캡션"])) > 30 else "")
            _type_icon = {"IMAGE": "📷", "VIDEO": "🎬", "CAROUSEL_ALBUM": "🖼"}.get(_r["타입"], "📄")
            _er_color = "#27AE60" if _r["ER"] >= 5 else "#E67E22" if _r["ER"] >= 2 else "#E74C3C"
            _rows_html2 += f"""<tr>
                <td style='padding:6px 10px;border-bottom:1px solid #F0F0F0;'>{_img_html}</td>
                <td style='padding:7px 10px;font-size:11px;color:#555;border-bottom:1px solid #F0F0F0;'>{_r['날짜']}</td>
                <td style='padding:7px 10px;font-size:11px;border-bottom:1px solid #F0F0F0;'>{_type_icon} {_cap}</td>
                {_td2(f"{_r['좋아요']:,}")}
                {_td2(f"{_r['댓글']:,}")}
                {_td2(f"{int(_r['도달']):,}")}
                {_td2(f"{int(_r['저장']):,}")}
                {_td2(f"{int(_r['공유']):,}" if _r['공유'] > 0 else "—")}
                {_td2(f"{_r['ER']:.2f}%", _er_color)}
                {_td2(f"{int(_r['조회수']):,}" if _r['조회수'] > 0 else "—")}
            </tr>"""

        st.markdown(f"""
        <div style='overflow-x:auto;'>
        <table style='width:100%;border-collapse:collapse;'>
            <thead><tr>
                {_th2('썸네일')}{_th2('날짜')}{_th2('내용')}
                {_th2('좋아요')}{_th2('댓글')}{_th2('도달')}{_th2('저장')}{_th2('공유')}{_th2('ER(%)')}{_th2('조회수')}
            </tr></thead>
            <tbody>{_rows_html2}</tbody>
        </table></div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# TAB 5: 플레이북 — 검증된 성공 사례 & 전략 가이드
# ════════════════════════════════════════════════════════════════
with tab5:
    st.markdown("---")
    st.markdown("### 📖 노미니컬 플레이북")
    st.caption("데이터로 검증된 패턴을 선례로 남겨 다음 전략에 그대로 활용하기 위한 기록입니다.")
    st.markdown("<br>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════
    # Good Case / Bad Case — expander 방식 (버튼 내비게이션 없음)
    # ════════════════════════════════════════════════════════════
    col_good, col_bad = st.columns(2)

    with col_good:
        st.markdown("<div style='font-size:15px;font-weight:700;color:#27AE60;margin-bottom:10px;'>✅ Good Case</div>", unsafe_allow_html=True)

        with st.expander("**5/24 — 러닝쇼츠 프리오더**  \n퍼포먼스 마케팅 · 이커머스", expanded=False):
            chart_container("✅ 사례 1 — 러닝쇼츠 프리오더 (2026-05-24)", "상시+리타겟팅 동시 집행")
            c1, c2, c3, c4 = st.columns(4)
            with c1: kpi_card("유입", "117명")
            with c2: kpi_card("CPC", "257원", "평균 대비 저렴", True)
            with c3: kpi_card("전환", "4건")
            with c4: kpi_card("ROAS", "6.15배", "목표 3배 이상", True)
            st.markdown("""<div style='background:#F0FAF5;border-left:4px solid #27AE60;border-radius:6px;padding:14px 18px;margin-top:10px;'>
프리오더 마감일을 명시한 콘텐츠를 상시 캠페인 + 리타겟팅 캠페인에 동시 집행 — 신규 유입과 장바구니 재공략이 같은 날 맞물리며 CPC가 평균보다 크게 낮아짐.
</div>""", unsafe_allow_html=True)

        with st.expander("**6/21~23 — 페이크레이어드티 전환 피크**  \n콘텐츠 · 퍼포먼스 마케팅 · 이커머스", expanded=False):
            chart_container("✅ 사례 2 — 페이크 레이어드티 릴스 (2026-06-21~23)", "재고·상세페이지 보강 → 광고 전환 → ROAS 3.9배 개선")
            st.markdown("""<div style='background:#FFF9E8;border-left:4px solid #F39C12;border-radius:6px;padding:14px 18px;margin-bottom:14px;'>
<b>비하인드 스토리</b><br>
6/17 오가닉 릴스는 저장·도달 반응이 좋았으나 <b>전환 0건</b> — 진단 결과 SOLD OUT 상태 + 상세페이지에 착용샷 부재가 원인.
재입고 및 상세페이지 보강 후 같은 콘텐츠를 광고 소재로 전환 → 6/21부터 자사몰·무신사·W컨셉에서 동시에 판매 회복.
</div>""", unsafe_allow_html=True)
            cc1, cc2 = st.columns(2)
            with cc1:
                st.markdown("**평소 (6/15~6/20, 6일)**")
                kc1, kc2, kc3 = st.columns(3)
                with kc1: kpi_card("일평균 광고비", "32,376원")
                with kc2: kpi_card("일평균 귀속매출", "46,192원")
                with kc3: kpi_card("블렌디드 ROAS", "1.43배")
            with cc2:
                st.markdown("**호조 (6/21~6/23, 3일)**")
                kc4, kc5, kc6 = st.columns(3)
                with kc4: kpi_card("일평균 광고비", "52,500원", "+62%")
                with kc5: kpi_card("일평균 귀속매출", "289,976원", "+528%", True)
                with kc6: kpi_card("블렌디드 ROAS", "5.52배", "3.9배 개선", True)
            st.markdown("""<div style='background:#F0FAF5;border-left:4px solid #27AE60;border-radius:6px;padding:14px 18px;margin-top:14px;'>
<b>핵심 교훈:</b> 광고비는 62%만 늘었는데 귀속매출은 528% 증가 — 매출 증가의 원인은 예산이 아니라 <b>소재 교체</b>였다.
같은 1원이 평소엔 1.43원, 호조 기간엔 5.52원을 벌어들임. <b>예산 확대보다 소재 검증이 먼저</b>라는 근거.
</div>""", unsafe_allow_html=True)
            st.markdown("""<div style='background:#F4F0FA;border-left:4px solid #9B59B6;border-radius:6px;padding:14px 18px;margin-top:12px;'>
<b>🔍 왜 이탈이 적었나 — 전환 퍼널 해부</b><br><br>
오가닉 소재 → 광고 페이지 → 자사몰 → <b>리뷰 바로 노출</b> → 주문<br><br>
특히 <b>자사몰 진입 후 리뷰가 즉시 보인 것</b>이 결정적. 89,000원 제품에 대한 망설임을 리뷰가 해소했음.<br><br>
<b>액션 아이템:</b> 리뷰 관리는 광고만큼 중요한 전환 요소 — 신상품 런칭 초기 리뷰 확보를 우선순위로.
</div>""", unsafe_allow_html=True)

        with st.expander("**7/9~7/12 — 장마 비수기 속 신상 쇼츠 회복**  \n상품기획 · 컨텐츠 · 이커머스", expanded=False):
            chart_container("✅ 사례 4 — 쉬어 립스탑 쇼츠, 장마 비수기 판매 견인 (2026-07-09~12)", "패션 비수기(7월)에도 신상품 + 개인 계정 콘텐츠 조합으로 자사몰 판매 회복")
            c1, c2, c3, c4 = st.columns(4)
            with c1: kpi_card("자사몰 주문", "13건", "4일간 (취소 제외)", True)
            with c2: kpi_card("자사몰 실수익", "116만원", "7/9~7/12 합산", True)
            with c3: kpi_card("방문자 피크", "297명", "7/12 — 기간 최고", True)
            with c4: kpi_card("ROAS 피크", "854%", "7/10", True)
            st.markdown("""<div style='background:#F0FAF5;border-left:4px solid #27AE60;border-radius:6px;padding:14px 18px;margin-top:10px;'>
<b>무슨 일이 있었나</b><br>
7월은 온라인 패션 거래가 연중 최저 수준으로 떨어지는 장마 비수기인데, 7/9부터 자사몰 판매가 뚜렷하게 회복됨.<br><br>
① <b>신상품이 견인</b> — 쉬어 립스탑 투인원 러닝 쇼츠가 7월에만 13건 이상 판매되며 페이크 레이어드티와 함께 투톱 형성.
기존 베스트(페이크레이어드)에만 의존하지 않고 신상이 매출 축을 추가함.<br>
② <b>개인 계정 콘텐츠 유입</b> — 7/5 개인 계정 러닝크루 게시물(도달 2,017 · 좋아요 136 · 공유 4) 이후
개인 인스타 경유 유입이 7/9 18명, 7/11 13명, 7/12 12명으로 상승. 방문자도 7/11 245명 → 7/12 297명으로 기간 최고 갱신.<br>
③ <b>W컨셉 보부상백 반복 판매</b> — 7월에만 4건(7/3·7/7·7/8·7/10). 채널(W컨셉)과 카테고리(백)의 궁합이 검증됨.<br><br>
<b>교훈:</b> 비수기는 광고 효율로 뚫는 게 아니라 <b>신상품 모멘텀 + 오가닉 콘텐츠</b>로 뚫는다.
그리고 잘 팔리는 채널·카테고리 조합(W컨셉×백)은 해당 채널 전용 콘텐츠/노출 강화로 키울 것.
</div>""", unsafe_allow_html=True)

    with col_bad:
        st.markdown("<div style='font-size:15px;font-weight:700;color:#E74C3C;margin-bottom:10px;'>⚠️ Bad Case</div>", unsafe_allow_html=True)

        with st.expander("**6/17 — 페이크레이어드티 전환 0건**  \n상품기획 · 이커머스", expanded=False):
            chart_container("⚠️ 사례 3 — 페이크 레이어드티 전환 0건 (2026-06-17)", "재고·상세페이지 미비로 콘텐츠 반응이 매출로 못 이어진 케이스")
            c1, c2, c3 = st.columns(3)
            with c1: kpi_card("조회수·저장", "양호", "오가닉 반응 좋음")
            with c2: kpi_card("전환", "0건", "", False)
            with c3: kpi_card("재고 상태", "SOLD OUT", "", False)
            st.markdown("""<div style='background:#FFF0F0;border-left:4px solid #E74C3C;border-radius:6px;padding:14px 18px;margin-top:14px;'>
<b>원인 진단</b><br>
① 상품이 SOLD OUT 상태 — 콘텐츠 보고 들어온 사람이 구매할 수 없었음<br>
② 상세페이지 착용샷 부재 — 플랫레이만 있어 "레이어드 효과"가 전달 안 됨<br>
③ 상세 설명 텍스트 부족 — 89,000원 가격을 설득할 근거 부재<br><br>
<b>교훈:</b> 콘텐츠가 잘 만들어졌어도 커머스 인프라(재고·상세페이지)가 준비 안 되면 전환은 0건이 된다.
</div>""", unsafe_allow_html=True)

        with st.expander("**7/1~7/8 — 전환 절벽 + 공식 계정 발행 공백**  \n컨텐츠 · 퍼포먼스 마케팅", expanded=False):
            chart_container("⚠️ 사례 5 — 7월 첫째주 전환 절벽 (2026-07-01~08)", "소재 피로 + 공식 계정 3주 공백 + 장마 비수기 3중 악재")
            c1, c2, c3 = st.columns(3)
            with c1: kpi_card("GA4 전환 0건일", "4일", "7/1·7/6·7/7 등", False)
            with c2: kpi_card("CTR 최저", "2.54%", "7/3 — 기준선 3% 붕괴", False)
            with c3: kpi_card("공식 계정 공백", "25일+", "마지막 게시물 6/18", False)
            st.markdown("""<div style='background:#FFF0F0;border-left:4px solid #E74C3C;border-radius:6px;padding:14px 18px;margin-top:14px;'>
<b>원인 진단</b><br>
① <b>소재 피로</b> — 6/21 투입 소재가 2주 경과. 노출이 급증한 날(7/3 4,401회 · 7/6 3,374회)마다 CTR이 2.5~2.7%로 반토막.
Meta가 오디언스를 넓힐수록 반응이 떨어지는 전형적 피로 패턴.<br>
② <b>공식 계정 발행 중단</b> — 6/18 이후 게시물 0. 공식 계정 경유 유입이 일 0~2명으로 소멸. 개인 계정 혼자 오가닉 유입을 지탱.<br>
③ <b>장마 비수기</b> — 7~8월 온라인 패션 거래량은 성수기(11월) 대비 최대 36% 낮음. 외부 환경도 역풍.<br><br>
<b>추가 발견 — 데이터 갭 주의:</b> GA4 전환 0으로 표시된 날에도 실제 주문은 존재했음
(7/6 무신사 2건, 7/11 자사몰 3건 등). GA4는 자사몰 일부만 잡으므로 <b>"오늘 판매 0"의 판단은 반드시 플랫폼 매출 시트 기준</b>으로 할 것.<br><br>
<b>교훈:</b> 소재 수명(3~6일 피크, 10일 내 교체)을 넘긴 채 비수기에 진입하면 하락이 증폭된다.
비수기일수록 ① 소재를 더 자주 교체하고 ② 공식 계정 발행 리듬(주 2회 이상)을 유지해 오가닉 바닥을 지켜야 한다.
</div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("📐 핵심 프레임워크 — 콘텐츠 → 커머스 → 광고", expanded=False):
        st.markdown("""<div style='background:#F7F9FC;border-radius:10px;padding:20px 24px;margin-bottom:8px;'>
<b>올바른 실행 순서</b><br><br>
① <b>커머스 세팅 (선행)</b> — 프로모션 확정 · 상세페이지 강화 · 재고·배송 세팅<br>
② <b>콘텐츠 발행</b> — 커머스와 연결된 서사로 제작 (링크는 이미 살 수 있는 상태)<br>
③ <b>퍼포먼스 부스팅 (즉시)</b> — 반응 좋은 콘텐츠를 바로 광고 소재로 전환 + 리타겟팅 동시 집행<br><br>
<i style='color:#888;'>예산을 늘리기 전에 소재 효율을 먼저 확인한다 — 검증된 오가닉 소재가 예산 확대보다 먼저다.</i>
</div>""", unsafe_allow_html=True)

    with st.expander("📏 소재 운영 기준 (벤치마크)", expanded=False):
        st.markdown("""<table style='width:100%;border-collapse:collapse;'>
<thead><tr>
<th style='text-align:left;padding:8px 10px;background:#F7F7F7;font-size:12px;border-bottom:2px solid #E8E8E8;'>지표</th>
<th style='text-align:left;padding:8px 10px;background:#F7F7F7;font-size:12px;border-bottom:2px solid #E8E8E8;'>정상</th>
<th style='text-align:left;padding:8px 10px;background:#F7F7F7;font-size:12px;border-bottom:2px solid #E8E8E8;'>주의</th>
<th style='text-align:left;padding:8px 10px;background:#F7F7F7;font-size:12px;border-bottom:2px solid #E8E8E8;'>교체 필요</th>
</tr></thead>
<tbody>
<tr><td style='padding:7px 10px;border-bottom:1px solid #F0F0F0;'>CTR</td>
<td style='padding:7px 10px;border-bottom:1px solid #F0F0F0;color:#27AE60;'>5~7%</td>
<td style='padding:7px 10px;border-bottom:1px solid #F0F0F0;color:#F39C12;'>피크 대비 30%↓</td>
<td style='padding:7px 10px;border-bottom:1px solid #F0F0F0;color:#E74C3C;'>3% 미만 또는 피크 대비 50%↓</td></tr>
<tr><td style='padding:7px 10px;border-bottom:1px solid #F0F0F0;'>소재 수명</td>
<td style='padding:7px 10px;border-bottom:1px solid #F0F0F0;' colspan='3'>집행 후 3~6일이 전환 집중 구간 — 7일 차부터 피로도 시작, 늦어도 10일 내 교체</td></tr>
<tr><td style='padding:7px 10px;border-bottom:1px solid #F0F0F0;'>캠페인 예산 배분</td>
<td style='padding:7px 10px;border-bottom:1px solid #F0F0F0;' colspan='3'>상시 70% (신규 유입·픽셀 누적) : 리타겟팅 30% (장바구니·방문자 재공략)</td></tr>
</tbody>
</table>""", unsafe_allow_html=True)

    with st.expander("🛡️ 콘텐츠 발행 전 체크리스트", expanded=False):
        st.markdown("""<div style='background:#F7F9FC;border-radius:10px;padding:18px 22px;'>
☐ <b>지금 사야 할 이유가 있는가</b> — 프리오더 마감일 · 한정수량 · 기한 있는 프로모션<br>
☐ <b>재고가 충분한가</b> — SOLD OUT 상태로 콘텐츠를 발행하면 유입이 전부 이탈됨<br>
☐ <b>상세페이지에 착용샷이 있는가</b> — 콘텐츠 톤과 이어지는 서사형 구성, 첫 이미지는 반드시 착용샷<br>
☐ <b>퍼널이 짧은가</b> — 콘텐츠 → 구매까지 클릭 수 최소화<br>
☐ <b>리타겟팅이 세팅되어 있는가</b> — 장바구니 이탈자 48시간 내 재접촉<br>
☐ <b>날씨·요일을 고려했는가</b> — 일요일 저녁 발행 → 월~화 구매 전환 패턴 확인됨
</div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.caption("이 플레이북은 대시보드에서 발견된 실제 성공/실패 사례가 누적될 때마다 업데이트됩니다.")


# ════════════════════════════════════════════════════════════════
# TAB 6: 입고·재고
# ════════════════════════════════════════════════════════════════
with tab6:
    st.markdown("---")
    st.markdown("### 📦 입고·재고 현황")
    st.caption(
        "기준재고는 재고 실사 시점의 수량 스냅샷이에요. 그 기준일자 이후 발생한 판매(취소·반품 제외)만 "
        "차감해서 현재 재고를 계산합니다. (현재 26SS 4개 스타일만 색상·사이즈 단위로 추적 중)"
    )

    df_inv = load_inventory_data()

    if df_inv.empty:
        st.info("📦 입고관리 시트에 데이터가 없어요. 구글 시트에서 직접 기준재고를 입력해 주세요.")
        st.stop()

    # ── KPI 요약 ──────────────────────────────────────────────────
    total_baseline = int(df_inv["기준재고"].sum())
    total_sold     = int(df_inv["판매수량(기준일 이후)"].sum())
    total_stock    = int(df_inv["재고"].sum())
    out_of_stock   = len(df_inv[(df_inv["기준재고"] > 0) & (df_inv["재고"] <= 0)])
    low_stock      = len(df_inv[(df_inv["재고"] > 0) & (df_inv["재고"] <= 5)])

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1: kpi_card("기준재고 합계", f"{total_baseline:,}개")
    with k2: kpi_card("기준일 이후 판매", f"{total_sold:,}개")
    with k3: kpi_card("현재 재고", f"{total_stock:,}개")
    with k4: kpi_card("품절", f"{out_of_stock}개", "재고 0 이하", out_of_stock == 0)
    with k5: kpi_card("재고 부족(5개 이하)", f"{low_stock}개", "", low_stock == 0)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 재고 부족/품절 알림 ───────────────────────────────────────
    _alert_df = df_inv[(df_inv["기준재고"] > 0) & (df_inv["재고"] <= 5)].sort_values("재고")
    if not _alert_df.empty:
        _alert_lines = []
        for _, r in _alert_df.iterrows():
            _icon = "🚨" if r["재고"] <= 0 else "⚠️"
            _label = f"{r['상품명']} · {r['컬러']}" + (f" / {r['사이즈']}" if r["사이즈"] != "-" else "")
            _alert_lines.append(f"{_icon} <b>{_label}</b> — 재고 {int(r['재고'])}개 (기준 {int(r['기준재고'])} · 판매 {int(r['판매수량(기준일 이후)'])})")
        insight_box(_alert_lines, COLOR["orange"])
        st.markdown("<br>", unsafe_allow_html=True)

    # ── 리오더 알림 (최근 7일 판매 속도 + 생산 리드타임 14일 감안) ──
    _reorder_df = df_inv[df_inv["리오더필요"]].sort_values("소진예상일")
    if not _reorder_df.empty:
        _reorder_lines = []
        for _, r in _reorder_df.iterrows():
            _label = f"{r['상품명']} · {r['컬러']}" + (f" / {r['사이즈']}" if r["사이즈"] != "-" else "")
            _reorder_lines.append(
                f"🏭 <b>{_label}</b> — 소진예상 <b>{r['소진예상일']}일 후</b> "
                f"(재고 {int(r['재고'])}개 ÷ 최근7일 일평균 {r['일평균판매']}개) · 생산기간 14일보다 짧아 지금 발주 필요"
            )
        insight_box(_reorder_lines, "#E74C3C")
        st.markdown("<br>", unsafe_allow_html=True)

    # ── 전체 재고 현황 표 ─────────────────────────────────────────
    chart_container("스타일·컬러·사이즈별 재고 현황", "기준재고 - 기준일 이후 판매 = 현재 재고")

    def _stock_badge(v):
        if v <= 0: return "#E74C3C"
        if v <= 5: return "#F39C12"
        return "#27AE60"

    _th3 = lambda t: f"<th style='padding:8px 10px;background:#F7F7F7;font-size:12px;font-weight:600;color:#555;border-bottom:2px solid #E8E8E8;text-align:left;white-space:nowrap;'>{t}</th>"
    _td3 = lambda v, align="right": f"<td style='padding:7px 10px;font-size:13px;border-bottom:1px solid #F0F0F0;text-align:{align};white-space:nowrap;'>{v}</td>"

    # 품번 → 컬러 → 사이즈(S/M/L 순) 순서로 정렬
    _size_order = {"S": 0, "M": 1, "L": 2, "XL": 3, "FREE": 4, "-": 5}
    _df_sorted = df_inv.copy()
    _df_sorted["_사이즈순서"] = _df_sorted["사이즈"].map(_size_order).fillna(9)
    _df_sorted = _df_sorted.sort_values(["품번", "컬러", "_사이즈순서"])

    _rows_html3 = ""
    for _, r in _df_sorted.iterrows():
        _color = _stock_badge(r["재고"])
        _rows_html3 += f"""<tr>
            {_td3(r['품번'], 'left')}
            {_td3(r['상품명'], 'left')}
            {_td3(r['컬러'], 'center')}
            {_td3(r['사이즈'], 'center')}
            {_td3(f"{int(r['기준재고']):,}")}
            {_td3(f"{int(r['판매수량(기준일 이후)']):,}")}
            <td style='padding:7px 10px;font-size:13px;font-weight:700;color:{_color};border-bottom:1px solid #F0F0F0;text-align:right;'>{int(r['재고']):,}</td>
            {_td3(f"{r['일평균판매']:.1f}개")}
            {_td3(f"{r['소진예상일']}일" if pd.notna(r['소진예상일']) else '-', 'center')}
            {_td3(f"{int(r['매칭건수'])}건", 'center')}
            {_td3(r['비고'] or '-', 'left')}
        </tr>"""

    st.markdown(f"""
    <div style='overflow-x:auto;'>
    <table style='width:100%;border-collapse:collapse;'>
        <thead><tr>
            {_th3('품번')}{_th3('상품명(Cafe24)')}{_th3('컬러')}{_th3('사이즈')}{_th3('기준재고')}{_th3('판매(기준일후)')}{_th3('현재재고')}{_th3('일평균판매(7일)')}{_th3('소진예상일')}{_th3('매칭건수')}{_th3('비고')}
        </tr></thead>
        <tbody>{_rows_html3}</tbody>
    </table></div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.caption(
        "⚠️ 매칭건수가 0이거나 비정상적으로 많으면 색상/사이즈 표기 차이일 수 있어요. "
        "'📦 입고관리' 시트에서 매칭키워드·컬러·사이즈를 직접 수정해 보정할 수 있습니다."
    )


# ── 푸터 ───────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<div style="text-align:center;color:#BDBDBD;font-size:12px;">NOMINICAL · 지표 자동화 대시보드 · 5분마다 캐시 갱신</div>',
    unsafe_allow_html=True
)
