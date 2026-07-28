@st.cache_resource(ttl=60)
def init_gspread():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    sheet_url = st.secrets.get("SPREADSHEET_URL", DEFAULT_SHEET_URL)

    if "GCP_SERVICE_ACCOUNT" in st.secrets:
        try:
            sec = st.secrets["GCP_SERVICE_ACCOUNT"]
            if isinstance(sec, str):
                creds_dict = json.loads(sec)
            else:
                creds_dict = dict(sec)

            # --- private_key 전처리 및 자동 정제 ---
            if "private_key" in creds_dict:
                pk = creds_dict["private_key"]

                # 1. 앞뒤에 잘못 포함된 마침표나 공백, 따옴표 제거
                pk = pk.strip().strip(".").strip('"').strip("'")

                # 2. escape된 \\n 문자를 실제 줄바꿈 \n 으로 변경
                pk = pk.replace("\\n", "\n")

                creds_dict["private_key"] = pk

            creds = Credentials.from_service_account_info(
                creds_dict, scopes=scopes
            )
            client = gspread.authorize(creds)
            sheet = client.open_by_url(sheet_url).sheet1

            existing_records = sheet.get_all_values()
            if not existing_records:
                sheet.append_row(
                    ["timestamp", "month", "member", "category", "amount"]
                )

            return sheet
        except Exception as e:
            st.error(
                f"🚨 구글 시트 연결 중 인증 오류 발생: {e}\n\n"
                "Secrets의 'private_key' 문자열 앞뒤에 점(.)이나 불필요한 따옴표가 들어갔는지 확인해주세요."
            )
            return None
    else:
        st.warning(
            "⚠️ Streamlit Secrets에 'GCP_SERVICE_ACCOUNT' 정보가 등록되지 않았습니다."
        )
        return None
