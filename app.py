import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar
from fpdf import FPDF
import os

# --- 0. 페이지 설정 ---
st.set_page_config(page_title="2026 강사 통합 관리 시스템", layout="wide")

st.sidebar.info("✅ v24.0 - 학기별 시수 분리 지원")

# ✅ [신규] 2학기 시작 기준일 (이 날짜부터 2학기 시수 적용)
#    7~8월은 방학 제외기간이라 그 사이 어느 날짜로 잡아도 결과는 동일합니다.
SEMESTER2_START = date(2026, 8, 1)

SEM1_COLS = ['mon', 'tue', 'wed', 'thu', 'fri']
SEM2_COLS = ['mon2', 'tue2', 'wed2', 'thu2', 'fri2']
DAY_LABELS = ['월', '화', '수', '목', '금']

# [데이터 연결]
conn = st.connection("gsheets", type=GSheetsConnection)


def safe_str(val, default="-"):
    """None, NaN, 빈값을 모두 default로 치환"""
    if val is None:
        return default
    if isinstance(val, float) and pd.isna(val):
        return default
    s = str(val).strip()
    return s if s and s.lower() != "nan" and s.lower() != "none" else default


def _num(val, default=0):
    """숫자로 변환, 실패 시 default"""
    v = pd.to_numeric(val, errors='coerce')
    if v is None or pd.isna(v):
        return default
    return int(v)


def _num_or_none(val):
    """숫자로 변환, 비어 있으면 None (미입력과 0을 구분하기 위함)"""
    v = pd.to_numeric(val, errors='coerce')
    if v is None or pd.isna(v):
        return None
    return int(v)


# ✅ [신규] 2학기 시수가 따로 입력되어 있는지 판단
def has_sem2(ins_row):
    return any(_num_or_none(ins_row.get(c)) is not None for c in SEM2_COLS)


# ✅ [신규] 날짜(또는 학기)에 맞는 요일별 시수 맵을 반환
#    2학기 값이 비어 있으면 1학기 값을 그대로 사용 (기존 강사 데이터 무수정 호환)
def get_hours_map(ins_row, work_date=None, semester=1):
    if work_date is not None:
        semester = 2 if work_date >= SEMESTER2_START else 1
    if semester == 2 and has_sem2(ins_row):
        return {i: _num(ins_row.get(SEM2_COLS[i]), 0) for i in range(5)}
    return {i: _num(ins_row.get(SEM1_COLS[i]), 0) for i in range(5)}


def hours_map_label(ins_row, semester):
    hm = get_hours_map(ins_row, semester=semester)
    return " ".join(f"{DAY_LABELS[i]}{hm.get(i, 0)}" for i in range(5))


# 추가출근일은 원래 요일 시수 대신 사용자가 입력한 시수로 계산
def get_default_additional_hours(work_date, weekday_hours):
    weekday_default = int(weekday_hours.get(work_date.weekday(), 0))
    if weekday_default > 0:
        return weekday_default

    positive_hours = [int(h) for h in weekday_hours.values() if int(h) > 0]
    if not positive_hours:
        return 0

    return max(set(positive_hours), key=lambda h: (positive_hours.count(h), h))


