import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar

st.set_page_config(page_title="실시간 2026 강사 관리", layout="wide")

# 1. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

# 데이터 불러오기 함수 (캐시를 해제하여 실시간성 확보)
def load_data():
    ins_df = conn.read(worksheet="Instructors", ttl=0)
    excl_df = conn.read(worksheet="Exclusions", ttl=0)
    return ins_df, excl_df

ins_df, excl_df = load_data()

# 2026년 공휴일
HOLIDAYS = [date(2026,3,1), date(2026,3,2), date(2026,5,5), date(2026,5,24), date(2026,5,25), 
            date(2026,6,6), date(2026,8,15), date(2026,8,17), date(2026,9,24), date(2026,9,25), 
            date(2026,9,26), date(2026,9,28), date(2026,10,3), date(2026,10,9), date(2026,12,25)]

st.title("🌐 실시간 공유형 2026 강사 관리 시스템")

# --- 사이드바: 입력 ---
with st.sidebar:
    st.header("👤 강사 등록")
    with st.form("ins_form"):
        name = st.text_input("이름")
        rate = st.number_input("시급", value=30000, step=1000)
        days = st.multiselect("요일", ["월", "화", "수", "목", "금", "토", "일"])
        if st.form_submit_button("저장"):
            day_map = {"월":"0", "화":"1", "수":"2", "목":"3", "금":"4", "토":"5", "일":"6"}
            day_str = ",".join([day_map[d] for d in days])
            new_row = pd.DataFrame([{"name": name, "rate": rate, "days": day_str}])
            updated_df = pd.concat([ins_df, new_row], ignore_index=True)
            conn.update(worksheet="Instructors", data=updated_df)
            st.success("시트에 저장되었습니다!"); st.rerun()

    st.header("🚫 날짜 제외")
    ex_date = st.date_input("제외할 날짜")
    if st.button("제외 날짜 시트에 추가"):
        new_ex = pd.DataFrame([{"date": ex_date.isoformat(), "type": "manual"}])
        updated_ex = pd.concat([excl_df, new_ex], ignore_index=True)
        conn.update(worksheet="Exclusions", data=updated_ex)
        st.success("제외 날짜 반영 완료!"); st.rerun()

# --- 메인: 조회 ---
if ins_df.empty:
    st.info("데이터가 없습니다. 강사를 등록하세요.")
else:
    target = st.selectbox("강사 선택", ins_df['name'].unique())
    row = ins_df[ins_df['name'] == target].iloc[-1]
    target_days = [int(d) for d in str(row['days']).split(",")]
    
    # 제외 날짜 리스트화
    manual_excludes = [date.fromisoformat(str(d)) for d in excl_df['date'].tolist()]
    
    # 수업일 계산 (3월-12월)
    work_dates = []
    current = date(2026, 3, 1)
    while current <= date(2026, 12, 31):
        if current.weekday() in target_days:
            if not (current in HOLIDAYS or current in manual_excludes):
                work_dates.append(current)
        current += timedelta(days=1)

    # 요약
    st.metric("총 급여", f"{len(work_dates) * row['rate']:,}원", f"총 {len(work_dates)}회")

    # 달력 시각화
    cols = st.columns(3)
    for m in range(3, 13):
        with cols[(m-3)%3]:
            st.write(f"**{m}월**")
            cal = calendar.monthcalendar(2026, m)
            df = pd.DataFrame(cal, columns=["월","화","수","목","금","토","일"])
            def style(v):
                if v == 0: return ""
                d = date(2026, m, v)
                if d in work_dates: return 'background-color: #90EE90'
                if d in HOLIDAYS or d in manual_excludes: return 'background-color: #FFB6C1'
                return ""
            st.table(df.style.applymap(style))
