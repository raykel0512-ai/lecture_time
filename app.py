import streamlit as st
import pandas as pd
from datetime import date, timedelta
import plotly.express as px

# 페이지 설정
st.set_page_config(page_title="2026 시수 계산기", layout="wide")

st.title("📅 2026년 강사 수업 시수 계산기")

# 사이드바 설정
st.sidebar.header("🗓️ 수업 설정")
selected_days = st.sidebar.multiselect(
    "수업 요일 선택",
    ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"],
    default=["월요일"]
)

# 요일 한글 -> 숫자 변환
day_map = {"월요일":0, "화요일":1, "수요일":2, "목요일":3, "금요일":4, "토요일":5, "일요일":6}
selected_days_idx = [day_map[d] for d in selected_days]

# 방학/휴무 기간 설정
st.sidebar.subheader("🚫 제외 기간 (방학 등)")
excl_start = st.sidebar.date_input("제외 시작일", value=date(2026, 7, 20))
excl_end = st.sidebar.date_input("제외 종료일", value=date(2026, 8, 20))

# 2026년 공휴일 리스트 (수동 추가 가능)
holidays = [
    date(2026, 3, 1), date(2026, 3, 2), # 삼일절
    date(2026, 5, 5), date(2026, 5, 24), date(2026, 5, 25), # 어린이날/부처님오신날
    date(2026, 6, 6), date(2026, 8, 15), date(2026, 8, 17), # 현충일/광복절
    date(2026, 9, 24), date(2026, 9, 25), date(2026, 9, 26), date(2026, 9, 28), # 추석
    date(2026, 10, 3), date(2026, 10, 9), date(2026, 12, 25) # 개천절/한글날/성탄절
]

# 계산 로직 (3월~12월)
start_date = date(2026, 3, 1)
end_date = date(2026, 12, 31)
current = start_date
res = []

while current <= end_date:
    if current.weekday() in selected_days_idx:
        status = "정상 수업"
        if current in holidays:
            status = "공휴일 제외"
        elif excl_start <= current <= excl_end:
            status = "방학 제외"
            
        if status == "정상 수업":
            res.append({"날짜": current, "월": f"{current.month}월", "요일": selected_days[selected_days_idx.index(current.weekday())]})
    current += timedelta(days=1)

df = pd.DataFrame(res)

# 결과 화면
if not df.empty:
    m_counts = df.groupby("월").size().reset_index(name="횟수")
    m_counts['월번호'] = m_counts['월'].str.replace('월','').astype(int)
    m_counts = m_counts.sort_values('월번호')

    c1, c2 = st.columns([1, 1])
    with c1:
        st.metric("✅ 연간 총 시수", f"{len(df)}회")
        st.dataframe(m_counts[["월", "횟수"]], use_container_width=True)
    with c2:
        fig = px.bar(m_counts, x='월', y='횟수', color='횟수', text_auto=True, title="월별 수업 분포")
        st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("📅 상세 수업 일정")
    st.table(df[["날짜", "요일"]])
else:
    st.warning("선택된 수업 일정이 없습니다. 요일을 선택해 주세요.")
