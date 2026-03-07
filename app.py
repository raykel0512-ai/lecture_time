import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar
from fpdf import FPDF
import os

# --- 0. 페이지 설정 ---
st.set_page_config(page_title="2026 강사 통합 관리 Pro", layout="wide")

# --- 1. 구글 시트 연결 및 데이터 로드 ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_initial_after_df(target_name):
    """방과후학교 초기 데이터 프레임"""
    months = [f"{m}월" for m in range(3, 13)]
    return pd.DataFrame({
        "name": [target_name]*10, "month": months,
        "w1": [0]*10, "w2": [0]*10, "w3": [0]*10, "w4": [0]*10, "w5": [0]*10
    })

if 'ins_df' not in st.session_state:
    try:
        df = conn.read(worksheet="Instructors", ttl=0)
        num_cols = ['rate', 'rate_after', 'mon', 'tue', 'wed', 'thu', 'fri']
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        st.session_state.ins_df = df
    except: st.session_state.ins_df = pd.DataFrame(columns=['name', 'rate', 'rate_after', 'mon', 'tue', 'wed', 'thu', 'fri'])

if 'excl_df' not in st.session_state:
    try: st.session_state.excl_df = conn.read(worksheet="Exclusions", ttl=0)
    except: st.session_state.excl_df = pd.DataFrame(columns=['start_date', 'end_date', 'note'])

if 'after_df' not in st.session_state:
    try: 
        df_aft = conn.read(worksheet="AfterSchool", ttl=0)
        for col in ['w1', 'w2', 'w3', 'w4', 'w5']:
            df_aft[col] = pd.to_numeric(df_aft[col], errors='coerce').fillna(0).astype(int)
        st.session_state.after_df = df_aft
    except: st.session_state.after_df = pd.DataFrame(columns=['name', 'month', 'w1', 'w2', 'w3', 'w4', 'w5'])

HOLIDAYS_DICT = {
    date(2026,3,1): "삼일절", date(2026,3,2): "대체공휴일", date(2026,5,5): "어린이날", 
    date(2026,5,24): "부처님오신날", date(2026,5,25): "대체공휴일", date(2026,6,6): "현충일", 
    date(2026,8,15): "광복절", date(2026,8,17): "대체공휴일", date(2026,9,24): "추석", 
    date(2026,9,25): "추석", date(2026,9,26): "추석", date(2026,9,28): "대체공휴일",
    date(2026,10,3): "개천절", date(2026,10,9): "한글날", date(2026,12,25): "성탄절"
}

# --- 2. PDF 생성 함수 (출근일: 정규기준 명시) ---
def create_pdf(target_name, rate, rate_after, total_reg, total_after, total_pay, monthly_stats, attendance_total):
    pdf = FPDF(); pdf.add_page()
    font_path = "font.ttf"
    if os.path.exists(font_path): pdf.add_font("Nanum", "", font_path); pdf.set_font("Nanum", size=18)
    else: pdf.set_font("Arial", size=18)
    pdf.cell(200, 20, txt="2026 강사 수업 시수 확인서", ln=True, align='C')
    if os.path.exists(font_path): pdf.set_font("Nanum", size=10)
    pdf.ln(10); pdf.cell(100, 10, txt=f"강사명: {target_name}", ln=True)
    pdf.cell(100, 8, txt=f"총 출근(정규수업기준): {attendance_total}일 | 총 시수: {int(total_reg + total_after)}시간", ln=True)
    pdf.cell(100, 8, txt=f"최종 예상 지급액: {int(total_pay):,}원", ln=True); pdf.ln(5)
    pdf.cell(12, 10, "월", 1, 0, 'C'); pdf.cell(12, 10, "출근", 1, 0, 'C'); pdf.cell(18, 10, "정규h", 1, 0, 'C'); pdf.cell(18, 10, "방과후h", 1, 0, 'C'); pdf.cell(32, 10, "정규급여", 1, 0, 'C'); pdf.cell(32, 10, "방과후급여", 1, 0, 'C'); pdf.cell(32, 10, "월지급액", 1, 1, 'C')
    for m in monthly_stats:
        pdf.cell(12, 10, m['월'], 1, 0, 'C'); pdf.cell(12, 10, str(m['출근']), 1, 0, 'C'); pdf.cell(18, 10, str(m['정규h']), 1, 0, 'C'); pdf.cell(18, 10, str(m['방과후h']), 1, 0, 'C'); pdf.cell(32, 10, m['정규급여'], 1, 0, 'R'); pdf.cell(32, 10, m['방과후급여'], 1, 0, 'R'); pdf.cell(32, 10, m['급여'], 1, 1, 'R')
    pdf.ln(15); pdf.cell(200, 10, txt="위와 같이 시수 및 급여 산출 내역을 확인합니다.", ln=True, align='C')
    pdf.cell(200, 10, txt=date.today().strftime("%Y년 %m월 %d일"), ln=True, align='C')
    return bytes(pdf.output())

