import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar
from fpdf import FPDF
import os

# --- 0. 페이지 설정 ---
st.set_page_config(page_title="2026 강사 통합 관리 시스템", layout="wide")

# 업데이트 확인용 버전
st.sidebar.info("✅ v10.2 - PDF 폰트 에러 수정 완료")

# [강제 초기화 버튼]
if st.sidebar.button("🔄 앱 완전 초기화"):
    st.cache_data.clear()
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

# --- 1. 데이터 연결 및 로드 ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_initial_after_df(target_name):
    months = [f"{m}월" for m in range(3, 13)]
    return pd.DataFrame({
        "name": [target_name]*10, "month": months,
        "w1": [0]*10, "w2": [0]*10, "w3": [0]*10, "w4": [0]*10, "w5": [0]*10, "w6": [0]*10
    })

def load_data():
    try:
        df_i = conn.read(worksheet="Instructors", ttl=0)
        num_cols = ['rate', 'rate_after', 'mon', 'tue', 'wed', 'thu', 'fri']
        for c in num_cols:
            if c in df_i.columns: df_i[c] = pd.to_numeric(df_i[c], errors='coerce').fillna(0).astype(int)
        df_e = conn.read(worksheet="Exclusions", ttl=0)
        df_a = conn.read(worksheet="AfterSchool", ttl=0)
        for c in ['w1', 'w2', 'w3', 'w4', 'w5', 'w6']:
            if c not in df_a.columns: df_a[col] = 0
            df_a[c] = pd.to_numeric(df_a[c], errors='coerce').fillna(0).astype(int)
        df_ind = conn.read(worksheet="Exclusions_Indiv", ttl=0)
        return df_i, df_e, df_a, df_ind
    except:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

i_raw, e_raw, a_raw, ind_raw = load_data()
if 'ins_df' not in st.session_state: st.session_state.ins_df = i_raw
if 'excl_df' not in st.session_state: st.session_state.excl_df = e_raw
if 'after_df' not in st.session_state: st.session_state.after_df = a_raw
if 'excl_indiv_df' not in st.session_state: st.session_state.excl_indiv_df = ind_raw

HOLIDAYS_DICT = {
    date(2026,3,1): "삼일절", date(2026,3,2): "대체공휴일", date(2026,5,5): "어린이날", 
    date(2026,5,24): "부처님오신날", date(2026,5,25): "대체공휴일", date(2026,6,6): "현충일", 
    date(2026,8,15): "광복절", date(2026,8,17): "대체공휴일", date(2026,9,24): "추석", 
    date(2026,9,25): "추석", date(2026,9,26): "추석", date(2026,9,28): "대체공휴일",
    date(2026,10,3): "개천절", date(2026,10,9): "한글날", date(2026,12,25): "성탄절"
}

# --- 2. PDF 생성 함수 (월별) ---
def create_monthly_pdf(target_row, month, worked_dates, h_map):
    pdf = FPDF(); pdf.add_page()
    font_path = "font.ttf"
    if os.path.exists(font_path): pdf.add_font("Nanum", "", font_path); pdf.set_font("Nanum", size=11)
    else: pdf.set_font("Arial", size=11)
    
    pdf.set_font("Nanum", size=18); pdf.cell(190, 15, txt=f"2026학년도 {month} 시간강사 수업 현황", ln=True, align='C')
    pdf.ln(5); col_w = [40, 150]; pdf.set_font("Nanum", size=11)
    pdf.cell(col_w[0], 10, "성 명", 1, 0, 'C'); pdf.cell(col_w[1], 10, f" {target_row['name']}", 1, 1, 'L')
    pdf.cell(col_w[0], 10, "담당과목", 1, 0, 'C'); pdf.cell(col_w[1], 10, f" {target_row.get('subject', '-')}", 1, 1, 'L')
    pdf.cell(col_w[0], 10, "담당학급", 1, 0, 'C'); pdf.cell(col_w[1], 10, f" {target_row.get('target_classes', '-')}", 1, 1, 'L')
    
    m_i = int(month.replace('월','')); ld = calendar.monthrange(2026, m_i)[1]
    pdf.cell(col_w[0], 10, "기 간", 1, 0, 'C'); pdf.cell(col_w[1], 10, f" 2026. {str(m_i).zfill(2)}. 01. ~ 2026. {str(m_i).zfill(2)}. {ld}.", 1, 1, 'L')
    
    dk = ["월", "화", "수", "목", "금"]
    pdf.ln(2); pdf.set_fill_color(240, 240, 240); cols = [15, 40, 25, 30, 40, 40]
    headers = ["연번", "날짜", "요일", "수업시수", "강사료(원)", "비고"]
    for i, h in enumerate(headers): pdf.cell(cols[i], 10, h, 1, 0, 'C', fill=True)
    pdf.ln(); rc, th, tp = 0, 0, 0
    for d in sorted(worked_dates):
        rc += 1; h = h_map[d.weekday()]; p = h * target_row['rate']
        pdf.cell(cols[0], 8, str(rc), 1, 0, 'C'); pdf.cell(cols[1], 8, d.strftime("%m월 %d일"), 1, 0, 'C'); pdf.cell(cols[2], 8, dk[d.weekday()], 1, 0, 'C'); pdf.cell(cols[3], 8, str(int(h)), 1, 0, 'C'); pdf.cell(cols[4], 8, f"{int(p):,}", 1, 0, 'R'); pdf.cell(cols[5], 8, "", 1, 1, 'C')
        th += h; tp += p
    while rc < 12:
        rc += 1
        for i in range(6): pdf.cell(cols[i], 8, "", 1, (1 if i==5 else 0), 'C')
    pdf.set_fill_color(255, 255, 153)
    pdf.cell(cols[0]+cols[1], 10, "합계", 1, 0, 'C', fill=True); pdf.cell(cols[2], 10, f"{len(worked_dates)}일", 1, 0, 'C', fill=True); pdf.cell(cols[3], 10, f"{int(th)}시간", 1, 0, 'C', fill=True); pdf.cell(cols[4], 10, f"{int(tp):,}원", 1, 0, 'C', fill=True); pdf.cell(cols[5], 10, "", 1, 1, 'C', fill=True)
    return bytes(pdf.output())

