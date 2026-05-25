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

# ── 설정 ───────────────────────────────────────────────────────────
SPREADSHEET_ID = "1y9mZirj81sR2tkkGV_wTzFvJonPdJU-JuErSRDo_73E"
SHEET_NAME     = "📅 일별 트래킹"
SA_FILE        = "/Users/kimeunbee/Documents/지표분석/service_account.json"
TOKEN_FILE     = "/Users/kimeunbee/Documents/지표분석/token.json"

COLOR = {
    "primary":    "#1A1A1A",
    "accent":     "#E8FF4D",   # 브랜드 옐로
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

st.set_page_config(
    page_title="NOMINICAL 대시보드",
    page_icon="🏃",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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
    .kpi-label { font-size: 12px; color: #8C8C8C; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 6px; }
    .kpi-value { font-size: 28px; font-weight: 700; color: #1A1A1A; line-height: 1; }
    .kpi-delta-pos { font-size: 13px; font-weight: 600; color: #4ECBA0; margin-top: 6px; }
    .kpi-delta-neg { font-size: 13px; font-weight: 600; color: #F7874F; margin-top: 6px; }
    .kpi-delta-neu { font-size: 13px; font-weight: 500; color: #8C8C8C; margin-top: 6px; }
    .section-title { font-size: 16px; font-weight: 700; color: #1A1A1A; margin-bottom: 4px; }
    .section-sub   { font-size: 12px; color: #8C8C8C; margin-bottom: 16px; }
    div[data-testid="stMetric"] { display: none; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
</style>
""", unsafe_allow_html=True)


# ── 데이터 로드 ─────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data():
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    # 클라우드(Streamlit secrets) → 로컬 서비스 계정 → 로컬 OAuth 순으로 인증
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

    date_col   = df.iloc[:, 0].apply(lambda x: str(x).strip())
    spend      = safe_num(headers[2])   # C
    impressions= safe_num(headers[3])   # D
    clicks     = safe_num(headers[4])   # E
    ctr        = safe_num(headers[5])   # F
    cpc        = safe_num(headers[6])   # G
    conv_meta  = safe_num(headers[7])   # H
    roas_meta  = safe_num(headers[8])   # I
    visitors   = safe_num(headers[10])  # K
    purchases  = safe_num(headers[11])  # L
    bounce     = safe_num(headers[13])  # N
    avg_price  = safe_num(headers[14])  # O
    revenue    = safe_num(headers[15])  # P
    ch_meta    = safe_num(headers[16])  # Q
    ch_off     = safe_num(headers[17])  # R
    ch_per     = safe_num(headers[18])  # S
    ch_dir     = safe_num(headers[19])  # T
    new_users  = safe_num(headers[20])  # U
    ret_users  = safe_num(headers[21])  # V

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

    # CPO 계산
    result["CPO"] = result.apply(
        lambda r: round(r["광고비"] / r["구매"]) if r["구매"] > 0 and r["광고비"] > 0 else 0, axis=1
    )
    result["전환율"] = result.apply(
        lambda r: round(r["구매"] / r["방문자"] * 100, 2) if r["방문자"] > 0 else 0, axis=1
    )
    result["ROAS"] = result.apply(
        lambda r: round(r["매출"] / r["광고비"], 2) if r["광고비"] > 0 and r["매출"] > 0 else 0, axis=1
    )

    # 데이터 있는 날짜만
    result = result[result["방문자"] > 0].reset_index(drop=True)
    return result


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

def chart_container(title, subtitle=""):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-sub">{subtitle}</div>', unsafe_allow_html=True)


# ── 메인 ───────────────────────────────────────────────────────────
df = load_data()

# 헤더
col_logo, col_refresh = st.columns([6, 1])
with col_logo:
    st.markdown("## 🏃 NOMINICAL 성과 대시보드")
    st.markdown(f'<span style="color:#8C8C8C;font-size:13px;">데이터 기준: {df["날짜"].iloc[0]} ~ {df["날짜"].iloc[-1]} | {len(df)}일</span>', unsafe_allow_html=True)
with col_refresh:
    if st.button("🔄 새로고침"):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# ── KPI 카드 행 ─────────────────────────────────────────────────────
ad_days = df[df["광고비"] > 0]
conv_days = df[df["구매"] > 0]

total_visitors = int(df["방문자"].sum())
total_purchases = int(df["구매"].sum())
total_spend = int(df["광고비"].sum())
total_revenue = int(df["매출"].sum())
avg_cpo = int(total_spend / total_purchases) if total_purchases > 0 else 0
overall_roas = round(total_revenue / total_spend, 1) if total_spend > 0 else 0
overall_cvr = round(total_purchases / total_visitors * 100, 2) if total_visitors > 0 else 0
avg_new_rate = int(df["신규"].sum() / (df["신규"].sum() + df["재방문"].sum()) * 100) if (df["신규"].sum() + df["재방문"].sum()) > 0 else 0

# 최근 7일 vs 이전 기간 비교
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

st.markdown("<br>", unsafe_allow_html=True)

# ── 차트 1: 일별 방문자 & 전환 추이 ────────────────────────────────
chart_container("일별 방문자 · 전환 추이", "바이럴 스파이크, 광고 집행일, 전환 발생 패턴을 한눈에")

fig1 = make_subplots(specs=[[{"secondary_y": True}]])

# 방문자 영역 차트
fig1.add_trace(go.Scatter(
    x=df["날짜"], y=df["방문자"],
    name="방문자",
    fill="tozeroy",
    fillcolor="rgba(79,142,247,0.12)",
    line=dict(color=COLOR["blue"], width=2),
    hovertemplate="<b>%{x}</b><br>방문자: %{y:,}명<extra></extra>",
), secondary_y=False)

# 광고비 막대
fig1.add_trace(go.Bar(
    x=df["날짜"], y=df["광고비"],
    name="광고비",
    marker_color="rgba(232,255,77,0.7)",
    marker_line_color=COLOR["accent"],
    marker_line_width=1,
    hovertemplate="<b>%{x}</b><br>광고비: %{y:,}원<extra></extra>",
    yaxis="y3",
), secondary_y=False)

# 전환 점 (전환 있는 날만 크게)
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
    height=320,
    margin=dict(l=0, r=0, t=10, b=0),
    plot_bgcolor="white",
    paper_bgcolor="white",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    xaxis=dict(showgrid=False, tickfont=dict(size=11)),
    yaxis=dict(showgrid=True, gridcolor="#F0F0F0", tickfont=dict(size=11), title="방문자수"),
    hovermode="x unified",
    barmode="overlay",
)
# 광고비 y축을 오른쪽에 보이지 않게 (스케일 조정용)
fig1.update_layout(yaxis2=dict(overlaying="y", visible=False))

st.plotly_chart(fig1, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── 차트 2+3: 광고 효율 & 채널 유입 ────────────────────────────────
col_left, col_right = st.columns([3, 2])

with col_left:
    chart_container("광고 효율 추이", "CPO는 낮을수록, ROAS는 높을수록 좋음")

    ad_df = df[df["광고비"] > 0].copy()
    if not ad_df.empty:
        fig2 = make_subplots(specs=[[{"secondary_y": True}]])

        fig2.add_trace(go.Bar(
            x=ad_df["날짜"], y=ad_df["CPO"],
            name="CPO (원)",
            marker_color=COLOR["orange"],
            opacity=0.8,
            hovertemplate="<b>%{x}</b><br>CPO: %{y:,}원<extra></extra>",
        ), secondary_y=False)

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

        # CPO 평균선
        if avg_cpo > 0:
            fig2.add_hline(y=avg_cpo, line_dash="dot", line_color=COLOR["gray"],
                           annotation_text=f"평균 CPO {avg_cpo:,}원", annotation_position="top left",
                           secondary_y=False)

        fig2.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="white",
            paper_bgcolor="white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            xaxis=dict(showgrid=False, tickfont=dict(size=11)),
            yaxis=dict(showgrid=True, gridcolor="#F0F0F0", tickfont=dict(size=11), title="CPO (원)"),
            yaxis2=dict(showgrid=False, tickfont=dict(size=11), title="ROAS (배)"),
            hovermode="x unified",
        )
        st.plotly_chart(fig2, use_container_width=True)
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
            height=300,
            margin=dict(l=0, r=0, t=10, b=10),
            showlegend=False,
            annotations=[dict(text=f"총<br>{fmt_num(sum(ch_totals.values()))}명",
                              x=0.5, y=0.5, font_size=14, font_color="#1A1A1A",
                              showarrow=False)]
        )
        st.plotly_chart(fig3, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── 차트 4: 신규 vs 재방문자 & 픽셀 모수 누적 ──────────────────────
chart_container("신규 vs 재방문자 · 픽셀 모수 누적", "신규 유입이 리타게팅 모수로 쌓이는 흐름")

nvr_df = df[(df["신규"] > 0) | (df["재방문"] > 0)].copy()
if not nvr_df.empty:
    nvr_df["누적_신규"] = nvr_df["신규"].cumsum()

    fig4 = make_subplots(specs=[[{"secondary_y": True}]])

    fig4.add_trace(go.Bar(
        x=nvr_df["날짜"], y=nvr_df["신규"],
        name="신규방문자",
        marker_color=COLOR["blue"],
        opacity=0.85,
        hovertemplate="<b>%{x}</b><br>신규: %{y:,}명<extra></extra>",
    ), secondary_y=False)

    fig4.add_trace(go.Bar(
        x=nvr_df["날짜"], y=nvr_df["재방문"],
        name="재방문자",
        marker_color=COLOR["green"],
        opacity=0.85,
        hovertemplate="<b>%{x}</b><br>재방문: %{y:,}명<extra></extra>",
    ), secondary_y=False)

    # 누적 픽셀 모수 라인
    fig4.add_trace(go.Scatter(
        x=nvr_df["날짜"], y=nvr_df["누적_신규"],
        name="누적 픽셀 모수",
        mode="lines",
        line=dict(color=COLOR["orange"], width=2, dash="dot"),
        hovertemplate="<b>%{x}</b><br>누적 픽셀 모수: %{y:,}명<extra></extra>",
    ), secondary_y=True)

    # 전환 발생 날 마킹
    for _, row in nvr_df[nvr_df["구매"] > 0].iterrows():
        fig4.add_vline(
            x=row["날짜"], line_width=1, line_dash="dot",
            line_color=COLOR["green"], opacity=0.4
        )

    fig4.update_layout(
        height=300,
        margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(showgrid=False, tickfont=dict(size=11)),
        yaxis=dict(showgrid=True, gridcolor="#F0F0F0", tickfont=dict(size=11), title="방문자수"),
        yaxis2=dict(showgrid=False, tickfont=dict(size=11), title="누적 모수"),
        hovermode="x unified",
    )
    st.plotly_chart(fig4, use_container_width=True)

    # 인사이트 배너
    pixel_total = int(nvr_df["신규"].sum())
    latest_ret = nvr_df["재방문"].iloc[-3:].mean()
    early_ret  = nvr_df["재방문"].iloc[:max(1, len(nvr_df)-7)].mean()
    ret_trend  = "📈 재방문자 증가 추세 — 브랜드 인지도 쌓이는 중" if latest_ret > early_ret * 1.2 else ""

    st.markdown(f"""
    <div style="background:#F0F9FF;border-left:4px solid {COLOR['blue']};padding:14px 18px;border-radius:8px;font-size:13px;color:#1A1A1A;">
    📌 <b>누적 픽셀 모수 {pixel_total:,}명</b> — 리타게팅 캠페인이 이 모수 전체를 커버하도록 설정됐는지 확인.
    신규 방문자는 방문 후 3~7일 내 리타게팅 시 전환율이 cold 대비 3~5배 높음.
    {"&nbsp;&nbsp;|&nbsp;&nbsp;" + ret_trend if ret_trend else ""}
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── 차트 5: 일별 채널 유입 스택 바 ─────────────────────────────────
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
            fig5.add_trace(go.Bar(
                x=ch_df["날짜"], y=ch_df[col_key],
                name=ch, marker_color=color,
                hovertemplate=f"<b>%{{x}}</b><br>{ch}: %{{y}}명<extra></extra>"
            ))
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

# ── 푸터 ───────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<div style="text-align:center;color:#BDBDBD;font-size:12px;">NOMINICAL · 지표 자동화 대시보드 · 5분마다 캐시 갱신</div>',
    unsafe_allow_html=True
)