# --- 3. 사이드바 ---
with st.sidebar:
    st.header("👤 강사 관리")
    mode = st.radio("작업", ["등록/수정", "제외일정"])
    if mode == "등록/수정":
        sub = st.selectbox("구분", ["신규 등록", "수정/삭제"])
        if sub == "신규 등록":
            with st.form("add"):
                n = st.text_input("강사 이름")
                r = st.number_input("정규 단가", value=25000, step=1000)
                ra = st.number_input("방과후 단가", value=50000, step=1000)
                m = st.number_input("월", 0); t = st.number_input("화", 0); w = st.number_input("수", 0); th = st.number_input("목", 0); f = st.number_input("금", 0)
                if st.form_submit_button("저장"):
                    new = pd.DataFrame([{"name":n,"rate":r,"rate_after":ra,"mon":m,"tue":t,"wed":w,"thu":th,"fri":f}])
                    st.session_state.ins_df = pd.concat([st.session_state.ins_df, new], ignore_index=True)
                    conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
        else:
            if not st.session_state.ins_df.empty:
                tn = st.selectbox("선택", st.session_state.ins_df['name'].unique())
                td = st.session_state.ins_df[st.session_state.ins_df['name'] == tn].iloc[0]
                with st.form("edit"):
                    er = st.number_input("정규 단가", value=int(td['rate']))
                    era = st.number_input("방과후 단가", value=int(td.get('rate_after', 50000)))
                    em = st.number_input("월", value=int(td['mon'])); et = st.number_input("화", value=int(td['tue'])); ew = st.number_input("수", value=int(td['wed'])); eth = st.number_input("목", value=int(td['thu'])); ef = st.number_input("금", value=int(td['fri']))
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("수정"):
                        st.session_state.ins_df.loc[st.session_state.ins_df['name']==tn, ['rate','rate_after','mon','tue','wed','thu','fri']] = [er, era, em, et, ew, eth, ef]
                        conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
                    if c2.form_submit_button("❌ 삭제"):
                        st.session_state.ins_df = st.session_state.ins_df[st.session_state.ins_df['name']!=tn]
                        conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
    else:
        ex_r = st.date_input("제외 기간", (date(2026,7,20), date(2026,8,20)))
        ex_n = st.text_input("사유")
        if st.button("제외 저장"):
            new_ex = pd.DataFrame([{"start_date": ex_r[0].isoformat(), "end_date": ex_r[1].isoformat(), "note": ex_n}])
            st.session_state.excl_df = pd.concat([st.session_state.excl_df, new_ex], ignore_index=True)
            conn.update(worksheet="Exclusions", data=st.session_state.excl_df); st.rerun()

# --- 4. 메인 대시보드 ---
st.title("👨‍🏫 2026 강사 통합 관리 시스템 (정규/방과후)")
all_excl = {d for d in HOLIDAYS_DICT}
for _, ex in st.session_state.excl_df.iterrows():
    try:
        s, e = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date']))
        while s <= e: all_excl.add(s); s += timedelta(days=1)
    except: continue

