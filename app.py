import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime

# [수정] 7번째 줄: 마케터님의 요청대로 직관적인 관리를 위해 상단 변수로 고정합니다.
API_KEY = "d751b84b1cddd360058fb9998209b7811509a33157139039547109ea9f494067"

# 대시보드 환경 설정
st.set_page_config(page_title="사업자등록 상태 조회기 PRO", page_icon="📈", layout="wide")
st.title("📈 기업 파트너 상태 검증 대시보드")
st.write("---")

# 사용자별 세션 격리 (조회 이력 저장소)
if "search_history" not in st.session_state:
    st.session_state["search_history"] = []

# 데이터 효율화 및 국세청 전용 URL 파라미터 처리 (인증키 특수문자 깨짐 결함 해결)
@st.cache_data(ttl=600)  
def fetch_business_status(biz_number, api_key):
    url = "https://api.odcloud.kr/api/nts-businessman/v1/status"
    
    # [인증키 결함 해결] serviceKey를 params 구조로 넘겨야 특수문자가 안전하게 국세청으로 전달됩니다.
    params = {"serviceKey": api_key}
    payload = json.dumps({"b_no": [biz_number]})
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    
    try:
        response = requests.post(url, params=params, headers=headers, data=payload)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        return None

# UI 레이아웃 분할
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("🔍 단건 조회")
    biz_no = st.text_input("사업자번호 10자리 (- 제외)", max_chars=10, placeholder="1234567890")
    
    if st.button("조회하기", type="primary"):
        if len(biz_no) != 10 or not biz_no.isdigit():
            st.error("⚠️ 10자리 숫자만 입력해 주세요.")
        elif not API_KEY or "진짜_인증키" in API_KEY:
            st.error("⚠️ 코드 상단의 API_KEY 변수에 실제 인증키를 입력해 주세요.")
        else:
            with st.spinner("국세청 확인 중..."):
                result = fetch_business_status(biz_no, API_KEY)
                
                if result and "data" in result and len(result["data"]) > 0:
                    info = result["data"][0]
                    status_code = info.get("b_stt_cd", "")  # 01: 계속, 02: 휴업, 03: 폐업
                    status_text = info.get("b_stt", "")
                    tax_type = info.get("tax_type", "등록되지 않은 번호")
                    
                    if not status_text:
                        status_text = "미등록 사업자"
                        status_code = "99"
                    
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 상태별 직관적 화면 출력
                    if status_code == "01": st.success(f"🟢 {status_text}")
                    elif status_code == "02": st.warning(f"🟡 {status_text}")
                    elif status_code == "03": st.error(f"🔴 {status_text} (폐업일: {info.get('end_dt', '-')})")
                    else: st.error(f"❌ {tax_type}")
                    
                    # 히스토리 데이터 구조화 및 적재
                    history_entry = {
                        "조회시간": current_time,
                        "사업자번호": biz_no,
                        "상태": status_text if status_code != "99" else "조회 실패",
                        "과세유형": tax_type
                    }
                    
                    if not st.session_state["search_history"] or st.session_state["search_history"][0]["사업자번호"] != biz_no:
                        st.session_state["search_history"].insert(0, history_entry)
                else:
                    st.error("❌ 국세청 API 응답을 받지 못했습니다. 인증키를 확인해 주세요.")

with col2:
    st.subheader("📊 실시간 조회 이력 관리")
    if st.session_state["search_history"]:
        df = pd.DataFrame(st.session_state["search_history"])
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 현재까지 조회 이력 다운로드 (CSV)",
            data=csv,
            file_name=f"biz_status_history_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("조회된 이력이 없습니다.")