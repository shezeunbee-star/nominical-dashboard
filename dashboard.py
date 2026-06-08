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
        FilterExpression, Filter, FilterExpressionList,
    )
    _GA4_AVAILABLE = True
except ImportError:
    _GA4_AVAILABLE = False

# ── 설정 ───────────────────────────────────────────────────────────
SPREADSHEET_ID      = "1y9mZirj81sR2tkkGV_wTzFvJonPdJU-JuErSRDo_73E"
SHEET_NAME          = "📅 일별 트래킹"
PLATFORM_SHEET_NAME = "🏬 플랫폼 매출"
SA_FILE             = "/Users/kimeunbee/Documents/지표분析/service_account.json"
TOKEN_FILE          = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")

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
    "지그재그":   "#FF9900",   # 지그재그 오렌지
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
                metrics = "reach,saved,total_interactions,views,ig_reels_avg_watch_time"
            else:
                metrics = "reach,saved,total_interactions"

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
        creds.refresh(Request())
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
        creds.refresh(Request())
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
        ch_meta     = get_channel("meta", "paid_feed") + get_channel("ig", "paid")
        time.sleep(0.3)
        ch_official = get_channel("instagram", "bio")
        time.sleep(0.3)
        ch_personal = get_channel("instagram", "personal_bio") + get_channel("instagram", "personal_story")
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

        # 데이터 업데이트 (K~V열)
        ws.update_cell(row_idx, 11, sessions)      # K: 방문자
        ws.update_cell(row_idx, 12, transactions)  # L: 구매
        ws.update_cell(row_idx, 13, bounce)        # M: 이탈율
        ws.update_cell(row_idx, 14, avg_price)     # N: 객단가
        ws.update_cell(row_idx, 15, revenue)       # O: 매출
        ws.update_cell(row_idx, 16, ch_meta)       # P: 유입_메타
        ws.update_cell(row_idx, 17, ch_official)   # Q: 유입_공식
        ws.update_cell(row_idx, 18, ch_personal)   # R: 유입_개인
        ws.update_cell(row_idx, 19, ch_direct)     # S: 유입_직접
        ws.update_cell(row_idx, 20, new_users)     # T: 신규
        ws.update_cell(row_idx, 21, returning_users) # U: 재방문

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

        # 갭 찾기
        dates_needed = set()
        min_date = min(date_objects)
        max_date = max(date_objects)

        current = min_date
        while current <= max_date:
            if current not in date_to_row:
                dates_needed.add(current)
            current += timedelta(days=1)

        if not dates_needed:
            return True, "갭이 없어요 (이미 모든 날짜가 있음)."

        print(f"   추가할 날짜: {sorted([f'{d.month}/{d.day}' for d in dates_needed])}")

        # 날짜별로 정렬해서 올바른 위치에 행 삽입
        sorted_dates = sorted(dates_needed)

        for insert_date in sorted_dates:
            # 이 날짜가 들어갈 위치 찾기
            insert_row = None
            for check_date in sorted(date_to_row.keys()):
                if check_date > insert_date:
                    insert_row = date_to_row[check_date]
                    break

            if insert_row is None:
                # 맨 뒤에 추가
                insert_row = len(all_dates) + 1

            # 행 삽입 (날짜만 입력)
            date_label = f"{insert_date.month}/{insert_date.day}"
            ws.insert_row([date_label], index=insert_row)

            # date_to_row 업데이트 (뒤의 행들 번호 변경)
            for d in list(date_to_row.keys()):
                if date_to_row[d] >= insert_row:
                    date_to_row[d] += 1
            date_to_row[insert_date] = insert_row

            print(f"   ✅ {date_label} 행 추가 (row {insert_row})")
            time.sleep(0.2)

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

        spend = impressions = clicks = purchases = 0
        if res.get("data"):
            d           = res["data"][0]
            spend       = round(float(d.get("spend", 0)))
            impressions = int(d.get("impressions", 0))
            clicks      = int(d.get("clicks", 0))
            for action in d.get("actions", []):
                if action["action_type"] in ("purchase", "offsite_conversion.fb_pixel_purchase"):
                    purchases = int(float(action["value"]))

        # Google Sheets에서 행 찾기
        all_dates = ws.col_values(1)
        row_idx = None
        for i, d in enumerate(all_dates):
            if str(d).strip() == day_label:
                row_idx = i + 1
                break

        if not row_idx:
            return False, f"'{day_label}' 행을 찾을 수 없음"

        # C~E, H 칼럼에 데이터 쓰기
        ws.update(values=[[spend, impressions, clicks]], range_name=f"C{row_idx}:E{row_idx}")
        time.sleep(0.2)
        ws.update(values=[[purchases]], range_name=f"H{row_idx}")

        return True, f"✅ Meta {day_label} 완료 — 광고비 {spend:,}원 · 전환 {purchases}건"

    except Exception as e:
        return False, f"❌ Meta 업데이트 실패 ({target_date}): {e}"


