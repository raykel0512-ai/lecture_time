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

# 공휴일 데이터 (날짜: 명칭)
HOLIDAYS_DICT = {
    date(2026,3,1): "삼일절", date(2026,3,2): "대체공휴일", date(2026,5,5): "어린이날", 
    date(2026,5,24): "부처님오신날", date(2026,5,25): "대체공휴일", date(2026,6,6): "현충일", 
    date(2026,8,15): "광복절", date(2026,8,17): "대체공휴일", date(2026,9,24): "추석", 
    date(2026,9,25): "추석", date(2026,9,26): "추석", date(2026,9,28): "대체공휴일",
    date(2026,10,3): "개천절", date(2026,10,9): "한글날", date(2026,12,25): "성탄절"
}

st.title("🚀 2026 강사 시수 관리 시스템 (말풍선 기능 포함)")

# --- 사이드바 (강사 관리 및 제외 추가 - 이전과 동일) ---
with st.sidebar:
    st.header("👤 강사 관리")
    mode = st.radio("작업 선택", ["신규 등록", "기존 강사 수정/삭제"])
    
    if mode == "신규 등록":
        with st.form("add_form", clear_on_submit=True):
            new_name = st.text_input("강사 이름")
            new_rate = st.number_input("시간당 단가", value=30000.0, step=1000.0)
            n_mon = st.number_input("월 시수", value=0.0, step=0.5)
            n_tue = st.number_input("화 시수", value=0.0, step=0.5)
            n_wed = st.number_input("수 시수", value=0.0, step=0.5)
            n_thu = st.number_input("목 시수", value=0.0, step=0.5)
            n_fri = st.number_input("금 시수", value=0.0, step=0.5)
            if st.form_submit_button("등록"):
                new_data = pd.DataFrame([{"name": new_name, "rate": new_rate, "mon": n_mon, "tue": n_tue, "wed": n_wed, "thu": n_thu, "fri": n_fri}])
                st.session_state.ins_df = pd.concat([st.session_state.ins_df, new_data], ignore_index=True)
                conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
    else:
        if not st.session_state.ins_df.empty:
            target_name = st.selectbox("강사 선택", st.session_state.ins_df['name'].unique())
            target_data = st.session_state.ins_df[st.session_state.ins_df['name'] == target_name].iloc[0]
            with st.form("edit_form"):
                e_rate = st.number_input("단가", value=float(target_data['rate']))
                e_mon = st.number_input("월", value=float(target_data['mon']))
                e_tue = st.number_input("화", value=float(target_data['tue']))
                e_wed = st.number_input("수", value=float(target_data['wed']))
                e_thu = st.number_input("목", value=float(target_data['thu']))
                e_fri = st.number_input("금", value=float(target_data['fri']))
                if st.form_submit_button("수정"):
                    st.session_state.ins_df.loc[st.session_state.ins_df['name'] == target_name, ['rate','mon','tue','wed','thu','fri']] = [e_rate, e_mon, e_tue, e_wed, e_thu, e_fri]
                    conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
                if st.form_submit_button("삭제"):
                    st.session_state.ins_df = st.session_state.ins_df[st.session_state.ins_df['name'] != target_name]
                    conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()

    st.header("🚫 제외 일정 추가")
    new_range = st.date_input("제외 기간 선택", value=(date(2026, 7, 20), date(2026, 8, 20)))
    note = st.text_input("사유 (말풍선에 표시됨)")
    if st.button("제외 저장"):
        if isinstance(new_range, tuple) and len(new_range) == 2:
            new_ex = pd.DataFrame([{"start_date": new_range[0].isoformat(), "end_date": new_range[1].isoformat(), "note": note}])
            st.session_state.excl_df = pd.concat([st.session_state.excl_df, new_ex], ignore_index=True)
            conn.update(worksheet="Exclusions", data=st.session_state.excl_df); st.rerun()

# --- 메인 화면 ---
if st.session_state.ins_df.empty:
    st.info("왼쪽에서 강사를 먼저 등록해 주세요.")
