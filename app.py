from datetime import datetime
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# --- 1. Page Configuration ---
st.set_page_config(
    page_title="팀 예산 관리 시스템",
    page_icon="📊",
    layout="wide",
)

# --- 2. Google Apps Script Web App URL ---
# 발급받은 URL을 직접 입력해 두었습니다. 
GAS_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbx3M_JahrsiBd0xHy9ExYaHaF5YcnDOZplHQKyCSjWW-6AZ-81DdTMQJXKwZUzk_iBgBw/exec"

st.title("📊 팀 예산 관리 시스템")
st.caption("부장님 보고용 월별 예산 취합 및 대시보드 (Google Apps Script API 연동)")


# --- 3. 데이터 조회 및 추가 함수 ---
@st.cache_data(ttl=5) # 최신 데이터를 빠르게 반영하기 위해 5초 단위 갱신
def fetch_data_from_gas(url: str) -> pd.DataFrame:
    """Google Apps Script API를 통해 구글 시트 데이터 로드"""
    try:
        # GET 요청으로 시트 데이터(JSON)를 가져옵니다. (리다이렉트 허용)
        response = requests.get(url, timeout=15, allow_redirects=True)
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data)

            # amount 컬럼이 있으면 숫자형으로 변환
            if not df.empty and "amount" in df.columns:
                df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
            return df
        else:
            st.error(f"데이터 로드 실패 (Status Code: {response.status_code})")
            return pd.DataFrame(
                columns=["timestamp", "month", "member", "category", "amount"]
            )
    except Exception as e:
        st.error(f"Apps Script 연결 오류: {e}")
        return pd.DataFrame(
            columns=["timestamp", "month", "member", "category", "amount"]
        )


def append_data_to_gas(url: str, payload: dict) -> bool:
    """Google Apps Script API를 통해 구글 시트에 신규 데이터 저장"""
    try:
        # POST 요청으로 새 데이터를 전송합니다. (리다이렉트 허용)
        response = requests.post(url, json=payload, timeout=15, allow_redirects=True)
        if response.status_code == 200:
            res_json = response.json()
            return res_json.get("status") == "success"
        return False
    except Exception as e:
        st.error(f"데이터 저장 중 에러 발생: {e}")
        return False


# --- 4. App Layout (Tabs) ---
tab1, tab2 = st.tabs(["📝 데이터 입력", "📈 전체 대시보드"])

# --- TAB 1: 데이터 입력 ---
with tab1:
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("내역 입력")
        with st.form("budget_form", clear_on_submit=True):
            member = st.selectbox(
                "팀원 선택",
                ["선택하세요", "부장님", "팀원1", "팀원2", "팀원3", "팀원4"],
            )

            current_month = datetime.now().strftime("%Y-%m")
            month = st.text_input(
                "해당 월 (YYYY-MM)", value=current_month, max_chars=7
            )

            category = st.selectbox(
                "예산 항목", ["수선유지비", "비품", "개량공사"]
            )
            amount = st.number_input(
                "사용 금액 (원)", min_value=0, step=1000, value=0
            )

            submitted = st.form_submit_button("기록 저장하기")

            if submitted:
                if member == "선택하세요":
                    st.error("팀원을 선택해 주세요.")
                elif amount <= 0:
                    st.error("사용 금액을 0원 이상 입력해 주세요.")
                else:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    payload = {
                        "timestamp": timestamp,
                        "month": month,
                        "member": member,
                        "category": category,
                        "amount": amount,
                    }

                    # 데이터 저장 실행
                    with st.spinner("구글 시트에 저장 중입니다..."):
                        success = append_data_to_gas(GAS_WEB_APP_URL, payload)
                        
                    if success:
                        st.success("구글 시트에 성공적으로 저장되었습니다!")
                        st.cache_data.clear() # 캐시 비우고 최신화
                        st.rerun() # 화면 새로고침
                    else:
                        st.error("❌ 저장에 실패했습니다. (Apps Script 권한 및 코드를 확인해주세요)")

    with col2:
        st.subheader("📂 최근 입력 내역")
        data_df = fetch_data_from_gas(GAS_WEB_APP_URL)

        if not data_df.empty and "timestamp" in data_df.columns:
            display_df = data_df.sort_values(
                by="timestamp", ascending=False
            ).copy()
            display_df["amount_formatted"] = display_df["amount"].apply(
                lambda x: f"{int(x):,}원"
            )

            st.dataframe(
                display_df[
                    ["month", "member", "category", "amount_formatted"]
                ].rename(
                    columns={
                        "month": "월",
                        "member": "팀원",
                        "category": "항목",
                        "amount_formatted": "금액",
                    }
                ),
                use_container_width=True,
                height=400,
            )
        else:
            st.info("현재 저장된 데이터가 없거나 로드 중입니다.")

# --- TAB 2: 전체 대시보드 ---
with tab2:
    data_df = fetch_data_from_gas(GAS_WEB_APP_URL)

    if not data_df.empty and "amount" in data_df.columns:
        total_amount = data_df["amount"].sum()
        total_count = len(data_df)

        cat_agg = data_df.groupby("category")["amount"].sum()
        top_category = cat_agg.idxmax() if not cat_agg.empty else "-"
        top_cat_amount = cat_agg.max() if not cat_agg.empty else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("전체 누적 사용액", f"{int(total_amount):,}원")
        m2.metric(
            "최대 사용 항목",
            f"{top_category}",
            f"{int(top_cat_amount):,}원",
        )
        m3.metric("데이터 건수", f"{total_count}건")

        st.divider()

        c1, c2 = st.columns(2)

        with c1:
            st.subheader("🏠 항목별 예산 분포")
            fig_pie = px.pie(
                data_df,
                names="category",
                values="amount",
                hole=0.5,
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig_pie.update_traces(textinfo="percent+label")
            st.plotly_chart(fig_pie, use_container_width=True)

        with c2:
            st.subheader("👥 팀원별 누적 사용액")
            member_agg = (
                data_df.groupby("member")["amount"].sum().reset_index()
            )
            fig_bar = px.bar(
                member_agg,
                x="member",
                y="amount",
                labels={"member": "팀원", "amount": "사용 금액(원)"},
                color_discrete_sequence=["#60a5fa"],
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        st.divider()

        st.subheader("📅 월별/항목별 요약 테이블 (취합본)")
        pivot_df = data_df.pivot_table(
            index="month",
            columns="category",
            values="amount",
            aggfunc="sum",
            fill_value=0,
        )

        for cat in ["수선유지비", "비품", "개량공사"]:
            if cat not in pivot_df.columns:
                pivot_df[cat] = 0

        pivot_df = pivot_df[["수선유지비", "비품", "개량공사"]]
        pivot_df["합계"] = pivot_df.sum(axis=1)
        pivot_df = pivot_df.sort_index(ascending=False)

        formatted_pivot = pivot_df.applymap(lambda x: f"{int(x):,}원")
        st.dataframe(formatted_pivot, use_container_width=True)

    else:
        st.info("시트에 집계할 데이터가 존재하지 않습니다.")
