import streamlit as st
import requests
import json
import pandas as pd
import time
from datetime import datetime

# [보안 규칙] 스트림릿 금고(Secrets)에서 마케터님의 단일 인증키를 안전하게 읽어옵니다.
API_KEY = st.secrets["API_KEY"]

st.set_page_config(page_title="사업자번호 휴/폐업여부 판별", page_icon="📊", layout="wide")
st.title("📊휴/폐업 사업자 검증 대시보드 (Single Key 5,000건+)")
st.markdown("100개 이상의 사업자번호를 조회할 경우 시간이 소요될 수 있습니다.")
st.write("---")

if "search_history" not in st.session_state:
    st.session_state["search_history"] = []

# 국세청 단일 청크(100개) 전송 함수 (단일 인증키 고정 사용)
def fetch_chunk_status(biz_numbers, api_key):
    url = "https://api.odcloud.kr/api/nts-businessman/v1/status"
    params = {"serviceKey": api_key}
    payload = json.dumps({"b_no": biz_numbers})
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    
    try:
        response = requests.post(url, params=params, headers=headers, data=payload)
        return response.status_code, response.json() if response.status_code == 200 else None
    except:
        return 500, None

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📥 사업자번호 입력")
    raw_input = st.text_area(
        "엑셀이나 메모장에서 몇 천 개의 사업자번호를 값복사하여 그대로 붙여넣으세요. (줄바꿈 필수)",
        height=350,
        placeholder="123-45-67890\n9876543210\n..."
    )
    
    if st.button("🚀 사업자번호 조회 시작", type="primary"):
        lines = raw_input.split('\n')
        
        # 데이터 정제 파이프라인: 하이픈/공백 제거 후 정상 10자리 숫자만 필터링 (잘못된 형식은 자동 Skip)
        processed_nos = []
        for line in lines:
            clean_no = line.replace("-", "").replace(" ", "").strip()
            if len(clean_no) == 10 and clean_no.isdigit():
                processed_nos.append(clean_no)
        
        total_count = len(processed_nos)
        
        if total_count == 0:
            st.error("⚠️ 입력된 데이터 중 유효한 사업자등록번호(10자리)가 없습니다.")
        elif not API_KEY:
            st.error("⚠️ 스트림릿 Secrets 설정에 API_KEY가 등록되지 않았습니다.")
        else:
            # 🟢 [핵심 알고리즘] 100개씩 쪼개서 연속으로 요청을 날리는 루프 실행
            chunk_size = 100
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 실시간 진행 상황을 보여줄 빈 모니터 생성
            status_monitor = st.empty()
            
            for i in range(0, total_count, chunk_size):
                # 5000개 중 현재 윈도우(예: 0~100번째, 100~200번째...)를 칼같이 슬라이싱
                chunk = processed_nos[i:i + chunk_size]
                
                status_monitor.info(f"⏳ 전체 {total_count}건 중 {i}번째 항목부터 {min(i + chunk_size, total_count)}건째 처리 중...")
                
                # 국세청 API 호출
                status_code, result = fetch_chunk_status(chunk, API_KEY)
                
                # 🛑 일일 할당량 한도(Quota) 초과 또는 국세청 서버 에러 발생 시 처리
                if status_code != 200 or not result or "data" not in result:
                    failed_start_no = chunk[0]
                    formatted_failed_no = f"{failed_start_no[:3]}-{failed_start_no[3:5]}-{failed_start_no[5:]}"
                    
                    st.error(f"❌ [ '{formatted_failed_no}'부터 할당량 초과로 검증에 실패했습니다. ]")
                    st.warning(f"⚠️ 일일 할당량이 소진되어 {i}번째까지만 조회된 데이터가 우측 이력에 안전하게 저장되었습니다.")
                    break # 조회를 중단하고 직전까지 성공한 소중한 수천 건의 데이터를 화면에 지킵니다.
                
                # 결과 가공 및 실시간 표 적재
                for info in result["data"]:
                    biz_no = info.get("b_no", "")
                    status_code_str = info.get("b_stt_cd", "")
                    status_text = info.get("b_stt", "미등록 사업자")
                    tax_type = info.get("tax_type", "등록되지 않은 번호")
                    
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
                
                # 국세청 서버 부하 방지 및 안정적인 조회를 위한 미세 딜레이 (0.2초)
                time.sleep(0.2)
                
            # 모든 루프가 에러 없이 끝나면 성공 메시지 출력
            if status_code == 200 and result:
                status_monitor.success(f"🎉 총 {total_count}개 사업자번호 검증이 완료됐습니다!")

with col2:
    st.subheader("📊사업자번호 휴/폐업 조회 결과 및 이력 관리")
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
        st.info("왼쪽 입력창에 사업자등록번호를 넣고 [휴/폐업 조회 시작] 버튼을 누르세요.")