def fill_missing_dates():
    """비어있는 날짜들을 자동 감지하고 GA4 + Meta 데이터로 채우기."""
    from datetime import date, timedelta

    try:
        creds = _get_oauth_creds()
        gc = gspread.authorize(creds)
        ws = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

        # 비어있는 날짜 찾기
        all_dates = ws.col_values(1)
        missing_dates = []

        # 6/2~6/6 직접 확인
        for month, day in [(6, 2), (6, 3), (6, 4), (6, 5), (6, 6)]:
            date_label = f"{month}/{day}"
            row_idx = None

            for i, d in enumerate(all_dates):
                if str(d).strip() == date_label:
                    row_idx = i + 1
                    # K~V 칼럼 (11~22)에 데이터가 있는지 확인
                    row_data = ws.row_values(row_idx)
                    if len(row_data) < 11 or not str(row_data[10]).strip():
                        # 데이터 없음
                        missing_dates.append(date(2026, month, day))
                    break

        if not missing_dates:
            return True, "비어있는 날짜가 없어요."

        # 각 날짜에 GA4 + Meta 데이터 추가
        for d in missing_dates:
            # GA4 데이터
            ok_ga4, msg_ga4 = update_ga4_for_date(d)
            if not ok_ga4:
                return False, msg_ga4

            # Meta 데이터
            ok_meta, msg_meta = update_meta_for_date(d)
            if not ok_meta:
                # Meta 실패는 경고만 표시하고 계속
                pass

            time.sleep(0.5)

        return True, f"✅ {len(missing_dates)}개 날짜 데이터 추가 완료!"

    except Exception as e:
        return False, f"❌ 갭 채우기 실패: {e}"