col_e, col_b = st.columns([0.6, 0.4])
with col_e:
    with st.expander("🗓️ 공통 제외 일정 관리"):
        edited_ex = st.data_editor(st.session_state.excl_df, num_rows="dynamic", use_container_width=True)
        if st.button("공통 일정 저장"):
            st.session_state.excl_df = edited_ex
            conn.update(worksheet="Exclusions", data=edited_ex); st.rerun()
with col_b:
    grand_total = 0
    if not st.session_state.ins_df.empty:
        for _, ins in st.session_state.ins_df.iterrows():
            hm_all = {0: int(ins['mon']), 1: int(ins['tue']), 2: int(ins['wed']), 3: int(ins['thu']), 4: int(ins['fri'])}
            curr = date(2026, 3, 1)
            while curr <= date(2026, 12, 31):
                if curr.weekday() < 5 and curr not in all_excl: grand_total += hm_all.get(curr.weekday(), 0) * int(ins['rate'])
                curr += timedelta(days=1)
            target_aft = st.session_state.after_df[st.session_state.after_df['name'] == ins['name']]
            grand_total += int(target_aft[['w1','w2','w3','w4','w5']].sum().sum() * ins.get('rate_after', 50000))
    st.metric("연간 총 소요 예산", f"{grand_total:,}원")

st.divider()

