"""
fill_missing_dates() 함수 실행 테스트
"""
import sys
import os

# dashboard.py에서 함수 임포트
sys.path.insert(0, '/Users/kimeunbee/Documents/nominical-dashboard')

# 필요한 라이브러리 임포트 (dashboard와 동일)
import streamlit as st
import pandas as pd

# secrets 모의 설정
class MockSecrets:
    def __init__(self):
        self.data = {}
    def __contains__(self, key):
        return False
    def __getitem__(self, key):
        return self.data.get(key)

st.secrets = MockSecrets()

# dashboard.py 실행
print("=" * 70)
print("🧪 fill_missing_dates() 실행 테스트")
print("=" * 70)
print()

try:
    # dashboard에서 함수들을 임포트
    from dashboard import fill_missing_dates

    print("✅ 함수 임포트 성공!")
    print()
    print("🚀 fill_missing_dates() 실행 중...")
    print()

    ok, msg = fill_missing_dates()

    print()
    print("=" * 70)
    if ok:
        print(f"✅ 성공: {msg}")
    else:
        print(f"❌ 실패: {msg}")
    print("=" * 70)

except Exception as e:
    print(f"❌ 에러: {e}")
    import traceback
    traceback.print_exc()