def update_meta_yesterday():
    """어제 메타 광고 데이터를 시트 C~H열에 업데이트. (bool, str) 반환."""
    try:
        from datetime import date, timedelta

        # Meta 토큰 우선순위: secrets → 로컬 파일
        meta_token = None
        for key in ("meta_access_token", "META_ACCESS_TOKEN", "meta_token"):
            try:
                meta_token = st.secrets[key]
                if meta_token:
                    break
            except Exception:
                pass
        if not meta_token:
            _tf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "meta_token.txt")
            if os.path.exists(_tf):
                meta_token = open(_tf).read().strip()
        if not meta_token:
            return False, "❌ Meta 토큰 없음. Streamlit secrets에 meta_access_token을 추가해 주세요."

        AD_ACCOUNT = "act_1599099620677018"

        creds = _get_sheet_creds()
        gc    = gspread.authorize(creds)
        ws    = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

        yesterday = date.today() - timedelta(days=1)
        date_str  = yesterday.strftime("%Y-%m-%d")
        day_label = f"{yesterday.month}/{yesterday.day}"

        res = _requests.get(
            f"https://graph.facebook.com/v25.0/{AD_ACCOUNT}/insights",
            params={
                "fields":     "spend,impressions,clicks,ctr,cpc,actions,purchase_roas",
                "time_range": f'{{"since":"{date_str}","until":"{date_str}"}}',
                "access_token": meta_token,
            },
            timeout=15,
        ).json()

        spend = impressions = clicks = purchases = 0
        if res.get("data"):
            d           = res["data"][0]
            spend       = round(float(d.get("spend", 0)))
            impressions = int(d.get("impressions", 0))
            clicks      = int(d.get("clicks", 0))
            for action in d.get("actions", []):
                if action["action_type"] in ("purchase", "offsite_conversion.fb_pixel_purchase"):
                    purchases = int(float(action["value"]))

        all_dates = ws.col_values(1)
        row_idx   = next((i + 1 for i, d in enumerate(all_dates) if d == day_label), None)
        if not row_idx:
            # 날짜 행이 없으면 새 행 추가
            ws.append_row([day_label], value_input_option="RAW")
            all_dates = ws.col_values(1)
            row_idx = next((i + 1 for i, d in enumerate(all_dates) if d == day_label), None)
        if not row_idx:
            return False, f"'{day_label}' 행 생성 실패"

        ws.update(values=[[spend, impressions, clicks]], range_name=f"C{row_idx}:E{row_idx}")
        time.sleep(0.2)
        ws.update(values=[[purchases]], range_name=f"H{row_idx}")

        return True, f"✅ Meta {day_label} 완료 — 광고비 {spend:,}원 · 전환 {purchases}건"

    except Exception as e:
        return False, f"❌ Meta 업데이트 실패: {e}"


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
        MARKET_MAP = {"musinsa": "무신사", "zigzag": "지그재그"}
        COMM_CAFE24 = 3
        COMM_DEFAULT = 30

        headers = {
            "Authorization": f"Bearer {t['access_token']}",
            "X-Cafe24-Api-Version": "2026-03-01",
        }
        resp = _requests.get(
            f"https://{t['shop_id']}.cafe24api.com/api/v2/orders",
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
        for order in orders:
            mid      = (order.get("market_id") or "").lower().strip()
            platform = MARKET_MAP.get(mid, "Cafe24")
            order_date = (order.get("order_date") or "")[:10]
            items = order.get("items", [])
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
                status = "정상"
                key = f"{platform}|{order_date}|{code}|{color}|{size}"
                if key not in existing_keys:
                    new_rows.append([platform, order_date, name, code,
                                     color, size, qty, total, comm, profit, status])
                    existing_keys.add(key)

        if new_rows:
            # 날짜순 정렬 후 append
            all_data = [r for r in existing_raw[1:] if r] + new_rows
            all_data.sort(key=lambda r: r[1] if len(r) > 1 else "")
            ws.resize(rows=1)
            ws.append_rows([existing_raw[0]] + all_data, value_input_option="USER_ENTERED")

        return True, f"✅ Cafe24 {date_str} 완료 — {len(new_rows)}건 추가"

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
        st.info("🚀 데이터 업데이트 프로세스 시작...")

        # Step 1: 빈 행 자동 추가
        with st.spinner("1️⃣  비어있는 날짜 감지 및 행 추가 중..."):
            ok_gap, msg_gap = add_empty_rows_for_gaps()

        if ok_gap:
            st.toast(msg_gap, icon="✅")
        else:
            st.toast(msg_gap, icon="⚠️")

        # Step 2: GA4 데이터 채우기
        with st.spinner("2️⃣  GA4 데이터 조회 및 채우기 중... (시간 소요)"):
            ok_fill, msg_fill = fill_missing_dates()

        if ok_fill:
            st.toast(msg_fill, icon="✅")
        else:
            st.toast(msg_fill, icon="⚠️")

        # Step 3: 기존 전일자 업데이트
        with st.spinner("3️⃣  어제 데이터 업데이트 중..."):
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

        st.cache_data.clear()
        st.success("✅ 모든 업데이트 완료!")
        st.rerun()

st.markdown("---")

# ── 탭 분기 ──────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📊 방문자 · 광고 성과", "🏬 플랫폼별 매출", "📅 기간별 매출 조회", "📱 인스타그램 콘텐츠"])


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
    conv_df = df[df["구매"] > 0].copy()
    # 날짜_dt → YYYY-MM-DD (Meta API 날짜 형식과 통일)
    conv_df["날짜_key"] = conv_df["날짜_dt"].dt.strftime("%Y-%m-%d")

    # ── 전환 발생일 소재 annotation ─────────────────────────────
    _daily_cr = load_meta_daily_creative("last_30d")
    # 날짜별 소재 그룹핑 (키: YYYY-MM-DD)
    _cr_by_date = {}
    if not _daily_cr.empty:
        for _d, _grp in _daily_cr.groupby("날짜"):
            _cr_by_date[_d] = _grp.sort_values("전환수", ascending=False)

    # 전환 발생일별 호버 텍스트 및 annotation 라벨 구성
    _hover_texts = []
    for _, _row in conv_df.iterrows():
        _date_key = str(_row["날짜_key"])  # YYYY-MM-DD
        _total_conv = int(_row["구매"])

        # ① 유입 경로 (GA4 채널 데이터)
        _ch_lines = []
        _ch_pairs = [
            ("메타광고", _row.get("유입_메타", 0)),
            ("공식 인스타", _row.get("유입_공식", 0)),
            ("개인 인스타", _row.get("유입_개인", 0)),
            ("직접 방문", _row.get("유입_직접", 0)),
        ]
        for _ch, _v in sorted(_ch_pairs, key=lambda x: -x[1]):
            if _v > 0:
                _ch_lines.append(f"  {_ch}: {int(_v)}명")

        # ② 전환 소재 (Meta daily breakdown)
        _cr_lines = []
        if _date_key in _cr_by_date:
            for _i, (_, _cr) in enumerate(_cr_by_date[_date_key].head(5).iterrows(), 1):
                _cr_lines.append(f"  {_i}위. {str(_cr['소재명'])[:30]} ({int(_cr['전환수'])}건)")

        # 호버 HTML 조립
        _ht = f"<b>📅 {_date_key} · 전환 {_total_conv}건</b>"
        if _ch_lines:
            _ht += "<br><br><b>유입 경로</b><br>" + "<br>".join(_ch_lines)
        if _cr_lines:
            _ht += "<br><br><b>전환 소재 (Meta)</b><br>" + "<br>".join(_cr_lines)
        elif not _cr_lines and not _daily_cr.empty:
            _ht += "<br><br><i style='color:#999'>Meta 소재 데이터 없음 (자연유입)</i>"
        _hover_texts.append(_ht)

    fig1.add_trace(go.Scatter(
        x=conv_df["날짜"], y=conv_df["방문자"],
        name="전환 발생",
        mode="markers",
        marker=dict(symbol="circle", size=12, color=COLOR["green"],
                    line=dict(color="white", width=2)),
        text=_hover_texts,
        hovertemplate="%{text}<extra></extra>",
    ), secondary_y=False)

    # annotation 라벨 (점 위 텍스트)
    if not conv_df.empty:
        for _, _row in conv_df.iterrows():
            _date_key  = str(_row["날짜_key"])  # YYYY-MM-DD — Meta 조회용
            _date_label = str(_row["날짜"])      # M/D — 차트 x축 좌표용
            _vis = _row["방문자"]
            if _date_key in _cr_by_date:
                _top = _cr_by_date[_date_key].iloc[0]
                _n_others = len(_cr_by_date[_date_key]) - 1
                _label = f"Meta · {str(_top['소재명'])[:18]}{'…' if len(str(_top['소재명']))>18 else ''}"
                if _n_others > 0:
                    _label += f" 외 {_n_others}개"
                _label += f" ({int(_top['전환수'])}건)"
            else:
                _label = f"전환 {int(_row['구매'])}건"
            fig1.add_annotation(
                x=_date_label, y=_vis,  # 차트 x축과 동일한 M/D 형식
                text=_label,
                showarrow=True,
                arrowhead=0, arrowwidth=1, arrowcolor="#27AE60",
                ax=0, ay=-36,
                font=dict(size=10, color="#1A6B35"),
                bgcolor="rgba(39,174,96,0.08)",
                bordercolor="#27AE60",
                borderwidth=1, borderpad=3,
                align="center",
            )

    fig1.update_layout(
        height=360, margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(type="category", showgrid=False, tickfont=dict(size=11)),
        yaxis=dict(showgrid=True, gridcolor="#F0F0F0", tickfont=dict(size=11), title="방문자수"),
        hovermode="x unified", barmode="overlay",
    )
    fig1.update_layout(yaxis2=dict(overlaying="y", visible=False))
    st.plotly_chart(fig1, use_container_width=True)

    # ── 방문자·전환 추이 인사이트 ─────────────────────────────────
    _t1_lines = []
    if len(df) > 1:
        _max_day = df.loc[df["방문자"].idxmax()]
        _avg_vis = df["방문자"].mean()
        if _max_day["방문자"] > _avg_vis * 2:
            _top_ch = max({"메타광고": _max_day["유입_메타"], "공식인스타": _max_day["유입_공식"],
                           "개인인스타": _max_day["유입_개인"], "직접방문": _max_day["유입_직접"]}, key=lambda k: {"메타광고": _max_day["유입_메타"], "공식인스타": _max_day["유입_공식"], "개인인스타": _max_day["유입_개인"], "직접방문": _max_day["유입_직접"]}[k])
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
            # ROAS 라인 (전환 있을 때만)
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
                xaxis=dict(type="category", showgrid=False, tickfont=dict(size=11)),
                yaxis=dict(showgrid=True, gridcolor="#F0F0F0", tickfont=dict(size=11)),
                hovermode="x unified",
            )
            st.plotly_chart(fig5, use_container_width=True)

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


