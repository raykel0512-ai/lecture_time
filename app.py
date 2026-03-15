import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar
from fpdf import FPDF
import os

# --- 0. 페이지 설정 ---
st.set_page_config(page_title="2026 강사 통합 관리 시스템 Pro", layout="wide")

# --- 1. 데이터 연결 및 로드 ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_initial_after_df(target_name):
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
    except: st.session_state.ins_df = pd.DataFrame(columns=['name', 'rate', 'rate_after', 'mon', 'tue', 'wed', 'thu', 'fri', 'subject', 'target_classes'])

if 'excl_df' not in st.session_state:
    try: st.session_state.excl_df = conn.read(worksheet="Exclusions", ttl=0)
    except: st.session_state.excl_df = pd.DataFrame(columns=['start_date', 'end_date', 'note'])

if 'after_df' not in st.session_state:
    try: 
        df_aft = conn.read(worksheet="AfterSchool", ttl=0)
        for col in ['w1', 'w2', 'w3', 'w4', 'w5']:
            if col in df_aft.columns: df_aft[col] = pd.to_numeric(df_aft[col], errors='coerce').fillna(0).astype(int)
        st.session_state.after_df = df_aft
    except: st.session_state.after_df = pd.DataFrame(columns=['name', 'month', 'w1', 'w2', 'w3', 'w4', 'w5'])

if 'excl_indiv_df' not in st.session_state:
    try: st.session_state.excl_indiv_df = conn.read(worksheet="Exclusions_Indiv", ttl=0)
    except: st.session_state.excl_indiv_df = pd.DataFrame(columns=['name', 'date', 'type', 'note'])

HOLIDAYS_DICT = {
    date(2026,3,1): "삼일절", date(2026,3,2): "대체공휴일", date(2026,5,5): "어린이날", 
    date(2026,5,24): "부처님오신날", date(2026,5,25): "대체공휴일", date(2026,6,6): "현충일", 
    date(2026,8,15): "광복절", date(2026,8,17): "대체공휴일", date(2026,9,24): "추석", 
    date(2026,9,25): "추석", date(2026,9,26): "추석", date(2026,9,28): "대체공휴일",
    date(2026,10,3): "개천절", date(2026,10,9): "한글날", date(2026,12,25): "성탄절"
}

