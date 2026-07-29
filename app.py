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
GAS_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbx3M_JahrsiBd0xHy9ExYaHaF5YcnDOZplHQKyCSjWW-6AZ-81DdTMQJXKwZUzk_iBgBw/exec"

st.title("📊 팀 예산 관리 시스템")
st.caption("부장님 보고용 월별 예산 취합 및 대시보드 (Google Apps Script API 연동)")

# --- 3. 데이터 조회 및 추가 함수 ---
@st.cache_data(ttl=5)
def fetch_data_from_gas(url: str) -> pd.DataFrame:
    """Google Apps Script API를 통해 구글 시트 데이터 로드"""
    try:
        response = requests.get(url, timeout=15, allow_redirects=True)
        if response.status_code == 200:
            data = response.json()
            # 데이터 구조가 dict 안에 data 키로 있을 경우를 대비
            if isinstance(data, dict) and "data" in data:
                data = data["data"]
            df = pd.DataFrame(data)

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
        response = requests.post(url, json=payload, timeout=15, allow_redirects=True)
        if response.status_code == 200:
            res_json = response.json()
            return res_json.get("status") == "success"
        return False
    except Exception as e:
        st.error(f"데이터 저장 중 에러 발생: {e}")
        return False

# --- 4. App State (팀원 목록 관리) ---
if "custom_members" not in st.session_state:
    st.session_state.custom_members = []

# 데이터 사전 로드 (동적 팀원 목록 추출용)
data_df = fetch_data_from_gas(GAS_WEB_APP_URL)

existing_members = data_df["member"].dropna().unique().tolist() if not data_df.empty and "member" in data_df.columns else []
default_members = ["부장님", "팀원1", "팀원2", "팀원3", "팀원4"]

# 기존 멤버, 기본 멤버, 세션에서 추가된 멤버 병합 후 정렬
all_members = list(set(default_members + existing_members + st.session_state.custom_members))
all_members = sorted([m for m in all_members if str(m).strip()])
member_options = ["선택하세요"] + all_members

# --- 5. App Layout (Tabs) ---
tab1, tab2 = st.tabs(["📝 데이터 입력", "📈 전체 대시보드"])

