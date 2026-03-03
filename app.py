import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar
from fpdf import FPDF
import os

# --- 페이지 설정 ---
st.set_page_config(page_title="2026 강사 관리 시스템", layout="wide")

# --- [추가] 파일 시스템 체크 (디버깅용) ---
with st.sidebar:
    st.divider()
    st.write("🔍 **파일 시스템 체크**")
    files_in_dir = os.listdir('.') # 현재 폴더의 파일 목록 가져오기
    if "font.ttf" in files_in_dir:
        st.success("✅ font.ttf 파일을 찾았습니다!")
    else:
        st.error("❌ font.ttf 파일이 없습니다.")
        st.write("현재 파일 목록:", files_in_dir)

# --- 1. 구글 시트 연결 및 세션 데이터 초기화 ---
conn = st.connection("gsheets", type=GSheetsConnection)

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

HOLIDAYS_DICT = {
    date(2026,3,1): "삼일절", date(2026,3,2): "대체공휴일", date(2026,5,5): "어린이날", 
    date(2026,5,24): "부처님오신날", date(2026,5,25): "대체공휴일", date(2026,6,6): "현충일", 
    date(2026,8,15): "광복절", date(2026,8,17): "대체공휴일", date(2026,9,24): "추석", 
    date(2026,9,25): "추석", date(2026,9,26): "추석", date(2026,9,28): "대체공휴일",
    date(2026,10,3): "개천절", date(2026,10,9): "한글날", date(2026,12,25): "성탄절"
}

# --- 2. PDF 생성 함수 (경로 보정) ---
def create_pdf(target_name, rate, total_h, total_pay, monthly_stats, work_data):
    pdf = FPDF()
    pdf.add_page()
    
    # 폰트 경로를 절대 경로로 시도
    current_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(current_dir, "font.ttf")
    
    if os.path.exists(font_path):
        pdf.add_font("Nanum", "", font_path)
        pdf.set_font("Nanum", size=18)
    else:
        # 폰트 파일이 없을 경우 기본 Arial (한글 깨짐 주의)
        pdf.set_font("Arial", size=18)

    pdf.cell(200, 20, txt="2026학년도 강사 수업 시수 확인서", ln=True, align='C')
    pdf.ln(10)
    
    if os.path.exists(font_path): pdf.set_font("Nanum", size=11)
    pdf.cell(100, 10, txt=f"강사 성명: {target_name}", ln=True)
    pdf.cell(100, 10, txt=f"해당 기간: 2026년 03월 ~ 12월", ln=True)
    pdf.cell(100, 10, txt=f"시간당 단가: {int(rate):,}원", ln=True)
    pdf.ln(5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)

    pdf.cell(100, 10, txt="[연간 최종 합계]", ln=True)
    pdf.cell(100, 10, txt=f"1. 총 수업 횟수: {len(work_data)}회", ln=True)
    pdf.cell(100, 10, txt=f"2. 총 수업 시수: {total_h:g}시간", ln=True)
    pdf.cell(100, 10, txt=f"3. 총 예상 지급액: {int(total_pay):,}원", ln=True)
    pdf.ln(10)

    pdf.cell(100, 10, txt="[월별 상세 내역]", ln=True)
    pdf.cell(30, 10, "월", border=1, align='C')
    pdf.cell(40, 10, "수업 횟수", border=1, align='C')
    pdf.cell(40, 10, "총 시수", border=1, align='C')
    pdf.cell(50, 10, "예상 지급액", border=1, align='C')
    pdf.ln()

    for item in monthly_stats:
        pdf.cell(30, 10, item['월'], border=1, align='C')
        pdf.cell(40, 10, item['횟수'], border=1, align='C')
        pdf.cell(40, 10, item['시수'], border=1, align='C')
        pdf.cell(50, 10, item['급여'], border=1, align='R')
        pdf.ln()

    pdf.ln(20)
    pdf.cell(200, 10, txt="위와 같이 수업 시수 및 강사료 산출 내역을 확인합니다.", ln=True, align='C')
    pdf.ln(10)
    pdf.cell(200, 10, txt=date.today().strftime("%Y년 %m월 %d일"), ln=True, align='C')
    
    return pdf.output(dest='S')

# --- 3. 사이드바 (등록/수정) ---
with st.sidebar:
    st.header("👤 강사 관리")
    mode = st.radio("작업 선택", ["신규 등록", "수정 및 삭제"])
    
    if mode == "신규 등록":
        with st.form("add_form", clear_on_submit=True):
            n_name = st.text_input("강사 이름")
            n_rate = st.number_input("단가", value=30000.0, step=1000.0)
            n_mon = st.number_input("월", value=0.0); n_tue = st.number_input("화", value=0.0)
            n_wed = st.number_input("수", value=0.0); n_thu = st.number_input("목", value=0.0)
            n_fri = st.number_input("금", value=0.0)
            if st.form_submit_button("등록"):
                new_row = pd.DataFrame([{"name": n_name, "rate": n_rate, "mon": n_mon, "tue": n_tue, "wed": n_wed, "thu": n_thu, "fri": n_fri}])
                st.session_state.ins_df = pd.concat([st.session_state.ins_df, new_row], ignore_index=True)
                conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
    else:
        if not st.session_state.ins_df.empty:
            t_name = st.selectbox("강사 선택", st.session_state.ins_df['name'].unique())
            t_data = st.session_state.ins_df[st.session_state.ins_df['name'] == t_name].iloc[0]
            with st.form("edit_form"):
                e_rate = st.number_input("단가", value=float(t_data['rate']))
                e_mon = st.number_input("월", value=float(t_data['mon'])); e_tue = st.number_input("화", value=float(t_data['tue']))
                e_wed = st.number_input("수", value=float(t_data['wed'])); e_thu = st.number_input("목", value=float(t_data['thu']))
                e_fri = st.number_input("금", value=float(t_data['fri']))
                c1, c2 = st.columns(2)
                if c1.form_submit_button("업데이트"):
                    st.session_state.ins_df.loc[st.session_state.ins_df['name'] == t_name, ['rate','mon','tue','wed','thu','fri']] = [e_rate, e_mon, e_tue, e_wed, e_thu, e_fri]
                    conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
                if c2.form_submit_button("삭제"):
                    st.session_state.ins_df = st.session_state.ins_df[st.session_state.ins_df['name'] != t_name]
                    conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()

