import streamlit as st
import requests
import random

st.set_page_config(page_title="심리 기반 영화 추천 🎬", page_icon="🎭")

st.title("🎬 내 마음을 위한 영화 추천기")
st.write("당신의 심리에 딱 맞는 영화를 찾아드릴게요 🍿")

# TMDb API 키 입력 (여기에 본인 키 입력!)
API_KEY = "YOUR_TMDB_API_KEY"
BASE_URL = "https://api.themoviedb.org/3"

# 심리 상태 선택
mood = st.radio(
    "지금 기분은 어떤가요? 😌",
    ["행복 😊", "우울 😔", "스트레스 😵", "지루함 😐", "설렘 💖", "고독 🥀"]
)

energy = st.selectbox(
    "오늘의 에너지 상태는 어떤가요? 🔋",
    ["넘치는 편 ⚡", "보통 🙂", "지친 상태 💤"]
)

genre = st.multiselect(
    "좋아하는 장르를 선택해주세요 🍿",
    ["로맨스 💕", "코미디 😂", "드라마 🎭", "스릴러 🔪", "SF 🚀", "애니메이션 🐭"]
)

# TMDb 장르 매핑
genre_map = {
    "로맨스 💕": 10749,
    "코미디 😂": 35,
    "드라마 🎭": 18,
    "스릴러 🔪": 53,
    "SF 🚀": 878,
    "애니메이션 🐭": 16,
}

# 기분별 추천 키워드 (검색용)
mood_keywords = {
    "행복 😊": "happy",
    "우울 😔": "healing",
    "스트레스 😵": "funny",
    "지루함 😐": "exciting",
    "설렘 💖": "romantic",
    "고독 🥀": "lonely"
}

def get_movies(genre_ids, keyword, count=3):
    """장르 + 키워드 기반 영화 검색"""
    genre_param = ",".join(map(str, genre_ids)) if genre_ids else ""
    url = f"{BASE_URL}/discover/movie"
    params = {
        "api_key": API_KEY,
        "language": "ko-KR",
        "sort_by": "popularity.desc",
        "with_genres": genre_param,
        "page": random.randint(1, 5)  # 랜덤 페이지에서 가져오기
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        movies = response.json().get("results", [])
        return random.sample(movies, min(count, len(movies)))
    return []

def get_cast(movie_id):
    """출연 배우 가져오기"""
    url = f"{BASE_URL}/movie/{movie_id}/credits"
    params = {"api_key": API_KEY, "language": "ko-KR"}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        cast = response.json().get("cast", [])
        return [c["name"] for c in cast[:3]]  # 주요 3명만
    return []

# 버튼 클릭 시 추천
if st.button("영화 추천 받기 🎥"):
    genre_ids = [genre_map[g] for g in genre] if genre else []
    keyword = mood_keywords[mood]

    movies = get_movies(genre_ids, keyword, count=3)

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
