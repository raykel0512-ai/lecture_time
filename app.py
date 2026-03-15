import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar
from fpdf import FPDF
import os

# --- 0. 페이지 설정 ---
st.set_page_config(page_title="2026 강사 통합 관리 시스템", layout="wide")

# 업데이트 확인용 주석 (새로고침 확인용)
# VERSION: 9.0_STABLE_FINAL

# --- 1. 데이터 연결 및 로드 ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_initial_after_df(target_name):
    """방과후학교 초기 데이터 프레임 (6주차 w6 포함)"""
    months = [f"{m}월" for m in range(3, 13)]
    return pd.DataFrame({
        "name": [target_name]*10, "month": months,
        "w1": [0]*10, "w2": [0]*10, "w3": [0]*10, "w4": [0]*10, "w5": [0]*10, "w6": [0]*10
    })

# [데이터 로딩 로직]
if 'ins_df' not in st.session_state:
    try:
        df = conn.read(worksheet="Instructors", ttl=0)
        num_cols = ['rate', 'rate_after', 'mon', 'tue', 'wed', 'thu', 'fri']
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        st.session_state.ins_df = df
    except:
        st.session_state.ins_df = pd.DataFrame(columns=['name', 'rate', 'rate_after', 'mon', 'tue', 'wed', 'thu', 'fri', 'subject', 'target_classes'])

if 'excl_df' not in st.session_state:
    try:
        st.session_state.excl_df = conn.read(worksheet="Exclusions", ttl=0)
    except:
        st.session_state.excl_df = pd.DataFrame(columns=['start_date', 'end_date', 'note'])

if 'after_df' not in st.session_state:
    try: 
        df_aft = conn.read(worksheet="AfterSchool", ttl=0)
        for col in ['w1', 'w2', 'w3', 'w4', 'w5', 'w6']:
            if col not in df_aft.columns: df_aft[col] = 0
            df_aft[col] = pd.to_numeric(df_aft[col], errors='coerce').fillna(0).astype(int)
        st.session_state.after_df = df_aft
    except:
        st.session_state.after_df = pd.DataFrame(columns=['name', 'month', 'w1', 'w2', 'w3', 'w4', 'w5', 'w6'])

if 'excl_indiv_df' not in st.session_state:
    try:
        st.session_state.excl_indiv_df = conn.read(worksheet="Exclusions_Indiv", ttl=0)
    except:
        st.session_state.excl_indiv_df = pd.DataFrame(columns=['name', 'date', 'type', 'note'])

HOLIDAYS_DICT = {
    date(2026,3,1): "삼일절", date(2026,3,2): "대체공휴일", date(2026,5,5): "어린이날", 
    date(2026,5,24): "부처님오신날", date(2026,5,25): "대체공휴일", date(2026,6,6): "현충일", 
    date(2026,8,15): "광복절", date(2026,8,17): "대체공휴일", date(2026,9,24): "추석", 
    date(2026,9,25): "추석", date(2026,9,26): "추석", date(2026,9,28): "대체공휴일",
    date(2026,10,3): "개천절", date(2026,10,9): "한글날", date(2026,12,25): "성탄절"
}