# --- 2. 이미지 양식 맞춤형 PDF 생성 함수 ---
def create_monthly_pdf(target_row, month, worked_dates, after_weeks, h_map):
    pdf = FPDF()
    pdf.add_page()
    font_path = "font.ttf"
    if os.path.exists(font_path): pdf.add_font("Nanum", "", font_path); pdf.set_font("Nanum", size=11)
    else: pdf.set_font("Arial", size=11)

    # 제목
    pdf.set_font("Nanum", size=18)
    pdf.cell(190, 15, txt=f"2026학년도 {month} 시간강사 수업 현황", ln=True, align='C')
    pdf.set_font("Nanum", size=11)
    pdf.ln(5)

    # 상단 정보 표 (이름, 과목, 학급 등)
    col_w = [40, 150]
    pdf.cell(col_w[0], 10, "성 명", 1, 0, 'C'); pdf.cell(col_w[1], 10, f" {target_row['name']}", 1, 1, 'L')
    pdf.cell(col_w[0], 10, "담당과목", 1, 0, 'C'); pdf.cell(col_w[1], 10, f" {target_row.get('subject', '-')}", 1, 1, 'L')
    pdf.cell(col_w[0], 10, "담당학급", 1, 0, 'C'); pdf.cell(col_w[1], 10, f" {target_row.get('target_classes', '-')}", 1, 1, 'L')
    
    start_day = f"2026. {month.replace('월','').zfill(2)}. 01."
    last_day = calendar.monthrange(2026, int(month.replace('월','')))[1]
    end_day = f"2026. {month.replace('월','').zfill(2)}. {last_day}."
    pdf.cell(col_w[0], 10, "기 간", 1, 0, 'C'); pdf.cell(col_w[1], 10, f" {start_day} ~ {end_day}", 1, 1, 'L')

    # 수업 요일/시간 정보 요약
    days_text = []
    days_kor = ["월", "화", "수", "목", "금"]
    for i in range(5):
        if h_map[i] > 0: days_text.append(f"{days_kor[i]}요일 {int(h_map[i])}시간")
    pdf.cell(col_w[0], 10, "실시요일-수업시수", 1, 0, 'C'); pdf.cell(col_w[1], 10, f" {', '.join(days_text)}", 1, 1, 'L')
    pdf.ln(2)

    # 메인 테이블 헤더
    pdf.set_fill_color(240, 240, 240)
    cols = [15, 40, 25, 30, 40, 40]
    headers = ["연번", "날짜", "요일", "수업시수", "강사료(원)", "비고"]
    for i, h in enumerate(headers):
        pdf.cell(cols[i], 10, h, 1, 0, 'C', fill=True)
    pdf.ln()

    # 데이터 작성 (최대 12줄 양식 유지)
    row_count = 0
    total_h = 0
    total_pay = 0
    
    # 1. 정규 수업 데이터
    for d in sorted(worked_dates):
        row_count += 1
        h = h_map[d.weekday()]
        pay = h * target_row['rate']
        pdf.cell(cols[0], 8, str(row_count), 1, 0, 'C')
        pdf.cell(cols[1], 8, d.strftime("%m월 %d일"), 1, 0, 'C')
        pdf.cell(cols[2], 8, days_kor[d.weekday()], 1, 0, 'C')
        pdf.cell(cols[3], 8, str(int(h)), 1, 0, 'C')
        pdf.cell(cols[4], 8, f"{int(pay):,}", 1, 0, 'R')
        pdf.cell(cols[5], 8, "", 1, 1, 'C')
        total_h += h
        total_pay += pay

    # 2. 방과후 수업 데이터 (주차별로 기입)
    for i, h in enumerate(after_weeks):
        if h > 0:
            row_count += 1
            pay = h * target_row.get('rate_after', 50000)
            pdf.cell(cols[0], 8, str(row_count), 1, 0, 'C')
            pdf.cell(cols[1], 8, f"방과후 {i+1}주차", 1, 0, 'C')
            pdf.cell(cols[2], 8, "-", 1, 0, 'C')
            pdf.cell(cols[3], 8, str(int(h)), 1, 0, 'C')
            pdf.cell(cols[4], 8, f"{int(pay):,}", 1, 0, 'R')
            pdf.cell(cols[5], 8, "방과후학교", 1, 1, 'C')
            total_h += h
            total_pay += pay

    # 12행까지 빈칸 채우기
    while row_count < 12:
        row_count += 1
        for i in range(6): pdf.cell(cols[i], 8, "", 1, (1 if i==5 else 0), 'C')

    # 합계 행
    pdf.set_fill_color(255, 255, 153) # 노란색 강조
    pdf.cell(cols[0]+cols[1]+cols[2], 10, "합계", 1, 0, 'C', fill=True)
    pdf.cell(cols[3], 10, f"{len(worked_dates)}일", 1, 0, 'C', fill=True)
    pdf.cell(cols[4], 10, f"{int(total_h)}시간", 1, 0, 'C', fill=True)
    pdf.cell(cols[5], 10, f"{int(total_pay):,}원", 1, 1, 'C', fill=True)

    pdf.ln(5)
    pdf.cell(190, 10, f"* 시간당 강사료 : 정규 {int(target_row['rate']):,}원 / 방과후 {int(target_row.get('rate_after', 50000)):,}원", ln=True)
    
    return bytes(pdf.output())