else:
    st.subheader("🗓️ 전체 제외 일정 관리")
    edited_excl = st.data_editor(st.session_state.excl_df, num_rows="dynamic", use_container_width=True)
    if st.button("수정사항 시트에 저장"):
        st.session_state.excl_df = edited_excl
        conn.update(worksheet="Exclusions", data=edited_excl); st.rerun()

    st.divider()
    
    target = st.selectbox("조회할 강사 선택", st.session_state.ins_df['name'].unique())
    row = st.session_state.ins_df[st.session_state.ins_df['name'] == target].iloc[-1]
    hours_map = {0: float(row['mon']), 1: float(row['tue']), 2: float(row['wed']), 3: float(row['thu']), 4: float(row['fri'])}
    
    # 제외 날짜와 메모를 매핑 {date: "note"}
    excl_notes = {}
    for _, ex in st.session_state.excl_df.iterrows():
        try:
            sd, ed = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date']))
            curr = sd
            while curr <= ed:
                excl_notes[curr] = ex['note']
                curr += timedelta(days=1)
        except: continue
    # 공휴일 메모 추가
    for d, n in HOLIDAYS_DICT.items():
        excl_notes[d] = n

    # 수업일 계산
    work_data = []
    current = date(2026, 3, 1)
    while current <= date(2026, 12, 31):
        if current.weekday() < 5:
            h = hours_map.get(current.weekday(), 0.0)
            if h > 0 and not (current in excl_notes):
                work_data.append(current)
        current += timedelta(days=1)

    # 요약 정보
    total_hours = sum([hours_map[d.weekday()] for d in work_data])
    c1, c2, c3 = st.columns(3)
    c1.metric("총 수업 횟수", f"{len(work_data)}회")
    c2.metric("총 시수", f"{total_hours:g}시간")
    c3.metric("예상 급여", f"{int(total_hours * row['rate']):,}원")

    # --- HTML 기반 커스텀 달력 출력 (말풍선 기능) ---
    st.markdown("""
    <style>
    .cal-table { width: 100%; border-collapse: collapse; font-family: sans-serif; }
    .cal-table th, .cal-table td { border: 1px solid #ddd; padding: 10px; text-align: center; width: 20%; }
    .cal-table th { background-color: #f8f9fa; }
    .workday { background-color: #90EE90; font-weight: bold; cursor: default; }
    .excluded { background-color: #FFB6C1; cursor: help; position: relative; }
    .empty { background-color: #ffffff; }
    </style>
    """, unsafe_allow_html=True)

    st.subheader(f"📅 2026년 {target} 강사 수업 일정 (분홍색 칸에 마우스를 대보세요)")
    cols = st.columns(2)
    for m in range(3, 13):
        with cols[(m-3)%2]:
            st.write(f"#### 🗓️ {m}월")
            cal = calendar.monthcalendar(2026, m)
            
            html = '<table class="cal-table"><tr><th>월</th><th>화</th><th>수</th><th>목</th><th>금</th></tr>'
            for week in cal:
                html += '<tr>'
                for i in range(5): # 월-금만
                    day = week[i]
                    if day == 0:
                        html += '<td class="empty"></td>'
                    else:
                        d = date(2026, m, day)
                        cls = ""
                        title = ""
                        if d in work_data:
                            cls = "workday"
                        elif d in excl_notes:
                            cls = "excluded"
                            title = f'title="{excl_notes[d]}"' # 브라우저 툴팁(말풍선) 속성
                        
                        html += f'<td class="{cls}" {title}>{day}</td>'
                html += '</tr>'
            html += '</table>'
            st.write(html, unsafe_allow_html=True)
            
            # 월별 요약
            m_work = [d for d in work_data if d.month == m]
            m_h = sum([hours_map[d.weekday()] for d in m_work])
            st.info(f"💰 {m}월: {int(m_h * row['rate']):,}원 ({m_h:g}시간)")
