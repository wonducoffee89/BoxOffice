from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import streamlit as st

# 페이지 기본 설정 (웹페이지 제목과 레이아웃 설정)
st.set_page_config(
    page_title="어제 박스오피스 순위", page_icon="🎬", layout="wide"
)

st.title("🎬 어제의 영화 박스오피스 순위")
st.write(
    "영화진흥위원회(KOBIS) Open API를 활용하여 한국 시간 기준 어제 날짜의 박스오피스 정보를 보여줍니다."
)


# 1. 한국 시간(KST) 기준으로 '어제' 날짜를 yyyymmdd 형식으로 구하는 함수
def get_yesterday_kst():
  kst = ZoneInfo("Asia/Seoul")
  yesterday = datetime.now(kst) - timedelta(days=1)
  return yesterday.strftime("%Y%m%d")


# 2. KOBIS API에서 박스오피스 데이터를 가져오는 함수
@st.cache_data(ttl=3600)  # 동일한 데이터를 1시간 동안 캐시하여 불필요한 요청 방지
def fetch_box_office_data(api_key, target_dt):
  url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
  params = {"key": api_key, "targetDt": target_dt}

  try:
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    # KOBIS API는 인증키 오류나 에러 시에도 200 코드를 주며 faultInfo를 포함함
    if "faultInfo" in data:
      return None, f"API 오류 발생: {data['faultInfo']}"

    box_office_result = data.get("boxOfficeResult", {})
    movie_list = box_office_result.get("dailyBoxOfficeList", [])

    if not movie_list:
      return None, "조회된 영화 데이터가 없습니다."

    return movie_list, None

  except Exception as e:
    return None, f"네트워크 요청 중 오류가 발생했습니다: {e}"


# 3. Streamlit Secrets에서 API 키 불러오기
try:
  API_KEY = st.secrets["15c322dbcef9ed424b4b9dfdd23448f6"]
except Exception:
  st.error(
      "⚠️ **API 키가 설정되지 않았습니다!**\n\n"
      "Streamlit Cloud 앱 설정의 **Secrets** 메뉴에 아래와 같이 등록해 주세요.\n\n"
      "```toml\n"
      'KOBIS_KEY = "여러분의_인증키"\n'
      "```"
  )
  st.stop()

# 어제 날짜 계산 및 화면 표시
target_dt = get_yesterday_kst()
formatted_date = f"{target_dt[:4]}년 {target_dt[4:6]}월 {target_dt[6:]}일"

st.subheader(f"📅 조회 기준일 (어제): {formatted_date}")

# 4. 데이터 요청
movie_list, error_msg = fetch_box_office_data(API_KEY, target_dt)

# 오류가 발생했거나 영화 목록이 비어 있는 경우 안내 메시지 출력
if error_msg or not movie_list:
  st.error(
      f"⚠️ **데이터를 불러오지 못했습니다.**\n\n"
      f"**확인해야 할 사항:**\n"
      f"1. **에러 내용:** {error_msg}\n"
      f"2. **인증키 확인:** Streamlit Secrets에 등록된 `KOBIS_KEY` 값이 정확한지 확인해 주세요.\n"
      f"3. **일일 한도 확인:** KOBIS API의 일일 요청 횟수 제한(일반적으로 3,000건)을 초과하지 않았는지 확인해 주세요.\n"
      f"4. **집계 시간 확인:** 아직 어제 날짜의 집계가 완전히 끝나지 않았거나 서버 점검 중일 수 있습니다."
  )
else:
  # 5. 데이터를 판다스(Pandas) 데이터프레임으로 변환
  df = pd.DataFrame(movie_list)

  # 필요한 컬럼만 골라서 보기 쉽게 이름 변경
  df_display = df[
      ["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
  ].copy()
  df_display.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]

  # API 응답 데이터는 모두 문자열이므로 연산을 위해 숫자로 변환
  for col in ["순위", "관객수", "누적관객", "스크린수"]:
    df_display[col] = pd.to_numeric(df_display[col])

  # --- [시각화 1] 1위 영화 지표 카드 3장 ---
  st.markdown("---")
  st.subheader("👑 어제의 박스오피스 1위 영화")

  top_movie = df_display.iloc[0]
  col1, col2, col3 = st.columns(3)

  with col1:
    st.metric(
        label=f"1위: {top_movie['영화명']}",
        value=f"{top_movie['관객수']:,}명",
        delta="일일 관객수",
    )
  with col2:
    st.metric(label="누적 관객수", value=f"{top_movie['누적관객']:,}명")
  with col3:
    st.metric(label="상영 스크린수", value=f"{top_movie['스크린수']:,}개")

  # --- [시각화 2] 관객수 상위 5편 막대그래프 ---
  st.markdown("---")
  st.subheader("📊 관객수 상위 5위 영화 비교")

  # 상위 5개 행을 추출하고 '영화명'을 인덱스로 지정하여 막대그래프 생성
  top5_df = df_display.head(5).set_index("영화명")[["관객수"]]
  st.bar_chart(top5_df)

  # --- [표] 전체 박스오피스 순위 표 ---
  st.markdown("---")
  st.subheader("📋 전체 박스오피스 순위표")

  st.dataframe(df_display.set_index("순위"), use_container_width=True)
