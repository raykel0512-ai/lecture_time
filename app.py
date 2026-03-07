import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar
from fpdf import FPDF
import os

# --- 0. 페이지 설정 ---
st.set_page_config(page_title="2026 강사 통합 관리 Pro", layout="wide")

# --- 1. 구글 시트 연결 및 세션 데이터 초기화 ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_initial_after_df(target_name):
    """특정 강사의 방과후 초기 데이터 프레임"""
    months = [f"{m}월" for m in range(3, 13)]
    return pd.DataFrame({
        "name": [target_name]*10,
        "month": months,
        "w1": [0.0]*10, "w2": [0.0]*10, "w3": [0.0]*10, "w4": [0.0]*10, "w5": [0.0]*10
    })

# 데이터 로드
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
    try: 
        df_aft = conn.read(worksheet="AfterSchool", ttl=0)
        for col in ['w1', 'w2', 'w3', 'w4', 'w5']:
            df_aft[col] = pd.to_numeric(df_aft[col], errors='coerce').fillna(0.0).astype(float)
        st.session_state.after_df = df_aft
    except: st.session_state.after_df = pd.DataFrame(columns=['name', 'month', 'w1', 'w2', 'w3', 'w4', 'w5'])

HOLIDAYS_DICT = {
    date(2026,3,1): "삼일절", date(2026,3,2): "대체공휴일", date(2026,5,5): "어린이날", 
    date(2026,5,24): "부처님오신날", date(2026,5,25): "대체공휴일", date(2026,6,6): "현충일", 
    date(2026,8,15): "광복절", date(2026,8,17): "대체공휴일", date(2026,9,24): "추석", 
    date(2026,9,25): "추석", date(2026,9,26): "추석", date(2026,9,28): "대체공휴일",
    date(2026,10,3): "개천절", date(2026,10,9): "한글날", date(2026,12,25): "성탄절"
}

# --- 2. PDF 생성 함수 ---
def create_pdf(target_name, rate, rate_after, total_reg, total_after, total_pay, monthly_stats, attendance_total):
    pdf = FPDF(); pdf.add_page()
    font_path = "font.ttf"
    if os.path.exists(font_path): pdf.add_font("Nanum", "", font_path); pdf.set_font("Nanum", size=18)
    else: pdf.set_font("Arial", size=18)
    pdf.cell(200, 20, txt="2026 강사 수업 시수 및 출근 확인서", ln=True, align='C')
    if os.path.exists(font_path): pdf.set_font("Nanum", size=11)
    pdf.ln(10); pdf.cell(100, 10, txt=f"강사명: {target_name}", ln=True)
    pdf.cell(100, 10, txt=f"총 출근 일수: {attendance_total}일", ln=True)
    pdf.cell(100, 10, txt=f"총 시수: {total_reg + total_after:g}시간 (정규 {total_reg:g}h, 방과후 {total_after:g}h)", ln=True)
    pdf.cell(100, 10, txt=f"총 예상 지급액: {int(total_pay):,}원", ln=True); pdf.ln(10)
    pdf.cell(20, 10, "월", 1, 0, 'C'); pdf.cell(30, 10, "출근일수", 1, 0, 'C'); pdf.cell(30, 10, "정규시수", 1, 0, 'C'); pdf.cell(30, 10, "방과후시수", 1, 0, 'C'); pdf.cell(50, 10, "월지급액", 1, 0, 'C'); pdf.ln()
    for m in monthly_stats:
        pdf.cell(20, 10, m['월'], 1, 0, 'C'); pdf.cell(30, 10, str(m['출근']), 1, 0, 'C'); pdf.cell(30, 10, m['정규'], 1, 0, 'C'); pdf.cell(30, 10, m['방과후'], 1, 0, 'C'); pdf.cell(50, 10, m['급여'], 1, 0, 'R'); pdf.ln()
    return bytes(pdf.output())

