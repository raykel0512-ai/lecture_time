import streamlit as st
import pandas as pd
from datetime import date, timedelta
import plotly.express as px

# 페이지 설정
st.set_page_config(page_title="2026 수업 시수 계산기", layout="wide")

st.title("📅 2026년 수업 시수 계산기")
st.sidebar.header("설정")

# 1. 요일 선택
days = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
selected_days_idx = st.sidebar.multiselect("수업 요일을 선택하세요", range(7), format_func=lambda x: days[x])

# 2. 제외 기간 (방학/휴일) 입력
st.sidebar.subheader("제외 기간 설정 (방학 등)")
exclude_start = st.sidebar.date_input("제외 시작일", value=date(2026, 7, 20))
exclude_end = st.sidebar.date_input("제외 종료일", value=date(2026, 8, 20))

# 3. 2026년 기본 공휴일 설정 (대체공휴일 포함)
korean_holidays = [
    date(2026, 3, 1), date(2026, 3, 2),  # 삼일절 및 대체
    date(2026, 5, 5), date(2026, 5, 24), date(2026, 5, 25), # 어린이날, 부처님오신날
    date(2026, 6, 6), date(2026, 8, 15), date(2026, 8, 17), # 현충일, 광복절 및 대체
    date(2026, 9, 24), date(2026, 9, 25), date(2026, 9, 26), date(2026, 9, 28), # 추석
    date(2026, 10, 3), date(2026, 10, 9), date(2026, 12, 25) # 개천절, 한글날, 성탄절
]

# 계산 로직
start_date = date(2026, 3, 1)
end_date = date(2026, 12, 31)

current_date = start_date
data = []

while current_date <= end_date:
    # 조건 확인: 선택한 요일인가? & 공휴일이 아닌가? & 제외 기간이 아닌가?
    is_selected_day = current_date.weekday() in selected_days_idx
    is_holiday = current_date in korean_holidays
    is_excluded_period = exclude_start <= current_date <= exclude_end
    
    if is_selected_day and not is_holiday and not is_excluded_period:
        data.append({
            "날짜": current_date,
            "월": f"{current_date.month}월",
            "요일": days[current_date.weekday()]
        })
    
    current_date += timedelta(days=1)

df = pd.DataFrame(data)

# 결과 표시
if not df.empty:
    # 월별 통계
    monthly_counts = df.groupby("월").size().reset_index(name="횟수")
    # 월 순서 정렬
    monthly_counts['월번호'] = monthly_counts['월'].str.replace('월', '').astype(int)
    monthly_counts = monthly_counts.sort_values('월번호')

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📊 월별 수업 횟수")
        st.dataframe(monthly_counts[["월", "횟수"]], use_container_width=True)
        st.metric("연간 총 수업 시수", f"{len(df)}회")

    with col2:
        st.subheader("📈 시각화")
        fig = px.bar(monthly_counts, x='월', y='횟수', text='횟수', color='횟수',
                     color_continuous_scale='Blues')
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("📋 전체 수업 일정 상세")
    st.write(df[["날짜", "요일"]])
else:
    st.info("왼쪽 사이드바에서 요일을 선택해 주세요.")