# ✅ [변경] 요일 시수 맵 대신 강사 행(ins_row)을 받아 날짜별 학기를 자동 판별
def get_regular_hours(work_date, ins_row, added_hours=None):
    hm = get_hours_map(ins_row, work_date)
    if added_hours and work_date in added_hours:
        extra_hours = int(added_hours.get(work_date, 0))
        if extra_hours > 0:
            return extra_hours
        return get_default_additional_hours(work_date, hm)
    return int(hm.get(work_date.weekday(), 0))


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
        for c in ['rate', 'rate_after'] + SEM1_COLS:
            if c in df_ins.columns:
                df_ins[c] = pd.to_numeric(df_ins[c], errors='coerce').fillna(0).astype(int)

        # ✅ [신규] 2학기 시수 컬럼 — 빈칸은 빈 문자열로 유지해서 "미입력"과 "0"을 구분
        for c in SEM2_COLS:
            if c not in df_ins.columns:
                df_ins[c] = ''
            parsed = pd.to_numeric(df_ins[c], errors='coerce')
            df_ins[c] = parsed.apply(lambda v: '' if pd.isna(v) else str(int(v)))

        for c in ['name', 'subject', 'target_classes']:
            if c in df_ins.columns:
                df_ins[c] = df_ins[c].fillna('').astype(str).str.strip()
        # 이름이 빈 행 제거 (GSheets 하단 빈 행 방지)
        df_ins = df_ins[df_ins['name'] != ''].reset_index(drop=True)

        df_excl = conn.read(worksheet="Exclusions", ttl=0)
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
        for c in ['name', 'date', 'type', 'hours', 'note']:
            if c not in df_indiv.columns:
                df_indiv[c] = 0 if c == 'hours' else ''
        if not df_indiv.empty:
            df_indiv['note'] = df_indiv['note'].fillna('').astype(str).str.strip()
            df_indiv['note'] = df_indiv['note'].replace({'nan': '', 'None': ''})
            for c in ['name', 'type', 'date']:
                df_indiv[c] = df_indiv[c].fillna('').astype(str).str.strip()
            df_indiv['hours'] = pd.to_numeric(df_indiv['hours'], errors='coerce').fillna(0).astype(int)
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
def create_monthly_pdf(target_row, month, worked_dates, added_hours=None):
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
    dk = ["월", "화", "수", "목", "금", "토", "일"]
    for d in sorted(worked_dates):
        rc += 1
        h = get_regular_hours(d, target_row, added_hours)
        p = h * int(target_row['rate'])
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
def create_yearly_calendar_pdf(ins_row, work_dates, tips, ind_adds, cur_aft_df, added_hours=None):
    target_name = safe_str(ins_row['name'], "")
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
        if (m-3) % 3 == 0 and m != 3:
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
                        reg_h += get_regular_hours(d, ins_row, added_hours)
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
    st.caption(f"2학기 시작 기준일: {SEMESTER2_START.isoformat()}")
    mode = st.radio("작업", ["등록/수정", "공통제외"])
    if mode == "등록/수정":
        sub = st.selectbox("구분", ["신규 등록", "수정/삭제"])
        if sub == "신규 등록":
            with st.form("add"):
                n = st.text_input("강사 이름")
                subj = st.text_input("담당 과목", "통합과학")
                cl = st.text_input("학급", "1학년 1반 ~ 8반")
                r = st.number_input("정규 단가", value=25000, step=1000)
                ra = st.number_input("방과후 단가", value=50000, step=1000)

                st.markdown("**1학기 요일별 시수**")
                m = st.number_input("월", value=0, step=1, key="add_mon")
                t = st.number_input("화", value=0, step=1, key="add_tue")
                w = st.number_input("수", value=0, step=1, key="add_wed")
                th = st.number_input("목", value=0, step=1, key="add_thu")
                f = st.number_input("금", value=0, step=1, key="add_fri")

                # ✅ [신규] 2학기 시수
                use_s2 = st.checkbox("2학기 시수 따로 지정", value=False, key="add_use_s2")
                st.caption("체크하지 않으면 2학기에도 1학기 시수를 그대로 적용합니다. "
                           "1학기 전용 강사는 체크 후 아래를 모두 0으로 두세요.")
                m2 = st.number_input("월(2학기)", value=0, step=1, key="add_mon2")
                t2 = st.number_input("화(2학기)", value=0, step=1, key="add_tue2")
                w2 = st.number_input("수(2학기)", value=0, step=1, key="add_wed2")
                th2 = st.number_input("목(2학기)", value=0, step=1, key="add_thu2")
                f2 = st.number_input("금(2학기)", value=0, step=1, key="add_fri2")

                if st.form_submit_button("저장"):
                    s2_vals = [str(int(v)) for v in [m2, t2, w2, th2, f2]] if use_s2 else ['']*5
                    new = pd.DataFrame([{
                        "name": n, "rate": r, "rate_after": ra,
                        "mon": m, "tue": t, "wed": w, "thu": th, "fri": f,
                        "mon2": s2_vals[0], "tue2": s2_vals[1], "wed2": s2_vals[2],
                        "thu2": s2_vals[3], "fri2": s2_vals[4],
                        "subject": subj, "target_classes": cl
                    }])
                    st.session_state.ins_df = pd.concat([st.session_state.ins_df, new], ignore_index=True)
                    conn.update(worksheet="Instructors", data=st.session_state.ins_df)
                    st.rerun()
        else:
            if not st.session_state.ins_df.empty:
                tn = st.selectbox("강사 선택", st.session_state.ins_df['name'].unique())
                td = st.session_state.ins_df[st.session_state.ins_df['name'] == tn].iloc[0]
                td_s2 = get_hours_map(td, semester=2)
                with st.form("edit"):
                    esj = st.text_input("과목", safe_str(td.get('subject', ''), ''))
                    ecl = st.text_input("학급", safe_str(td.get('target_classes', ''), ''))
                    er = st.number_input("정규", value=_num(td.get('rate'), 25000), step=1000)
                    era = st.number_input("방과후", value=_num(td.get('rate_after'), 50000), step=1000)

                    st.markdown("**1학기 요일별 시수**")
                    em = st.number_input("월", value=_num(td.get('mon')), step=1, key="ed_mon")
                    et = st.number_input("화", value=_num(td.get('tue')), step=1, key="ed_tue")
                    ew = st.number_input("수", value=_num(td.get('wed')), step=1, key="ed_wed")
                    eth = st.number_input("목", value=_num(td.get('thu')), step=1, key="ed_thu")
                    ef = st.number_input("금", value=_num(td.get('fri')), step=1, key="ed_fri")

                    # ✅ [신규] 2학기 시수
                    e_use_s2 = st.checkbox("2학기 시수 따로 지정", value=has_sem2(td), key="ed_use_s2")
                    st.caption("체크 해제 시 2학기에도 1학기 시수를 적용합니다.")
                    em2 = st.number_input("월(2학기)", value=td_s2[0], step=1, key="ed_mon2")
                    et2 = st.number_input("화(2학기)", value=td_s2[1], step=1, key="ed_tue2")
                    ew2 = st.number_input("수(2학기)", value=td_s2[2], step=1, key="ed_wed2")
                    eth2 = st.number_input("목(2학기)", value=td_s2[3], step=1, key="ed_thu2")
                    ef2 = st.number_input("금(2학기)", value=td_s2[4], step=1, key="ed_fri2")

                    if st.form_submit_button("수정 완료"):
                        s2_vals = ([str(int(v)) for v in [em2, et2, ew2, eth2, ef2]]
                                   if e_use_s2 else ['']*5)
                        st.session_state.ins_df.loc[
                            st.session_state.ins_df['name'] == tn,
                            ['rate','rate_after','mon','tue','wed','thu','fri',
                             'mon2','tue2','wed2','thu2','fri2','subject','target_classes']
                        ] = [er, era, em, et, ew, eth, ef,
                             s2_vals[0], s2_vals[1], s2_vals[2], s2_vals[3], s2_vals[4], esj, ecl]
                        conn.update(worksheet="Instructors", data=st.session_state.ins_df)
                        st.rerun()
                    if st.form_submit_button("❌ 삭제"):
                        st.session_state.ins_df = st.session_state.ins_df[st.session_state.ins_df['name']!=tn]
                        conn.update(worksheet="Instructors", data=st.session_state.ins_df)
                        st.rerun()
    else:
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
            ind_add_hours = {}
            if not st.session_state.excl_indiv_df.empty:
                i_df = st.session_state.excl_indiv_df[st.session_state.excl_indiv_df['name'] == ins['name']]
                for _, ind in i_df.iterrows():
                    try:
                        ind_date = date.fromisoformat(str(ind['date']))
                    except:
                        continue
                    if ind['type'] == '개인휴무':
                        ind_ex.add(ind_date)
                    elif ind['type'] == '추가출근':
                        ind_add_hours[ind_date] = int(ind.get('hours', 0))
            curr_d = date(2026, 3, 1)
            while curr_d <= date(2026, 12, 31):
                if curr_d in ind_add_hours:
                    gt += get_regular_hours(curr_d, ins, ind_add_hours) * int(ins['rate'])
                elif curr_d.weekday() < 5 and curr_d not in all_ex_common and curr_d not in ind_ex:
                    # ✅ [변경] 날짜별 학기에 맞는 시수 사용
                    gt += get_hours_map(ins, curr_d).get(curr_d.weekday(), 0) * int(ins['rate'])
                curr_d += timedelta(days=1)
            t_aft_sum = st.session_state.after_df[st.session_state.after_df['name']==ins['name']]
            gt += int(t_aft_sum[['w1','w2','w3','w4','w5','w6']].sum().sum() * _num(ins.get('rate_after'), 50000))
    st.metric("💰 2026년 전체 소요 예산", f"{gt:,}원")