# --- 3. 사이드바 ---
with st.sidebar:
    st.header("👤 강사 관리")
    mode = st.radio("작업", ["등록/수정", "제외일정"])
    if mode == "등록/수정":
        sub = st.selectbox("구분", ["신규", "수정/삭제"])
        if sub == "신규":
            with st.form("add"):
                n = st.text_input("이름")
                r = st.number_input("정규 단가", value=25000.0)
                ra = st.number_input("방과후 단가", value=50000.0)
                m = st.number_input("월", 0.0); t = st.number_input("화", 0.0); w = st.number_input("수", 0.0); th = st.number_input("목", 0.0); f = st.number_input("금", 0.0)
                if st.form_submit_button("저장"):
                    new = pd.DataFrame([{"name":n,"rate":r,"rate_after":ra,"mon":m,"tue":t,"wed":w,"thu":th,"fri":f}])
                    st.session_state.ins_df = pd.concat([st.session_state.ins_df, new], ignore_index=True)
                    conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
        else:
            if not st.session_state.ins_df.empty:
                tn = st.selectbox("선택", st.session_state.ins_df['name'].unique())
                td = st.session_state.ins_df[st.session_state.ins_df['name'] == tn].iloc[0]
                with st.form("edit"):
                    er = st.number_input("정규 단가", value=float(td['rate']))
                    era = st.number_input("방과후 단가", value=float(td.get('rate_after', 50000.0)))
                    em = st.number_input("월", value=float(td['mon'])); et = st.number_input("화", value=float(td['tue']))
                    ew = st.number_input("수", value=float(td['wed'])); eth = st.number_input("목", value=float(td['thu'])); ef = st.number_input("금", value=float(td['fri']))
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("수정"):
                        st.session_state.ins_df.loc[st.session_state.ins_df['name']==tn, ['rate','rate_after','mon','tue','wed','thu','fri']] = [er, era, em, et, ew, eth, ef]
                        conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
                    if c2.form_submit_button("삭제"):
                        st.session_state.ins_df = st.session_state.ins_df[st.session_state.ins_df['name']!=tn]
                        conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
    else:
        ex_r = st.date_input("제외 기간", (date(2026,7,20), date(2026,8,20)))
        ex_n = st.text_input("사유")
        if st.button("제외 저장"):
            new_ex = pd.DataFrame([{"start_date": ex_r[0].isoformat(), "end_date": ex_r[1].isoformat(), "note": ex_n}])
            st.session_state.excl_df = pd.concat([st.session_state.excl_df, new_ex], ignore_index=True)
            conn.update(worksheet="Exclusions", data=st.session_state.excl_df); st.rerun()

# --- 4. 메인 화면 ---
st.title("📚 2026 강사 통합 관리 시스템 (정규/방과후)")
all_excl = {d for d in HOLIDAYS_DICT}
for _, ex in st.session_state.excl_df.iterrows():
    try:
        s, e = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date']))
        while s <= e: all_excl.add(s); s += timedelta(days=1)
    except: continue

col_e, col_b = st.columns([0.65, 0.35])
with col_e:
    with st.expander("🗓️ 공통 제외 일정 관리"):
        edited_ex = st.data_editor(st.session_state.excl_df, num_rows="dynamic", use_container_width=True)
        if st.button("공통 일정 저장"):
            st.session_state.excl_df = edited_ex
            conn.update(worksheet="Exclusions", data=edited_ex); st.rerun()
with col_b:
    grand_total = 0.0
    for _, ins in st.session_state.ins_df.iterrows():
        hm_all = {0: ins['mon'], 1: ins['tue'], 2: ins['wed'], 3: ins['thu'], 4: ins['fri']}
        curr = date(2026, 3, 1)
        while curr <= date(2026, 12, 31):
            if curr.weekday() < 5 and curr not in all_excl: grand_total += hm_all.get(curr.weekday(), 0.0) * ins['rate']
            curr += timedelta(days=1)
        target_after = st.session_state.after_df[st.session_state.after_df['name'] == ins['name']]
        grand_total += target_after[['w1','w2','w3','w4','w5']].sum().sum() * ins.get('rate_after', 50000.0)
    st.metric("연간 총 소요 예산", f"{int(grand_total):,}원")

st.divider()

