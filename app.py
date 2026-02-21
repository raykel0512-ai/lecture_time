import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar

st.set_page_config(page_title="2026 강사 시수 관리 Pro", layout="wide")

# 1. 구글 시트 연결 설정
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. 세션 상태 초기화 (데이터를 메모리에 상주시켜 실시간 반응 유도)
if 'ins_df' not in st.session_state:
    try:
        # 첫 로딩 시에만 구글에서 가져옴
        st.session_state.ins_df = conn.read(worksheet="Instructors", ttl=0)
        # 숫자 변환
        num_cols = ['rate', 'mon', 'tue', 'wed', 'thu', 'fri']
        for col in num_cols:
            if col in st.session_state.ins_df.columns:
                st.session_state.ins_df[col] = pd.to_numeric(st.session_state.ins_df[col], errors='coerce').fillna(0)
    except:
        st.session_state.ins_df = pd.DataFrame()

if 'excl_df' not in st.session_state:
    try:
        st.session_state.excl_df = conn.read(worksheet="Exclusions", ttl=0)
    except:
        st.session_state.excl_df = pd.DataFrame()

# 2026년 공휴일
HOLIDAYS = [date(2026,3,1), date(2026,3,2), date(2026,5,5), date(2026,5,24), date(2026,5,25), 
            date(2026,6,6), date(2026,8,15), date(2026,8,17), date(2026,9,24), date(2026,9,25), 
            date(2026,9,26), date(2026,9,28), date(2026,10,3), date(2026,10,9), date(2026,12,25)]

st.title("🚀 2026 강사 시수 관리 시스템")

# --- 사이드바 ---
with st.sidebar:
    st.header("👤 1. 강사 등록")
    with st.form("ins_form", clear_on_submit=True):
        name = st.text_input("강사 이름")
        rate = st.number_input("시간당 단가", value=30000, step=1000)
        mon = st.number_input("월요일", min_value=0.0, value=0.0)
        tue = st.number_input("화요일", min_value=0.0, value=0.0)
        wed = st.number_input("수요일", min_value=0.0, value=0.0)
        thu = st.number_input("목요일", min_value=0.0, value=0.0)
        fri = st.number_input("금요일", min_value=0.0, value=0.0)
        
        if st.form_submit_button("강사 정보 저장"):
            new_row = pd.DataFrame([{"name": name, "rate": rate, "mon": mon, "tue": tue, "wed": wed, "thu": thu, "fri": fri}])
            # 1. 메모리(세션)에 즉시 반영
            st.session_state.ins_df = pd.concat([st.session_state.ins_df, new_row], ignore_index=True).drop_duplicates(subset=['name'], keep='last')
            # 2. 구글 시트 업데이트
            conn.update(worksheet="Instructors", data=st.session_state.ins_df)
            st.success("저장되었습니다!"); st.rerun()

    st.header("🚫 2. 제외 일정 추가")
    new_range = st.date_input("새 제외 기간 선택", value=(date(2026, 7, 20), date(2026, 8, 20)))
    note = st.text_input("메모")
    if st.button("제외 기간 추가"):
        if isinstance(new_range, tuple) and len(new_range) == 2:
            new_ex = pd.DataFrame([{"start_date": new_range[0].isoformat(), "end_date": new_range[1].isoformat(), "note": note}])
            # 1. 메모리에 즉시 반영
            st.session_state.excl_df = pd.concat([st.session_state.excl_df, new_ex], ignore_index=True)
            # 2. 구글 시트 업데이트
            conn.update(worksheet="Exclusions", data=st.session_state.excl_df)
            st.success("추가되었습니다!"); st.rerun()

    st.divider()
    if st.button("🔄 구글 시트에서 강제 새로고침"):
        del st.session_state.ins_df
        del st.session_state.excl_df
        st.rerun()

# --- 메인 화면 ---
if st.session_state.ins_df.empty:
    st.info("데이터가 없습니다. 사이드바에서 강사를 등록하세요.")
else:
    st.subheader("🗓️ 전체 제외 일정 관리 (수정 후 저장 버튼을 누르세요)")
    # data_editor는 메모리상의 데이터를 직접 수정함
    edited_excl = st.data_editor(st.session_state.excl_df, num_rows="dynamic", use_container_width=True)
    if st.button("수정사항 시트에 최종 저장"):
        st.session_state.excl_df = edited_excl
        conn.update(worksheet="Exclusions", data=edited_excl)
        st.success("구글 시트에 동기화되었습니다!"); st.rerun()

    st.divider()
    
    # 강사 선택 및 계산 (이후 로직은 동일하지만 st.session_state를 참조함)
    instructor_list = st.session_state.ins_df['name'].unique()
    target = st.selectbox("조회할 강사 선택", instructor_list)
    
    row = st.session_state.ins_df[st.session_state.ins_df['name'] == target].iloc[-1]
    hours_map = {0: float(row['mon']), 1: float(row['tue']), 2: float(row['wed']), 
                 3: float(row['thu']), 4: float(row['fri'])}
    
    all_excluded_dates = set()
    for _, ex in st.session_state.excl_df.iterrows():
        try:
            sd = date.fromisoformat(str(ex['start_date']))
            ed = date.fromisoformat(str(ex['end_date']))
            curr = sd
            while curr <= ed:
                all_excluded_dates.add(curr)
                curr += timedelta(days=1)
        except: continue

    work_data = []
    current = date(2026, 3, 1)
    while current <= date(2026, 12, 31):
        if current.weekday() < 5:
            h = hours_map.get(current.weekday(), 0)
            if h > 0 and not (current in HOLIDAYS or current in all_excluded_dates):
                work_data.append(current)
        current += timedelta(days=1)

    # 요약 및 달력 출력 (이전 코드와 동일)
    total_hours = sum([hours_map[d.weekday()] for d in work_data])
    c1, c2, c3 = st.columns(3)
    c1.metric("총 수업 횟수", f"{len(work_data)}회")
    c2.metric("총 수업 시수", f"{total_hours:g}시간")
    c3.metric("연간 예상 총액", f"{int(total_hours * row['rate']):,}원")

    st.divider()
    st.subheader("📅 2026년 월별 수업 일정")
    cols = st.columns(2)
    for m in range(3, 13):
        with cols[(m-3)%2]:
            st.write(f"#### 🗓️ {m}월")
            cal = calendar.monthcalendar(2026, m)
            weekdays_only = [week[0:5] for week in cal]
            df = pd.DataFrame(weekdays_only, columns=["월","화","수","목","금"])
            month_work_dates = [d for d in work_data if d.month == m]
            m_h = sum([hours_map[d.weekday()] for d in month_work_dates])
            
            def style(v):
                if v == 0: return ""
                d = date(2026, m, v)
                if d in month_work_dates: return 'background-color: #90EE90; font-weight: bold; color: black'
                if d in HOLIDAYS or d in all_excluded_dates: return 'background-color: #FFB6C1; color: black'
                return ""
            st.table(df.style.applymap(style))
            st.info(f"💰 **{m}월 급여:** {int(m_h * row['rate']):,}원 ({m_h:g}시간)")