# --- 4. 메인 화면 ---
st.title("👨‍🏫 2026 강사 시수 관리 통합 리포트")

col_l, col_r = st.columns([0.6, 0.4])

all_excl_dates = {d for d in HOLIDAYS_DICT}
for _, ex in st.session_state.excl_df.iterrows():
    try:
        s, e = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date']))
        while s <= e:
            all_excl_dates.add(s); s += timedelta(days=1)
    except: continue

with col_l:
    st.subheader("🗓️ 전체 제외 일정")
    edited_excl = st.data_editor(st.session_state.excl_df, num_rows="dynamic", use_container_width=True)
    if st.button("제외 일정 저장"):
        st.session_state.excl_df = edited_excl
        conn.update(worksheet="Exclusions", data=edited_excl); st.rerun()

with col_r:
    st.subheader("💰 전체 예산 현황")
    total_all = 0.0
    if not st.session_state.ins_df.empty:
        for _, ins in st.session_state.ins_df.iterrows():
            hm = {0: ins['mon'], 1: ins['tue'], 2: ins['wed'], 3: ins['thu'], 4: ins['fri']}
            curr = date(2026, 3, 1)
            while curr <= date(2026, 12, 31):
                if curr.weekday() < 5 and curr not in all_excl_dates:
                    total_all += hm.get(curr.weekday(), 0.0) * ins['rate']
                curr += timedelta(days=1)
    st.metric("연간 총 소요액", f"{int(total_all):,}원")

st.divider()

if not st.session_state.ins_df.empty:
    target = st.selectbox("조회 강사 선택", st.session_state.ins_df['name'].unique())
    row = st.session_state.ins_df[st.session_state.ins_df['name'] == target].iloc[-1]
    hm = {0: float(row['mon']), 1: float(row['tue']), 2: float(row['wed']), 3: float(row['thu']), 4: float(row['fri'])}
    
    tooltips = {d: HOLIDAYS_DICT[d] for d in HOLIDAYS_DICT}
    for _, ex in st.session_state.excl_df.iterrows():
        try:
            s, e = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date']))
            while s <= e: tooltips[s] = ex['note']; s += timedelta(days=1)
        except: continue

    work_dates = []
    curr = date(2026, 3, 1)
    while curr <= date(2026, 12, 31):
        if curr.weekday() < 5 and curr not in tooltips and hm.get(curr.weekday(), 0) > 0:
            work_dates.append(curr)
        curr += timedelta(days=1)

    m_stats = []
    for m in range(3, 13):
        m_d = [d for d in work_dates if d.month == m]
        m_h = sum([hm[d.weekday()] for d in m_d])
        m_stats.append({"월": f"{m}월", "횟수": f"{len(m_d)}회", "시수": f"{m_h:g}시간", "급여": f"{int(m_h * row['rate']):,}원"})

    t_h = sum([hm[d.weekday()] for d in work_dates])
    t_p = t_h * row['rate']

    # 리포트 및 PDF 버튼
    cl, cr = st.columns([0.7, 0.3])
    with cr:
        try:
            pdf_bytes = create_pdf(target, row['rate'], t_h, t_p, m_stats, work_dates)
            st.download_button("📄 PDF 확인서 다운로드", data=pdf_bytes, file_name=f"2026_{target}_확인서.pdf", mime="application/pdf")
        except Exception as e:
            st.error(f"PDF 오류: {e}")

    c1, c2, c3 = st.columns(3)
    c1.metric("수업 횟수", f"{len(work_dates)}회")
    c2.metric("총 시수", f"{t_h:g}시간"); c3.metric("예상 강사료", f"{int(t_p):,}원")

    # 달력 스타일
    st.markdown("""<style>.cal-table { width: 100%; border-collapse: collapse; }
    .cal-table td, .cal-table th { border: 1px solid #ddd; padding: 8px; text-align: center; }
    .workday { background-color: #90EE90; font-weight: bold; }
    .excluded { background-color: #FFB6C1; cursor: help; }</style>""", unsafe_allow_html=True)

    cols = st.columns(2)
    for m in range(3, 13):
        with cols[(m-3)%2]:
            st.write(f"#### {m}월 일정")
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
                        if d in work_dates: cls = "workday"
                        elif d in tooltips: cls = "excluded"; title = f'title="{tooltips[d]}"'
                        html += f'<td class="{cls}" {title}>{day}</td>'
                html += '</tr>'
            html += '</table>'
            st.write(html, unsafe_allow_html=True)
            m_h = sum([hm[d.weekday()] for d in work_dates if d.month == m])
            st.info(f"💰 {m}월 급여: {int(m_h * row['rate']):,}원")
