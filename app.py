import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar
from fpdf import FPDF
import os

# --- 0. 페이지 설정 ---
st.set_page_config(page_title="2026 강사 통합 관리 시스템", layout="wide")

st.sidebar.info("✅ v22.0 - PDF 함수 삼항표현식 None 출력 제거")

# [데이터 연결]
conn = st.connection("gsheets", type=GSheetsConnection)

# ✅ 수정 1: None을 안전하게 문자열로 변환하는 헬퍼 함수 추가
def safe_str(val, default="-"):
    """None, NaN, 빈값을 모두 default로 치환"""
    if val is None:
        return default
    if isinstance(val, float) and pd.isna(val):
        return default
    s = str(val).strip()
    return s if s and s.lower() != "nan" and s.lower() != "none" else default

# [기본 데이터 틀 생성 함수]
def get_initial_after_df(target_name):
    months = [f"{m}월" for m in range(3, 13)]
    return pd.DataFrame({
        "name": [target_name]*10, "month": months,
        "w1": [0]*10, "w2": [0]*10, "w3": [0]*10, "w4": [0]*10, "w5": [0]*10, "w6": [0]*10
    })

# [데이터 로드 함수]
def load_all_data():
    try:
        df_ins = conn.read(worksheet="Instructors", ttl=0)
        for c in ['rate', 'rate_after', 'mon', 'tue', 'wed', 'thu', 'fri']:
            if c in df_ins.columns:
                df_ins[c] = pd.to_numeric(df_ins[c], errors='coerce').fillna(0).astype(int)
        
        # ✅ 수정 2: 문자열 컬럼의 None/NaN을 빈 문자열로 치환
        for c in ['name', 'subject', 'target_classes']:
            if c in df_ins.columns:
                df_ins[c] = df_ins[c].fillna('').astype(str).str.strip()
        # 이름이 빈 행 제거 (GSheets 하단 빈 행 방지)
        df_ins = df_ins[df_ins['name'] != ''].reset_index(drop=True)

        df_excl = conn.read(worksheet="Exclusions", ttl=0)
        # ✅ 수정 3: 제외일정의 note None 처리
        if 'note' in df_excl.columns:
            df_excl['note'] = df_excl['note'].fillna('').astype(str).str.strip()
            df_excl['note'] = df_excl['note'].replace({'nan': '', 'None': ''})
        for c in ['start_date', 'end_date']:
            if c in df_excl.columns:
                df_excl[c] = df_excl[c].fillna('').astype(str).str.strip()
        df_excl = df_excl[df_excl['start_date'] != ''].reset_index(drop=True)

        df_aft = conn.read(worksheet="AfterSchool", ttl=0)
        for c in ['w1', 'w2', 'w3', 'w4', 'w5', 'w6']:
            if c not in df_aft.columns:
                df_aft[c] = 0
            df_aft[c] = pd.to_numeric(df_aft[c], errors='coerce').fillna(0).astype(int)
            
        df_indiv = conn.read(worksheet="Exclusions_Indiv", ttl=0)
        # ✅ 수정 4: 개인일정의 note/date None 처리
        if not df_indiv.empty:
            if 'note' in df_indiv.columns:
                df_indiv['note'] = df_indiv['note'].fillna('').astype(str).str.strip()
                df_indiv['note'] = df_indiv['note'].replace({'nan': '', 'None': ''})
            for c in ['name', 'type', 'date']:
                if c in df_indiv.columns:
                    df_indiv[c] = df_indiv[c].fillna('').astype(str).str.strip()
            df_indiv = df_indiv[df_indiv['date'] != ''].reset_index(drop=True)

        return df_ins, df_excl, df_aft, df_indiv
    except Exception as e:
        st.warning(f"데이터 로드 오류: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# 데이터 할당
if 'ins_df' not in st.session_state:
    i_raw, e_raw, a_raw, ind_raw = load_all_data()
    st.session_state.ins_df = i_raw
    st.session_state.excl_df = e_raw
    st.session_state.after_df = a_raw
    st.session_state.excl_indiv_df = ind_raw

HOLIDAYS_DICT = {
    date(2026,3,1): "삼일절", date(2026,3,2): "대체공휴일", date(2026,5,5): "어린이날", 
    date(2026,5,24): "부처님오신날", date(2026,5,25): "대체공휴일", date(2026,6,6): "현충일", 
    date(2026,8,15): "광복절", date(2026,8,17): "대체공휴일", date(2026,9,24): "추석", 
    date(2026,9,25): "추석", date(2026,9,26): "추석", date(2026,9,28): "대체공휴일",
    date(2026,10,3): "개천절", date(2026,10,9): "한글날", date(2026,12,25): "성탄절"
}

# --- 2. PDF 생성 함수 (1: 월별 확인서) ---
def create_monthly_pdf(target_row, month, worked_dates, h_map):
    pdf = FPDF()
    pdf.add_page()
    font_path = "font.ttf"
    if os.path.exists(font_path):
        pdf.add_font("Nanum", "", font_path)
        pdf.set_font("Nanum", size=11)
    else:
        pdf.set_font("Arial", size=11)
    
    pdf.set_font("Nanum", size=18) if os.path.exists(font_path) else pdf.set_font("Arial", size=18)
    pdf.cell(190, 15, txt=f"2026학년도 {month} 시간강사 수업 현황", ln=True, align='C')
    pdf.set_font("Nanum", size=11) if os.path.exists(font_path) else pdf.set_font("Arial", size=11)
    pdf.ln(5)
    
    col_w = [40, 150]
    pdf.cell(col_w[0], 10, "성 명", 1, 0, 'C')
    # ✅ 수정 5: PDF 출력 시에도 safe_str 적용
    pdf.cell(col_w[1], 10, f" {safe_str(target_row['name'])}", 1, 1, 'L')
    pdf.cell(col_w[0], 10, "담당과목", 1, 0, 'C')
    pdf.cell(col_w[1], 10, f" {safe_str(target_row.get('subject'))}", 1, 1, 'L')
    pdf.cell(col_w[0], 10, "담당학급", 1, 0, 'C')
    pdf.cell(col_w[1], 10, f" {safe_str(target_row.get('target_classes'))}", 1, 1, 'L')
    
    m_int = int(month.replace('월',''))
    ld = calendar.monthrange(2026, m_int)[1]
    pdf.cell(col_w[0], 10, "기 간", 1, 0, 'C')
    pdf.cell(col_w[1], 10, f" 2026. {str(m_int).zfill(2)}. 01. ~ 2026. {str(m_int).zfill(2)}. {ld}.", 1, 1, 'L')
    
    pdf.ln(2)
    pdf.set_fill_color(240, 240, 240)
    cols = [15, 40, 25, 30, 40, 40]
    headers = ["연번", "날짜", "요일", "수업시수", "강사료(원)", "비고"]
    for i, h in enumerate(headers):
        pdf.cell(cols[i], 10, h, 1, 0, 'C', fill=True)
    pdf.ln()
    
    rc, th, tp = 0, 0, 0
    dk = ["월", "화", "수", "목", "금"]
    for d in sorted(worked_dates):
        rc += 1
        h = h_map[d.weekday()]
        p = h * target_row['rate']
        pdf.cell(cols[0], 8, str(rc), 1, 0, 'C')
        pdf.cell(cols[1], 8, d.strftime("%m월 %d일"), 1, 0, 'C')
        pdf.cell(cols[2], 8, dk[d.weekday()], 1, 0, 'C')
        pdf.cell(cols[3], 8, str(int(h)), 1, 0, 'C')
        pdf.cell(cols[4], 8, f"{int(p):,}", 1, 0, 'R')
        pdf.cell(cols[5], 8, "", 1, 1, 'C')
        th += h
        tp += p
    while rc < 12:
        rc += 1
        for i in range(6):
            pdf.cell(cols[i], 8, "", 1, (1 if i==5 else 0), 'C')
    
    pdf.set_fill_color(255, 255, 153)
    pdf.cell(cols[0]+cols[1], 10, "합계", 1, 0, 'C', fill=True)
    pdf.cell(cols[2], 10, f"{len(worked_dates)}일", 1, 0, 'C', fill=True)
    pdf.cell(cols[3], 10, f"{int(th)}시간", 1, 0, 'C', fill=True)
    pdf.cell(cols[4], 10, f"{int(tp):,}원", 1, 0, 'C', fill=True)
    pdf.cell(cols[5], 10, "", 1, 1, 'C', fill=True)
    return bytes(pdf.output())

# --- 2-2. PDF 생성 함수 (2: 연간 통합 달력) ---
def create_yearly_calendar_pdf(target_name, work_dates, tips, ind_adds, hm, cur_aft_df):
    pdf = FPDF()
    pdf.add_page()
    font_path = "font.ttf"
    use_nanum = os.path.exists(font_path)
    if use_nanum:
        pdf.add_font("Nanum", "", font_path)
        pdf.set_font("Nanum", size=14)
    else:
        pdf.set_font("Arial", size=14)

    pdf.cell(190, 10, txt=f"2026학년도 연간 수업 달력 ({target_name} 선생님)", ln=True, align='C')
    pdf.ln(5)
    for m in range(3, 13):
        if (m-3) % 2 == 0 and m != 3:
            pdf.add_page()
        if use_nanum:
            pdf.set_font("Nanum", size=12)
        else:
            pdf.set_font("Arial", size=12)
        pdf.cell(190, 10, txt=f"■ {m}월 일정", ln=True)
        if use_nanum:
            pdf.set_font("Nanum", size=9)
        else:
            pdf.set_font("Arial", size=9)
        cal = calendar.monthcalendar(2026, m)
        headers = ["월", "화", "수", "목", "금", "정규h", "통합h"]
        col_w = [25, 25, 25, 25, 25, 30, 35]
        pdf.set_fill_color(230, 230, 230)
        for i, h in enumerate(headers): pdf.cell(col_w[i], 8, h, 1, 0, 'C', fill=True)
        pdf.ln()
        m_rows = cur_aft_df[cur_aft_df['month'] == f"{m}월"]
        for w_idx, week in enumerate(cal):
            reg_h = 0
            for i in range(5):
                day = week[i]
                fill = False
                if day != 0:
                    d = date(2026, m, day)
                    if d in work_dates:
                        reg_h += hm.get(d.weekday(), 0)
                        fill = True
                        if d in ind_adds: pdf.set_fill_color(173, 216, 230)
                        else: pdf.set_fill_color(144, 238, 144)
                    elif d in tips:
                        pdf.set_fill_color(255, 182, 193)
                        fill = True
                pdf.cell(col_w[i], 8, str(day) if day != 0 else "", 1, 0, 'C', fill=fill)
            
            aft_h = 0
            if not m_rows.empty:
                col_name = f'w{w_idx+1}'
                if col_name in m_rows.columns: aft_h = int(m_rows.iloc[0][col_name])
            pdf.set_fill_color(245, 245, 245)
            pdf.cell(col_w[5], 8, f"{reg_h}h", 1, 0, 'C', fill=True)
            pdf.set_fill_color(238, 246, 255)
            pdf.cell(col_w[6], 8, f"{reg_h + aft_h}h", 1, 1, 'C', fill=True)
        pdf.ln(5)
    return bytes(pdf.output())

# --- 3. 사이드바 (등록/수정) ---
with st.sidebar:
    st.header("👤 강사 관리")
    mode = st.radio("작업", ["등록/수정", "공통제외"])
    if mode == "등록/수정":
        sub = st.selectbox("구분", ["신규 등록", "수정/삭제"])
        if sub == "신규 등록":
            with st.form("add"):
                n = st.text_input("강사 이름")
                subj = st.text_input("담당 과목", "통합과학")
                cl = st.text_input("학급", "1학년 1반 ~ 8반")
                r = st.number_input("정규 단가", value=25000)
                ra = st.number_input("방과후 단가", value=50000)
                m, t, w, th, f = st.number_input("월", 0), st.number_input("화", 0), st.number_input("수", 0), st.number_input("목", 0), st.number_input("금", 0)
                if st.form_submit_button("저장"):
                    new = pd.DataFrame([{"name":n,"rate":r,"rate_after":ra,"mon":m,"tue":t,"wed":w,"thu":th,"fri":f, "subject":subj, "target_classes":cl}])
                    st.session_state.ins_df = pd.concat([st.session_state.ins_df, new], ignore_index=True)
                    conn.update(worksheet="Instructors", data=st.session_state.ins_df)
                    st.rerun()
        else:
            if not st.session_state.ins_df.empty:
                tn = st.selectbox("강사 선택", st.session_state.ins_df['name'].unique())
                td = st.session_state.ins_df[st.session_state.ins_df['name'] == tn].iloc[0]
                with st.form("edit"):
                    esj = st.text_input("과목", safe_str(td.get('subject', '')))
                    ecl = st.text_input("학급", safe_str(td.get('target_classes', '')))
                    er = st.number_input("정규", int(td['rate']))
                    era = st.number_input("방과후", int(td.get('rate_after', 50000)))
                    em, et, ew, eth, ef = st.number_input("월", int(td['mon'])), st.number_input("화", int(td['tue'])), st.number_input("수", int(td['wed'])), st.number_input("목", int(td['thu'])), st.number_input("금", int(td['fri']))
                    if st.form_submit_button("수정 완료"):
                        st.session_state.ins_df.loc[st.session_state.ins_df['name']==tn, ['rate','rate_after','mon','tue','wed','thu','fri','subject','target_classes']] = [er, era, em, et, ew, eth, ef, esj, ecl]
                        conn.update(worksheet="Instructors", data=st.session_state.ins_df)
                        st.rerun()
                    if st.form_submit_button("❌ 삭제"):
                        st.session_state.ins_df = st.session_state.ins_df[st.session_state.ins_df['name']!=tn]
                        conn.update(worksheet="Instructors", data=st.session_state.ins_df)
                        st.rerun()
    else:
        # ✅ 수정 6: 공통제외 사유 입력을 form 안으로 이동 (기존엔 버튼 콜백 밖에 있어서 항상 빈값 저장됨)
        with st.form("excl_form"):
            ex_r = st.date_input("공통 제외일", (date(2026,7,20), date(2026,8,20)))
            ex_note = st.text_input("사유", "")
            if st.form_submit_button("공통 제외 저장"):
                if len(ex_r) == 2:
                    new_ex = pd.DataFrame([{
                        "start_date": ex_r[0].isoformat(),
                        "end_date": ex_r[1].isoformat(),
                        "note": ex_note if ex_note else ""
                    }])
                    st.session_state.excl_df = pd.concat([st.session_state.excl_df, new_ex], ignore_index=True)
                    conn.update(worksheet="Exclusions", data=st.session_state.excl_df)
                    st.rerun()

# --- 4. 메인 대시보드 ---
st.title("👨‍🏫 2026 강사 통합 관리 시스템 Pro")
all_ex_common = {d for d in HOLIDAYS_DICT}
for _, ex in st.session_state.excl_df.iterrows():
    try:
        s_d = date.fromisoformat(str(ex['start_date']))
        e_d = date.fromisoformat(str(ex['end_date']))
        while s_d <= e_d:
            all_ex_common.add(s_d)
            s_d += timedelta(days=1)
    except: continue

c_d1, c_d2 = st.columns([0.65, 0.35])
with c_d1:
    with st.expander("🗓️ 공통 제외 일정 관리 (방학/공휴일)", expanded=True):
        ed_ex = st.data_editor(st.session_state.excl_df, num_rows="dynamic", use_container_width=True)
        if st.button("공통 일정 최종 저장"):
            st.session_state.excl_df = ed_ex
            conn.update(worksheet="Exclusions", data=ed_ex)
            st.rerun()
with c_d2:
    gt = 0
    if not st.session_state.ins_df.empty:
        for _, ins in st.session_state.ins_df.iterrows():
            ind_ex = set()
            if not st.session_state.excl_indiv_df.empty:
                i_df = st.session_state.excl_indiv_df[
                    (st.session_state.excl_indiv_df['name'] == ins['name']) &
                    (st.session_state.excl_indiv_df['type'] == '개인휴무')
                ]
                for d_str in i_df['date'].tolist():
                    try:
                        ind_ex.add(date.fromisoformat(str(d_str)))
                    except: continue
            hm_i = {0:int(ins['mon']), 1:int(ins['tue']), 2:int(ins['wed']), 3:int(ins['thu']), 4:int(ins['fri'])}
            curr_d = date(2026, 3, 1)
            while curr_d <= date(2026, 12, 31):
                if curr_d.weekday()<5 and curr_d not in all_ex_common and curr_d not in ind_ex:
                    gt += hm_i.get(curr_d.weekday(), 0) * int(ins['rate'])
                curr_d += timedelta(days=1)
            t_aft_sum = st.session_state.after_df[st.session_state.after_df['name']==ins['name']]
            gt += int(t_aft_sum[['w1','w2','w3','w4','w5','w6']].sum().sum() * ins.get('rate_after', 50000))
    st.metric("💰 2026년 전체 소요 예산", f"{gt:,}원")

st.divider()

# --- 5. 상세 리포트 및 달력 ---
if not st.session_state.ins_df.empty:
    target = st.selectbox("조회 강사 선택", st.session_state.ins_df['name'].unique())
    ins_row = st.session_state.ins_df[st.session_state.ins_df['name'] == target].iloc[-1]
    hm = {0: int(ins_row['mon']), 1: int(ins_row['tue']), 2: int(ins_row['wed']), 3: int(ins_row['thu']), 4: int(ins_row['fri'])}
    
    with st.expander(f"📍 {target} 선생님 개인 일정 관리"):
        ind_cols = st.columns(2)
        with ind_cols[0]:
            with st.form(f"ind_{target}"):
                id_d, it_t, in_n = st.date_input("날짜"), st.selectbox("구분", ["개인휴무","추가출근"]), st.text_input("사유")
                if st.form_submit_button("추가"):
                    new_ind = pd.DataFrame([{"name":target,"date":id_d.isoformat(),"type":it_t,"note":in_n if in_n else ""}])
                    st.session_state.excl_indiv_df = pd.concat([st.session_state.excl_indiv_df, new_ind], ignore_index=True)
                    conn.update(worksheet="Exclusions_Indiv", data=st.session_state.excl_indiv_df)
                    st.rerun()
        with ind_cols[1]:
            t_ind_df = st.session_state.excl_indiv_df[st.session_state.excl_indiv_df['name']==target].copy()
            if 'note' in t_ind_df.columns:
                t_ind_df['note'] = t_ind_df['note'].fillna('').astype(str).replace({'nan':'','None':''})
            e_ind_df = st.data_editor(t_ind_df[['date','type','note']], num_rows="dynamic", key=f"e_{target}")
            if st.button("개인 일정 저장"):
                others_ind = st.session_state.excl_indiv_df[st.session_state.excl_indiv_df['name'] != target]
                e_ind_df['name'] = target
                st.session_state.excl_indiv_df = pd.concat([others_ind, e_ind_df], ignore_index=True)
                conn.update(worksheet="Exclusions_Indiv", data=st.session_state.excl_indiv_df)
                st.rerun()

    cur_aft = st.session_state.after_df[st.session_state.after_df['name']==target].copy().reset_index(drop=True)
    if cur_aft.empty: cur_aft = get_initial_after_df(target)
    
    # ✅ 수정 8: tips 딕셔너리에 None이 절대 들어가지 않도록 safe_str 적용
    tips = {d: safe_str(label, "공휴일") for d, label in HOLIDAYS_DICT.items()}

    for _, ex in st.session_state.excl_df.iterrows():
        try:
            ts_d = date.fromisoformat(str(ex['start_date']))
            te_d = date.fromisoformat(str(ex['end_date']))
            note_val = safe_str(ex.get('note'), "제외일")
            while ts_d <= te_d:
                tips[ts_d] = note_val
                ts_d += timedelta(days=1)
        except: continue
    
    # ✅ t_ind_df 재참조 안전하게 처리
    t_ind_df = st.session_state.excl_indiv_df[st.session_state.excl_indiv_df['name']==target].copy()
    if 'note' in t_ind_df.columns:
        t_ind_df['note'] = t_ind_df['note'].fillna('').astype(str).replace({'nan':'','None':''})

    adds = set()
    for _, ex in t_ind_df.iterrows():
        try:
            td_d = date.fromisoformat(str(ex['date']))
            note_val = safe_str(ex.get('note'), '')
            if ex['type'] == '개인휴무':
                tips[td_d] = f"[개인] {note_val}".strip()
            else:
                adds.add(td_d)
                tips[td_d] = f"[추가] {note_val}".strip()
        except: continue
    
    work_dates = list(filter(
        lambda d: (d.weekday() < 5 and d not in tips and hm.get(d.weekday(), 0) > 0) or (d in adds),
        [date(2026,3,1) + timedelta(n) for n in range(306)]
    ))

    st.subheader(f"📊 {target} 선생님 상세 리포트")
    try:
        y_pdf = create_yearly_calendar_pdf(target, work_dates, tips, adds, hm, cur_aft)
        _ = st.download_button("📄 1년치 통합 달력 PDF 출력", y_pdf, f"2026_연간달력_{target}.pdf", "application/pdf")
    except Exception as e:
        st.caption(f"연간 달력 PDF 생성 실패: {type(e).__name__}")

    cols = st.columns(2)
    t_reg_h, t_aft_h, t_att_d = 0, 0, 0
    for m in range(3, 13):
        with cols[(m-3)%2]:
            m_l = f"{m}월"
            cal = calendar.monthcalendar(2026, m)
            st.markdown(f"#### 🗓️ {m_l}")
            r_idx = cur_aft[cur_aft['month'] == m_l].index[0]
            inner_cols = st.columns([0.8, 0.2])

            # 오른쪽 컬럼: 방과후 시수 입력
            inner_cols[1].caption("방과후 시수")
            wa = []
            for i in range(len(cal)):
                cn = f'w{i+1}'
                val = int(cur_aft.at[r_idx, cn]) if cn in cur_aft.columns else 0
                wi = inner_cols[1].number_input(f"{m}월{i+1}주", value=val, step=1, key=f"w{i+1}_{target}_{m}")
                wa.append(wi)
            cur_aft.loc[r_idx, [f'w{i+1}' for i in range(len(cal))]] = wa
            mw = sorted([d for d in work_dates if d.month == m])
            if inner_cols[1].button(f"📄 {m}월 양식 PDF", key=f"btn_{m}"):
                pdf_m = create_monthly_pdf(ins_row, m_l, mw, hm)
                f_name = f"2026학년도 {m_l} {safe_str(ins_row.get('subject', ''))} 시간강사({target}선생님) 수업 현황.pdf"
                inner_cols[1].download_button(f"⬇️ 다운로드", pdf_m, f_name, "application/pdf", key=f"dl_{m}")

            # 왼쪽 컬럼: 달력 HTML
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
                        d = date(2026, m, day)
                        cls, t = "", ""
                        if d in work_dates:
                            cls = "background:#90EE90; font-weight:bold;"
                            wh += hm.get(d.weekday(), 0)
                            m_rc += 1
                            if d in adds: cls = "background:#add8e6; font-weight:bold;"
                        elif d in tips:
                            cls = "background:#FFB6C1; cursor:help;"
                            tip_text = safe_str(tips.get(d), '')
                            t = f'title="{tip_text}"' if tip_text else ''
                        html += f'<td style="border:1px solid #ddd; padding:4px; {cls}" {t}>{day}</td>'
                html += f'<td style="border:1px solid #ddd; background:#f9f9f9; color:#666;">{int(wh)}</td>'
                html += f'<td style="border:1px solid #ddd; background:#eef6ff; font-weight:bold; color:#007bff;">{int(wh + wa[w_idx])}</td></tr>'
            inner_cols[0].markdown(html + '</table>', unsafe_allow_html=True)
            m_ah, m_rh = sum(wa), sum([hm.get(d.weekday(), 0) for d in mw])
            m_rp, m_ap = m_rh * int(ins_row['rate']), m_ah * int(ins_row.get('rate_after', 50000))
            st.info(f"💰 {m}월 합계: {(m_rp + m_ap):,}원 (출근 {m_rc}일) | 정규 {int(m_rh)}h | 방과후 {int(m_ah)}h")
            t_reg_h += m_rh
            t_aft_h += m_ah
            t_att_d += m_rc

    st.divider()
    if st.button(f"💾 {target} 강사 시수 데이터 최종 저장"):
        others_aft = st.session_state.after_df[st.session_state.after_df['name'] != target]
        st.session_state.after_df = pd.concat([others_aft, cur_aft], ignore_index=True)
        conn.update(worksheet="AfterSchool", data=st.session_state.after_df)
        st.rerun()

    st.subheader("🏁 연간 최종 합계 요약")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 출근", f"{t_att_d}일")
    c2.metric("정규 시수", f"{t_reg_h}h")
    c3.metric("방과후 시수", f"{t_aft_h}h")
    c4.metric("급여 합계", f"{int((t_reg_h*ins_row['rate'])+(t_aft_h*ins_row.get('rate_after',50000))):,}원")
