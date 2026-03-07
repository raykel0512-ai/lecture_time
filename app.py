import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar
from fpdf import FPDF
import os

# --- 0. 페이지 설정 ---
st.set_page_config(page_title="2026 강사 통합 관리 Pro (Full)", layout="wide")

# --- 1. 구글 시트 연결 및 세션 데이터 초기화 ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_initial_after_df():
    """방과후학교 초기 입력 틀"""
    months = [f"{m}월" for m in range(3, 13)]
    return pd.DataFrame({
        "month": months, "w1": [0.0]*10, "w2": [0.0]*10, "w3": [0.0]*10, "w4": [0.0]*10, "w5": [0.0]*10
    })

# 데이터 로드 (에러 방지용 try-except 포함)
if 'ins_df' not in st.session_state:
    try:
        df = conn.read(worksheet="Instructors", ttl=0)
        num_cols = ['rate', 'rate_after', 'mon', 'tue', 'wed', 'thu', 'fri']
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0).astype(float)
        st.session_state.ins_df = df
    except: st.session_state.ins_df = pd.DataFrame(columns=['name', 'rate', 'rate_after', 'mon', 'tue', 'wed', 'thu', 'fri'])

if 'excl_df' not in st.session_state:
    try: st.session_state.excl_df = conn.read(worksheet="Exclusions", ttl=0)
    except: st.session_state.excl_df = pd.DataFrame(columns=['start_date', 'end_date', 'note'])

if 'after_df' not in st.session_state:
    try: st.session_state.after_df = conn.read(worksheet="AfterSchool", ttl=0)
    except: st.session_state.after_df = pd.DataFrame(columns=['name', 'month', 'w1', 'w2', 'w3', 'w4', 'w5'])

# 공휴일 사전
HOLIDAYS_DICT = {
    date(2026,3,1): "삼일절", date(2026,3,2): "대체공휴일", date(2026,5,5): "어린이날", 
    date(2026,5,24): "부처님오신날", date(2026,5,25): "대체공휴일", date(2026,6,6): "현충일", 
    date(2026,8,15): "광복절", date(2026,8,17): "대체공휴일", date(2026,9,24): "추석", 
    date(2026,9,25): "추석", date(2026,9,26): "추석", date(2026,9,28): "대체공휴일",
    date(2026,10,3): "개천절", date(2026,10,9): "한글날", date(2026,12,25): "성탄절"
}

# --- 2. PDF 생성 함수 (분리 단가 반영) ---
def create_pdf(target_name, rate, rate_after, total_reg, total_after, total_pay, monthly_stats):
    pdf = FPDF(); pdf.add_page()
    font_path = "font.ttf"
    if os.path.exists(font_path):
        pdf.add_font("Nanum", "", font_path); pdf.set_font("Nanum", size=20)
    else: pdf.set_font("Arial", size=20)
    
    pdf.cell(200, 20, txt="2026학년도 강사 수업 시수 확인서 (통합)", ln=True, align='C')
    if os.path.exists(font_path): pdf.set_font("Nanum", size=11)
    pdf.ln(10)
    pdf.cell(100, 10, txt=f"강사 성명: {target_name}", ln=True)
    pdf.cell(100, 10, txt=f"정규 수업 단가: {int(rate):,}원 | 방과후 단가: {int(rate_after):,}원", ln=True)
    pdf.cell(100, 10, txt=f"연간 최종 시수: 정규 {total_reg:g}h + 방과후 {total_after:g}h = 총 {total_reg+total_after:g}h", ln=True)
    pdf.set_font("Nanum", style='B', size=12)
    pdf.cell(100, 10, txt=f"연간 최종 예상 급여: {int(total_pay):,}원", ln=True)
    pdf.set_font("Nanum", size=11); pdf.ln(10)

    # 표 헤더
    pdf.cell(20, 10, "월", 1, 0, 'C'); pdf.cell(35, 10, "정규시수", 1, 0, 'C'); pdf.cell(35, 10, "방과후시수", 1, 0, 'C'); pdf.cell(45, 10, "출근횟수", 1, 0, 'C'); pdf.cell(50, 10, "합계급여", 1, 0, 'C'); pdf.ln()
    
    for m in monthly_stats:
        pdf.cell(20, 10, m['월'], 1, 0, 'C')
        pdf.cell(35, 10, m['정규'], 1, 0, 'C')
        pdf.cell(35, 10, m['방과후'], 1, 0, 'C')
        pdf.cell(45, 10, m['횟수'], 1, 0, 'C')
        pdf.cell(50, 10, m['급여'], 1, 0, 'R'); pdf.ln()

    pdf.ln(20); pdf.cell(200, 10, txt="위와 같이 2026학년도 수업 내역을 확인합니다.", ln=True, align='C')
    pdf.cell(200, 10, txt=date.today().strftime("%Y년 %m월 %d일"), ln=True, align='C')
    return bytes(pdf.output())

