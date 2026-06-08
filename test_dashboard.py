"""최소한의 대시보드 테스트 — 데이터 로드와 차트 렌더링만"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import gspread
import json
import os
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.auth.transport.requests import Request

st.set_page_config(page_title="테스트", layout="wide")

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")
SPREADSHEET_ID = "1y9mZirj81sR2tkkGV_wTzFvJonPdJU-JuErSRDo_73E"
SHEET_NAME = "📅 일별 트래킹"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

st.title("🧪 대시보드 테스트")

try:
    # ① 인증
    st.write("**Step 1: Google OAuth 인증...**")
    creds = OAuthCredentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    st.success("✅ 인증 성공!")

    # ② Google Sheets 연결
    st.write("**Step 2: Google Sheets 연결...**")
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    raw = ws.get("A2:W40", value_render_option="UNFORMATTED_VALUE")
    st.success(f"✅ Sheets 연결 성공! ({len(raw)}행)")

    # ③ 데이터 파싱
    st.write("**Step 3: 데이터 파싱...**")
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
    visitors    = safe_num(headers[10])
    purchases   = safe_num(headers[11])

    result = pd.DataFrame({
        "날짜":       date_col.values,
        "광고비":     spend.values,
        "노출수":     impressions.values,
        "방문자":     visitors.values,
        "구매":       purchases.values,
    })

    st.success(f"✅ 데이터 파싱 성공! ({len(result)}행)")
    st.dataframe(result.head(10))

    # ④ 차트 렌더링
    st.write("**Step 4: 차트 렌더링...**")

    # 데이터 상태 확인
    st.write("**데이터 타입 확인:**")
    st.write(f"- result['날짜'].dtype: {result['날짜'].dtype}")
    st.write(f"- result['방문자'].dtype: {result['방문자'].dtype}")
    st.write(f"- result['광고비'].dtype: {result['광고비'].dtype}")
    st.write(f"- 날짜 샘플: {result['날짜'].tolist()[:5]}")
    st.write(f"- 방문자 샘플: {result['방문자'].tolist()[:5]}")
    st.write(f"- 광고비 샘플: {result['광고비'].tolist()[:5]}")

    # x축을 카테고리형으로 명시
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(
        x=result["날짜"].astype(str).values,  # 명시적으로 문자열로 변환
        y=result["방문자"].values,
        name="방문자",
        mode="lines+markers",
        fill="tozeroy",
        fillcolor="rgba(79,142,247,0.12)",
        line=dict(color="#4F8EF7", width=2),
        hovertemplate="<b>%{x}</b><br>방문자: %{y:,}명<extra></extra>",
    ), secondary_y=False)

    fig.add_trace(go.Bar(
        x=result["날짜"].astype(str).values,  # 명시적으로 문자열로 변환
        y=result["광고비"].values,
        name="광고비",
        marker_color="rgba(232,255,77,0.7)",
        marker_line_color="#E8FF4D",
        marker_line_width=1,
        hovertemplate="<b>%{x}</b><br>광고비: %{y:,}원<extra></extra>",
    ), secondary_y=False)

    fig.update_xaxes(type="category")  # x축을 카테고리형으로 설정
    fig.update_layout(
        height=400, margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(showgrid=False, tickfont=dict(size=11)),
        yaxis=dict(showgrid=True, gridcolor="#F0F0F0", tickfont=dict(size=11), title="방문자수"),
        hovermode="x unified", barmode="overlay",
    )
    fig.update_layout(yaxis2=dict(overlaying="y", visible=False))

    st.plotly_chart(fig, use_container_width=True)
    st.success("✅ 차트 렌더링 성공!")

except Exception as e:
    st.error(f"❌ 에러: {e}")
    import traceback
    st.write(traceback.format_exc())
