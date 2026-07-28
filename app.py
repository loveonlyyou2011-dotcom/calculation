from datetime import datetime
import json
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import plotly.express as px
import streamlit as st

# --- Page Configuration ---
st.set_page_config(
    page_title="팀 예산 관리 시스템", page_icon="📊", layout="wide"
)

# --- Google Sheets URL (기본값 설정) ---
DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1eDRHR3Jfd0P7hwmZy1d_Ncdb-AXhGhwe62lFaNKjF8s/edit?usp=drive_link"


# --- Google Sheets Connection ---
@st.cache_resource(ttl=300)
def init_gspread():
    """Streamlit Secrets의 인증 정보와 지정된 시트 URL을 연동"""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    # Secrets에서 URL 및 인증정보 로드
    sheet_url = st.secrets.get("SPREADSHEET_URL", DEFAULT_SHEET_URL)

    if "GCP_SERVICE_ACCOUNT" in st.secrets:
        try:
            creds_dict = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
            creds = Credentials.from_service_account_info(
                creds_dict, scopes=scopes
            )
            client = gspread.authorize(creds)
            sheet = client.open_by_url(sheet_url).sheet1

            # 만약 시트가 비어있다면 초기 헤더 추가
            existing_records = sheet.get_all_values()
            if not existing_records:
                sheet.append_row(
                    ["timestamp", "month", "member", "category", "amount"]
                )

            return sheet
        except Exception as e:
            st.error(f"구글 시트 연결 오류: {e}")
            return None
    else:
        return None


def fetch_data(sheet):
    """구글 시트 데이터 불러오기"""
    if sheet is None:
        return pd.DataFrame(
            columns=["timestamp", "month", "member", "category", "amount"]
        )

    try:
        records = sheet.get_all_records()
        df = pd.DataFrame(records)

        if not df.empty and "amount" in df.columns:
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

        return df
    except Exception:
        return pd.DataFrame(
            columns=["timestamp", "month", "member", "category", "amount"]
        )


def append_data(sheet, row_data):
    """구글 시트에 신규 행 추가"""
    if sheet:
        sheet.append_row(row_data)


# --- Initialize Connection ---
sheet = init_gspread()

st.title("📊 팀 예산 관리 시스템")
st.caption("부장님 보고용 월별 예산 취합 및 대시보드")

if sheet is None:
    st.info(
        "💡 Google Cloud 서비스 계정 비밀키(`GCP_SERVICE_ACCOUNT`)가 Streamlit Secrets에 등록되어 있어야 완전한 데이터 저장이 가능합니다."
    )

# --- App Layout (Tabs) ---
tab1, tab2 = st.tabs(["📝 데이터 입력", "📈 전체 대시보드"])

# --- TAB 1: 데이터 입력 ---
with tab1:
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("내역 입력")
        with st.form("budget_form", clear_on_submit=True):
            member = st.selectbox(
                "팀원 선택",
                [
                    "선택하세요",
                    "부장님",
                    "팀원1",
                    "팀원2",
                    "팀원3",
                    "팀원4",
                ],
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
                    st.error("팀원을 선택해주세요.")
                elif amount <= 0:
                    st.error("사용 금액을 0원 이상 입력해주세요.")
                else:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    new_row = [timestamp, month, member, category, amount]

                    try:
                        append_data(sheet, new_row)
                        st.success("지정한 구글 시트에 성공적으로 데이터가 입력되었습니다!")
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"저장 중 오류 발생: {e}")

    with col2:
        st.subheader("📂 최근 입력 내역")
        data_df = fetch_data(sheet)

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
            st.info("현재 저장된 데이터가 없습니다.")

# --- TAB 2: 전체 대시보드 ---
with tab2:
    data_df = fetch_data(sheet)

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
