import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar

st.set_page_config(page_title="2026 강사 관리 Pro", layout="wide")

# 1. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    # Instructors: name, rate, mon, tue, wed, thu, fri, sat, sun
    ins_df = conn.read(worksheet="Instructors", ttl=0)
    # Exclusions: start_date, end_date, note
    excl_df = conn.read(worksheet="Exclusions", ttl=0)
    return ins_df, excl_df

ins_df, excl_df = load_data()

# 2026년 공휴일
HOLIDAYS = [date(2026,3,1), date(2026,3,2), date(2026,5,5), date(2026,5,24), date(2026,5,25), 
            date(2026,6,6), date(2026,8,15), date(2026,8,17), date(2026,9,24), date(2026,9,25), 
            date(2026,9,26), date(2026,9,28), date(2026,10,3), date(2026,10,9), date(2026,12,25)]

st.title("🚀 2026 강사 시수 관리 시스템 (Pro)")

# --- 사이드바: 설정 ---
with st.sidebar:
    st.header("👤 1. 강사 정보 등록/수정")
    with st.form("ins_form"):
        name = st.text_input("강사 이름")
        rate = st.number_input("시간당 단가", value=30000, step=1000)
        st.write("--- 요일별 수업 시간(시수) ---")
        mon = st.number_input("월요일", min_value=0, max_value=24, value=0)
        tue = st.number_input("화요일", min_value=0, max_value=24, value=0)
        wed = st.number_input("수요일", min_value=0, max_value=24, value=0)
        thu = st.number_input("목요일", min_value=0, max_value=24, value=0)
        fri = st.number_input("금요일", min_value=0, max_value=24, value=0)
        sat = st.number_input("토요일", min_value=0, max_value=24, value=0)
        sun = st.number_input("일요일", min_value=0, max_value=24, value=0)
        
        if st.form_submit_button("강사 정보 시트에 저장"):
            new_row = pd.DataFrame([{
                "name": name, "rate": rate, 
                "mon": mon, "tue": tue, "wed": wed, "thu": thu, "fri": fri, "sat": sat, "sun": sun
            }])
            # 기존 동일 이름 삭제 후 추가(업데이트 로직)
            if not ins_df.empty:
                ins_df = ins_df[ins_df['name'] != name]
            updated_ins = pd.concat([ins_df, new_row], ignore_index=True)
            conn.update(worksheet="Instructors", data=updated_ins)
            st.success("저장되었습니다!"); st.rerun()

    st.header("🚫 2. 제외 일정 관리 (방학 등)")
    # 기간 선택기로 쉽게 입력
    new_range = st.date_input("새 제외 기간 선택", value=(date(2026, 7, 20), date(2026, 8, 20)))
    note = st.text_input("메모(예: 여름방학)")
    if st.button("제외 기간 추가"):
        if len(new_range) == 2:
            new_ex = pd.DataFrame([{"start_date": new_range[0].isoformat(), "end_date": new_range[1].isoformat(), "note": note}])
            updated_ex = pd.concat([excl_df, new_ex], ignore_index=True)
            conn.update(worksheet="Exclusions", data=updated_ex)
            st.success("제외 기간 추가 완료!"); st.rerun()

# --- 메인 화면 ---
if ins_df.empty:
    st.info("왼쪽에서 강사를 먼저 등록해주세요.")
else:
    # 1. 제외 일정 편집기 (여기서 직접 삭제/수정 가능)
    st.subheader("🗓️ 전체 제외 일정 관리")
    edited_excl = st.data_editor(excl_df, num_rows="dynamic", use_container_width=True, key="excl_editor")
    if st.button("제외 일정 수정사항 저장"):
        conn.update(worksheet="Exclusions", data=edited_excl)
        st.success("제외 일정이 업데이트되었습니다!"); st.rerun()

    st.divider()

    # 2. 강사별 결과 조회
    target = st.selectbox("조회할 강사 선택", ins_df['name'].unique())
    row = ins_df[ins_df['name'] == target].iloc[-1]
    
    # 요일별 시수 매핑 (월:0 ~ 일:6)
    hours_map = {0: row['mon'], 1: row['tue'], 2: row['wed'], 3: row['thu'], 4: row['fri'], 5: row['sat'], 6: row['sun']}
    
    # 모든 제외 날짜를 하나의 세트로 생성
    all_excluded_dates = set()
    for _, ex in edited_excl.iterrows():
        try:
            sd = date.fromisoformat(str(ex['start_date']))
            ed = date.fromisoformat(str(ex['end_date']))
            curr = sd
            while curr <= ed:
                all_excluded_dates.add(curr)
                curr += timedelta(days=1)
        except: continue

    # 수업일 및 총 시간 계산
    work_data = []
    total_hours = 0
    current = date(2026, 3, 1)
    while current <= date(2026, 12, 31):
        day_hours = hours_map[current.weekday()]
        if day_hours > 0:
            if not (current in HOLIDAYS or current in all_excluded_dates):
                work_data.append(current)
                total_hours += day_hours
        current += timedelta(days=1)

    # 요약 통계
    c1, c2, c3 = st.columns(3)
    c1.metric("총 수업 횟수", f"{len(work_data)}회")
    c2.metric("총 수업 시수", f"{total_hours}시간")
    c3.metric("예상 급여액", f"{total_hours * row['rate']:,}원")

    # 달력 시각화
    st.subheader("📅 2026년 수업 달력 (초록: 수업, 분홍: 제외)")
    cols = st.columns(3)
    for m in range(3, 13):
        with cols[(m-3)%3]:
            st.write(f"**{m}월**")
            cal = calendar.monthcalendar(2026, m)
            df = pd.DataFrame(cal, columns=["월","화","수","목","금","토","일"])
            def style(v):
                if v == 0: return ""
                d = date(2026, m, v)
                if d in work_data: return 'background-color: #90EE90; font-weight: bold'
                if d in HOLIDAYS or d in all_excluded_dates: return 'background-color: #FFB6C1'
                return ""
            st.table(df.style.applymap(style))

    # 월별 상세 내역
    st.subheader("💵 월별 상세 통계")
    monthly_stats = []
    for m in range(3, 13):
        m_dates = [d for d in work_data if d.month == m]
        m_hours = sum([hours_map[d.weekday()] for d in m_dates])
        monthly_stats.append({"월": f"{m}월", "횟수": f"{len(m_dates)}회", "시수": f"{m_hours}시간", "급여": f"{m_hours * row['rate']:,}원"})
    st.dataframe(pd.DataFrame(monthly_stats), use_container_width=True)