st.divider()

# --- 5. 상세 리포트 및 달력 ---
if not st.session_state.ins_df.empty:
    target = st.selectbox("조회 강사 선택", st.session_state.ins_df['name'].unique())
    ins_row = st.session_state.ins_df[st.session_state.ins_df['name'] == target].iloc[-1]

    # ✅ [신규] 현재 적용 중인 학기별 시수 안내
    if has_sem2(ins_row):
        st.caption(f"🔹 1학기 시수: {hours_map_label(ins_row, 1)}  |  "
                   f"2학기 시수: {hours_map_label(ins_row, 2)}  "
                   f"(2학기 시작 {SEMESTER2_START.isoformat()})")
    else:
        st.caption(f"🔹 연간 동일 시수: {hours_map_label(ins_row, 1)}")

    with st.expander(f"📍 {target} 선생님 개인 일정 관리"):
        ind_cols = st.columns(2)
        with ind_cols[0]:
            with st.form(f"ind_{target}"):
                id_d = st.date_input("날짜")
                it_t = st.selectbox("구분", ["개인휴무","추가출근"])
                ih = st.number_input(
                    "추가출근 시수", min_value=0,
                    value=get_default_additional_hours(id_d, get_hours_map(ins_row, id_d)), step=1,
                    help="원래 수업 요일이 아닌 날은 해당 학기 요일별 시수 중 가장 많이 쓰는 시수를 기본값으로 넣습니다. 필요하면 직접 수정하세요."
                )
                in_n = st.text_input("사유")
                if st.form_submit_button("추가"):
                    new_ind = pd.DataFrame([{"name":target,"date":id_d.isoformat(),"type":it_t,"hours":int(ih) if it_t == "추가출근" else 0,"note":in_n if in_n else ""}])
                    st.session_state.excl_indiv_df = pd.concat([st.session_state.excl_indiv_df, new_ind], ignore_index=True)
                    conn.update(worksheet="Exclusions_Indiv", data=st.session_state.excl_indiv_df)
                    st.rerun()
        with ind_cols[1]:
            t_ind_df = st.session_state.excl_indiv_df[st.session_state.excl_indiv_df['name']==target].copy()
            if 'note' in t_ind_df.columns:
                t_ind_df['note'] = t_ind_df['note'].fillna('').astype(str).replace({'nan':'','None':''})
            if 'hours' not in t_ind_df.columns:
                t_ind_df['hours'] = 0
            e_ind_df = st.data_editor(t_ind_df[['date','type','hours','note']], num_rows="dynamic", key=f"e_{target}")
            if st.button("개인 일정 저장"):
                others_ind = st.session_state.excl_indiv_df[st.session_state.excl_indiv_df['name'] != target]
                e_ind_df['hours'] = pd.to_numeric(e_ind_df['hours'], errors='coerce').fillna(0).astype(int)
                e_ind_df['name'] = target
                st.session_state.excl_indiv_df = pd.concat([others_ind, e_ind_df], ignore_index=True)
                conn.update(worksheet="Exclusions_Indiv", data=st.session_state.excl_indiv_df)
                st.rerun()

    cur_aft = st.session_state.after_df[st.session_state.after_df['name']==target].copy().reset_index(drop=True)
    if cur_aft.empty: cur_aft = get_initial_after_df(target)

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

    t_ind_df = st.session_state.excl_indiv_df[st.session_state.excl_indiv_df['name']==target].copy()
    if 'note' in t_ind_df.columns:
        t_ind_df['note'] = t_ind_df['note'].fillna('').astype(str).replace({'nan':'','None':''})
    if 'hours' not in t_ind_df.columns:
        t_ind_df['hours'] = 0
    t_ind_df['hours'] = pd.to_numeric(t_ind_df['hours'], errors='coerce').fillna(0).astype(int)

    adds = set()
    add_hours = {}
    for _, ex in t_ind_df.iterrows():
        try:
            td_d = date.fromisoformat(str(ex['date']))
            note_val = safe_str(ex.get('note'), '')
            if ex['type'] == '개인휴무':
                tips[td_d] = f"[개인] {note_val}".strip()
            else:
                adds.add(td_d)
                add_hours[td_d] = int(ex.get('hours', 0))
                tips[td_d] = f"[추가] {note_val}".strip()
        except: continue

    # ✅ [변경] 시수 0인 요일 판정을 날짜별 학기 기준으로
    work_dates = list(filter(
        lambda d: (d.weekday() < 5 and d not in tips
                   and get_hours_map(ins_row, d).get(d.weekday(), 0) > 0) or (d in adds),
        [date(2026,3,1) + timedelta(n) for n in range(306)]
    ))

    st.subheader(f"📊 {target} 선생님 상세 리포트")
    try:
        y_pdf = create_yearly_calendar_pdf(ins_row, work_dates, tips, adds, cur_aft, add_hours)
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
                pdf_m = create_monthly_pdf(ins_row, m_l, mw, add_hours)
                f_name = f"2026학년도 {m_l} {safe_str(ins_row.get('subject', ''), '')} 시간강사({target}선생님) 수업 현황.pdf"
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
                            wh += get_regular_hours(d, ins_row, add_hours)
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
            m_ah = sum(wa)
            m_rh = sum([get_regular_hours(d, ins_row, add_hours) for d in mw])
            m_rp = m_rh * int(ins_row['rate'])
            m_ap = m_ah * _num(ins_row.get('rate_after'), 50000)
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
    c4.metric("급여 합계", f"{int((t_reg_h*int(ins_row['rate']))+(t_aft_h*_num(ins_row.get('rate_after'), 50000))):,}원")
