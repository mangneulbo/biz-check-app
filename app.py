import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime

# [보안 규칙] 스트림릿 금고(Secrets)에서 인증키를 완벽하게 연동합니다.
API_KEY = st.secrets["API_KEY"]

# 대시보드 환경 설정
st.set_page_config(page_title="사업자등록 상태 대량 조회기 PRO", page_icon="📊", layout="wide")
st.title("📊 기업 파트너 상태 대량 검증 대시보드")
st.markdown("여러 개의 사업자번호를 줄바꿈으로 입력하여 한 번에 실시간 상태 조회가 가능합니다. (최대 100개)")
st.write("---")

if "search_history" not in st.session_state:
    st.session_state["search_history"] = []

# 대량 조회용 국세청 API 연동 함수 (HTTP 상태 코드 반환 추가)
def fetch_bulk_business_status(biz_numbers, api_key):
    url = "https://api.odcloud.kr/api/nts-businessman/v1/status"
    params = {"serviceKey": api_key}
    payload = json.dumps({"b_no": biz_numbers})
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    
    try:
        response = requests.post(url, params=params, headers=headers, data=payload)
        return response.status_code, response.json() if response.status_code == 200 else None
    except Exception as e:
        return 500, None

# UI 레이아웃 분할
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📥 대량 번호 입력")
    
    raw_input = st.text_area(
        "사업자등록번호를 줄바꿈(Enter)으로 입력해 주세요. (최대 100개)",
        height=250,
        placeholder="123-45-67890\n9876543210"
    )
    
    if st.button("🚀 한 번에 조회하기", type="primary"):
        lines = raw_input.split('\n')
        
        processed_nos = []     # 공백/하이픈 제거 후 정상 10자리 번호
        too_long_nos = []      # 10자리를 초과한 잘못된 번호
        invalid_format_nos = [] # 10자리 미만이거나 숫자가 아닌 번호
        
        for line in lines:
            original_line = line.strip()
            if not original_line:
                continue
                
            # 하이픈과 공백을 무조건 제거하여 탈락 처리 후 순수 숫자만 추출
            clean_no = original_line.replace("-", "").replace(" ", "")
            
            if len(clean_no) > 10:
                too_long_nos.append(original_line)
            elif len(clean_no) == 10 and clean_no.isdigit():
                processed_nos.append(clean_no)
            else:
                invalid_format_nos.append(original_line)
        
        # ❌ 유효성 검사 1단계: 숫자가 10개가 넘는 데이터가 하나라도 있을 때 (마케터님 요청 규격)
        if too_long_nos:
            st.error("⚠️ 사업자번호는 10자리의 숫자로 이루어져 있습니다.")
            st.markdown("**글자 수가 초과된 입력값:**")
            for num in too_long_nos:
                st.markdown(f"- ❌ `{num}` (10자리 초과)")
                
        # ❌ 유효성 검사 2단계: 10자리 미만이거나 형식이 안 맞을 때
        elif invalid_format_nos and not processed_nos:
            st.error("⚠️ 입력된 번호들의 형식을 확인해 주세요. (10자리 미만 또는 문자 포함)")
            
        elif not processed_nos:
            st.error("⚠️ 입력된 사업자등록번호가 없습니다.")
            
        elif len(processed_nos) > 100:
            st.error(f"⚠️ 한 번에 최대 100개까지만 조회 가능합니다. (현재 입력: {len(processed_nos)}개)")
            
        else:
            # 🟢 모든 검증 통과 시 국세청 API 호출
            with st.spinner(f"국세청에서 {len(processed_nos)}개 기업 데이터를 실시간 확인 중..."):
                status_code, result = fetch_bulk_business_status(processed_nos, API_KEY)
                
                # 🛑 [핵심 개발] API 데이터 열람 한도 초과 및 서버 에러 발생 시 처리
                if status_code != 200 or not result or "data" not in result:
                    # 요청한 배열의 첫 번째 번호를 에러 메시지에 바인딩
                    failed_start_no = processed_nos[0]
                    formatted_failed_no = f"{failed_start_no[:3]}-{failed_start_no[3:5]}-{failed_start_no[5:]}"
                    
                    # 마케터님이 요청하신 정확한 알럿 문구 출력
                    st.error(f"❌ [ '{formatted_failed_no}'부터 할당량 초과로 검증에 실패했습니다. ]")
                    st.info("ℹ️ 공공데이터포털의 일일 호출 한도(Quota)를 초과했거나 국세청 서버의 일시적 제안이 발생했습니다.")
                
                else:
                    # 📊 정상 응답 처리 및 이력 적재
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    success_count = 0
                    
                    for info in result["data"]:
                        biz_no = info.get("b_no", "")
                        status_code_str = info.get("b_stt_cd", "")
                        status_text = info.get("b_stt", "")
                        tax_type = info.get("tax_type", "등록되지 않은 번호")
                        
                        if not status_text:
                            status_text = "미등록 사업자"
                            status_code_str = "99"
                        else:
                            success_count += 1
                        
                        end_dt = info.get('end_dt', '')
                        if end_dt and status_code_str == "03":
                            status_text += f" (폐업일: {end_dt})"
                            
                        history_entry = {
                            "조회시간": current_time,
                            "사업자번호": f"{biz_no[:3]}-{biz_no[3:5]}-{biz_no[5:]}",
                            "상태": status_text,
                            "과세유형": tax_type
                        }
                        
                        st.session_state["search_history"].insert(0, history_entry)
                    
                    st.success(f"✅ 총 {len(processed_nos)}개 기업 조회 완료 (성공: {success_count}개)")

with col2:
    st.subheader("📊 실시간 대량 조회 결과 및 이력 관리")
    if st.session_state["search_history"]:
        df = pd.DataFrame(st.session_state["search_history"])
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 전체 조회 이력 다운로드 (CSV)",
            data=csv,
            file_name=f"bulk_biz_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.info("조회된 이력이 없습니다. 왼쪽 입력창에 번호들을 넣고 대량 조회를 시작하세요.")
