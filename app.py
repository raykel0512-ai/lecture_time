import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar
from fpdf import FPDF
import os

# --- 0. 페이지 설정 ---
st.set_page_config(page_title="2026 강사 통합 관리 Pro", layout="wide")

# 업데이트 확인용 버전 표시 (이게 화면에 떠야 새 코드가 적용된 것입니다)
st.sidebar.info("버전: v7.0 - 3월 31일 수정완료")

# [강제 초기화 버튼] - 업데이트가 안 될 때 눌러주세요
if st.sidebar.button("🔄 앱 완전 초기화 (업데이트 반영 안 될 때)"):
    st.cache_data.clear()
    for key in st.session_state.keys():
        del st.session_state[key]
    st.rerun()

# --- 1. 데이터 로드 (캐시 비활성화로 실시간성 확보) ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # Instructors
        df_i = conn.read(worksheet="Instructors", ttl=0)
        # Exclusions
        df_e = conn.read(worksheet="Exclusions", ttl=0)
        # AfterSchool (w1~w6 강제 보정)
        df_a = conn.read(worksheet="AfterSchool", ttl=0)
        for col in ['w1', 'w2', 'w3', 'w4', 'w5', 'w6']:
            if col not in df_a.columns: df_a[col] = 0
            df_a[col] = pd.to_numeric(df_a[col], errors='coerce').fillna(0).astype(int)
        # Individual Exclusions
        df_ind = conn.read(worksheet="Exclusions_Indiv", ttl=0)
        return df_i, df_e, df_a, df_ind
    except:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# 데이터 할당
i_raw, e_raw, a_raw, ind_raw = load_data()

# 세션 관리 (한 번 로드 후 세션에서 관리)
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

# --- 2. 사이드바 (등록/수정) ---
with st.sidebar:
    st.header("👤 강사/일정 관리")
    mode = st.radio("작업", ["강사 등록/수정", "공통제외 관리"])
    if mode == "강사 등록/수정":
        sub = st.selectbox("구분", ["신규", "수정/삭제"])
        if sub == "신규":
            with st.form("add"):
                n = st.text_input("이름"); sub_j = st.text_input("과목", "과학"); cl_i = st.text_input("학급", "1학년"); r = st.number_input("정규", 25000); ra = st.number_input("방과후", 50000)
                m, t, w, th, f = st.number_input("월",0), st.number_input("화",0), st.number_input("수",0), st.number_input("목",0), st.number_input("금",0)
                if st.form_submit_button("저장"):
                    new = pd.DataFrame([{"name":n,"rate":r,"rate_after":ra,"mon":m,"tue":t,"wed":w,"thu":th,"fri":f, "subject":sub_j, "target_classes":cl_i}])
                    st.session_state.ins_df = pd.concat([st.session_state.ins_df, new], ignore_index=True); conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
        else:
            if not st.session_state.ins_df.empty:
                tn = st.selectbox("선택", st.session_state.ins_df['name'].unique())
                td = st.session_state.ins_df[st.session_state.ins_df['name'] == tn].iloc[0]
                with st.form("edit"):
                    es = st.text_input("과목", td.get('subject','')); ec = st.text_input("학급", td.get('target_classes','')); er = st.number_input("정규", int(td['rate'])); era = st.number_input("방과후", int(td.get('rate_after', 50000)))
                    em, et, ew, eth, ef = st.number_input("월", int(td['mon'])), st.number_input("화", int(td['tue'])), st.number_input("수", int(td['wed'])), st.number_input("목", int(td['thu'])), st.number_input("금", int(td['fri']))
                    if st.form_submit_button("수정"):
                        st.session_state.ins_df.loc[st.session_state.ins_df['name']==tn, ['rate','rate_after','mon','tue','wed','thu','fri','subject','target_classes']] = [er, era, em, et, ew, eth, ef, es, ec]
                        conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
                    if st.form_submit_button("삭제"):
                        st.session_state.ins_df = st.session_state.ins_df[st.session_state.ins_df['name']!=tn]; conn.update(worksheet="Instructors", data=st.session_state.ins_df); st.rerun()
    else:
        ex_r = st.date_input("제외일", (date(2026,7,20), date(2026,8,20)))
        if st.button("제외 저장"):
            new_ex = pd.DataFrame([{"start_date": ex_r[0].isoformat(), "end_date": ex_r[1].isoformat(), "note": st.text_input("사유")}])
            st.session_state.excl_df = pd.concat([st.session_state.excl_df, new_ex], ignore_index=True); st.rerun()

# --- 4. 메인 화면: 대시보드 ---
st.title("👨‍🏫 2026 강사 통합 관리 Pro")

# 공통 제외 일정 (강제 노출)
with st.expander("🗓️ 공통 제외 일정(방학/공휴일) 관리", expanded=True):
    col_e, col_b = st.columns([0.7, 0.3])
    with col_e:
        edited_ex = st.data_editor(st.session_state.excl_df, num_rows="dynamic", use_container_width=True, key="main_ex_editor")
        if st.button("공통 일정 최종 저장"):
            st.session_state.excl_df = edited_ex
            conn.update(worksheet="Exclusions", data=edited_ex); st.rerun()
    with col_b:
        # 모든 제외 날짜 Set
        common_all = {d for d in HOLIDAYS_DICT}
        for _, ex in st.session_state.excl_df.iterrows():
            try:
                s, e = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date']))
                while s <= e: common_all.add(s); s += timedelta(days=1)
            except: continue
        
        # 총 예산 계산
        g_total = 0
        for _, ins in st.session_state.ins_df.iterrows():
            hm_all = {0:int(ins['mon']), 1:int(ins['tue']), 2:int(ins['wed']), 3:int(ins['thu']), 4:int(ins['fri'])}
            curr = date(2026,3,1)
            while curr <= date(2026,12,31):
                if curr.weekday()<5 and curr not in common_all: g_total += hm_all.get(curr.weekday(),0)*int(ins['rate'])
                curr += timedelta(days=1)
            t_aft = st.session_state.after_df[st.session_state.after_df['name']==ins['name']]
            g_total += int(t_aft[['w1','w2','w3','w4','w5','w6']].sum().sum() * ins.get('rate_after',50000))
        st.metric("💰 2026년 전체 소요액", f"{g_total:,}원")

