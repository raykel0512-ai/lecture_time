import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar

st.set_page_config(page_title="2026 평일 시수 관리", layout="wide")

# 1. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    # 데이터 읽어오기
    ins_df = conn.read(worksheet="Instructors", ttl=0)
    excl_df = conn.read(worksheet="Exclusions", ttl=0)
    
    # [핵심 수정] 강사 데이터의 숫자 컬럼들을 강제로 숫자형으로 변환
    # 빈칸(NaN)은 0으로 채웁니다.
    num_cols = ['rate', 'mon', 'tue', 'wed', 'thu', 'fri']
    if not ins_df.empty:
        for col in num_cols:
            if col in ins_df.columns:
                ins_df[col] = pd.to_numeric(ins_df[col], errors='coerce').fillna(0)
    
    return ins_df, excl_df

ins_df, excl_df = load_data()

# 2026년 공휴일
HOLIDAYS = [date(2026,3,1), date(2026,3,2), date(2026,5,5), date(2026,5,24), date(2026,5,25), 
            date(2026,6,6), date(2026,8,15), date(2026,8,17), date(2026,9,24), date(2026,9,25), 
            date(2026,9,26), date(2026,9,28), date(2026,10,3), date(2026,10,9), date(2026,12,25)]

st.title("🚀 2026 강사 시수 관리 (주말 제외)")

# --- 사이드바 ---
with st.sidebar:
    st.header("👤 1. 강사 등록 (월~금)")
    with st.form("ins_form"):
        name = st.text_input("강사 이름")
        rate = st.number_input("시간당 단가", value=30000, step=1000)
        st.write("--- 평일 수업 시간(시수) ---")
        mon = st.number_input("월요일", min_value=0, max_value=24, value=0)
        tue = st.number_input("화요일", min_value=0, max_value=24, value=0)
        wed = st.number_input("수요일", min_value=0, max_value=24, value=0)
        thu = st.number_input("목요일", min_value=0, max_value=24, value=0)
        fri = st.number_input("금요일", min_value=0, max_value=24, value=0)
        
        if st.form_submit_button("강사 정보 저장"):
            new_row = pd.DataFrame([{
                "name": name, "rate": rate, 
                "mon": mon, "tue": tue, "wed": wed, "thu": thu, "fri": fri
            }])
            if not ins_df.empty:
                ins_df = ins_df[ins_df['name'] != name]
            updated_ins = pd.concat([ins_df, new_row], ignore_index=True)
            conn.update(worksheet="Instructors", data=updated_ins)
            st.success("저장되었습니다!"); st.rerun()

    st.header("🚫 2. 제외 일정 관리")
    new_range = st.date_input("새 제외 기간 선택", value=(date(2026, 7, 20), date(2026, 8, 20)))
    note = st.text_input("메모(예: 여름방학)")
    if st.button("제외 기간 추가"):
        if len(new_range) == 2:
            new_ex = pd.DataFrame([{"start_date": new_range[0].isoformat(), "end_date": new_range[1].isoformat(), "note": note}])
            updated_ex = pd.concat([excl_df, new_ex], ignore_index=True)
            conn.update(worksheet="Exclusions", data=updated_ex)
            st.success("추가 완료!"); st.rerun()

# --- 메인 화면 ---
if ins_df.empty:
    st.info("왼쪽에서 강사를 먼저 등록해주세요.")
else:
    st.subheader("🗓️ 전체 제외 일정 관리")
    edited_excl = st.data_editor(excl_df, num_rows="dynamic", use_container_width=True, key="excl_editor")
    if st.button("제외 일정 수정사항 저장"):
        conn.update(worksheet="Exclusions", data=edited_excl)
        st.success("업데이트되었습니다!"); st.rerun()

    st.divider()

    target = st.selectbox("조회할 강사 선택", ins_df['name'].unique())
    # 선택된 강사 데이터 추출
    row = ins_df[ins_df['name'] == target].iloc[-1]
    
    # 시수 매핑 시 한 번 더 숫자형으로 확인
    hours_map = {
        0: float(row['mon']), 1: float(row['tue']), 2: float(row['wed']), 
        3: float(row['thu']), 4: float(row['fri'])
    }
    
    all_excluded_dates = set()
    if not edited_excl.empty:
        for _, ex in edited_excl.iterrows():
            try:
                sd = date.fromisoformat(str(ex['start_date']))
                ed = date.fromisoformat(str(ex['end_date']))
                curr = sd
                while curr <= ed:
                    all_excluded_dates.add(curr)
                    curr += timedelta(days=1)
            except: continue

    work_data = []
    total_hours = 0.0
    current = date(2026, 3, 1)
    while current <= date(2026, 12, 31):
        if current.weekday() < 5:
            day_hours = hours_map.get(current.weekday(), 0.0)
            if day_hours > 0:
                if not (current in HOLIDAYS or current in all_excluded_dates):
                    work_data.append(current)
                    total_hours += float(day_hours)
        current += timedelta(days=1)

    c1, c2, c3 = st.columns(3)
    c1.metric("총 수업 횟수", f"{len(work_data)}회")
    c2.metric("총 수업 시수", f"{total_hours:g}시간")
    c3.metric("예상 급여액", f"{int(total_hours * row['rate']):,}원")

    # --- 주말 제외 달력 ---
    st.subheader("📅 2026년 평일 수업 달력 (월-금)")
    cols = st.columns(2)
    for m in range(3, 13):
        with cols[(m-3)%2]:
            st.write(f"#### {m}월")
            cal = calendar.monthcalendar(2026, m)
            weekdays_only = [week[0:5] for week in cal]
            df = pd.DataFrame(weekdays_only, columns=["월","화","수","목","금"])
            
            def style(v):
                if v == 0: return ""
                d = date(2026, m, v)
                if d in work_data: return 'background-color: #90EE90; font-weight: bold; color: black'
                if d in HOLIDAYS or d in all_excluded_dates: return 'background-color: #FFB6C1; color: black'
                return ""
            st.table(df.style.applymap(style))

    st.subheader("💵 월별 상세 통계")
    monthly_stats = []
    for m in range(3, 13):
        m_dates = [d for d in work_data if d.month == m]
        m_hours = sum([hours_map.get(d.weekday(), 0.0) for d in m_dates])
        monthly_stats.append({
            "월": f"{m}월", 
            "횟수": f"{len(m_dates)}회", 
            "시수": f"{m_hours:g}시간", 
            "급여": f"{int(m_hours * row['rate']):,}원"
        })
    st.dataframe(pd.DataFrame(monthly_stats), use_container_width=True)
