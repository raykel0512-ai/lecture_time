import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date, timedelta
import calendar

st.set_page_config(page_title="2026 강사 시수 관리 Pro", layout="wide")

# 1. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. 세션 상태 초기화 (메모리 로딩)
if 'ins_df' not in st.session_state:
    try:
        st.session_state.ins_df = conn.read(worksheet="Instructors", ttl=0)
        num_cols = ['rate', 'mon', 'tue', 'wed', 'thu', 'fri']
        for col in num_cols:
            if col in st.session_state.ins_df.columns:
                st.session_state.ins_df[col] = pd.to_numeric(st.session_state.ins_df[col], errors='coerce').fillna(0)
    except:
        st.session_state.ins_df = pd.DataFrame()

if 'excl_df' not in st.session_state:
    try:
        st.session_state.excl_df = conn.read(worksheet="Exclusions", ttl=0)
    except:
        st.session_state.excl_df = pd.DataFrame()

# 2026년 공휴일
HOLIDAYS = [date(2026,3,1), date(2026,3,2), date(2026,5,5), date(2026,5,24), date(2026,5,25), 
            date(2026,6,6), date(2026,8,15), date(2026,8,17), date(2026,9,24), date(2026,9,25), 
            date(2026,9,26), date(2026,9,28), date(2026,10,3), date(2026,10,9), date(2026,12,25)]

st.t