# --- 5. 상세 리포트 ---
if not st.session_state.ins_df.empty:
    target = st.selectbox("조회 강사 선택", st.session_state.ins_df['name'].unique())
    ins_row = st.session_state.ins_df[st.session_state.ins_df['name'] == target].iloc[-1]
    hm = {0: int(ins_row['mon']), 1: int(ins_row['tue']), 2: int(ins_row['wed']), 3: int(ins_row['thu']), 4: int(ins_row['fri'])}
    
    # 방과후 데이터
    target_aft_data = st.session_state.after_df[st.session_state.after_df['name'] == target]
    cur_aft_df = target_aft_data.copy().reset_index(drop=True) if not target_aft_data.empty else get_initial_after_df(target)

    tips = {d: HOLIDAYS_DICT[d] for d in HOLIDAYS_DICT}
    for _, ex in st.session_state.excl_df.iterrows():
        try:
            s, e = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date']))
            while s <= e: tips[s] = ex['note']; s += timedelta(days=1)
        except: continue

    work_dates = [d for d in [date(2026,3,1) + timedelta(n) for n in range(306)] if d.weekday() < 5 and d not in tips and hm.get(d.weekday(), 0) > 0]

    m_stats = []
    total_reg_h, total_aft_h, total_att = 0, 0, 0
    
    st.subheader(f"📊 {target} 강사 상세 리포트")
    cols = st.columns(2)
    for m in range(3, 13):
        with cols[(m-3)%2]:
            st.write(f"#### 🗓️ {m}월")
            cal_col, aft_col = st.columns([0.75, 0.25])
            
            monthly_reg_att_days = set()
            with cal_col:
                cal = calendar.monthcalendar(2026, m)
                html = '<table style="width:100%; border-collapse:collapse; text-align:center; font-size:14px;">'
                html += '<tr style="background:#f0f2f6;"><th>월</th><th>화</th><th>수</th><th>목</th><th>금</th><th style="color:#666;">정규h</th><th style="color:#007bff; font-weight:bold;">통합h</th></tr>'
                
                # 방과후 시수 추출 (월별/주별)
                m_label = f"{m}월"
                r_idx = cur_aft_df[cur_aft_df['month'] == m_label].index[0]
                aft_vals = [int(cur_aft_df.at[r_idx, f'w{i+1}']) for i in range(5)]

                for w_idx, week in enumerate(cal):
                    if w_idx >= 5: break # 5주차까지만 표시
                    html += '<tr>'
                    w_reg_h = 0
                    for i in range(5):
                        day = week[i]
                        if day == 0: html += '<td></td>'
                        else:
                            d = date(2026, m, day)
                            cls, title = "", ""
                            if d in work_dates: 
                                cls = "background:#90EE90; font-weight:bold;"
                                w_reg_h += hm[d.weekday()]
                                monthly_reg_att_days.add(d)
                            elif d in tips: 
                                cls = "background:#FFB6C1; cursor:help;"
                                title = f'title="{tips[d]}"'
                            html += f'<td style="border:1px solid #ddd; padding:5px; {cls}" {title}>{day}</td>'
                    
                    # 주별 합계 열
                    w_aft_h = aft_vals[w_idx]
                    html += f'<td style="border:1px solid #ddd; background:#f9f9f9; color:#666;">{int(w_reg_h)}</td>'
                    html += f'<td style="border:1px solid #ddd; background:#eef6ff; color:#007bff; font-weight:bold;">{int(w_reg_h + w_aft_h)}</td></tr>'
                st.write(html + '</table>', unsafe_allow_html=True)

            with aft_col:
                st.caption("방과후 입력")
                w1 = st.number_input(f"{m}월 1주", value=aft_vals[0], step=1, key=f"w1_{target}_{m}")
                w2 = st.number_input(f"{m}월 2주", value=aft_vals[1], step=1, key=f"w2_{target}_{m}")
                w3 = st.number_input(f"{m}월 3주", value=aft_vals[2], step=1, key=f"w3_{target}_{m}")
                w4 = st.number_input(f"{m}월 4주", value=aft_vals[3], step=1, key=f"w4_{target}_{m}")
                w5 = st.number_input(f"{m}월 5주", value=aft_vals[4], step=1, key=f"w5_{target}_{m}")
                cur_aft_df.loc[r_idx, ['w1','w2','w3','w4','w5']] = [w1, w2, w3, w4, w5]

            # 통계 계산 (출근일: 정규수업 기준)
            m_att = len(monthly_reg_att_days)
            m_reg_h = sum([hm[d.weekday()] for d in monthly_reg_att_days])
            m_aft_h = int(w1+w2+w3+w4+w5)
            m_reg_pay = m_reg_h * int(ins_row['rate'])
            m_aft_pay = m_aft_h * int(ins_row.get('rate_after', 50000))
            
            st.info(f"""
            **💰 {m}월 통합 급여: {(m_reg_pay + m_aft_pay):,}원**  
            - 정규: {m_reg_pay:,}원 ({int(m_reg_h)}h) | 방과후: {m_aft_pay:,}원 ({int(m_aft_h)}h)  
            - 정규 출근: {m_att}일 / 통합 시수: {int(m_reg_h+m_aft_h)}h
            """)
            m_stats.append({"월":f"{m}월", "출근":m_att, "정규h":m_reg_h, "방과후h":m_aft_h, "정규급여":f"{m_reg_pay:,}원", "방과후급여":f"{m_aft_pay:,}원", "급여":f"{(m_reg_pay + m_aft_pay):,}"})
            total_reg_h += m_reg_h; total_aft_h += m_aft_h; total_att += m_att

    # 저장 및 최종 요약
    st.divider()
    if st.button(f"💾 {target} 강사 시수 저장 및 동기화"):
        others = st.session_state.after_df[st.session_state.after_df['name'] != target]
        st.session_state.after_df = pd.concat([others, cur_aft_df], ignore_index=True)
        conn.update(worksheet="AfterSchool", data=st.session_state.after_df); st.rerun()

    st.subheader("🏁 연간 최종 합계")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 출근 (정규기준)", f"{total_att}일")
    c2.metric("정규 총 시수", f"{int(total_reg_h)}h")
    c3.metric("방과후 총 시수", f"{int(total_aft_h)}h")
    c4.metric("최종 예상 급여", f"{int((total_reg_h*ins_row['rate'])+(total_aft_h*ins_row.get('rate_after',50000))):,}원")

    try:
        pdf_b = create_pdf(target, ins_row['rate'], ins_row.get('rate_after', 50000), total_reg_h, total_aft_h, (total_reg_h*ins_row['rate'])+(total_aft_h*ins_row.get('rate_after',50000)), m_stats, total_att)
        st.download_button("📄 PDF 확인서 다운로드", pdf_b, f"Report_{target}.pdf", "application/pdf")
    except: st.caption("PDF 생성 중...")