# --- 3. 사이드바: 강사 및 일정 관리 ---
with st.sidebar:
    st.header("👤 강사/일정 관리")
    mode = st.radio("모드 선택", ["강사 등록/수정", "제외 일정 추가"])
    
    if mode == "강사 등록/수정":
        sub_mode = st.selectbox("작업", ["신규 등록", "수정/삭제"])
        if sub_mode == "신규 등록":
            with st.form("add_form", clear_on_submit=True):
                n_name = st.text_input("이름")
                n_rate = st.number_input("정규 단가", 30000.0, step=1000.0)
                n_rate_after = st.number_input("방과후 단가", 30000.0, step=1000.0)
                n_mon = st.number_input("월", 0.0); n_tue = st.number_input("화", 0.0); n_wed = st.number_input("수", 0.0); n_thu = st.number_input("목", 0.0); n_fri = st.number_input("금", 0.0)
                if st.form_submit_button("등록"):
                    new = pd.DataFrame([{"name": n_name, "rate": n_rate, "rate_after": n_rate_after, "mon": n_mon, "tue": n_tue, "wed": n_wed, "thu": n_thu, "fri": n_fri}])
                    st.session_state.ins_df = pd.concat([st.session_state.ins_df, new], ignore_index=True)
                    conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
        else:
            if not st.session_state.ins_df.empty:
                t_name = st.selectbox("강사 선택", st.session_state.ins_df['name'].unique())
                t_data = st.session_state.ins_df[st.session_state.ins_df['name'] == t_name].iloc[0]
                with st.form("edit_form"):
                    e_rate = st.number_input("정규 단가", value=float(t_data['rate']))
                    e_rate_after = st.number_input("방과후 단가", value=float(t_data.get('rate_after', 30000.0)))
                    e_mon = st.number_input("월", value=float(t_data['mon'])); e_tue = st.number_input("화", value=float(t_data['tue'])); e_wed = st.number_input("수", value=float(t_data['wed'])); e_thu = st.number_input("목", value=float(t_data['thu'])); e_fri = st.number_input("금", value=float(t_data['fri']))
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("수정"):
                        st.session_state.ins_df.loc[st.session_state.ins_df['name'] == t_name, ['rate','rate_after','mon','tue','wed','thu','fri']] = [e_rate, e_rate_after, e_mon, e_tue, e_wed, e_thu, e_fri]
                        conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
                    if c2.form_submit_button("삭제"):
                        st.session_state.ins_df = st.session_state.ins_df[st.session_state.ins_df['name'] != t_name]
                        conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()

    else:
        ex_range = st.date_input("제외 기간", (date(2026,7,20), date(2026,8,20)))
        ex_note = st.text_input("사유")
        if st.button("제외 저장"):
            new_ex = pd.DataFrame([{"start_date": ex_range[0].isoformat(), "end_date": ex_range[1].isoformat(), "note": ex_note}])
            st.session_state.excl_df = pd.concat([st.session_state.excl_df, new_ex], ignore_index=True)
            conn.update(worksheet="Exclusions", data=st.session_state.excl_df); st.rerun()

# --- 4. 메인 대시보드 (통계 및 예산 합계) ---
st.subheader("🛠️ 통합 관리 현황")
col_e, col_b = st.columns([0.6, 0.4])

# 모든 제외 날짜 Set (공통)
common_excl = {d for d in HOLIDAYS_DICT}
for _, ex in st.session_state.excl_df.iterrows():
    try:
        s, e = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date']))
        while s <= e: common_excl.add(s); s += timedelta(days=1)
    except: continue

with col_e:
    st.write("**🗓️ 공통 제외 일정 에디터**")
    edited_ex = st.data_editor(st.session_state.excl_df, num_rows="dynamic", use_container_width=True)
    if st.button("공통 일정 저장"):
        st.session_state.excl_df = edited_ex
        conn.update(worksheet="Exclusions", data=edited_ex); st.rerun()

with col_b:
    st.write("**💰 연간 총 지출 예상액 (정규+방과후)**")
    grand_total = 0.0
    if not st.session_state.ins_df.empty:
        for _, ins in st.session_state.ins_df.iterrows():
            # 정규 수업 합산
            h_map = {0: ins['mon'], 1: ins['tue'], 2: ins['wed'], 3: ins['thu'], 4: ins['fri']}
            curr = date(2026, 3, 1)
            while curr <= date(2026, 12, 31):
                if curr.weekday() < 5 and curr not in common_excl:
                    grand_total += h_map.get(curr.weekday(), 0.0) * ins['rate']
                curr += timedelta(days=1)
            # 방과후 합산
            after_data = st.session_state.after_df[st.session_state.after_df['name'] == ins['name']]
            if not after_data.empty:
                after_hours = after_data[['w1','w2','w3','w4','w5']].sum().sum()
                grand_total += after_hours * ins.get('rate_after', 30000.0)
    st.metric("전체 강사비 소요액 합계", f"{int(grand_total):,}원")

st.divider()

