import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar

st.set_page_config(page_title="2026 강사 시수 관리", layout="wide")

# 1. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    """데이터를 안전하게 불러오는 함수"""
    try:
        # 시트 읽기 (ttl=60은 60초 동안 캐시를 보관하여 구글 차단을 방지함)
        ins_df = conn.read(worksheet="Instructors", ttl=60)
        excl_df = conn.read(worksheet="Exclusions", ttl=60)
        
        # 숫자형 변환 로직
        num_cols = ['rate', 'mon', 'tue', 'wed', 'thu', 'fri']
        if not ins_df.empty:
            for col in num_cols:
                if col in ins_df.columns:
                    ins_df[col] = pd.to_numeric(ins_df[col], errors='coerce').fillna(0)
        
        return ins_df, excl_df

    except Exception as e:
        # 오류 발생 시 빈 데이터프레임을 반환하여 NameError 방지
        st.error(f"❌ 구글 시트 연결 중 오류가 발생했습니다.")
        st.warning(f"상세 오류 내용: {e}")
        st.info("💡 체크리스트:\n1. 시트 하단 탭 이름이 정확히 'Instructors'와 'Exclusions'인가요?\n2. 시트 공유에 서비스 계정 이메일을 넣으셨나요?")
        return pd.DataFrame(), pd.DataFrame()

# 데이터 호출 (여기서 변수가 반드시 생성됨)
ins_df, excl_df = load_data()

# 2026년 공휴일
HOLIDAYS = [date(2026,3,1), date(2026,3,2), date(2026,5,5), date(2026,5,24), date(2026,5,25), 
            date(2026,6,6), date(2026,8,15), date(2026,8,17), date(2026,9,24), date(2026,9,25), 
            date(2026,9,26), date(2026,9,28), date(2026,10,3), date(2026,10,9), date(2026,12,25)]

st.title("🚀 2026 강사 시수 관리 시스템")

# --- 메인 로직 시작 ---
# ins_df가 정상적으로 로드되었는지 확인
if ins_df.empty:
    st.sidebar.warning("데이터가 비어있습니다. 강사를 새로 등록하거나 시트 설정을 확인하세요.")
    
# 사이드바 입력 폼
with st.sidebar:
    st.header("👤 1. 강사 등록")
    with st.form("ins_form"):
        name = st.text_input("강사 이름")
        rate = st.number_input("시간당 단가", value=30000, step=1000)
        st.write("--- 평일 수업 시간 ---")
        mon = st.number_input("월요일", min_value=0.0, max_value=24.0, value=0.0)
        tue = st.number_input("화요일", min_value=0.0, max_value=24.0, value=0.0)
        wed = st.number_input("수요일", min_value=0.0, max_value=24.0, value=0.0)
        thu = st.number_input("목요일", min_value=0.0, max_value=24.0, value=0.0)
        fri = st.number_input("금요일", min_value=0.0, max_value=24.0, value=0.0)
        
        if st.form_submit_button("저장"):
            new_row = pd.DataFrame([{"name": name, "rate": rate, "mon": mon, "tue": tue, "wed": wed, "thu": thu, "fri": fri}])
            # 기존 데이터와 합치기
            updated_ins = pd.concat([ins_df, new_row], ignore_index=True).drop_duplicates(subset=['name'], keep='last')
            conn.update(worksheet="Instructors", data=updated_ins)
            st.success("저장되었습니다! 반영까지 약 1분이 소요될 수 있습니다."); st.rerun()

    st.header("🚫 2. 제외 일정 관리")
    # 날짜 범위 선택 (기본값 설정)
    new_range = st.date_input("새 제외 기간 선택", value=(date(2026, 7, 20), date(2026, 8, 20)))
    note = st.text_input("메모")
    if st.button("제외 기간 추가"):
        if isinstance(new_range, tuple) and len(new_range) == 2:
            new_ex = pd.DataFrame([{"start_date": new_range[0].isoformat(), "end_date": new_range[1].isoformat(), "note": note}])
            updated_ex = pd.concat([excl_df, new_ex], ignore_index=True)
            conn.update(worksheet="Exclusions", data=updated_ex)
            st.success("추가되었습니다!"); st.rerun()

# --- 데이터 표시부 ---
if not ins_df.empty:
    st.subheader("🗓️ 전체 제외 일정 관리")
    # 에디터에서 빈 데이터프레임일 경우 방어 로직
    edited_excl = st.data_editor(excl_df, num_rows="dynamic", use_container_width=True)
    if st.button("제외 일정 수정사항 저장"):
        conn.update(worksheet="Exclusions", data=edited_excl)
        st.success("업데이트 완료!"); st.rerun()

    st.divider()
    
    # 강사 선택
    instructor_list = ins_df['name'].unique()
    target = st.selectbox("조회할 강사 선택", instructor_list)
    
    # 선택된 강사 정보 추출
    row = ins_df[ins_df['name'] == target].iloc[-1]
    hours_map = {0: float(row['mon']), 1: float(row['tue']), 2: float(row['wed']), 
                 3: float(row['thu']), 4: float(row['fri'])}
    
    # 제외 날짜 계산
    all_excluded_dates = set()
    if not edited_excl.empty:
        for _, ex in edited_excl.iterrows():
            try:
                sd = date.fromisoformat(str(ex.get('start_date', '')))
                ed = date.fromisoformat(str(ex.get('end_date', '')))
                curr = sd
                while curr <= ed:
                    all_excluded_dates.add(curr)
                    curr += timedelta(days=1)
            except: continue

    # 수업일 리스트 생성
    work_data = []
    current = date(2026, 3, 1)
    while current <= date(2026, 12, 31):
        if current.weekday() < 5: # 평일만
            h = hours_map.get(current.weekday(), 0)
            if h > 0 and not (current in HOLIDAYS or current in all_excluded_dates):
                work_data.append(current)
        current += timedelta(days=1)

    # 요약 출력
    total_hours = sum([hours_map[d.weekday()] for d in work_data])
    c1, c2, c3 = st.columns(3)
    c1.metric("총 수업 횟수", f"{len(work_data)}회")
    c2.metric("총 수업 시수", f"{total_hours:g}시간")
    c3.metric("연간 예상 총액", f"{int(total_hours * row['rate']):,}원")

    # 월별 달력
    st.divider()
    st.subheader("📅 2026년 월별 수업 일정 및 강사료")
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

else:
    st.info("사이드바에서 강사를 등록하거나 구글 시트 연결을 확인해 주세요.")
