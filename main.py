from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import streamlit as st

# 페이지 기본 설정
st.set_page_config(
    page_title="일별 박스오피스 순위", page_icon="🎬", layout="wide"
)

st.title("🎬 일별 영화 박스오피스 순위")
st.write(
    "영화진흥위원회(KOBIS) Open API를 활용하여 선택한 날짜의 박스오피스 정보를 보여줍니다."
)


# 1. 한국 시간(KST) 기준 어제 날짜 구하기 함수 (달력 선택의 최댓값)
def get_yesterday_kst():
  kst = ZoneInfo("Asia/Seoul")
  return datetime.now(kst).date() - timedelta(days=1)


yesterday = get_yesterday_kst()

# 2. 사이드바에서 날짜 선택 (최대 날짜는 '어제'로 제한)
st.sidebar.header("🗓️ 날짜 선택")
selected_date = st.sidebar.date_input(
    label="조회할 날짜를 선택하세요",
    value=yesterday,
    max_value=yesterday,
    help="오늘 날짜 이후는 선택할 수 없습니다.",
)

# API 요청용 yyyymmdd 포맷 문자열 생성
target_dt = selected_date.strftime("%Y%m%d")


# 3. KOBIS API 데이터 호출 함수
@st.cache_data(ttl=3600)
def fetch_box_office_data(api_key, target_dt):
  url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
  params = {"key": api_key, "targetDt": target_dt}

  try:
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    # KOBIS API 오류 반환 처리
    if "faultInfo" in data:
      return None, f"API 오류 발생: {data['faultInfo']}"

    box_office_result = data.get("boxOfficeResult", {})
    movie_list = box_office_result.get("dailyBoxOfficeList", [])

    if not movie_list:
      return None, "그날은 아직 집계 전입니다."

    return movie_list, None

  except Exception as e:
    return None, f"네트워크 요청 중 오류가 발생했습니다: {e}"


# 4. Secrets에서 API 키 불러오기
try:
  API_KEY = st.secrets["KOBIS_KEY"]
except Exception:
  st.error(
      "⚠️ **API 키가 설정되지 않았습니다!**\n\n"
      "Streamlit Cloud 앱 설정의 **Secrets** 메뉴에 등록해 주세요.\n\n"
      "```toml\n"
      'KOBIS_KEY = "발급받은_인증키_입력"\n'
      "```"
  )
  st.stop()


# 5. 선택한 날짜 화면 출력
formatted_date = selected_date.strftime("%Y년 %m월 %d일")
st.subheader(f"📅 조회 기준일: {formatted_date}")

# 데이터 요청
movie_list, error_msg = fetch_box_office_data(API_KEY, target_dt)

# 데이터가 없거나 에러 발생 시 처리
if error_msg:
  if error_msg == "그날은 아직 집계 전입니다.":
    st.warning(f"⚠️ **{error_msg}** 다른 날짜를 선택해 주세요.")
  else:
    st.error(
        f"⚠️ **데이터를 불러오지 못했습니다.**\n\n"
        f"**확인해야 할 사항:**\n"
        f"1. **에러 내용:** {error_msg}\n"
        f"2. **인증키 확인:** Streamlit Secrets에 `KOBIS_KEY`가 올바르게 입력되었는지 확인해 주세요.\n"
        f"3. **일일 한도 확인:** KOBIS API 일일 요청 제한(3,000건)을 초과하지 않았는지 확인해 주세요."
    )
else:
  # 데이터프레임 변환
  df = pd.DataFrame(movie_list)

  # 숫자로 변환할 컬럼 처리
  numeric_cols = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt"]
  for col in numeric_cols:
    df[col] = pd.to_numeric(df[col])

  # --- [포맷팅 처리] ---
  # 1) 순위 증감(rankInten) 화살표 포맷팅
  def format_rank_change(row):
    if row.get("rankOldAndNew") == "NEW":
      return "🆕"
    inten = row["rankInten"]
    if inten > 0:
      return f"🔺 {inten}"
    elif inten < 0:
      return f"🔹 {abs(inten)}"
    else:
      return "-"

  df["순위변동"] = df.apply(format_rank_change, axis=1)

  # 2) 누적 관객 100만 이상 시 트로피(🏆) 추가
  def format_movie_title(row):
    title = row["movieNm"]
    if row["audiAcc"] >= 1000000:
      return f"🏆 {title}"
    return title

  df["표시영화명"] = df.apply(format_movie_title, axis=1)

  # 보기 좋은 데이터프레임으로 정리
  df_display = df[
      [
          "rank",
          "순위변동",
          "표시영화명",
          "openDt",
          "audiCnt",
          "audiAcc",
          "scrnCnt",
          "movieNm",
      ]
  ].copy()
  df_display.columns = [
      "순위",
      "순위변동",
      "영화명",
      "개봉일",
      "관객수",
      "누적관객",
      "스크린수",
      "원래영화명",
  ]

  # --- [시각화 1] 1위 영화 지표 카드 3장 ---
  st.markdown("---")
  top_movie = df_display.iloc[0]
  st.subheader(f"👑 {top_movie['영화명']} (1위)")

  col1, col2, col3 = st.columns(3)
  with col1:
    st.metric(
        label="일일 관객수",
        value=f"{top_movie['관객수']:,}명",
        delta=top_movie["순위변동"],
    )
  with col2:
    st.metric(label="누적 관객수", value=f"{top_movie['누적관객']:,}명")
  with col3:
    st.metric(label="상영 스크린수", value=f"{top_movie['스크린수']:,}개")

  # --- [시각화 2] 관객수 상위 5편 막대그래프 ---
  st.markdown("---")
  st.subheader("📊 관객수 상위 5위 영화 비교")

  top5_df = df_display.head(5).set_index("원래영화명")[["관객수"]]
  st.bar_chart(top5_df)

  # --- [표] 전체 박스오피스 순위 표 ---
  st.markdown("---")
  st.subheader("📋 전체 박스오피스 순위표")

  # 화면 출력용 최종 컬럼 선택 (원래영화명 제외)
  table_df = df_display[
      ["순위", "순위변동", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]
  ].set_index("순위")

  st.dataframe(table_df, use_container_width=True)
