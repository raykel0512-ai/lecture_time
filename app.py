import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar

st.set_page_config(page_title="2026 강사 시수 관리 시스템", layout="wide")

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

# 2026 공휴일 설정
HOLIDAYS_DICT = {
    date(2026,3,1): "삼일절", date(2026,3,2): "대체공휴일", date(2026,5,5): "어린이날", 
    date(2026,5,24): "부처님오신날", date(2026,5,25): "대체공휴일", date(2026,6,6): "현충일", 
    date(2026,8,15): "광복절", date(2026,8,17): "대체공휴일", date(2026,9,24): "추석", 
    date(2026,9,25): "추석", date(2026,9,26): "추석", date(2026,9,28): "대체공휴일",
    date(2026,10,3): "개천절", date(2026,10,9): "한글날", date(2026,12,25): "성탄절"
}

st.title("👨‍🏫 2026 강사 시수 및 통합 지출 관리")

# --- 사이드바: 강사 및 일정 등록 ---
with st.sidebar:
    st.header("👤 강사 관리")
    mode = st.radio("작업 선택", ["신규 등록", "기존 강사 수정/삭제"])
    
    if mode == "신규 등록":
        with st.form("add_form", clear_on_submit=True):
            new_name = st.text_input("강사 이름")
            new_rate = st.number_input("시간당 단가", value=30000.0, step=1000.0)
            n_mon = st.number_input("월 시수", value=0.0, step=0.5); n_tue = st.number_input("화 시수", value=0.0, step=0.5)
            n_wed = st.number_input("수 시수", value=0.0, step=0.5); n_thu = st.number_input("목 시수", value=0.0, step=0.5)
            n_fri = st.number_input("금 시수", value=0.0, step=0.5)
            if st.form_submit_button("신규 등록 저장"):
                if new_name:
                    new_data = pd.DataFrame([{"name": new_name, "rate": new_rate, "mon": n_mon, "tue": n_tue, "wed": n_wed, "thu": n_thu, "fri": n_fri}])
                    st.session_state.ins_df = pd.concat([st.session_state.ins_df, new_data], ignore_index=True)
                    conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()

    else:
        if not st.session_state.ins_df.empty:
            target_name = st.selectbox("관리할 강사 선택", st.session_state.ins_df['name'].unique())
            target_data = st.session_state.ins_df[st.session_state.ins_df['name'] == target_name].iloc[0]
            with st.form("edit_form"):
                e_rate = st.number_input("단가", value=float(target_data['rate']), step=1000.0)
                e_mon = st.number_input("월", value=float(target_data['mon']), step=0.5)
                e_tue = st.number_input("화", value=float(target_data['tue']), step=0.5)
                e_wed = st.number_input("수", value=float(target_data['wed']), step=0.5)
                e_thu = st.number_input("목", value=float(target_data['thu']), step=0.5)
                e_fri = st.number_input("금", value=float(target_data['fri']), step=0.5)
                c1, c2 = st.columns(2)
                if c1.form_submit_button("정보 업데이트"):
                    st.session_state.ins_df.loc[st.session_state.ins_df['name'] == target_name, ['rate','mon','tue','wed','thu','fri']] = [e_rate, e_mon, e_tue, e_wed, e_thu, e_fri]
                    conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
                if c2.form_submit_button("❌ 삭제"):
                    st.session_state.ins_df = st.session_state.ins_df[st.session_state.ins_df['name'] != target_name]
                    conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()

    st.header("🚫 제외 일정 추가")
    new_range = st.date_input("제외 기간 선택", value=(date(2026, 7, 20), date(2026, 8, 20)))
    note = st.text_input("사유 (달력에 표시됨)")
    if st.button("제외 일정 저장"):
        if isinstance(new_range, tuple) and len(new_range) == 2:
            new_ex = pd.DataFrame([{"start_date": new_range[0].isoformat(), "end_date": new_range[1].isoformat(), "note": note}])
            st.session_state.excl_df = pd.concat([st.session_state.excl_df, new_ex], ignore_index=True)
            conn.update(worksheet="Exclusions", data=st.session_state.excl_df); st.rerun()

# --- 메인 화면 상단: 일정 관리 & 지출 합산 ---
st.subheader("🛠️ 통합 관리 현황")
col_excl, col_total = st.columns([0.65, 0.35])

# 제외 날짜 및 휴일 통합 (합산용)
excl_dates_set = set()
for _, ex in st.session_state.excl_df.iterrows():
    try:
        sd, ed = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date']))
        curr = sd
        while curr <= ed:
            excl_dates_set.add(curr)
            curr += timedelta(days=1)
    except: continue