# --- 2. PDF 생성 함수 ---
def create_monthly_pdf(target_row, month, worked_dates, h_map):
    pdf = FPDF()
    pdf.add_page()
    font_path = "font.ttf"
    if os.path.exists(font_path):
        pdf.add_font("Nanum", "", font_path)
        pdf.set_font("Nanum", size=11)
    else:
        pdf.set_font("Arial", size=11)
    
    pdf.set_font("Nanum", size=18)
    pdf.cell(190, 15, txt=f"2026학년도 {month} 시간강사 수업 현황", ln=True, align='C')
    pdf.set_font("Nanum", size=11)
    pdf.ln(5)

    col_w = [40, 150]
    pdf.cell(col_w[0], 10, "성 명", 1, 0, 'C'); pdf.cell(col_w[1], 10, f" {target_row['name']}", 1, 1, 'L')
    pdf.cell(col_w[0], 10, "담당과목", 1, 0, 'C'); pdf.cell(col_w[1], 10, f" {target_row.get('subject', '-')}", 1, 1, 'L')
    pdf.cell(col_w[0], 10, "담당학급", 1, 0, 'C'); pdf.cell(col_w[1], 10, f" {target_row.get('target_classes', '-')}", 1, 1, 'L')
    
    m_int = int(month.replace('월',''))
    ld = calendar.monthrange(2026, m_int)[1]
    pdf.cell(col_w[0], 10, "기 간", 1, 0, 'C'); pdf.cell(col_w[1], 10, f" 2026. {str(m_int).zfill(2)}. 01. ~ 2026. {str(m_int).zfill(2)}. {ld}.", 1, 1, 'L')
    
    dk = ["월", "화", "수", "목", "금"]
    dt = [f"{dk[i]}요일 {int(h_map[i])}시간" for i in range(5) if h_map[i] > 0]
    pdf.cell(col_w[0], 10, "실시요일-시수", 1, 0, 'C'); pdf.cell(col_w[1], 10, f" {', '.join(dt)}", 1, 1, 'L'); pdf.ln(2)
    
    cols = [15, 40, 25, 30, 40, 40]
    h_labels = ["연번", "날짜", "요일", "시수", "강사료", "비고"]
    for i, h in enumerate(h_labels):
        pdf.cell(cols[i], 10, h, 1, 0, 'C')
    pdf.ln()
    
    rc, th, tp = 0, 0, 0
    for d in sorted(worked_dates):
        rc += 1; h = h_map[d.weekday()]; p = h * target_row['rate']
        pdf.cell(cols[0], 8, str(rc), 1, 0, 'C')
        pdf.cell(cols[1], 8, d.strftime("%m월 %d일"), 1, 0, 'C')
        pdf.cell(cols[2], 8, dk[d.weekday()], 1, 0, 'C')
        pdf.cell(cols[3], 8, str(int(h)), 1, 0, 'C')
        pdf.cell(cols[4], 8, f"{int(p):,}", 1, 0, 'R')
        pdf.cell(cols[5], 8, "", 1, 1, 'C')
        th += h; tp += p
    while rc < 12:
        rc += 1
        for i in range(6): pdf.cell(cols[i], 8, "", 1, (1 if i==5 else 0), 'C')
    pdf.cell(80, 10, "합계", 1, 0, 'C'); pdf.cell(30, 10, f"{len(worked_dates)}일", 1, 0, 'C'); pdf.cell(40, 10, f"{int(th)}시간", 1, 0, 'C'); pdf.cell(40, 10, f"{int(tp):,}원", 1, 1, 'C')
    return bytes(pdf.output())

# --- 3. 사이드바 (강사 관리) ---
with st.sidebar:
    st.header("👤 강사 관리")
    mode = st.radio("작업", ["등록/수정", "공통제외"])
    if mode == "등록/수정":
        sub = st.selectbox("구분", ["신규 등록", "수정/삭제"])
        if sub == "신규 등록":
            with st.form("add"):
                n = st.text_input("이름"); subj = st.text_input("담당 과목", "과학"); cls_i = st.text_input("학급", "1학년"); r = st.number_input("정규", 25000); ra = st.number_input("방과후", 50000)
                m, t, w, th, f = st.number_input("월", 0), st.number_input("화", 0), st.number_input("수", 0), st.number_input("목", 0), st.number_input("금", 0)
                if st.form_submit_button("저장"):
                    new = pd.DataFrame([{"name":n,"rate":r,"rate_after":ra,"mon":m,"tue":t,"wed":w,"thu":th,"fri":f, "subject":subj, "target_classes":cls_i}])
                    st.session_state.ins_df = pd.concat([st.session_state.ins_df, new], ignore_index=True); conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
        else:
            if not st.session_state.ins_df.empty:
                tn = st.selectbox("강사", st.session_state.ins_df['name'].unique())
                td = st.session_state.ins_df[st.session_state.ins_df['name'] == tn].iloc[0]
                with st.form("edit"):
                    esubj = st.text_input("과목", td.get('subject','')); ecls = st.text_input("학급", td.get('target_classes','')); er = st.number_input("정규", int(td['rate'])); era = st.number_input("방과후", int(td.get('rate_after', 50000)))
                    em, et, ew, eth, ef = st.number_input("월", int(td['mon'])), st.number_input("화", int(td['tue'])), st.number_input("수", int(td['wed'])), st.number_input("목", int(td['thu'])), st.number_input("금", int(td['fri']))
                    if st.form_submit_button("수정"):
                        st.session_state.ins_df.loc[st.session_state.ins_df['name']==tn, ['rate','rate_after','mon','tue','wed','thu','fri','subject','target_classes']] = [er, era, em, et, ew, eth, ef, esubj, ecls]
                        conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
                    if st.form_submit_button("❌ 삭제"):
                        st.session_state.ins_df = st.session_state.ins_df[st.session_state.ins_df['name']!=tn]; conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
    else:
        ex_r = st.date_input("공통 제외 기간", (date(2026,7,20), date(2026,8,20)))
        if st.button("공통 제외 저장"):
            new_ex = pd.DataFrame([{"start_date": ex_r[0].isoformat(), "end_date": ex_r[1].isoformat(), "note": st.text_input("사유")}])
            st.session_state.excl_df = pd.concat([st.session_state.excl_df, new_ex], ignore_index=True); st.rerun()