# --- 3. 사이드바 (정보입력 보완) ---
with st.sidebar:
    st.header("👤 강사 관리")
    mode = st.radio("작업", ["등록/수정", "공통제외일정"])
    if mode == "등록/수정":
        sub = st.selectbox("구분", ["신규 등록", "수정/삭제"])
        if sub == "신규 등록":
            with st.form("add"):
                n = st.text_input("강사 이름")
                subj = st.text_input("담당 과목", value="통합과학")
                cls_info = st.text_input("담당 학급", value="1학년 1반 ~ 8반")
                r = st.number_input("정규 단가", value=25000)
                ra = st.number_input("방과후 단가", value=50000)
                m = st.number_input("월 시수", 0); t = st.number_input("화", 0); w = st.number_input("수", 0); th = st.number_input("목", 0); f = st.number_input("금", 0)
                if st.form_submit_button("저장"):
                    new = pd.DataFrame([{"name":n,"rate":r,"rate_after":ra,"mon":m,"tue":t,"wed":w,"thu":th,"fri":f, "subject":subj, "target_classes":cls_info}])
                    st.session_state.ins_df = pd.concat([st.session_state.ins_df, new], ignore_index=True)
                    conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
        else:
            if not st.session_state.ins_df.empty:
                tn = st.selectbox("선택", st.session_state.ins_df['name'].unique())
                td = st.session_state.ins_df[st.session_state.ins_df['name'] == tn].iloc[0]
                with st.form("edit"):
                    esubj = st.text_input("과목", value=td.get('subject', ''))
                    ecls = st.text_input("학급", value=td.get('target_classes', ''))
                    er = st.number_input("정규단가", value=int(td['rate']))
                    era = st.number_input("방과후단가", value=int(td.get('rate_after', 50000)))
                    em = st.number_input("월", value=int(td['mon'])); et = st.number_input("화", value=int(td['tue'])); ew = st.number_input("수", value=int(td['wed'])); eth = st.number_input("목", value=int(td['thu'])); ef = st.number_input("금", value=int(td['fri']))
                    if st.form_submit_button("수정"):
                        st.session_state.ins_df.loc[st.session_state.ins_df['name']==tn, ['rate','rate_after','mon','tue','wed','thu','fri','subject','target_classes']] = [er, era, em, et, ew, eth, ef, esubj, ecls]
                        conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
                    if st.form_submit_button("❌ 삭제"):
                        st.session_state.ins_df = st.session_state.ins_df[st.session_state.ins_df['name']!=tn]
                        conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
    else:
        ex_r = st.date_input("제외 기간", (date(2026,7,20), date(2026,8,20)))
        ex_n = st.text_input("사유")
        if st.button("공통 제외 저장"):
            new_ex = pd.DataFrame([{"start_date": ex_r[0].isoformat(), "end_date": ex_r[1].isoformat(), "note": ex_n}])
            st.session_state.excl_df = pd.concat([st.session_state.excl_df, new_ex], ignore_index=True)
            conn.update(worksheet="Exclusions", data=st.session_state.excl_df); st.rerun()

# --- 4. 메인 화면 및 리포트 ---
st.title("👨‍🏫 2026 강사 통합 관리 시스템 (양식 출력 포함)")

all_excl_common = {d for d in HOLIDAYS_DICT}
for _, ex in st.session_state.excl_df.iterrows():
    try:
        s, e = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date']))
        while s <= e: all_excl_common.add(s); s += timedelta(days=1)
    except: continue

# 대시보드
grand_total = 0
if not st.session_state.ins_df.empty:
    for _, ins in st.session_state.ins_df.iterrows():
        ind_ex = set()
        ind_add = set()
        if not st.session_state.excl_indiv_df.empty:
            i_df = st.session_state.excl_indiv_df[st.session_state.excl_indiv_df['name'] == ins['name']]
            ind_ex = {date.fromisoformat(str(d)) for d in i_df[i_df['type']=='개인휴무']['date'].tolist()}
            ind_add = {date.fromisoformat(str(d)) for d in i_df[i_df['type']=='추가출근']['date'].tolist()}
        hm_all = {0: int(ins['mon']), 1: int(ins['tue']), 2: int(ins['wed']), 3: int(ins['thu']), 4: int(ins['fri'])}
        curr = date(2026, 3, 1)
        while curr <= date(2026, 12, 31):
            if (curr.weekday() < 5 and curr not in all_excl_common and curr not in ind_ex) or (curr in ind_add):
                grand_total += hm_all.get(curr.weekday(), 0) * int(ins['rate'])
            curr += timedelta(days=1)
        t_aft = st.session_state.after_df[st.session_state.after_df['name'] == ins['name']]
        grand_total += int(t_aft[['w1','w2','w3','w4','w5']].sum().sum() * ins.get('rate_after', 50000))