for d in HOLIDAYS_DICT.keys(): excl_dates_set.add(d)

with col_excl:
    st.write("**🗓️ 전체 제외 일정 에디터**")
    edited_excl = st.data_editor(st.session_state.excl_df, num_rows="dynamic", use_container_width=True)
    if st.button("일정 수정사항 저장"):
        st.session_state.excl_df = edited_excl
        conn.update(worksheet="Exclusions", data=edited_excl); st.rerun()

with col_total:
    st.write("**💰 연간 총 지출 예상액**")
    # 모든 강사의 전체 비용 계산
    all_total_fees = 0.0
    if not st.session_state.ins_df.empty:
        for _, ins in st.session_state.ins_df.iterrows():
            h_map = {0: ins['mon'], 1: ins['tue'], 2: ins['wed'], 3: ins['thu'], 4: ins['fri']}
            curr = date(2026, 3, 1)
            while curr <= date(2026, 12, 31):
                if curr.weekday() < 5 and curr not in excl_dates_set:
                    all_total_fees += h_map.get(curr.weekday(), 0.0) * ins['rate']
                curr += timedelta(days=1)
    
    # 총액 강조 표시
    st.metric("전체 강사료 합계", f"{int(all_total_fees):,}원")
    st.info("※ 등록된 모든 강사의 3월~12월 수업 시수를 공휴일 및 제외 일정을 반영하여 합산한 금액입니다.")

st.divider()

# --- 개별 강사 상세 리포트 ---
if not st.session_state.ins_df.empty:
    target = st.selectbox("상세 조회할 강사 선택", st.session_state.ins_df['name'].unique())
    row = st.session_state.ins_df[st.session_state.ins_df['name'] == target].iloc[-1]
    hours_map = {0: float(row['mon']), 1: float(row['tue']), 2: float(row['wed']), 3: float(row['thu']), 4: float(row['fri'])}
    
    # 말풍선용 툴팁 사전
    excl_tooltip = {d: HOLIDAYS_DICT[d] for d in HOLIDAYS_DICT}
    for _, ex in st.session_state.excl_df.iterrows():
        try:
            sd, ed = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date']))
            curr = sd
            while curr <= ed:
                excl_tooltip[curr] = ex['note']
                curr += timedelta(days=1)
        except: continue

    # 수업일 리스트
    work_data = []
    curr = date(2026, 3, 1)
    while curr <= date(2026, 12, 31):
        if curr.weekday() < 5 and curr not in excl_tooltip and hours_map.get(curr.weekday(), 0) > 0:
            work_data.append(curr)
        curr += timedelta(days=1)

    t_h = sum([hours_map[d.weekday()] for d in work_data])
    st.subheader(f"👨‍🏫 {target} 강사 상세 일정")
    c1, c2, c3 = st.columns(3)
    c1.metric("연간 수업 횟수", f"{len(work_data)}회")
    c2.metric("연간 총 시수", f"{t_h:g}시간")
    c3.metric("연간 예상 강사료", f"{int(t_h * row['rate']):,}원")

    # 커스텀 달력 스타일
    st.markdown("""<style>
    .cal-table { width: 100%; border-collapse: collapse; margin-bottom: 15px; font-size: 14px; }
    .cal-table td, .cal-table th { border: 1px solid #ddd; padding: 8px; text-align: center; }
    .workday { background-color: #90EE90; font-weight: bold; }
    .excluded { background-color: #FFB6C1; cursor: help; }
    </style>""", unsafe_allow_html=True)

    cols = st.columns(2)
    for m in range(3, 13):
        with cols[(m-3)%2]:
            st.write(f"#### {m}월 수업")
            cal = calendar.monthcalendar(2026, m)
            html = '<table class="cal-table"><tr><th>월</th><th>화</th><th>수</th><th>목</th><th>금</th></tr>'
            for week in cal:
                html += '<tr>'
                for i in range(5):
                    day = week[i]
                    if day == 0: html += '<td></td>'
                    else:
                        d = date(2026, m, day)
                        cls, title = "", ""
                        if d in work_data: cls = "workday"
                        elif d in excl_tooltip: cls = "excluded"; title = f'title="{excl_tooltip[d]}"'
                        html += f'<td class="{cls}" {title}>{day}</td>'
                html += '</tr>'
            html += '</table>'
            st.write(html, unsafe_allow_html=True)
            m_h = sum([hours_map[d.weekday()] for d in work_data if d.month == m])
            st.info(f"💰 {m}월 예상 지급액: {int(m_h * row['rate']):,}원")
