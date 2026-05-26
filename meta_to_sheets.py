import os
"""
메타광고 → 구글 시트 일별 자동 기록 스크립트
매일 실행하면 어제 광고 데이터를 C~J 컬럼에 자동 입력 + W열 딥 인사이트 작성
"""
import os
import requests, gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from datetime import date, timedelta

TOKEN_FILE     = os.environ.get("GOOGLE_TOKEN_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")
META_TOKEN     = os.environ.get("META_ACCESS_TOKEN") or open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "meta_token.txt")).read().strip()
AD_ACCOUNT     = "act_1599099620677018"
SPREADSHEET_ID = "1y9mZirj81sR2tkkGV_wTzFvJonPdJU-JuErSRDo_73E"
SHEET_NAME     = "📅 일별 트래킹"

creds = Credentials.from_authorized_user_file(TOKEN_FILE, [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/analytics.readonly"
])
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
gc = gspread.authorize(creds)
ws = gc.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

yesterday = date.today() - timedelta(days=1)
date_str  = yesterday.strftime("%Y-%m-%d")
day_label = f"{yesterday.month}/{yesterday.day}"
print(f"📣 {day_label} 메타광고 데이터 수집 중...")

res = requests.get(
    f"https://graph.facebook.com/v25.0/{AD_ACCOUNT}/insights",
    params={
        "fields": "spend,impressions,clicks,ctr,cpc,actions,purchase_roas",
        "time_range": f'{{"since":"{date_str}","until":"{date_str}"}}',
        "access_token": META_TOKEN
    }
).json()

spend = impressions = clicks = ctr = cpc = purchases = roas = 0

if res.get("data"):
    d = res["data"][0]
    spend       = round(float(d.get("spend", 0)))
    impressions = int(d.get("impressions", 0))
    clicks      = int(d.get("clicks", 0))
    ctr         = round(float(d.get("ctr", 0)), 2)
    cpc         = round(float(d.get("cpc", 0)))

    for action in d.get("actions", []):
        if action["action_type"] in ("purchase", "offsite_conversion.fb_pixel_purchase"):
            purchases = int(float(action["value"]))

    for r in d.get("purchase_roas", []):
        if r.get("action_type") == "omni_purchase":
            roas = round(float(r["value"]), 2)

    print(f"   광고비: {spend:,}원 | 노출: {impressions:,} | 클릭: {clicks} | CTR: {ctr}% | 전환: {purchases} | ROAS: {roas}")
else:
    print("   광고 데이터 없음 (어제 광고 미집행)")

all_dates = ws.col_values(1)
row_idx = next((i+1 for i, d in enumerate(all_dates) if d == day_label), None)

if not row_idx:
    print(f"❌ '{day_label}' 날짜를 시트에서 찾을 수 없어요!")