# ════════════════════════════════════════════════════════════════
# TAB 2: 플랫폼별 매출 대시보드
# ════════════════════════════════════════════════════════════════
with tab2:

    if df_platform_all.empty:
        st.info("🏬 플랫폼 매출 데이터가 없어요. platform_to_sheets.py로 데이터를 먼저 업로드해 주세요.")
        st.stop()

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
    platforms_avail = [p for p in ["29CM", "W컨셉", "SSF", "SI Village", "무신사", "지그재그", "Cafe24"]
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
                {_td2(f"{_r['ER']:.2f}%", _er_color)}
                {_td2(f"{int(_r['조회수']):,}" if _r['조회수'] > 0 else "—")}
            </tr>"""

        st.markdown(f"""
        <div style='overflow-x:auto;'>
        <table style='width:100%;border-collapse:collapse;'>
            <thead><tr>
                {_th2('썸네일')}{_th2('날짜')}{_th2('내용')}
                {_th2('좋아요')}{_th2('댓글')}{_th2('도달')}{_th2('저장')}{_th2('ER(%)')}{_th2('조회수')}
            </tr></thead>
            <tbody>{_rows_html2}</tbody>
        </table></div>""", unsafe_allow_html=True)


# ── 푸터 ───────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<div style="text-align:center;color:#BDBDBD;font-size:12px;">NOMINICAL · 지표 자동화 대시보드 · 5분마다 캐시 갱신</div>',
    unsafe_allow_html=True
)