st.metric("✅ 2026년 전체 예상 소요 예산", f"{grand_total:,}원")
st.divider()

if not st.session_state.ins_df.empty:
    target = st.selectbox("조회 강사", st.session_state.ins_df['name'].unique())
    ins_row = st.session_state.ins_df[st.session_state.ins_df['name'] == target].iloc[-1]
    hm = {0: int(ins_row['mon']), 1: int(ins_row['tue']), 2: int(ins_row['wed']), 3: int(ins_row['thu']), 4: int(ins_row['fri'])}
    
    # 개인 일정 관리
    st.subheader(f"📍 {target} 강사 개인 일정")
    c_i1, c_i2 = st.columns([0.6, 0.4])
    with c_i1:
        with st.form(f"indiv_{target}"):
            in_d = st.date_input("날짜"); in_t = st.selectbox("구분", ["개인휴무", "추가출근"]); in_n = st.text_input("사유")
            if st.form_submit_button("추가"):
                new_i = pd.DataFrame([{"name":target, "date":in_d.isoformat(), "type":in_t, "note":in_n}])
                st.session_state.excl_indiv_df = pd.concat([st.session_state.excl_indiv_df, new_i], ignore_index=True)
                conn.update(worksheet="Exclusions_Indiv", data=st.session_state.excl_indiv_df); st.rerun()
    with c_i2:
        target_ind_ex = st.session_state.excl_indiv_df[st.session_state.excl_indiv_df['name'] == target]
        edited_ind = st.data_editor(target_ind_ex[['date', 'type', 'note']], num_rows="dynamic", key=f"ed_ind_{target}")
        if st.button("개인 일정 저장"):
            others = st.session_state.excl_indiv_df[st.session_state.excl_indiv_df['name'] != target]
            edited_ind['name'] = target
            st.session_state.excl_indiv_df = pd.concat([others, edited_ind], ignore_index=True)
            conn.update(worksheet="Exclusions_Indiv", data=st.session_state.excl_indiv_df); st.rerun()

    # 데이터 준비
    target_aft_data = st.session_state.after_df[st.session_state.after_df['name'] == target]
    cur_aft_df = target_aft_data.copy().reset_index(drop=True) if not target_aft_data.empty else get_initial_after_df(target)
    
    tips = {d: HOLIDAYS_DICT[d] for d in HOLIDAYS_DICT}
    for _, ex in st.session_state.excl_df.iterrows():
        try:
            s, e = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date']))
            while s <= e: tips[s] = ex['note']; s += timedelta(days=1)
        except: continue
    indiv_adds = set()
    for _, ex in target_ind_ex.iterrows():
        d = date.fromisoformat(str(ex['date']))
        if ex['type'] == '개인휴무': tips[d] = f"[개인휴무] {ex['note']}"
        else: indiv_adds.add(d); tips[d] = f"[추가출근] {ex['note']}"

    work_dates = [d for d in [date(2026,3,1) + timedelta(n) for n in range(306)] 
                  if (d.weekday() < 5 and d not in tips and d not in indiv_adds and hm.get(d.weekday(), 0) > 0) or (d in indiv_adds)]

    # 월별 출력 루프
    st.subheader(f"📊 {target} 강사 상세 일정 및 월별 PDF 양식")
    cols = st.columns(2)
    m_stats = []
    total_reg_h, total_aft_h, total_att = 0, 0, 0

    for m in range(3, 13):
        with cols[(m-3)%2]:
            m_label = f"{m}월"
            r_idx = cur_aft_df[cur_aft_df['month'] == m_label].index[0]
            
            # 레이아웃: 달력 | 입력창 | PDF버튼
            st.write(f"#### 🗓️ {m_label}")
            cal_c, aft_c = st.columns([0.75, 0.25])
            
            with aft_c:
                wa = [st.number_input(f"{m}월 {i+1}주", value=int(cur_aft_df.at[r_idx, f'w{i+1}']), step=1, key=f"w{i+1}_{target}_{m}") for i in range(5)]
                cur_aft_df.loc[r_idx, ['w1','w2','w3','w4','w5']] = wa
                
                # [양식 출력 버튼]
                m_work_dates = sorted([d for d in work_dates if d.month == m])
                try:
                    pdf_data = create_monthly_pdf(ins_row, m_label, m_work_dates, wa, hm)
                    st.download_button(f"📄 {m}월 양식 PDF", pdf_data, f"2026_{m}월_확인서_{target}.pdf", "application/pdf", key=f"pdf_{m}")
                except: st.caption("PDF 대기")

            with cal_c:
                cal = calendar.monthcalendar(2026, m)
                html = '<table style="width:100%; border-collapse:collapse; text-align:center; font-size:13px;">'
                html += '<tr style="background:#f0f2f6;"><th>월</th><th>화</th><th>수</th><th>목</th><th>금</th><th style="color:#007bff;">통합h</th></tr>'
                m_reg_days = set()
                for w_idx, week in enumerate(cal):
                    if w_idx >= 5: break
                    html += '<tr>'
                    wrh = 0
                    for i in range(5):
                        day = week[i]
                        if day == 0: html += '<td></td>'
                        else:
                            d = date(2026, m, day)
                            cls, title = "", ""
                            if d in work_dates: 
                                cls = "background:#90EE90; font-weight:bold;"
                                wrh += hm.get(d.weekday(), 0); m_reg_days.add(d)
                                if d in indiv_adds: cls = "background:#add8e6; font-weight:bold;"
                            elif d in tips: cls = "background:#FFB6C1; cursor:help;"; title = f'title="{tips[d]}"'
                            html += f'<td style="border:1px solid #ddd; padding:4px; {cls}" {title}>{day}</td>'
                    html += f'<td style="border:1px solid #ddd; background:#eef6ff; font-weight:bold;">{int(wrh + wa[w_idx])}</td></tr>'
                st.write(html + '</table>', unsafe_allow_html=True)

            m_att = len(m_reg_days); m_rh = sum([hm.get(d.weekday(), 0) for d in m_reg_days]); m_ah = sum(wa)
            m_rp = m_rh * int(ins_row['rate']); m_ap = m_ah * int(ins_row.get('rate_after', 50000))
            st.info(f"**💰 {m}월 합계: {(m_rp + m_ap):,}원**\n- 정규 {int(m_rh)}h / 방과후 {int(m_ah)}h / 출근 {m_att}일")
            m_stats.append({"월":f"{m}월", "출근":m_att, "정규h":m_rh, "방과후h":m_ah, "정규급여":f"{m_rp:,}원", "방과후급여":f"{m_ap:,}원", "급여":f"{(m_rp+m_ap):,}원"})
            total_reg_h += m_rh; total_aft_h += m_ah; total_att += m_att

    st.divider()
    if st.button(f"💾 {target} 강사 데이터 최종 저장 및 동기화"):
        others = st.session_state.after_df[st.session_state.after_df['name'] != target]
        st.session_state.after_df = pd.concat([others, cur_aft_df], ignore_index=True)
        conn.update(worksheet="AfterSchool", data=st.session_state.after_df); st.rerun()

    st.subheader("🏁 연간 합계 요약")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 출근", f"{total_att}일")
    c2.metric("정규 시수", f"{int(total_reg_h)}h")
    c3.metric("방과후 시수", f"{int(total_aft_h)}h")
    c4.metric("급여 합계", f"{int((total_reg_h*ins_row['rate'])+(total_aft_h*ins_row.get('rate_after',50000))):,}원")
