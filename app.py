import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar

st.set_page_config(page_title="2026 강사 시수 관리", layout="wide")

# 1. 구글 시트 연결 설정
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. 세션 상태 초기화 및 데이터 로드/업데이트
if 'ins_df' not in st.session_state:
    try:
        st.session_state.ins_df = conn.read(worksheet="Instructors", ttl=0)
        num_cols = ['rate', 'mon', 'tue', 'wed', 'thu', 'fri']
        for col in num_cols:
            if col in st.session_state.ins_df.columns:
                st.session_state.ins_df[col] = pd.to_numeric(st.session_state.ins_df[col], errors='coerce').fillna(0)
    except Exception as e:
        st.error(f"⚠️ 'Instructors' 시트를 불러오는데 실패했습니다: {e}")
        st.session_state.ins_df = pd.DataFrame(columns=['name', 'rate', 'mon', 'tue', 'wed', 'thu', 'fri'])

if 'excl_df' not in st.session_state:
    try:
        st.session_state.excl_df = conn.read(worksheet="Exclusions", ttl=0)
    except Exception as e:
        st.error(f"⚠️ 'Exclusions' 시트를 불러오는데 실패했습니다: {e}")
        st.session_state.excl_df = pd.DataFrame(columns=['start_date', 'end_date', 'note'])

# 2026년 공휴일
HOLIDAYS = [date(2026,3,1), date(2026,3,2), date(2026,5,5), date(2026,5,24), date(2026,5,25), 
            date(2026,6,6), date(2026,8,15), date(2026,8,17), date(2026,9,24), date(2026,9,25), 
            date(2026,9,26), date(2026,9,28), date(2026,10,3), date(2026,10,9), date(2026,12,25)]

st.title("🚀 2026 강사 시수 관리 시스템")