# --- TAB 1: 데이터 입력 ---
with tab1:
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("내역 입력")
        
        # 팀원 추가 UI
        with st.expander("➕ 새 팀원 추가하기"):
            new_member = st.text_input("추가할 팀원 이름", key="new_mem_input")
            if st.button("목록에 추가"):
                if new_member and new_member not in st.session_state.custom_members and new_member not in all_members:
                    st.session_state.custom_members.append(new_member)
                    st.success(f"'{new_member}' 팀원이 추가되었습니다.")
                    st.rerun()
                elif new_member in all_members:
                    st.warning("이미 존재하는 팀원입니다.")

        # 메인 폼
        with st.form("budget_form", clear_on_submit=True):
            member = st.selectbox("팀원 선택", member_options)
            
            current_month = datetime.now().strftime("%Y-%m")
            month = st.text_input("해당 월 (YYYY-MM)", value=current_month, max_chars=7)

            category = st.selectbox("예산 항목", ["수선유지비", "비품", "개량공사"])
            amount = st.number_input("사용 금액 (원)", min_value=0, step=1000, value=0)

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

                    with st.spinner("구글 시트에 저장 중입니다..."):
                        success = append_data_to_gas(GAS_WEB_APP_URL, payload)

                    if success:
                        st.success("구글 시트에 성공적으로 저장되었습니다!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("❌ 저장에 실패했습니다. (Apps Script 권한 및 코드를 확인해주세요)")

    with col2:
        st.subheader("📂 최근 입력 내역")

        if not data_df.empty and "timestamp" in data_df.columns:
            display_df = data_df.sort_values(by="timestamp", ascending=False).copy()
            if "amount" in display_df.columns:
                display_df["amount_formatted"] = display_df["amount"].apply(
                    lambda x: f"{int(x):,}원"
                )

                cols_to_show = ["month", "member", "category", "amount_formatted"]
                existing_cols = [c for c in cols_to_show if c in display_df.columns]

                st.dataframe(
                    display_df[existing_cols].rename(
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
    if not data_df.empty and "amount" in data_df.columns:
        total_amount = data_df["amount"].sum()
        total_count = len(data_df)

        cat_agg = data_df.groupby("category")["amount"].sum()
        top_category = cat_agg.idxmax() if not cat_agg.empty else "-"
        top_cat_amount = cat_agg.max() if not cat_agg.empty else 0
        
        mem_agg = data_df.groupby("member")["amount"].sum()
        top_member = mem_agg.idxmax() if not mem_agg.empty else "-"
        top_mem_amount = mem_agg.max() if not mem_agg.empty else 0

        # 기본 데이터 분석 요약 기능
        st.success(f"💡 **데이터 분석 요약**\n\n"
                   f"현재까지 총 **{total_count}건**의 내역이 등록되었으며, 전체 누적 사용액은 **{int(total_amount):,}원**입니다. "
                   f"가장 많은 예산이 소요된 항목은 **{top_category}**({int(top_cat_amount):,}원)이며, "
                   f"누적 예산을 가장 많이 사용한 팀원은 **{top_member}**({int(top_mem_amount):,}원)입니다.")
                   
        # ✨ Gemini AI 연동 섹션 추가 (입력창 제거 버전)
        st.markdown("### 🤖 AI 심층 요약 (Gemini)")
        
        # Streamlit Secrets에서 API 키 자동 가져오기
        try:
            api_key = st.secrets["GEMINI_API_KEY"]
        except (KeyError, FileNotFoundError):
            api_key = None

        if not api_key:
            st.warning("⚠️ Streamlit 앱 설정(Settings) -> Secrets에 'GEMINI_API_KEY'가 설정되지 않았습니다.")
        else:
            if st.button("✨ AI 요약하기"):
                with st.spinner("AI가 데이터를 분석하고 있습니다. 잠시만 기다려주세요... 🤖 (약 5~10초 소요)"):
                    try:
                        # 1. 데이터 단순화
                        simplified_data = data_df[["month", "member", "category", "amount"]].rename(
                            columns={"month": "월", "member": "팀원", "category": "항목", "amount": "금액"}
                        ).to_dict(orient="records")
                        
                        prompt = f"다음은 우리 팀의 예산 사용 내역 데이터입니다. 이 데이터를 분석해서 지출 패턴, 비중, 트렌드 등 가장 눈에 띄는 특징이나 인사이트를 찾아주세요. 반드시 **딱 한 줄로 요약**해서 대답해야 합니다.\n\n데이터: {simplified_data}"
                        
                        # 2. REST API를 통해 Gemini 호출 (모델명 gemini-3-flash-preview)
                        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={api_key}"
                        payload = {
                            "contents": [{"parts": [{"text": prompt}]}],
                            "systemInstruction": {
                                "parts": [{"text": "당신은 전문적인 재무 데이터 분석가입니다. 주어진 예산 데이터를 분석하여 가장 핵심적인 특징을 통찰력 있고 명확하게 딱 한 줄로 요약해야 합니다."}]
                            },
                        }
                        
                        response = requests.post(api_url, json=payload, headers={'Content-Type': 'application/json'})
                        result = response.json()
                        
                        # 3. 결과 출력
                        if response.status_code == 200:
                            ai_text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            if ai_text:
                                st.info(f"✨ **AI 분석 결과:** {ai_text}")
                            else:
                                st.error("AI 분석 결과를 불러오지 못했습니다.")
                        else:
                            error_msg = result.get("error", {}).get("message", "알 수 없는 오류")
                            st.error(f"API 호출 실패: {error_msg}")
                            
                    except Exception as e:
                        st.error(f"AI 분석 중 오류가 발생했습니다: {e}")

        st.divider()

        m1, m2, m3 = st.columns(3)
        m1.metric("전체 누적 사용액", f"{int(total_amount):,}원")
        m2.metric("최대 사용 항목", f"{top_category}", f"{int(top_cat_amount):,}원")
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
            member_agg_df = mem_agg.reset_index()
            fig_bar = px.bar(
                member_agg_df,
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

        formatted_pivot = pivot_df.map(lambda x: f"{int(x):,}원")
        st.dataframe(formatted_pivot, use_container_width=True)

    else:
        st.info("시트에 집계할 데이터가 존재하지 않습니다.")
