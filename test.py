import streamlit as st
import requests
import random

st.set_page_config(page_title="심리 기반 영화 추천 🎬", page_icon="🎭")

st.title("🎬 내 마음을 위한 영화 추천기")
st.write("당신의 심리에 딱 맞는 영화를 찾아드릴게요 🍿")

# 🔑 본인 TMDB API 키 입력!
API_KEY = "YOUR_TMDB_API_KEY"
BASE_URL = "https://api.themoviedb.org/3"

# 기분 선택
mood = st.radio(
    "지금 기분은 어떤가요? 😌",
    ["행복 😊", "우울 😔", "스트레스 😵", "지루함 😐", "설렘 💖", "고독 🥀"]
)

# 장르 선택
genre = st.multiselect(
    "좋아하는 장르를 선택해주세요 🍿",
    ["로맨스 💕", "코미디 😂", "드라마 🎭", "스릴러 🔪", "SF 🚀", "애니메이션 🐭"]
)

# TMDb 장르 코드 매핑
genre_map = {
    "로맨스 💕": 10749,
    "코미디 😂": 35,
    "드라마 🎭": 18,
    "스릴러 🔪": 53,
    "SF 🚀": 878,
    "애니메이션 🐭": 16,
}

# 기분별 기본 장르 보정
mood_genre_map = {
    "행복 😊": [35, 10749],     # 코미디, 로맨스
    "우울 😔": [18, 35],        # 드라마, 코미디
    "스트레스 😵": [16, 35],    # 애니, 코미디
    "지루함 😐": [878, 53],     # SF, 스릴러
    "설렘 💖": [10749, 18],     # 로맨스, 드라마
    "고독 🥀": [18, 10749],     # 드라마, 로맨스
}

def get_movies(genre_ids, count=3):
    """장르 기반 영화 추천"""
    genre_param = ",".join(map(str, genre_ids))
    url = f"{BASE_URL}/discover/movie"
    params = {
        "api_key": API_KEY,
        "language": "ko-KR",
        "sort_by": "popularity.desc",
        "with_genres": genre_param,
        "page": random.randint(1, 5)  # 랜덤 페이지에서 뽑기
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        movies = response.json().get("results", [])
        return random.sample(movies, min(count, len(movies)))
    else:
        return []

def get_cast(movie_id):
    """출연 배우 불러오기"""
    url = f"{BASE_URL}/movie/{movie_id}/credits"
    params = {"api_key": API_KEY, "language": "ko-KR"}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        cast = response.json().get("cast", [])
        return [c["name"] for c in cast[:3]]  # 상위 3명
    return []

# 버튼 클릭 시 영화 추천
if st.button("영화 추천 받기 🎥"):
    # 선택한 장르 없으면 mood 기본 장르 사용
    if genre:
        genre_ids = [genre_map[g] for g in genre]
    else:
        genre_ids = mood_genre_map[mood]

    movies = get_movies(genre_ids, count=3)

    if movies:
        for movie in movies:
            title = movie["title"]
            overview = movie.get("overview", "줄거리 없음")
            poster = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}" if movie.get("poster_path") else None
            cast = get_cast(movie["id"])

            st.subheader(f"🎬 {title}")
            if poster:
                st.image(poster, width=250)
            st.write(f"**줄거리**: {overview}")
            if cast:
                st.write(f"👥 주요 출연진: {', '.join(cast)}")
            st.markdown("---")
    else:
        st.warning("😢 해당 조건에 맞는 영화를 찾을 수 없어요. 다른 기분이나 장르를 선택해보세요!")
