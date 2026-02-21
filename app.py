import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar

st.set_page_config(page_title="2026 강사 관리 Pro", layout="wide")

# 1. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. 데이터 로딩 및 세션 상태 초기화
if 'ins_df' not in st.session_state:
    try:
        df = conn.read(worksheet="Instructors", ttl=0)
        # 모든 숫자 컬럼을 float로 통일하여 에러 방지
        num_cols = ['rate', 'mon', 'tue', 'wed', 'thu', 'fri']
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0).astype(float)
        st.session_state.ins_df = df
    except:
        st.session_state.ins_df = pd.DataFrame(columns=['name', 'rate', 'mon', 'tue', 'wed', 'thu', 'fri'])

if 'excl_df' not in st.session_state:
    try:
        st.session_state.excl_df = conn.read(worksheet="Exclusions", ttl=0)
    except:
        st.session_state.excl_df = pd.DataFrame(columns=['start_date', 'end_date', 'note'])

HOLIDAYS = [date(2026,3,1), date(2026,3,2), date(2026,5,5), date(2026,5,24), date(2026,5,25), 
            date(2026,6,6), date(2026,8,15), date(2026,8,17), date(2026,9,24), date(2026,9,25), 
            date(2026,9,26), date(2026,9,28), date(2026,10,3), date(2026,10,9), date(2026,12,25)]

st.title("🚀 2026 강사 시수 관리 시스템")

# --- 사이드바: 강사 관리 ---
with st.sidebar:
    st.header("👤 강사 관리")
    
    # 작업 모드 선택
    mode = st.radio("작업 선택", ["신규 등록", "기존 강사 수정/삭제"])
    
    if mode == "신규 등록":
        with st.form("add_form", clear_on_submit=True):
            new_name = st.text_input("강사 이름")
            new_rate = st.number_input("시간당 단가", value=30000.0, step=1000.0)
            st.write("요일별 시수")
            n_mon = st.number_input("월", value=0.0, step=0.5)
            n_tue = st.number_input("화", value=0.0, step=0.5)
            n_wed = st.number_input("수", value=0.0, step=0.5)
            n_thu = st.number_input("목", value=0.0, step=0.5)
            n_fri = st.number_input("금", value=0.0, step=0.5)
            
            if st.form_submit_button("신규 등록 저장"):
                if new_name:
                    new_data = pd.DataFrame([{"name": new_name, "rate": new_rate, "mon": n_mon, "tue": n_tue, "wed": n_wed, "thu": n_thu, "fri": n_fri}])
                    st.session_state.ins_df = pd.concat([st.session_state.ins_df, new_data], ignore_index=True)
                    conn.update(worksheet="Instructors", data=st.session_state.ins_df)
                    st.success(f"{new_name} 강사 등록 완료!"); st.rerun()

    else: # 수정/삭제 모드
        if not st.session_state.ins_df.empty:
            target_name = st.selectbox("수정/삭제할 강사 선택", st.session_state.ins_df['name'].unique())
            target_data = st.session_state.ins_df[st.session_state.ins_df['name'] == target_name].iloc[0]
            
            with st.form("edit_form"):
                e_name = st.text_input("이름 (수정 불가)", value=target_data['name'], disabled=True)
                e_rate = st.number_input("시간당 단가", value=float(target_data['rate']), step=1000.0)
                e_mon = st.number_input("월", value=float(target_data['mon']), step=0.5)
                e_tue = st.number_input("화", value=float(target_data['tue']), step=0.5)
                e_wed = st.number_input("수", value=float(target_data['wed']), step=0.5)
                e_thu = st.number_input("목", value=float(target_data['thu']), step=0.5)
                e_fri = st.number_input("금", value=float(target_data['fri']), step=0.5)
                
                col1, col2 = st.columns(2)
                if col1.form_submit_button("정보 업데이트"):
                    st.session_state.ins_df.loc[st.session_state.ins_df['name'] == target_name, ['rate','mon','tue','wed','thu','fri']] = [e_rate, e_mon, e_tue, e_wed, e_thu, e_fri]
                    conn.update(worksheet="Instructors", data=st.session_state.ins_df)
                    st.success("수정되었습니다!"); st.rerun()
                
                if col2.form_submit_button("❌ 강사 삭제"):
                    st.session_state.ins_df = st.session_state.ins_df[st.session_state.ins_df['name'] != target_name]
                    conn.update(worksheet="Instructors", data=st.session_state.ins_df)
                    st.warning("삭제되었습니다."); st.rerun()
        else:
            st.write("등록된 강사가 없습니다.")

    st.divider()
    st.header("🚫 제외 일정 추가")
    new_range = st.date_input("제외 기간 선택", value=(date(2026, 7, 20), date(2026, 8, 20)))
    note = st.text_input("제외 사유")
    if st.button("제외 일정 저장"):
        if isinstance(new_range, tuple) and len(new_range) == 2:
            new_ex = pd.DataFrame([{"start_date": new_range[0].isoformat(), "end_date": new_range[1].isoformat(), "note": note}])
            st.session_state.excl_df = pd.concat([st.session_state.excl_df, new_ex], ignore_index=True)
            conn.update(worksheet="Exclusions", data=st.session_state.excl_df)
            st.success("추가 완료!"); st.rerun()

    if st.button("🔄 구글 시트 새로고침"):
        del st.session_state.ins_df
        del st.session_state.excl_df
        st.rerun()

# --- 메인 화면 ---
if st.session_state.ins_df.empty:
    st.info("왼쪽에서 강사를 먼저 등록해 주세요.")
else:
    st.subheader("🗓️ 전체 제외 일정 관리")
    edited_excl = st.data_editor(st.session_state.excl_df, num_rows="dynamic", use_container_width=True)
    if st.button("수정사항 시트에 저장"):
        st.session_state.excl_df = edited_excl
        conn.update(worksheet="Exclusions", data=edited_excl)
        st.success("저장 완료!"); st.rerun()

    st.divider()
    
    # 강사 선택 및 계산
    instructor_list = st.session_state.ins_df['name'].unique()
    target = st.selectbox("시수 조회할 강사 선택", instructor_list)
    row = st.session_state.ins_df[st.session_state.ins_df['name'] == target].iloc[-1]
    
    hours_map = {0: float(row['mon']), 1: float(row['tue']), 2: float(row['wed']), 3: float(row['thu']), 4: float(row['fri'])}
    
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
            h = hours_map.get(current.weekday(), 0.0)
            if h > 0 and not (current in HOLIDAYS or current in all_excluded_dates):
                work_data.append(current)
        current += timedelta(days=1)

    # 연간 요약
    total_hours = sum([hours_map[d.weekday()] for d in work_data])
    c1, c2, c3 = st.columns(3)
    c1.metric("총 수업 횟수", f"{len(work_data)}회")
    c2.metric("총 수업 시수", f"{total_hours:g}시간")
    c3.metric("연간 예상 총액", f"{int(total_hours * row['rate']):,}원")

    # 월별 달력
    st.divider()
    st.subheader(f"📅 2026년 {target} 강사 수업 일정")
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