# --- 3. [오류 수정] 1년치 통합 달력 PDF 함수 (Bold 스타일 제거) ---
def create_yearly_calendar_pdf(target_name, work_dates, tips, ind_adds, hm, cur_aft_df):
    pdf = FPDF(); pdf.add_page()
    font_path = "font.ttf"
    if os.path.exists(font_path): pdf.add_font("Nanum", "", font_path); pdf.set_font("Nanum", size=14)
    else: pdf.set_font("Arial", size=14)
    
    pdf.cell(190, 10, txt=f"2026학년도 연간 수업 달력 ({target_name} 선생님)", ln=True, align='C')
    pdf.ln(5)
    
    for m in range(3, 13):
        if (m - 3) % 2 == 0 and m != 3: pdf.add_page()
        pdf.set_font("Nanum", size=12) # style='B' 제거
        pdf.cell(190, 10, txt=f"■ {m}월 일정", ln=True)
        pdf.set_font("Nanum", size=9)
        
        cal = calendar.monthcalendar(2026, m)
        headers = ["월", "화", "수", "목", "금", "정규h", "통합h"]
        col_widths = [25, 25, 25, 25, 25, 30, 35]
        
        pdf.set_fill_color(230, 230, 230)
        for i, h in enumerate(headers): pdf.cell(col_widths[i], 8, h, 1, 0, 'C', fill=True)
        pdf.ln()
        
        m_rows = cur_aft_df[cur_aft_df['month'] == f"{m}월"]
        
        for w_idx, week in enumerate(cal):
            reg_h_sum = 0
            for i in range(5):
                day = week[i]
                fill_color = None
                if day != 0:
                    d = date(2026, m, day)
                    if d in work_dates:
                        reg_h_sum += hm.get(d.weekday(), 0)
                        fill_color = (173, 216, 230) if d in ind_adds else (144, 238, 144)
                    elif d in tips:
                        fill_color = (255, 182, 193)
                
                txt = str(day) if day != 0 else ""
                if fill_color: pdf.set_fill_color(*fill_color)
                pdf.cell(col_widths[i], 8, txt, 1, 0, 'C', fill=True if fill_color else False)
            
            aft_h = 0
            if not m_rows.empty:
                col_name = f'w{w_idx+1}'
                if col_name in m_rows.columns: aft_h = int(m_rows.iloc[0][col_name])
            
            pdf.set_fill_color(245, 245, 245); pdf.cell(col_widths[5], 8, f"{reg_h_sum}h", 1, 0, 'C', fill=True)
            pdf.set_fill_color(238, 246, 255); pdf.cell(col_widths[6], 8, f"{reg_h_sum + aft_h}h", 1, 1, 'C', fill=True)
        pdf.ln(5)
    return bytes(pdf.output())