if not st.session_state.ins_df.empty:
    target = st.selectbox("조회 강사 선택", st.session_state.ins_df['name'].unique())
    ins_row = st.session_state.ins_df[st.session_state.ins_df['name'] == target].iloc[-1]
    hm = {0: float(ins_row['mon']), 1: float(ins_row['tue']), 2: float(ins_row['wed']), 3: float(ins_row['thu']), 4: float(ins_row['fri'])}
    
    # 해당 강사 방과후 데이터
    target_after = st.session_state.after_df[st.session_state.after_df['name'] == target]
    if target_after.empty: after_input_df = get_initial_after_df(target)
    else: after_input_df = target_after[['month','w1','w2','w3','w4','w5']].reset_index(drop=True)

    tips = {d: HOLIDAYS_DICT[d] for d in HOLIDAYS_DICT}
    for _, ex in st.session_state.excl_df.iterrows():
        try:
            s, e = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date']))
            while s <= e: tips[s] = ex['note']; s += timedelta(days=1)
        except: continue

    work_dates = []
    curr = date(2026, 3, 1)
    while curr <= date(2026, 12, 31):
        if curr.weekday() < 5 and curr not in tips and hm.get(curr.weekday(), 0) > 0: work_dates.append(curr)
        curr += timedelta(days=1)

    m_stats = []
    total_reg_h, total_aft_h, total_att = 0.0, 0.0, 0
    
    # ------------------ 메인 루프 (달력 및 계산) ------------------
    st.subheader(f"👨‍🏫 {target} 강사 상세 리포트")
    cols = st.columns(2)
    for m in range(3, 13):
        with cols[(m-3)%2]:
            st.write(f"#### {m}월 수업 및 방과후 입력")
            
            # 레이아웃 분할: 왼쪽 달력, 오른쪽 방과후 입력
            cal_col, aft_col = st.columns([0.7, 0.3])
            
            with cal_col:
                cal = calendar.monthcalendar(2026, m)
                html = '<table style="width:100%; border-collapse:collapse; text-align:center; font-size:14px;">'
                html += '<tr style="background:#f0f2f6;"><th>월</th><th>화</th><th>수</th><th>목</th><th>금</th><th style="color:#666;">주합계</th></tr>'
                
                monthly_reg_att_days = set()
                weeks_with_aft = [] # 각 주차별 방과후 여부
                
                for week_idx, week in enumerate(cal):
                    html += '<tr>'
                    w_h = 0.0
                    for i in range(5):
                        day = week[i]
                        if day == 0: html += '<td></td>'
                        else:
                            d = date(2026, m, day)
                            cls, title = "", ""
                            if d in work_dates: 
                                cls = "background:#90EE90; font-weight:bold;"
                                w_h += hm[d.weekday()]
                                monthly_reg_att_days.add(d)
                            elif d in tips: 
                                cls = "background:#FFB6C1; cursor:help;"
                                title = f'title="{tips[d]}"'
                            html += f'<td style="border:1px solid #ddd; padding:5px; {cls}" {title}>{day}</td>'
                    html += f'<td style="border:1px solid #ddd; background:#f9f9f9; color:#666;">{w_h:g}h</td></tr>'
                html += '</table>'
                st.write(html, unsafe_allow_html=True)

            with aft_col:
                st.caption("방과후 시수")
                m_aft_row = after_input_df[after_input_df['month'] == f"{m}월"].iloc[0]
                w1 = st.number_input(f"{m}월 1주", value=float(m_aft_row['w1']), key=f"w1_{m}")
                w2 = st.number_input(f"{m}월 2주", value=float(m_aft_row['w2']), key=f"w2_{m}")
                w3 = st.number_input(f"{m}월 3주", value=float(m_aft_row['w3']), key=f"w3_{m}")
                w4 = st.number_input(f"{m}월 4주", value=float(m_aft_row['w4']), key=f"w4_{m}")
                w5 = st.number_input(f"{m}월 5주", value=float(m_aft_row['w5']), key=f"w5_{m}")
                after_input_df.loc[after_input_df['month'] == f"{m}월", ['w1','w2','w3','w4','w5']] = [w1, w2, w3, w4, w5]

            # 출근 일수 계산 (정규일수 + 방과후만 있는 주차 카운트)
            # 엄격한 OR 조건을 위해: 정규수업이 없는 주에 방과후가 있다면 출근+1로 가정
            aft_weeks_count = 0
            for wi, wv in enumerate([w1, w2, w3, w4, w5]):
                if wv > 0:
                    # 해당 주차에 정규수업이 하나도 없었는지 체크
                    week_days = [d for d in cal[wi] if d != 0]
                    if not any(date(2026, m, d) in monthly_reg_att_days for d in week_days):
                        aft_weeks_count += 1
            
            m_att_count = len(monthly_reg_att_days) + aft_weeks_count
            m_reg_h = sum([hm[d.weekday()] for d in monthly_reg_att_days])
            m_aft_h = w1+w2+w3+w4+w5
            m_pay = (m_reg_h * ins_row['rate']) + (m_aft_h * ins_row.get('rate_after', 50000.0))
            
            st.info(f"💰 {m}월 급여: {int(m_pay):,}원 (출근 {m_att_count}일 / {m_reg_h+m_aft_h:g}시간)")
            m_stats.append({"월":f"{m}월", "출근":m_att_count, "정규":f"{m_reg_h:g}h", "방과후":f"{m_aft_h:g}h", "급여":f"{int(m_pay):,}원"})
            total_reg_h += m_reg_h; total_aft_h += m_aft_h; total_att += m_att_count

    # 저장 버튼 (방과후 데이터 일괄 저장)
    st.divider()
    if st.button(f"💾 {target} 강사의 모든 방과후 시수 및 수정사항 저장"):
        others = st.session_state.after_df[st.session_state.after_df['name'] != target]
        st.session_state.after_df = pd.concat([others, after_input_df], ignore_index=True)
        conn.update(worksheet="AfterSchool", data=st.session_state.after_df)
        st.success("데이터가 구글 시트에 안전하게 저장되었습니다!"); st.rerun()

    # 최종 요약 대시보드
    st.subheader("🏁 최종 합계")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 출근 일수", f"{total_att}일")
    c2.metric("총 정규 시수", f"{total_reg_h:g}h")
    c3.metric("총 방과후 시수", f"{total_aft_h:g}h")
    c4.metric("최종 예상 급여", f"{int((total_reg_h*ins_row['rate'])+(total_aft_h*ins_row.get('rate_after',50000.0))):,}원")

    # PDF 다운로드
    try:
        pdf_b = create_pdf(target, ins_row['rate'], ins_row.get('rate_after', 50000.0), total_reg_h, total_aft_h, (total_reg_h*ins_row['rate'])+(total_aft_h*ins_row.get('rate_after',50000.0)), m_stats, total_att)
        st.download_button("📄 통합 확인서 PDF 다운로드", pdf_b, f"Report_{target}.pdf", "application/pdf")
    except: st.caption("PDF 생성 대기 중 (font.ttf 필요)")