# --- 4. 메인 대시보드 (공통 제외 및 예산 합산) ---
st.title("👨‍🏫 2026 강사 통합 관리 Pro")
all_excl_common = {d for d in HOLIDAYS_DICT}
for _, ex in st.session_state.excl_df.iterrows():
    try:
        s = date.fromisoformat(str(ex['start_date']))
        e = date.fromisoformat(str(ex['end_date']))
        while s <= e:
            all_excl_common.add(s)
            s += timedelta(days=1)
    except:
        continue

cd1, cd2 = st.columns([0.65, 0.35])
with cd1:
    with st.expander("🗓️ 공통 제외 일정 관리 (방학/공휴일)", expanded=True):
        edited_ex = st.data_editor(st.session_state.excl_df, num_rows="dynamic", use_container_width=True)
        if st.button("공통 일정 최종 저장"):
            st.session_state.excl_df = edited_ex
            conn.update(worksheet="Exclusions", data=edited_ex); st.rerun()
with cd2:
    gt = 0
    if not st.session_state.ins_df.empty:
        for _, ins in st.session_state.ins_df.iterrows():
            ind_ex = set()
            if not st.session_state.excl_indiv_df.empty:
                i_df = st.session_state.excl_indiv_df[(st.session_state.excl_indiv_df['name'] == ins['name']) & (st.session_state.excl_indiv_df['type'] == '개인휴무')]
                ind_ex = {date.fromisoformat(str(d)) for d in i_df['date'].tolist()}
            hm_i = {0:int(ins['mon']), 1:int(ins['tue']), 2:int(ins['wed']), 3:int(ins['thu']), 4:int(ins['fri'])}
            c = date(2026,3,1)
            while c <= date(2026,12,31):
                if c.weekday()<5 and c not in all_excl_common and c not in ind_ex:
                    gt += hm_i.get(c.weekday(),0)*int(ins['rate'])
                c += timedelta(days=1)
            ta = st.session_state.after_df[st.session_state.after_df['name']==ins['name']]
            gt += int(ta[['w1','w2','w3','w4','w5','w6']].sum().sum() * ins.get('rate_after',50000))
    st.metric("💰 2026년 전체 소요 예산", f"{gt:,}원")

st.divider()