# --- 4. 사이드바 및 메인 로직 (기존과 동일) ---
with st.sidebar:
    st.header("👤 강사 관리")
    mode = st.radio("작업", ["등록/수정", "공통제외"])
    if mode == "등록/수정":
        sub = st.selectbox("구분", ["신규 등록", "수정/삭제"])
        if sub == "신규 등록":
            with st.form("add"):
                n = st.text_input("강사 이름"); subj = st.text_input("과목", "통합과학"); cl = st.text_input("학급", "1학년"); r = st.number_input("정규", 25000); ra = st.number_input("방과후", 50000)
                m, t, w, th, f = st.number_input("월", 0), st.number_input("화", 0), st.number_input("수", 0), st.number_input("목", 0), st.number_input("금", 0)
                if st.form_submit_button("저장"):
                    new = pd.DataFrame([{"name":n,"rate":r,"rate_after":ra,"mon":m,"tue":t,"wed":w,"thu":th,"fri":f, "subject":subj, "target_classes":cl}])
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
        ex_r = st.date_input("제외일", (date(2026,7,20), date(2026,8,20)))
        if st.button("공통 제외 저장"):
            new_ex = pd.DataFrame([{"start_date": ex_r[0].isoformat(), "end_date": ex_r[1].isoformat(), "note": st.text_input("사유")}])
            st.session_state.excl_df = pd.concat([st.session_state.excl_df, new_ex], ignore_index=True); st.rerun()

st.title("👨‍🏫 2026 강사 통합 관리 Pro")
all_ex_c = {d for d in HOLIDAYS_DICT}
for _, ex in st.session_state.excl_df.iterrows():
    try: s, e = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date'])); 
    while s <= e: all_ex_c.add(s); s += timedelta(days=1)
    except: continue

cd1, cd2 = st.columns([0.65, 0.35])
with cd1:
    with st.expander("🗓️ 공통 제외 일정 관리 (방학/공휴일)", expanded=True):
        ed_ex = st.data_editor(st.session_state.excl_df, num_rows="dynamic", use_container_width=True)
        if st.button("공통 일정 최종 저장"): st.session_state.excl_df = ed_ex; conn.update(worksheet="Exclusions", data=ed_ex); st.rerun()
with cd2:
    gt = 0
    if not st.session_state.ins_df.empty:
        for _, ins in st.session_state.ins_df.iterrows():
            ind_ex = {date.fromisoformat(str(d)) for d in st.session_state.excl_indiv_df[(st.session_state.excl_indiv_df['name'] == ins['name']) & (st.session_state.excl_indiv_df['type'] == '개인휴무')]['date'].tolist()} if not st.session_state.excl_indiv_df.empty else set()
            hm_i = {0:int(ins['mon']), 1:int(ins['tue']), 2:int(ins['wed']), 3:int(ins['thu']), 4:int(ins['fri'])}
            c_d = date(2026,3,1)
            while c_d <= date(2026,12,31):
                if c_d.weekday()<5 and c_d not in all_ex_c and c_d not in ind_ex: gt += hm_i.get(c_d.weekday(),0)*int(ins['rate'])
                c_d += timedelta(days=1)
            ta = st.session_state.after_df[st.session_state.after_df['name']==ins['name']]
            gt += int(ta[['w1','w2','w3','w4','w5','w6']].sum().sum() * ins.get('rate_after',50000))
    st.metric("💰 2026년 전체 소요 예산", f"{gt:,}원")

st.divider()