# --- 사이드바 ---
with st.sidebar:
    st.header("👤 강사 정보 관리")

    # 강사 선택 드롭다운 (수정/삭제용)
    instructor_names = st.session_state.ins_df['name'].tolist() if not st.session_state.ins_df.empty else []
    selected_instructor_for_edit = st.selectbox(
        "강사 선택 (수정/삭제 또는 새 강사 추가)", 
        ["새 강사 추가"] + instructor_names, 
        key="edit_instructor_selector"
    )

    # 선택된 강사 정보 불러오기 (폼 자동 채우기)
    current_ins_data = {}
    if selected_instructor_for_edit != "새 강사 추가":
        # 현재 선택된 강사의 데이터를 찾아 딕셔너리로 변환
        current_ins_data = st.session_state.ins_df[st.session_state.ins_df['name'] == selected_instructor_for_edit].iloc[0].to_dict()

    # 강사 등록/수정 폼
    with st.form("instructor_form", clear_on_submit=False): # 수정 시 폼이 비워지지 않도록 False
        form_name = st.text_input("강사 이름", value=current_ins_data.get('name', ''))
        form_rate = st.number_input("시간당 단가", value=float(current_ins_data.get('rate', 30000)), step=1000, key="form_rate")
        
        st.write("--- 평일 수업 시간 ---")
        form_mon = st.number_input("월요일", min_value=0.0, max_value=24.0, value=float(current_ins_data.get('mon', 0.0)), key="form_mon")
        form_tue = st.number_input("화요일", min_value=0.0, max_value=24.0, value=float(current_ins_data.get('tue', 0.0)), key="form_tue")
        form_wed = st.number_input("수요일", min_value=0.0, max_value=24.0, value=float(current_ins_data.get('wed', 0.0)), key="form_wed")
        form_thu = st.number_input("목요일", min_value=0.0, max_value=24.0, value=float(current_ins_data.get('thu', 0.0)), key="form_thu")
        form_fri = st.number_input("금요일", min_value=0.0, max_value=24.0, value=float(current_ins_data.get('fri', 0.0)), key="form_fri")
        
        submit_label = "강사 정보 업데이트" if selected_instructor_for_edit != "새 강사 추가" else "새 강사 추가"
        if st.form_submit_button(submit_label):
            if form_name:
                new_row_data = {
                    "name": form_name, "rate": form_rate, 
                    "mon": form_mon, "tue": form_tue, "wed": form_wed, "thu": form_thu, "fri": form_fri
                }
                new_row_df = pd.DataFrame([new_row_data])

                if selected_instructor_for_edit == "새 강사 추가":
                    # 새 강사 추가
                    st.session_state.ins_df = pd.concat([st.session_state.ins_df, new_row_df], ignore_index=True)
                else:
                    # 기존 강사 업데이트 (선택된 이름의 강사를 제거하고 새 정보 추가)
                    st.session_state.ins_df = st.session_state.ins_df[st.session_state.ins_df['name'] != selected_instructor_for_edit]
                    st.session_state.ins_df = pd.concat([st.session_state.ins_df, new_row_df], ignore_index=True)
                
                conn.update(worksheet="Instructors", data=st.session_state.ins_df)
                st.success("강사 정보가 저장되었습니다!"); st.rerun()
            else:
                st.warning("강사 이름을 입력해주세요.")
    
    # 강사 삭제 기능
    if selected_instructor_for_edit != "새 강사 추가":
        st.subheader(f"🗑️ {selected_instructor_for_edit} 강사 삭제")
        confirm_delete = st.checkbox(f"**{selected_instructor_for_edit}** 강사를 정말로 삭제하시겠습니까?", key="confirm_delete_checkbox")
        if confirm_delete and st.button(f"확인: {selected_instructor_for_edit} 강사 삭제", key="delete_button"):
            st.session_state.ins_df = st.session_state.ins_df[st.session_state.ins_df['name'] != selected_instructor_for_edit]
            conn.update(worksheet="Instructors", data=st.session_state.ins_df)
            st.success(f"{selected_instructor_for_edit} 강사가 삭제되었습니다."); st.rerun()

    st.header("🚫 2. 제외 일정 추가")
    new_range = st.date_input("새 제외 기간 선택", value=(date(2026, 7, 20), date(2026, 8, 20)))
    note = st.text_input("메모(예: 여름방학)")
    if st.button("제외 기간 추가"):
        if isinstance(new_range, tuple) and len(new_range) == 2:
            new_ex = pd.DataFrame([{"start_date": new_range[0].isoformat(), "end_date": new_range[1].isoformat(), "note": note}])
            st.session_state.excl_df = pd.concat([st.session_state.excl_df, new_ex], ignore_index=True)
            conn.update(worksheet="Exclusions", data=st.session_state.excl_df)
            st.success("제외 기간이 추가되었습니다!"); st.rerun()

    st.divider()
    if st.button("🔄 구글 시트에서 데이터 강제 새로고침"):
        del st.session_state.ins_df
        del st.session_state.excl_df
        st.rerun()

# --- 메인 화면 ---
if st.session_state.ins_df.empty:
    st.info("데이터를 불러오지 못했거나, 등록된 강사가 없습니다. 사이드바에서 강사를 등록하세요.")
else:
    st.subheader("🗓️ 전체 제외 일정 관리 (수정 후 '최종 저장' 버튼을 누르세요)")
    edited_excl = st.data_editor(st.session_state.excl_df, num_rows="dynamic", use_container_width=True)
    if st.button("제외 일정 수정사항 시트에 최종 저장"):
        st.session_state.excl_df = edited_excl
        conn.update(worksheet="Exclusions", data=edited_excl)
        st.success("구글 시트에 동기화되었습니다!"); st.rerun()

    st.divider()
    
    # 강사 선택 (계산 및 달력 표시용)
    instructor_list_for_view = st.session_state.ins_df['name'].unique().tolist()
    if not instructor_list_for_view: # 강사가 없으면 빈 목록 처리
        st.warning("표시할 강사가 없습니다. 강사를 추가해주세요.")
        st.stop()
        
    target = st.selectbox("조회할 강사 선택", instructor_list_for_view)
    
    row = st.session_state.ins_df[st.session_state.ins_df['name'] == target].iloc[-1]
    hours_map = {0: float(row['mon']), 1: float(row['tue']), 2: float(row['wed']), 
                 3: float(row['thu']), 4: float(row['fri'])}
    
    all_excluded_dates = set()
    if not st.session_state.excl_df.empty: # edited_excl 대신 st.session_state.excl_df를 직접 참조
        for _, ex in st.session_state.excl_df.iterrows():
            try:
                sd = date.fromisoformat(str(ex.get('start_date', '')))
                ed = date.fromisoformat(str(ex.get('end_date', '')))
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