# --- 5. 상세 리포트 및 달력 (UI 조정) ---
if not st.session_state.ins_df.empty:
    target = st.selectbox("조회 강사 선택", st.session_state.ins_df['name'].unique())
    ins_row = st.session_state.ins_df[st.session_state.ins_df['name'] == target].iloc[-1]
    hm = {0: int(ins_row['mon']), 1: int(ins_row['tue']), 2: int(ins_row['wed']), 3: int(ins_row['thu']), 4: int(ins_row['fri'])}
    
    # 개인 일정
    with st.expander(f"📍 {target} 선생님 개인 일정 관리"):
        ci1, ci2 = st.columns(2)
        with ci1:
            with st.form(f"ind_{target}"):
                id, it, in_ = st.date_input("날짜"), st.selectbox("구분",["개인휴무","추가출근"]), st.text_input("사유")
                if st.form_submit_button("추가"):
                    new_i = pd.DataFrame([{"name":target,"date":id.isoformat(),"type":it,"note":in_}])
                    st.session_state.excl_indiv_df = pd.concat([st.session_state.excl_indiv_df, new_i], ignore_index=True); conn.update(worksheet="Exclusions_Indiv", data=st.session_state.excl_indiv_df); st.rerun()
        with ci2:
            t_ind = st.session_state.excl_indiv_df[st.session_state.excl_indiv_df['name']==target]
            e_ind = st.data_editor(t_ind[['date','type','note']], num_rows="dynamic", key=f"e_{target}")
            if st.button("개인 일정 저장"):
                others = st.session_state.excl_indiv_df[st.session_state.excl_indiv_df['name'] != target]
                e_ind['name'] = target; st.session_state.excl_indiv_df = pd.concat([others, e_ind], ignore_index=True); conn.update(worksheet="Exclusions_Indiv", data=st.session_state.excl_indiv_df); st.rerun()

    # 데이터 준비
    cur_aft = st.session_state.after_df[st.session_state.after_df['name']==target].copy().reset_index(drop=True)
    if cur_aft.empty: cur_aft = get_initial_after_df(target)
    
    tips = {d: HOLIDAYS_DICT[d] for d in HOLIDAYS_DICT}
    for _, ex in st.session_state.excl_df.iterrows():
        try:
            ts, te = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date']))
            while ts <= te:
                tips[ts] = ex['note']
                ts += timedelta(days=1)
        except: continue
    adds = set()
    for _, ex in t_ind.iterrows():
        try:
            td_ind = date.fromisoformat(str(ex['date']))
            if ex['type'] == '개인휴무': tips[td_ind] = f"[개인] {ex['note']}"
            else: adds.add(td_ind); tips[td_ind] = f"[추가] {ex['note']}"
        except: continue
    
    work_dates = [d for d in [date(2026,3,1) + timedelta(n) for n in range(306)] if (d.weekday() < 5 and d not in tips and d not in adds and hm.get(d.weekday(), 0) > 0) or (d in adds)]

    st.subheader(f"📊 {target} 선생님 상세 리포트")
    cols = st.columns(2); total_reg, total_aft, total_att = 0, 0, 0

    for m in range(3, 13):
        with cols[(m-3)%2]:
            m_label = f"{m}월"
            st.write(f"#### 🗓️ {m_label}")
            cal = calendar.monthcalendar(2026, m)
            r_idx = cur_aft[cur_aft['month'] == m_label].index[0]
            
            # [UI 조정] 달력(0.8) | 입력창(0.2)
            cal_c, aft_c = st.columns([0.8, 0.2])
            
            with aft_c:
                st.caption("방과후 시수")
                wa = []
                # 달력 주차 수만큼 입력창 생성 (6주차 대응)
                for i in range(len(cal)):
                    col_nm = f'w{i+1}'
                    val = int(cur_aft.at[r_idx, col_nm]) if col_nm in cur_aft.columns else 0
                    w_input = st.number_input(f"{m}월{i+1}주", value=val, step=1, key=f"w{i+1}_{target}_{m}")
                    wa.append(w_input)
                    cur_aft.at[r_idx, col_nm] = w_input

                m_work = sorted([d for d in work_dates if d.month == m])
                if st.button(f"📄 PDF 생성", key=f"btn_{m}"):
                    pdf_data = create_monthly_pdf(ins_row, m_label, m_work, hm)
                    fname = f"2026학년도 {m_label} {ins_row.get('subject','')} 시간강사({target}선생님) 수업 현황.pdf"
                    st.download_button(f"⬇️ 다운로드", pdf_data, fname, "application/pdf", key=f"dl_{m}")

            with cal_c:
                html = '<table style="width:100%; border-collapse:collapse; text-align:center; font-size:12px;">'
                html += '<tr style="background:#f0f2f6;"><th>월</th><th>화</th><th>수</th><th>목</th><th>금</th><th style="color:#666;">정규h</th><th style="color:#007bff;">통합h</th></tr>'
                m_rc = 0
                for w_idx, week in enumerate(cal):
                    html += '<tr>'
                    wrh = 0
                    for i in range(5):
                        day = week[i]
                        if day == 0: html += '<td></td>'
                        else:
                            d = date(2026, m, day); cls, t = "", ""
                            if d in work_dates: 
                                cls = "background:#90EE90; font-weight:bold;"
                                wrh += hm.get(d.weekday(), 0); m_rc += 1
                                if d in adds: cls = "background:#add8e6; font-weight:bold;"
                            elif d in tips: cls = "background:#FFB6C1; cursor:help;"; t = f'title="{tips[d]}"'
                            html += f'<td style="border:1px solid #ddd; padding:4px; {cls}" {t}>{day}</td>'
                    # 통합h 합산
                    w_total_h = int(wrh + wa[w_idx])
                    html += f'<td style="border:1px solid #ddd; background:#f9f9f9; color:#666;">{int(wrh)}</td>'
                    html += f'<td style="border:1px solid #ddd; background:#eef6ff; font-weight:bold; color:#007bff;">{w_total_h}</td></tr>'
                st.write(html + '</table>', unsafe_allow_html=True)

            m_ah, m_rh = sum(wa), sum([hm.get(d.weekday(), 0) for d in m_work])
            m_rp = m_rh * int(ins_row['rate'])
            m_ap = m_ah * int(ins_row.get('rate_after', 50000))
            st.info(f"**💰 {m}월 합계: {(m_rp + m_ap):,}원**\n- 정규: {m_rp:,}원 ({m_rh}h) | 방과후: {m_ap:,}원 ({m_ah}h) | 출근 {m_rc}일")
            total_reg+=m_rh; total_aft+=m_ah; total_att+=m_rc

    st.divider()
    if st.button(f"💾 {target} 선생님 최종 데이터 저장"):
        others = st.session_state.after_df[st.session_state.after_df['name'] != target]
        st.session_state.after_df = pd.concat([others, cur_aft], ignore_index=True)
        conn.update(worksheet="AfterSchool", data=st.session_state.after_df); st.rerun()

    st.subheader("🏁 연간 최종 합계 요약")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 출근", f"{total_att}일"); c2.metric("정규 시수", f"{total_reg}h"); c3.metric("방과후 시수", f"{total_aft}h"); c4.metric("급여 합계", f"{int((total_reg*ins_row['rate'])+(total_aft*ins_row.get('rate_after',50000))):,}원")