else:
    ws.update(values=[[spend, impressions, clicks]], range_name=f"C{row_idx}:E{row_idx}")
    ws.update(values=[[purchases]], range_name=f"H{row_idx}")
    print(f"✅ {day_label} 메타광고 데이터 입력 완료! (행 {row_idx})")

    # ── 딥 패턴 인사이트 생성 ───────────────────────────────────────
    # 최근 14일치 데이터를 시트에서 읽어 패턴 분석
    start_row = max(3, row_idx - 13)
    end_row   = row_idx
    range_str = f"A{start_row}:W{end_row}"
    raw = ws.get(range_str)

    def col(row_vals, letter):
        idx = ord(letter.upper()) - ord('A')
        v = row_vals[idx] if idx < len(row_vals) else ""
        try: return float(v)
        except: return 0.0

    def col_str(row_vals, letter):
        idx = ord(letter.upper()) - ord('A')
        return row_vals[idx] if idx < len(row_vals) else ""

    days = []
    for r in raw:
        days.append({
            "label":      col_str(r, 'A'),
            "spend":      col(r, 'C'),
            "impressions":col(r, 'D'),
            "clicks":     col(r, 'E'),
            "ctr":        col(r, 'F'),
            "purchases_meta": col(r, 'H'),
            "visitors":   col(r, 'K'),
            "purchases_ga":   col(r, 'L'),
            "bounce":     col(r, 'N'),
            "revenue":    col(r, 'P'),
            "ch_meta":    col(r, 'Q'),
            "ch_official":col(r, 'R'),
            "ch_personal":col(r, 'S'),
            "ch_direct":  col(r, 'T'),
            "new_users":  col(r, 'U'),
            "returning":  col(r, 'V'),
        })

    today = days[-1]
    lines = []

    # ── 1. 전환 패턴 분석 (요일별 + 연속 미전환) ──────────────────
    no_conv_streak = 0
    for d in reversed(days):
        if d["purchases_ga"] == 0 and d["spend"] > 0:
            no_conv_streak += 1
        else:
            break

    conv_days = [d for d in days if d["purchases_ga"] > 0]
    total_spend_window = sum(d["spend"] for d in days if d["spend"] > 0)
    total_conv_window  = sum(d["purchases_ga"] for d in days)
    cpo_window = round(total_spend_window / total_conv_window) if total_conv_window > 0 else 0

    if today["purchases_ga"] > 0:
        cpo_today = round(today["spend"] / today["purchases_ga"]) if today["spend"] > 0 else 0
        label = today["label"]
        channels = {
            "메타광고": today["ch_meta"],
            "공식인스타": today["ch_official"],
            "개인인스타": today["ch_personal"],
            "직접방문": today["ch_direct"]
        }
        top_ch = max(channels, key=channels.get)
        lines.append(
            f"🛍 구매 {int(today['purchases_ga'])}건 발생. 전환 유입 1위는 {top_ch}({int(channels[top_ch])}명). "
            f"오늘 CPO {cpo_today:,}원 (최근 {len(days)}일 평균 CPO {cpo_window:,}원). "
            + ("CPO가 평균보다 낮음 → 오늘 소재·타겟 조합 유지 권장." if cpo_today <= cpo_window and cpo_window > 0
               else "CPO가 평균보다 높음 → 전환 채널 효율 점검 필요.")
        )
        if today["spend"] > 0 and today["revenue"] > 0:
            roas_calc = round(today["revenue"] / today["spend"], 1)
            lines.append(
                f"광고 ROAS {roas_calc}배 "
                + ("— 수익권. 예산 증액 검토 가능." if roas_calc >= 3
                   else "— 손익분기 미달. 타겟 또는 소재 최적화 선행 필요.")
            )
    else:
        if no_conv_streak >= 3 and today["spend"] > 0:
            total_no_conv_spend = sum(d["spend"] for d in days[-no_conv_streak:])
            lines.append(
                f"⚠️ {no_conv_streak}일 연속 전환 0건 (누적 광고비 {total_no_conv_spend:,}원 소진). "
                f"클릭은 발생하고 있으나 구매로 이어지지 않음 — 상품 상세페이지 내 구매 버튼 위치·가격·리뷰 수 점검, "
                f"또는 현재 타겟 오디언스가 실제 구매층과 불일치할 가능성 높음. "
                f"소재 전면 교체 또는 타겟 리셋(구매 전환 유사 타겟으로 전환) 검토."
            )
        elif today["spend"] > 0 and today["clicks"] >= 20:
            lines.append(
                f"🔍 클릭 {int(today['clicks'])}회 발생했으나 구매 0건. "
                f"클릭→구매 병목 발생 구간: 상품페이지(구매버튼 CTA, 리뷰 부재) 또는 결제 단계(배송비 노출 시점). "
                f"GA4 퍼널에서 어느 단계 이탈률이 높은지 확인 필요."
            )
        elif today["spend"] > 0:
            lines.append(f"📉 오늘 전환 없음. 광고비 {today['spend']:,}원 집행.")

    # ── 2. 메타 유입 품질 분석 (이탈율 vs 오가닉 비교) ────────────
    organic_days = [d for d in days if d["spend"] == 0 and d["visitors"] > 0 and d["bounce"] > 0]
    ad_days      = [d for d in days if d["spend"] > 0 and d["visitors"] > 0 and d["bounce"] > 0]

    if organic_days and ad_days and today["spend"] > 0:
        avg_bounce_organic = sum(d["bounce"] for d in organic_days) / len(organic_days)
        avg_bounce_ad      = sum(d["bounce"] for d in ad_days) / len(ad_days)
        bounce_gap = round(avg_bounce_ad - avg_bounce_organic, 1)
        if bounce_gap >= 10:
            lines.append(
                f"⚠️ 광고 집행일 평균 이탈율 {avg_bounce_ad:.1f}% vs 오가닉 {avg_bounce_organic:.1f}% "
                f"(+{bounce_gap}%p 차이). 광고로 유입되는 타겟이 실제 구매 의향 고객과 다를 가능성 — "
                f"광고 소재 이미지·문구가 실제 상품과 다른 기대를 심어주는지 점검. "
                f"랜딩 페이지를 신상품/베스트 상품 직링크로 변경하면 이탈율 개선 효과 있음."
            )
        elif today["bounce"] > 0:
            if today["bounce"] >= 60:
                lines.append(
                    f"🔶 오늘 이탈율 {today['bounce']}% — 오가닉 평균({avg_bounce_organic:.1f}%)보다 높음. "
                    f"광고 소재 또는 랜딩 페이지 일관성 확인 필요."
                )
            else:
                lines.append(f"✅ 이탈율 {today['bounce']}% — 오가닉 평균 수준. 랜딩 경험 양호.")
    elif today["bounce"] > 0:
        if today["bounce"] >= 65:
            lines.append(
                f"⚠️ 이탈율 {today['bounce']}% — 첫 페이지에서 다수 이탈. "
                f"로딩 속도, 메인 이미지 품질, 가격 노출 위치 점검 권장."
            )
        elif today["bounce"] >= 50:
            lines.append(f"🔶 이탈율 {today['bounce']}% — 보통 수준. 상품 페이지 CTA 개선 여지 있음.")
        else:
            lines.append(f"✅ 이탈율 {today['bounce']}% — 양호.")

    # ── 3. UTM 추적 신뢰성 점검 ────────────────────────────────────
    if today["spend"] > 0 and today["clicks"] >= 10:
        utm_capture_rate = today["ch_meta"] / today["clicks"] * 100 if today["clicks"] > 0 else 0
        if utm_capture_rate < 30 and today["ch_meta"] < today["clicks"] * 0.3:
            lines.append(
                f"🚨 UTM 추적 이상: 메타 클릭 {int(today['clicks'])}회인데 GA4 메타 유입 {int(today['ch_meta'])}명 "
                f"(포착률 {utm_capture_rate:.0f}%). 광고 URL에 UTM 파라미터(utm_source=meta&utm_medium=paid_feed) "
                f"누락 가능성 — 메타 광고관리자에서 URL 파라미터 설정 확인 필요."
            )

    # ── 4. 재방문자 인사이트 ────────────────────────────────────────
    if today["returning"] > 0 and today["visitors"] > 0:
        ret_pct = round(today["returning"] / today["visitors"] * 100)
        if ret_pct >= 25:
            lines.append(
                f"🔁 재방문자 {int(today['returning'])}명({ret_pct}%) — 브랜드에 관심 있는 잠재 구매층 형성 중. "
                f"이들을 전환시키는 가장 효과적인 방법: 첫 구매 할인 쿠폰 팝업 + 장바구니 리타겟팅 광고 집행. "
                f"재방문자가 증가하는데 전환이 없다면 구매 결정 장벽(가격·리뷰·배송비)이 문제."
            )
        elif today["returning"] > 0:
            prev_days_with_ret = [d for d in days[:-1] if d["returning"] > 0]
            if prev_days_with_ret:
                prev_avg_ret = sum(d["returning"] for d in prev_days_with_ret) / len(prev_days_with_ret)
                if today["returning"] > prev_avg_ret * 1.3:
                    lines.append(
                        f"🔁 재방문자 {int(today['returning'])}명 — 최근 평균 대비 증가. 리타겟팅 광고 집행 타이밍."
                    )

    # ── 5. 광고 소재 효율 ───────────────────────────────────────────
    if today["spend"] > 0:
        recent_ad_ctrs = [d["ctr"] for d in days if d["spend"] > 0 and d["ctr"] > 0]
        avg_ctr = sum(recent_ad_ctrs) / len(recent_ad_ctrs) if recent_ad_ctrs else 0
        if today["ctr"] > 0:
            if today["ctr"] < avg_ctr * 0.7:
                lines.append(
                    f"📉 CTR {today['ctr']}% — 최근 평균({avg_ctr:.2f}%) 대비 저하. 소재 피로 신호. "
                    f"이미지 교체 또는 문구 A/B 테스트 시작 권장."
                )
            elif today["ctr"] >= avg_ctr * 1.3 and today["ctr"] >= 2.0:
                lines.append(
                    f"📣 CTR {today['ctr']}% — 최근 평균({avg_ctr:.2f}%) 대비 높음. 현재 소재 반응 좋음. "
                    f"예산 증액 고려."
                )

    # ── 최종 fallback ───────────────────────────────────────────────
    if not lines:
        if today["spend"] == 0 and today["visitors"] == 0:
            lines.append("광고 미집행, 방문자 없음.")
        elif today["spend"] == 0:
            lines.append(f"광고 미집행일. 방문자 {int(today['visitors'])}명 (오가닉 유입).")
        else:
            lines.append("데이터 수집 완료. 분석 기준 데이터 부족.")

    comment = "\n".join(lines)
    ws.update(values=[[comment]], range_name=f"W{row_idx}")
    print(f"💬 딥 인사이트 작성 완료!")
    print(f"\n{comment}")