st.divider()

# --- 5. 개별 상세 리포트 (3월 31일 해결 핵심부) ---
if not st.session_state.ins_df.empty:
    target = st.selectbox("조회 강사 선택", st.session_state.ins_df['name'].unique())
    row = st.session_state.ins_df[st.session_state.ins_df['name'] == target].iloc[-1]
    hm = {0:int(row['mon']), 1:int(row['tue']), 2:int(row['wed']), 3:int(row['thu']), 4:int(row['fri'])}
    
    # 개인 일정
    t_ind = st.session_state.excl_indiv_df[st.session_state.excl_indiv_df['name']==target]
    tips = {d:HOLIDAYS_DICT[d] for d in HOLIDAYS_DICT}
    for _, ex in st.session_state.excl_df.iterrows():
        try:
            s, e = date.fromisoformat(str(ex['start_date'])), date.fromisoformat(str(ex['end_date']))
            while s<=e: tips[s]=ex['note']; s+=timedelta(days=1)
        except: continue
    adds = set()
    for _, ex in t_ind.iterrows():
        d = date.fromisoformat(str(ex['date']))
        if ex['type']=='개인휴무': tips[d]=f"[개인] {ex['note']}"
        else: adds.add(d); tips[d]=f"[추가] {ex['note']}"
    
    work_dates = [d for d in [date(2026,3,1)+timedelta(n) for n in range(306)] if (d.weekday()<5 and d not in tips and d not in adds and hm.get(d.weekday(),0)>0) or (d in adds)]

    # 방과후 데이터 보정
    cur_aft = st.session_state.after_df[st.session_state.after_df['name']==target].copy().reset_index(drop=True)
    if cur_aft.empty:
        cur_aft = pd.DataFrame({"name":[target]*10, "month":[f"{m}월" for m in range(3,13)], "w1":[0]*10, "w2":[0]*10, "w3":[0]*10, "w4":[0]*10, "w5":[0]*10, "w6":[0]*10})

    st.subheader(f"📊 {target} 선생님 리포트")
    cols = st.columns(2); total_reg, total_aft, total_att = 0, 0, 0

    for m in range(3, 13):
        with cols[(m-3)%2]:
            m_label = f"{m}월"
            cal = calendar.monthcalendar(2026, m) # 3월은 여기서 반드시 6줄 생성
            
            r_idx = cur_aft[cur_aft['month'] == m_label].index[0]
            st.write(f"#### 🗓️ {m_label}")
            
            c_cal, c_aft = st.columns([0.7, 0.3])
            
            with c_aft:
                st.caption("방과후 시수")
                wa = []
                for i in range(len(cal)): # 달력 줄 수(6줄)만큼 입력창 생성
                    col_nm = f'w{i+1}'
                    val = int(cur_aft.at[r_idx, col_nm]) if col_nm in cur_aft.columns else 0
                    w_in = st.number_input(f"{m}월 {i+1}주", value=val, step=1, key=f"w{i+1}_{target}_{m}")
                    wa.append(w_in)
                    cur_aft.at[r_idx, col_nm] = w_in

            with c_cal:
                # [핵심] HTML 테이블 생성 (6주차 31일까지 출력)
                html = '<table style="width:100%; border-collapse:collapse; text-align:center; font-size:12px;">'
                html += '<tr style="background:#f0f2f6;"><th>월</th><th>화</th><th>수</th><th>목</th><th>금</th><th style="color:#007bff;">통합h</th></tr>'
                m_rc = 0
                for w_idx, week in enumerate(cal):
                    html += '<tr>'
                    wh = 0
                    for i in range(5):
                        day = week[i]
                        if day == 0: html += '<td></td>'
                        else:
                            d = date(2026, m, day); cl, t = "", ""
                            if d in work_dates: 
                                cl = "background:#90EE90; font-weight:bold;"
                                wh += hm.get(d.weekday(), 0); m_rc += 1
                                if d in adds: cl = "background:#add8e6; font-weight:bold;"
                            elif d in tips: cl = "background:#FFB6C1; cursor:help;"; t = f'title="{tips[d]}"'
                            html += f'<td style="border:1px solid #ddd; padding:4px; {cl}" {t}>{day}</td>'
                    # 통합h
                    html += f'<td style="border:1px solid #ddd; background:#eef6ff; font-weight:bold;">{int(wh + wa[w_idx])}</td></tr>'
                st.write(html + '</table>', unsafe_allow_html=True)

            m_ah, m_rh = sum(wa), sum([hm.get(d.weekday(), 0) for d in [d for d in work_dates if d.month==m]])
            m_p = (m_rh*int(row['rate'])) + (m_ah*int(row.get('rate_after', 50000)))
            st.info(f"💰 {m}월: {m_p:,}원 (출근 {m_rc}일)"); total_reg+=m_rh; total_aft+=m_ah; total_att+=m_rc

    if st.button(f"💾 {target} 선생님 데이터 저장"):
        others = st.session_state.after_df[st.session_state.after_df['name'] != target]
        st.session_state.after_df = pd.concat([others, cur_aft], ignore_index=True)
        conn.update(worksheet="AfterSchool", data=st.session_state.after_df); st.success("저장됨!"); st.rerun()
