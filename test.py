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

# 4) 무드-장르/키워드 매핑
MOOD_MAP = {
    "위로가 필요해": {
        "genres_movie": [35, 10749, 16],  # Comedy, Romance, Animation
        "genres_tv": [18, 35],            # Drama, Comedy
        "keywords": [],
        "sort": "popularity.desc"
    },
    "카타르시스/스트레스 해소": {
        "genres_movie": [28, 53, 80],     # Action, Thriller, Crime
        "genres_tv": [10759, 80, 9648],   # Action & Adventure, Crime, Mystery
        "keywords": [],
        "sort": "vote_average.desc"
    },
    "불안이 커": {
        "genres_movie": [18, 10751],      # Drama, Family
        "genres_tv": [18, 10751],         # Drama, Family
        "keywords": [],
        "sort": "popularity.desc"
    },
    "무기력/번아웃": {
        "genres_movie": [99, 10402, 18],  # Documentary, Music, Drama
        "genres_tv": [99, 18],            # Documentary, Drama
        "keywords": [],
        "sort": "popularity.desc"
    },
    "설렘/두근거림": {
        "genres_movie": [10749, 35],
        "genres_tv": [18, 35, 10749],
        "keywords": [],
        "sort": "popularity.desc"
    },
    "깊게 몰입하고 싶어": {
        "genres_movie": [9648, 878, 18],  # Mystery, Sci-Fi, Drama
        "genres_tv": [9648, 18, 80],
        "keywords": [],
        "sort": "vote_average.desc"
    },
}

# 5) TMDb Discover로 넷플릭스 제공작 가져오기
def discover_titles(content_type, region="KR", lang="ko-KR", with_genres=None, sort_by="popularity.desc", page=1):
    # content_type: "movie" or "tv"
    path = f"/discover/{content_type}"
    params = {
        "with_watch_providers": NETFLIX_PROVIDER_ID,  # 넷플릭스
        "watch_region": region,
        "sort_by": sort_by,
        "include_adult": "false",
        "page": page,
        "language": lang,
        "with_original_language": None,  # 필요 시 제한
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

# 7) 무드 스코어링(간단 문항 → 대표 무드)
def infer_mood(answers):
    # answers: dict
    # 간단한 규칙 기반
    scores = {
        "위로가 필요해": 0,
        "카타르시스/스트레스 해소": 0,
        "불안이 커": 0,
        "무기력/번아웃": 0,
        "설렘/두근거림": 0,
        "깊게 몰입하고 싶어": 0,
    }
    # 문항 가중치
    if answers["오늘 기분"]:  # -5~+5
        if answers["오늘 기분"] <= -2:
            scores["위로가 필요해"] += 2
            scores["무기력/번아웃"] += 1
        elif answers["आज 기분"] if False else False:  # guard (무시)
            pass
        elif answers["오늘 기분"] >= 2:
            scores["설렘/두근거림"] += 2
    if answers["스트레스"]:  # 0~10
        if answers["스트레스"] >= 7:
            scores["카타르시스/스트레스 해소"] += 2
            scores["깊게 몰입하고 싶어"] += 1
    if answers["불안감"]:  # 0~10
        if answers["불안감"] >= 6:
            scores["불안이 커"] += 2
    if answers["집중력"]:  # 0~10
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

    # 최고 점수 무드 선택(동점 시 임의 선택)
    mood = max(scores, key=scores.get)
    return mood, scores

# 8) Streamlit UI
def main():
    st.set_page_config(page_title="심리-무드 기반 넷플릭스 추천", page_icon="🎬", layout="wide")
    st.title("지금 마음에 맞는 넷플릭스 추천 🎬")
    st.caption("너의 현재 심리 상태를 가볍게 진단하고, 그 무드에 맞는 영화/시리즈를 골라줄게.")

    with st.sidebar:
        st.subheader("환경 설정")
        region = st.text_input("국가 코드(예: KR, US, JP)", value="KR").upper().strip()
        lang = st.selectbox("언어", ["ko-KR", "en-US"], index=0)
        adult = st.checkbox("성인물 포함", value=False)
        st.caption("국가 코드는 넷플릭스 제공 작품 필터에 바로 반영돼.")

    st.markdown("### 심리 상태 체크")
    col1, col2 = st.columns(2)
    with col1:
        mood_val = st.slider("오늘 기분(-5=매우 다운, +5=매우 업)", -5, 5, 0)
        stress = st.slider("스트레스", 0, 10, 5)
        anxiety = st.slider("불안감", 0, 10, 4)
    with col2:
        focus = st.slider("집중력", 0, 10, 5)
        tone = st.radio("오늘 보고 싶은 톤", ["밝고 따뜻한", "강렬/짜릿한", "진지/사색"], index=0)
        include_tv = st.checkbox("시리즈도 추천에 포함", value=True)

    answers = {
        "오늘 기분": mood_val,
        "스트레스": stress,
        "불안감": anxiety,
        "집중력": focus,
        "보고 싶은 톤": tone,
    }

    if st.button("추천 받기"):
        if not TMDB_API_KEY:
            st.error("TMDb API 키가 설정되지 않았어. .env 파일에 TMDB_API_KEY를 넣어줘.")
            st.stop()

        mood, scores = infer_mood(answers)
        st.success(f"지금 무드: {mood}")
        with st.expander("무드 스코어 보기", expanded=False):
            st.write(scores)

        pref = MOOD_MAP.get(mood, MOOD_MAP["위로가 필요해"])
        sort_by = pref["sort"]
        adult_flag = "true" if adult else "false"

        # Discover 영화
        movies = discover_titles(
            "movie",
            region=region,
            lang=lang,
            with_genres=pref["genres_movie"],
            sort_by=sort_by,
            page=1
        )
        # 성인물 필터
        movies = [m for m in movies if not m.get("adult")]

        # Discover TV (옵션)
        shows = []
        if include_tv:
            shows = discover_titles(
                "tv",
                region=region,
                lang=lang,
                with_genres=pref["genres_tv"],
                sort_by=sort_by,
                page=1
            )

        # 후보 섞고 상위 N
        results = []
        for m in movies[:10]:
            results.append(("movie", m))
        for t in shows[:10]:
            results.append(("tv", t))

        if not results:
            st.warning("해당 무드/지역에서 넷플릭스 후보가 부족해. 무드 조건을 살짝 완화해서 다시 시도해볼래?")
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
                overview = item.get("overview") or "줄거리 정보가 부족해."
                vote = item.get("vote_average", 0)
                date = item.get("release_date") if ctype == "movie" else item.get("first_air_date")
                st.subheader(f"{title}")
                st.caption(f"형식: {('영화' if ctype=='movie' else '시리즈')} | 공개일: {date or '정보 없음'} | 평점: {vote:.1f}")
                st.write(overview)

                with st.expander("등장인물/예고편 자세히"):
                    detail, cast, trailer_key = get_title_detail(ctype, item["id"], lang=lang)
                    if cast:
                        cast_names = ", ".join([c["name"] for c in cast if c.get("name")])
                        st.write(f"주요 출연: {cast_names}")
                    else:
                        st.write("출연 정보 없음")

                    if trailer_key:
                        st.video(f"https://www.youtube.com/watch?v={trailer_key}")
                    else:
                        st.write("예고편 영상 없음")

        st.info("팁: 국가 코드를 바꾸면(예: US ↔ KR) 넷플릭스 제공작이 달라져. 무드도 다시 조정해봐.")

if __name__ == "__main__":
    main()