if not st.session_state.ins_df.empty:
    target = st.selectbox("조회 강사 선택", st.session_state.ins_df['name'].unique())
    ins_row = st.session_state.ins_df[st.session_state.ins_df['name'] == target].iloc[-1]
    hm = {0: int(ins_row['mon']), 1: int(ins_row['tue']), 2: int(ins_row['wed']), 3: int(ins_row['thu']), 4: int(ins_row['fri'])}
    
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

    cur_aft = st.session_state.after_df[st.session_state.after_df['name']==target].copy().reset_index(drop=True)
    if cur_aft.empty: cur_aft = get_initial_after_df(target)
    
    tips = {d:HOLIDAYS_DICT[d] for d in HOLIDAYS_DICT}
    for _,ex in st.session_state.excl_df.iterrows():
        try: ts, te = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date'])); 
        while ts <= te: tips[ts]=ex['note']; ts+=timedelta(days=1)
        except: continue
    adds = set()
    for _,ex in t_ind.iterrows():
        try: td_ind = date.fromisoformat(str(ex['date'])); 
        if ex['type']=='개인휴무': tips[td_ind]=f"[개인] {ex['note']}"
        else: adds.add(td_ind); tips[td_ind]=f"[추가] {ex['note']}"
        except: continue
    work_dates = [d for d in [date(2026,3,1) + timedelta(n) for n in range(306)] if (d.weekday() < 5 and d not in tips and d not in adds and hm.get(d.weekday(), 0) > 0) or (d in adds)]

    st.subheader(f"📊 {target} 선생님 상세 리포트")
    try:
        y_cal_pdf = create_yearly_calendar_pdf(target, work_dates, tips, adds, hm, cur_aft)
        st.download_button("📄 1년치 통합 달력 PDF 출력", y_cal_pdf, f"2026_연간달력_{target}.pdf", "application/pdf")
    except Exception as e: st.error(f"연간 PDF 생성 오류: {e}")

    cols = st.columns(2); total_reg, total_aft, total_att = 0, 0, 0
    for m in range(3, 13):
        with cols[(m-3)%2]:
            m_l = f"{m}월"; cal = calendar.monthcalendar(2026, m); st.write(f"#### 🗓️ {m_l}")
            r_idx = cur_aft[cur_aft['month'] == m_l].index[0]
            cc, ac = st.columns([0.8, 0.2])
            with ac:
                wa = []
                for i in range(len(cal)):
                    cn = f'w{i+1}'; val = int(cur_aft.at[r_idx, cn]) if cn in cur_aft.columns else 0
                    wi = st.number_input(f"{m}월{i+1}주", value=val, step=1, key=f"w{i+1}_{target}_{m}"); wa.append(wi)
                    cur_aft.at[r_idx, cn] = wi
                mw = sorted([d for d in work_dates if d.month == m])
                if st.button(f"📄 {m}월 양식 PDF", key=f"btn_{m}"):
                    pdf_m = create_monthly_pdf(ins_row, m_l, mw, hm)
                    f_name = f"2026학년도 {m_l} {ins_row.get('subject', '')} 시간강사({target}선생님) 수업 현황.pdf"
                    st.download_button(f"⬇️ 다운로드", pdf_m, f_name, "application/pdf", key=f"dl_{m}")
            with cc:
                html = '<table style="width:100%; border-collapse:collapse; text-align:center; font-size:12px;">'
                html += '<tr style="background:#f0f2f6;"><th>월</th><th>화</th><th>수</th><th>목</th><th>금</th><th style="color:#666;">정규h</th><th style="color:#007bff;">통합h</th></tr>'
                m_rc = 0
                for w_idx, week in enumerate(cal):
                    html += '<tr>'
                    wh = 0
                    for i in range(5):
                        day = week[i]
                        if day == 0: html += '<td></td>'
                        else:
                            d = date(2026, m, day); cls, t = "", ""
                            if d in work_dates: cls = "background:#90EE90; font-weight:bold;"; wh += hm.get(d.weekday(), 0); m_rc += 1
                            elif d in tips: cls = "background:#FFB6C1; cursor:help;"; t = f'title="{tips[d]}"'
                            html += f'<td style="border:1px solid #ddd; padding:4px; {cls}" {t}>{day}</td>'
                    html += f'<td style="border:1px solid #ddd; background:#f9f9f9; color:#666;">{int(wh)}</td>'
                    html += f'<td style="border:1px solid #ddd; background:#eef6ff; font-weight:bold; color:#007bff;">{int(wh + wa[w_idx])}</td></tr>'
                st.write(html + '</table>', unsafe_allow_html=True)
            m_ah, m_rh = sum(wa), sum([hm.get(d.weekday(), 0) for d in mw])
            m_p = (m_rh*int(ins_row['rate'])) + (m_ah*int(ins_row.get('rate_after', 50000)))
            st.info(f"💰 {m}월 합계: {(m_p):,}원 (출근 {m_rc}일)"); total_reg+=m_rh; total_aft+=m_ah; total_att+=m_rc

    st.divider()
    if st.button(f"💾 {target} 강사 시수 데이터 최종 저장"):
        others = st.session_state.after_df[st.session_state.after_df['name'] != target]
        st.session_state.after_df = pd.concat([others, cur_aft], ignore_index=True)
        conn.update(worksheet="AfterSchool", data=st.session_state.after_df); st.rerun()

    st.subheader("🏁 연간 최종 합계 요약")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 출근", f"{total_att}일"); c2.metric("정규 시수", f"{total_reg}h"); c3.metric("방과후 시수", f"{total_aft}h"); c4.metric("급여 합계", f"{int((total_reg*ins_row['rate'])+(total_aft*ins_row.get('rate_after',50000))):,}원")
