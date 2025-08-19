import os
import requests
import streamlit as st
from dotenv import load_dotenv

# 1) 환경변수 로드
load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE = "https://api.themoviedb.org/3"
IMG_BASE = "https://image.tmdb.org/t/p/w500"

# 2) 공용 요청 헬퍼
def tmdb_get(path, params=None):
    if params is None:
        params = {}
    headers = {"accept": "application/json"}
    params["api_key"] = TMDB_API_KEY
    r = requests.get(f"{TMDB_BASE}{path}", params=params, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()

# 3) 넷플릭스 필터용 상수
NETFLIX_PROVIDER_ID = 8  # TMDb watch provider id

# 4) 무드-장르 매핑
MOOD_MAP = {
    "위로가 필요해": {
        "genres_movie": [35, 10749, 16],
        "genres_tv": [18, 35],
        "sort": "popularity.desc"
    },
    "카타르시스/스트레스 해소": {
        "genres_movie": [28, 53, 80],
        "genres_tv": [10759, 80, 9648],
        "sort": "vote_average.desc"
    },
    "불안이 커": {
        "genres_movie": [18, 10751],
        "genres_tv": [18, 10751],
        "sort": "popularity.desc"
    },
    "무기력/번아웃": {
        "genres_movie": [99, 10402, 18],
        "genres_tv": [99, 18],
        "sort": "popularity.desc"
    },
    "설렘/두근거림": {
        "genres_movie": [10749, 35],
        "genres_tv": [18, 35, 10749],
        "sort": "popularity.desc"
    },
    "깊게 몰입하고 싶어": {
        "genres_movie": [9648, 878, 18],
        "genres_tv": [9648, 18, 80],
        "sort": "vote_average.desc"
    },
}

# 5) Discover로 넷플릭스 제공작 가져오기
def discover_titles(content_type, region="KR", lang="ko-KR", with_genres=None, sort_by="popularity.desc", page=1):
    path = f"/discover/{content_type}"
    params = {
        "with_watch_providers": NETFLIX_PROVIDER_ID,
        "watch_region": region,
        "sort_by": sort_by,
        "include_adult": "false",
        "page": page,
        "language": lang,
    }
    if with_genres:
        params["with_genres"] = ",".join(map(str, with_genres))
    data = tmdb_get(path, params)
    return data.get("results", [])

# 6) 상세 정보(출연, 예고편)
def get_title_detail(content_type, tmdb_id, lang="ko-KR"):
    detail = tmdb_get(f"/{content_type}/{tmdb_id}", {"language": lang})
    credits = tmdb_get(f"/{content_type}/{tmdb_id}/credits", {"language": lang})
    videos = tmdb_get(f"/{content_type}/{tmdb_id}/videos", {"language": lang})
    cast = [c for c in credits.get("cast", [])][:8]
    trailer_key = None
    for v in videos.get("results", []):
        if v.get("type") in ["Trailer", "Teaser"] and v.get("site") == "YouTube":
            trailer_key = v.get("key")
            break
    return detail, cast, trailer_key

# 7) 무드 스코어링
def infer_mood(answers):
    scores = {k: 0 for k in MOOD_MAP.keys()}

    if answers["오늘 기분"] <= -2:
        scores["위로가 필요해"] += 2
        scores["무기력/번아웃"] += 1
    elif answers["오늘 기분"] >= 2:
        scores["설렘/두근거림"] += 2

    if answers["스트레스"] >= 7:
        scores["카타르시스/스트레스 해소"] += 2
        scores["깊게 몰입하고 싶어"] += 1

    if answers["불안감"] >= 6:
        scores["불안이 커"] += 2

    if answers["집중력"] <= 3:
        scores["무기력/번아웃"] += 2
    else:
        scores["깊게 몰입하고 싶어"] += 1

    if answers["보고 싶은 톤"] == "밝고 따뜻한":
        scores["위로가 필요해"] += 2
        scores["설렘/두근거림"] += 1
    elif answers["보고 싶은 톤"] == "강렬/짜릿한":
        scores["카타르시스/스트레스 해소"] += 2
    elif answers["보고 싶은 톤"] == "진지/사색":
        scores["깊게 몰입하고 싶어"] += 2

    mood = max(scores, key=scores.get)
    return mood, scores

# 8) Streamlit UI
def main():
    st.set_page_config(page_title="심리-무드 기반 넷플릭스 추천", page_icon="🎬", layout="wide")
    st.title("지금 마음에 맞는 넷플릭스 추천 🎬")
    st.caption("현재 심리 상태에 맞는 영화/시리즈를 추천해줄게요!")

    with st.sidebar:
        region = st.text_input("국가 코드(예: KR, US, JP)", value="KR").upper().strip()
        lang = st.selectbox("언어", ["ko-KR", "en-US"], index=0)
        adult = st.checkbox("성인물 포함", value=False)

    st.markdown("### 심리 상태 체크")
    col1, col2 = st.columns(2)
    with col1:
        mood_val = st.slider("오늘 기분(-5=매우 다운, +5=매우 업)", -5, 5, 0)
        stress = st.slider("스트레스", 0, 10, 5)
        anxiety = st.slider("불안감", 0, 10, 4)
    with col2:
        focus = st.slider("집중력", 0, 10, 5)
        tone = st.radio("오늘 보고 싶은 톤", ["밝고 따뜻한", "강렬/짜릿한", "진지/사색"], index=0)
        include_tv = st.checkbox("시리즈도 포함", value=True)

    answers = {
        "오늘 기분": mood_val,
        "스트레스": stress,
        "불안감": anxiety,
        "집중력": focus,
        "보고 싶은 톤": tone,
    }

    if st.button("추천 받기"):
        if not TMDB_API_KEY:
            st.error("TMDb API 키가 설정되지 않았습니다. .env 파일에 TMDB_API_KEY를 넣어주세요.")
            st.stop()

        mood, scores = infer_mood(answers)
        st.success(f"지금 무드: {mood}")

        pref = MOOD_MAP.get(mood)
        sort_by = pref["sort"]

        # 영화 가져오기
        movies = discover_titles("movie", region=region, lang=lang, with_genres=pref["genres_movie"], sort_by=sort_by)
        if not movies:  # fallback (장르 제한 해제)
            movies = discover_titles("movie", region=region, lang=lang, sort_by="popularity.desc")

        # 시리즈 가져오기
        shows = []
        if include_tv:
            shows = discover_titles("tv", region=region, lang=lang, with_genres=pref["genres_tv"], sort_by=sort_by)
            if not shows:
                shows = discover_titles("tv", region=region, lang=lang, sort_by="popularity.desc")

        results = [("movie", m) for m in movies[:10]] + [("tv", t) for t in shows[:10]]

        if not results:
            st.warning("추천할 작품을 찾지 못했습니다. 국가 코드를 바꿔보세요!")
            st.stop()

        st.markdown("### 추천 결과")
        for ctype, item in results:
            colA, colB = st.columns([1, 2])
            with colA:
                poster = item.get("poster_path")
                if poster:
                    st.image(IMG_BASE + poster, use_column_width=True)
                else:
                    st.write("포스터 없음")
            with colB:
                title = item.get("title") if ctype == "movie" else item.get("name")
                overview = item.get("overview") or "줄거리 정보가 없습니다."
                vote = item.get("vote_average", 0)
                date = item.get("release_date") if ctype == "movie" else item.get("first_air_date")
                st.subheader(title)
                st.caption(f"{'영화' if ctype=='movie' else '시리즈'} | 공개일: {date or '정보 없음'} | 평점: {vote:.1f}")
                st.write(overview)

                with st.expander("출연/예고편"):
                    detail, cast, trailer_key = get_title_detail(ctype, item["id"], lang=lang)
                    if cast:
                        st.write("주요 출연: " + ", ".join([c["name"] for c in cast]))
                    if trailer_key:
                        st.video(f"https://www.youtube.com/watch?v={trailer_key}")

if __name__ == "__main__":
    main()
