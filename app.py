import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar
from fpdf import FPDF
import os

# --- 0. 페이지 설정 ---
st.set_page_config(page_title="2026 강사 관리 Pro (v6.0)", layout="wide")

# --- 1. 구글 시트 연결 및 데이터 로드 ---
conn = st.connection("gsheets", type=GSheetsConnection)

# [데이터 초기화 함수]
def clear_all_cache():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.cache_data.clear()
    st.rerun()

with st.sidebar:
    if st.button("🔄 데이터 및 설정 강제 초기화"):
        clear_all_cache()

# [데이터 로딩 로직 - w6 완벽 대응]
@st.cache_data(ttl=0) # 캐시를 강제로 끄고 실시간으로 읽음
def load_all_data():
    try:
        # Instructors
        df_ins = conn.read(worksheet="Instructors", ttl=0)
        num_cols = ['rate', 'rate_after', 'mon', 'tue', 'wed', 'thu', 'fri']
        for col in num_cols:
            if col in df_ins.columns:
                df_ins[col] = pd.to_numeric(df_ins[col], errors='coerce').fillna(0).astype(int)
        
        # Exclusions
        df_ex = conn.read(worksheet="Exclusions", ttl=0)
        
        # AfterSchool (w6 포함 구조 강제화)
        df_aft = conn.read(worksheet="AfterSchool", ttl=0)
        for col in ['w1', 'w2', 'w3', 'w4', 'w5', 'w6']:
            if col not in df_aft.columns: df_aft[col] = 0
            df_aft[col] = pd.to_numeric(df_aft[col], errors='coerce').fillna(0).astype(int)
            
        # Indiv Exclusions
        df_ind = conn.read(worksheet="Exclusions_Indiv", ttl=0)
        
        return df_ins, df_ex, df_aft, df_ind
    except Exception as e:
        st.error(f"시트 로딩 에러: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# 실제 데이터 할당
ins_df_raw, excl_df_raw, after_df_raw, excl_indiv_df_raw = load_all_data()

# 세션 상태에 저장 (편집을 위해)
if 'ins_df' not in st.session_state: st.session_state.ins_df = ins_df_raw
if 'excl_df' not in st.session_state: st.session_state.excl_df = excl_df_raw
if 'after_df' not in st.session_state: st.session_state.after_df = after_df_raw
if 'excl_indiv_df' not in st.session_state: st.session_state.excl_indiv_df = excl_indiv_df_raw

HOLIDAYS_DICT = {
    date(2026,3,1): "삼일절", date(2026,3,2): "대체공휴일", date(2026,5,5): "어린이날", 
    date(2026,5,24): "부처님오신날", date(2026,5,25): "대체공휴일", date(2026,6,6): "현충일", 
    date(2026,8,15): "광복절", date(2026,8,17): "대체공휴일", date(2026,9,24): "추석", 
    date(2026,9,25): "추석", date(2026,9,26): "추석", date(2026,9,28): "대체공휴일",
    date(2026,10,3): "개천절", date(2026,10,9): "한글날", date(2026,12,25): "성탄절"
}

# --- 2. PDF 함수 생략 (위와 동일) ---
def create_monthly_pdf(target_row, month, worked_dates, h_map):
    pdf = FPDF(); pdf.add_page()
    font_path = "font.ttf"
    if os.path.exists(font_path): pdf.add_font("Nanum", "", font_path); pdf.set_font("Nanum", size=11)
    else: pdf.set_font("Arial", size=11)
    pdf.set_font("Nanum", size=18); pdf.cell(190, 15, txt=f"2026학년도 {month} 시간강사 수업 현황", ln=True, align='C')
    col_w = [40, 150]; pdf.set_font("Nanum", size=11)
    pdf.cell(col_w[0], 10, "성 명", 1, 0, 'C'); pdf.cell(col_w[1], 10, f" {target_row['name']}", 1, 1, 'L')
    pdf.cell(col_w[0], 10, "담당과목", 1, 0, 'C'); pdf.cell(col_w[1], 10, f" {target_row.get('subject', '-')}", 1, 1, 'L')
    pdf.cell(col_w[0], 10, "담당학급", 1, 0, 'C'); pdf.cell(col_w[1], 10, f" {target_row.get('target_classes', '-')}", 1, 1, 'L')
    row_count, total_h, total_pay = 0, 0, 0
    pdf.ln(5); cols = [15, 40, 25, 30, 40, 40]
    for h in ["연번", "날짜", "요일", "시수", "강사료", "비고"]: pdf.cell(cols[headers.index(h) if 'headers' in locals() else 0], 8, h, 1, 0, 'C')
    pdf.ln()
    for d in sorted(worked_dates):
        row_count += 1; h = h_map[d.weekday()]; pay = h * target_row['rate']
        pdf.cell(cols[0], 8, str(row_count), 1, 0, 'C'); pdf.cell(cols[1], 8, d.strftime("%m월 %d일"), 1, 0, 'C'); pdf.cell(cols[2], 8, " ", 1, 0, 'C'); pdf.cell(cols[3], 8, str(h), 1, 0, 'C'); pdf.cell(cols[4], 8, f"{pay:,}", 1, 0, 'R'); pdf.cell(cols[5], 8, "", 1, 1, 'C')
        total_h += h; total_pay += pay
    while row_count < 12:
        row_count += 1
        for i in range(6): pdf.cell(cols[i], 8, "", 1, (1 if i==5 else 0), 'C')
    pdf.cell(80, 10, "합계", 1, 0, 'C'); pdf.cell(30, 10, f"{len(worked_dates)}일", 1, 0, 'C'); pdf.cell(40, 10, f"{total_h}시간", 1, 0, 'C'); pdf.cell(40, 10, f"{total_pay:,}원", 1, 1, 'C')
    return bytes(pdf.output())

# --- 3. 사이드바 (등록/수정) ---
with st.sidebar:
    st.header("👤 강사 관리")
    mode = st.radio("작업", ["등록/수정", "제외일정 설정"])
    if mode == "등록/수정":
        sub = st.selectbox("구분", ["신규", "수정/삭제"])
        if sub == "신규":
            with st.form("add"):
                n = st.text_input("강사 이름"); subj = st.text_input("담당 과목", "통합과학"); cls_i = st.text_input("학급", "1학년"); r = st.number_input("정규", 25000); ra = st.number_input("방과후", 50000)
                m, t, w, th, f = st.number_input("월",0), st.number_input("화",0), st.number_input("수",0), st.number_input("목",0), st.number_input("금",0)
                if st.form_submit_button("저장"):
                    new = pd.DataFrame([{"name":n,"rate":r,"rate_after":ra,"mon":m,"tue":t,"wed":w,"thu":th,"fri":f, "subject":subj, "target_classes":cls_i}])
                    st.session_state.ins_df = pd.concat([st.session_state.ins_df, new], ignore_index=True)
                    conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
        else:
            if not st.session_state.ins_df.empty:
                tn = st.selectbox("강사 선택", st.session_state.ins_df['name'].unique())
                td = st.session_state.ins_df[st.session_state.ins_df['name'] == tn].iloc[0]
                with st.form("edit"):
                    esubj = st.text_input("과목", td.get('subject','')); ecls = st.text_input("학급", td.get('target_classes','')); er = st.number_input("정규", int(td['rate'])); era = st.number_input("방과후", int(td.get('rate_after', 50000)))
                    em, et, ew, eth, ef = st.number_input("월", int(td['mon'])), st.number_input("화", int(td['tue'])), st.number_input("수", int(td['wed'])), st.number_input("목", int(td['thu'])), st.number_input("금", int(td['fri']))
                    if st.form_submit_button("수정"):
                        st.session_state.ins_df.loc[st.session_state.ins_df['name']==tn, ['rate','rate_after','mon','tue','wed','thu','fri','subject','target_classes']] = [er, era, em, et, ew, eth, ef, esubj, ecls]
                        conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
                    if st.form_submit_button("❌ 강사 삭제"):
                        st.session_state.ins_df = st.session_state.ins_df[st.session_state.ins_df['name']!=tn]; conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()

# --- 4. 메인 화면: 최상단 공통 제외 관리 (강제 노출) ---
st.title("👨‍🏫 2026 강사 통합 관리 시스템 (v6.0)")

# [공통 제외 일정 및 예산 합계]
col_dash1, col_dash2 = st.columns([0.65, 0.35])
with col_dash1:
    st.subheader("🗓️ 공통 제외 일정 (방학/공휴일)")
    edited_ex = st.data_editor(st.session_state.excl_df, num_rows="dynamic", use_container_width=True, key="common_ex_editor")
    if st.button("공통 일정 저장"):
        st.session_state.excl_df = edited_ex
        conn.update(worksheet="Exclusions", data=edited_ex); st.rerun()

with col_dash2:
    st.subheader("💰 전체 예산 소요액")
    all_ex_dates = {d for d in HOLIDAYS_DICT}
    for _, ex in st.session_state.excl_df.iterrows():
        try:
            s, e = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date']))
            while s <= e: all_ex_dates.add(s); s += timedelta(days=1)
        except: continue
    
    grand_total = 0
    if not st.session_state.ins_df.empty:
        for _, ins in st.session_state.ins_df.iterrows():
            # 정규 합산
            hm_all = {0:int(ins['mon']), 1:int(ins['tue']), 2:int(ins['wed']), 3:int(ins['thu']), 4:int(ins['fri'])}
            curr = date(2026, 3, 1)
            while curr <= date(2026, 12, 31):
                if curr.weekday() < 5 and curr not in all_ex_dates: grand_total += hm_all.get(curr.weekday(), 0) * int(ins['rate'])
                curr += timedelta(days=1)
            # 방과후 합산
            aft_data = st.session_state.after_df[st.session_state.after_df['name'] == ins['name']]
            grand_total += int(aft_data[['w1','w2','w3','w4','w5','w6']].sum().sum() * ins.get('rate_after', 50000))
    st.metric("연간 합계", f"{grand_total:,}원")

st.divider()

# --- 5. 상세 리포트 및 3월 31일 해결 달력 ---
if not st.session_state.ins_df.empty:
    target = st.selectbox("강사 선택", st.session_state.ins_df['name'].unique())
    ins_row = st.session_state.ins_df[st.session_state.ins_df['name'] == target].iloc[-1]
    hm = {0: int(ins_row['mon']), 1: int(ins_row['tue']), 2: int(ins_row['wed']), 3: int(ins_row['thu']), 4: int(ins_row['fri'])}
    
    # 해당 강사 방과후 데이터 (w6 포함 여부 재확인)
    cur_aft = st.session_state.after_df[st.session_state.after_df['name'] == target].copy().reset_index(drop=True)
    if cur_aft.empty:
        months = [f"{m}월" for m in range(3, 13)]
        cur_aft = pd.DataFrame({"name":[target]*10, "month":months, "w1":[0]*10, "w2":[0]*10, "w3":[0]*10, "w4":[0]*10, "w5":[0]*10, "w6":[0]*10})

    # 개인 일정 반영
    t_ind = st.session_state.excl_indiv_df[st.session_state.excl_indiv_df['name'] == target]
    tips = {d: HOLIDAYS_DICT[d] for d in HOLIDAYS_DICT}
    for _, ex in st.session_state.excl_df.iterrows():
        try:
            s, e = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date']))
            while s <= e: tips[s] = ex['note']; s += timedelta(days=1)
        except: continue
    adds = set()
    for _, ex in t_ind.iterrows():
        try:
            d = date.fromisoformat(str(ex['date']))
            if ex['type'] == '개인휴무': tips[d] = f"[개인] {ex['note']}"
            else: adds.add(d); tips[d] = f"[추가] {ex['note']}"
        except: continue
    
    work_dates = [d for d in [date(2026,3,1) + timedelta(n) for n in range(306)] if (d.weekday() < 5 and d not in tips and d not in adds and hm.get(d.weekday(), 0) > 0) or (d in adds)]

    st.subheader(f"📊 {target} 선생님 상세 리포트")
    cols = st.columns(2); total_reg, total_aft, total_att = 0, 0, 0

    for m in range(3, 13):
        with cols[(m-3)%2]:
            m_label = f"{m}월"
            cal = calendar.monthcalendar(2026, m) # 3월은 6주 생성됨
            num_w = len(cal)
            
            r_idx = cur_aft[cur_aft['month'] == m_label].index[0]
            st.write(f"#### 🗓️ {m_label}")
            
            cal_c, aft_c = st.columns([0.7, 0.3])
            with aft_c:
                st.caption("방과후 시수")
                wa = []
                for i in range(num_w):
                    col_key = f'w{i+1}'
                    val = int(cur_aft.at[r_idx, col_key]) if col_key in cur_aft.columns else 0
                    w_in = st.number_input(f"{m}월 {i+1}주", value=val, step=1, key=f"w{i+1}_{target}_{m}")
                    wa.append(w_in); cur_aft.at[r_idx, col_key] = w_in
                
                m_work = sorted([d for d in work_dates if d.month == m])
                if st.button(f"📄 PDF 생성", key=f"pdf_btn_{m}"):
                    pdf_data = create_monthly_pdf(ins_row, m_label, m_work, hm)
                    st.download_button(f"⬇️ 다운로드", pdf_data, f"2026_{m}월_{target}.pdf", "application/pdf", key=f"dl_{m}")

            with cal_c:
                html = '<table style="width:100%; border-collapse:collapse; text-align:center; font-size:12px;">'
                html += '<tr style="background:#f0f2f6;"><th>월</th><th>화</th><th>수</th><th>목</th><th>금</th><th style="color:#007bff;">통합</th></tr>'
                m_reg_cnt = 0
                for w_idx in range(num_w):
                    week = cal[w_idx]
                    html += '<tr>'
                    wrh = 0
                    for i in range(5):
                        day = week[i]
                        if day == 0: html += '<td></td>'
                        else:
                            d = date(2026, m, day); cls, t = "", ""
                            if d in work_dates: 
                                cls = "background:#90EE90; font-weight:bold;"
                                wrh += hm.get(d.weekday(), 0); m_reg_cnt += 1
                                if d in adds: cls = "background:#add8e6; font-weight:bold;"
                            elif d in tips: cls = "background:#FFB6C1; cursor:help;"; t = f'title="{tips[d]}"'
                            html += f'<td style="border:1px solid #ddd; padding:4px; {cls}" {t}>{day}</td>'
                    html += f'<td style="border:1px solid #ddd; background:#eef6ff; font-weight:bold;">{int(wrh + wa[w_idx])}</td></tr>'
                st.write(html + '</table>', unsafe_allow_html=True)

            m_ah, m_rh = sum(wa), sum([hm.get(d.weekday(), 0) for d in m_work])
            m_p = (m_rh*int(ins_row['rate'])) + (m_ah*int(ins_row.get('rate_after', 50000)))
            st.info(f"💰 {m}월: {m_p:,}원 (출근 {m_reg_cnt}일)"); total_reg+=m_rh; total_aft+=m_ah; total_att+=m_reg_cnt

    st.divider()
    if st.button(f"💾 {target} 선생님 최종 데이터 저장"):
        others = st.session_state.after_df[st.session_state.after_df['name'] != target]
        st.session_state.after_df = pd.concat([others, cur_aft], ignore_index=True)
        conn.update(worksheet="AfterSchool", data=st.session_state.after_df); st.success("저장 완료!"); st.rerun()

    st.subheader("🏁 연간 합계")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 출근", f"{total_att}일"); c2.metric("정규 시수", f"{total_reg}h"); c3.metric("방과후 시수", f"{total_aft}h"); c4.metric("최종 급여", f"{int((total_reg*ins_row['rate'])+(total_aft*ins_row.get('rate_after',50000))):,}원")