# --- 5. 개별 강사 상세 페이지 ---
if not st.session_state.ins_df.empty:
    target = st.selectbox("조회 강사 선택", st.session_state.ins_df['name'].unique())
    ins_row = st.session_state.ins_df[st.session_state.ins_df['name'] == target].iloc[-1]
    hm = {0: float(ins_row['mon']), 1: float(ins_row['tue']), 2: float(ins_row['wed']), 3: float(ins_row['thu']), 4: float(ins_row['fri'])}
    
    # 툴팁용 사전
    tips = {d: HOLIDAYS_DICT[d] for d in HOLIDAYS_DICT}
    for _, ex in st.session_state.excl_df.iterrows():
        try:
            s, e = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date']))
            while s <= e: tips[s] = ex['note']; s += timedelta(days=1)
        except: continue

    # 방과후 입력 섹션
    st.subheader(f"🎨 {target} 강사 방과후 주별 시수 입력")
    t_after = st.session_state.after_df[st.session_state.after_df['name'] == target]
    after_edit_df = t_after[['month','w1','w2','w3','w4','w5']].reset_index(drop=True) if not t_after.empty else get_initial_after_df()
    
    new_after = st.data_editor(after_edit_df, use_container_width=True, key=f"editor_{target}")
    if st.button(f"{target} 방과후 저장"):
        new_after['name'] = target
        others = st.session_state.after_df[st.session_state.after_df['name'] != target]
        st.session_state.after_df = pd.concat([others, new_after], ignore_index=True)
        conn.update(worksheet="AfterSchool", data=st.session_state.after_df); st.rerun()

    # 데이터 계산
    work_dates = []
    curr = date(2026, 3, 1)
    while curr <= date(2026, 12, 31):
        if curr.weekday() < 5 and curr not in tips and hm.get(curr.weekday(), 0) > 0:
            work_dates.append(curr)
        curr += timedelta(days=1)

    m_stats = []
    total_reg_h, total_aft_h = 0.0, 0.0
    for m in range(3, 13):
        m_dates = [d for d in work_dates if d.month == m]
        r_h = sum([hm[d.weekday()] for d in m_dates])
        a_row = new_after[new_after['month'] == f"{m}월"]
        a_h = a_row[['w1','w2','w3','w4','w5']].sum(axis=1).values[0] if not a_row.empty else 0.0
        m_pay = (r_h * ins_row['rate']) + (a_h * ins_row.get('rate_after', 30000.0))
        m_stats.append({"월": f"{m}월", "정규": f"{r_h:g}h", "방과후": f"{a_h:g}h", "횟수": f"{len(m_dates)}회", "급여": f"{int(m_pay):,}원"})
        total_reg_h += r_h; total_aft_h += a_h

    # 상세 리포트 상단
    st.subheader(f"📊 {target} 강사 상세 리포트")
    pdf_col, space = st.columns([0.2, 0.8])
    with pdf_col:
        try:
            pdf_data = create_pdf(target, ins_row['rate'], ins_row.get('rate_after', 30000.0), total_reg_h, total_aft_h, (total_reg_h*ins_row['rate'])+(total_aft_h*ins_row.get('rate_after',30000.0)), m_stats)
            st.download_button("📄 PDF 리포트 다운로드", pdf_data, f"Report_{target}.pdf", "application/pdf")
        except: st.caption("PDF 폰트 확인 필요")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("정규 시수 합계", f"{total_reg_h:g}h")
    c2.metric("방과후 시수 합계", f"{total_aft_h:g}h")
    c3.metric("최종 통합 시수", f"{total_reg_h+total_aft_h:g}h")
    c4.metric("최종 예상 급여", f"{int((total_reg_h*ins_row['rate'])+(total_aft_h*ins_row.get('rate_after',30000.0))):,}원")

    # 달력 시각화
    st.markdown("""<style>.cal-table { width: 100%; border-collapse: collapse; margin-bottom: 5px; } .cal-table td, .cal-table th { border: 1px solid #ddd; padding: 8px; text-align: center; } .workday { background-color: #90EE90; font-weight: bold; } .excluded { background-color: #FFB6C1; cursor: help; } .weekly-sum { background-color: #f0f2f6; font-size: 0.85em; color: #666; font-weight: bold; }</style>""", unsafe_allow_html=True)
    
    cols = st.columns(2)
    for m in range(3, 13):
        with cols[(m-3)%2]:
            st.write(f"#### {m}월 정규 수업 일정")
            cal = calendar.monthcalendar(2026, m)
            html = '<table class="cal-table"><tr><th>월</th><th>화</th><th>수</th><th>목</th><th>금</th><th class="weekly-sum">주합계</th></tr>'
            for week in cal:
                html += '<tr>'
                w_h = 0.0
                for i in range(5):
                    day = week[i]
                    if day == 0: html += '<td></td>'
                    else:
                        d = date(2026, m, day)
                        cls, title = "", ""
                        if d in work_dates: cls = "workday"; w_h += hm[d.weekday()]
                        elif d in tips: cls = "excluded"; title = f'title="{tips[d]}"'
                        html += f'<td class="{cls}" {title}>{day}</td>'
                html += f'<td class="weekly-sum">{w_h:g}h</td></tr>'
            st.write(html + '</table>', unsafe_allow_html=True)
            ms = m_stats[m-3]
            st.info(f"💰 {m}월 급여: {ms['급여']} | 정규: {ms['정규']} | 방과후: {ms['방과후']}")
