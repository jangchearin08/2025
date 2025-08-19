import streamlit as st
import requests
import random

st.set_page_config(page_title="심리 기반 영화 추천 🎬", page_icon="🎭")

st.title("🎬 내 마음을 위한 영화 추천기")
st.write("당신의 심리에 딱 맞는 영화를 찾아드릴게요 🍿")

# 🔑 TMDB API 키 (없으면 빈 문자열 "" 그대로 두세요)
API_KEY = ""  # 여기에 본인 TMDB 키 넣으면 실시간 추천 가능
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

# 기분별 기본 장르
mood_genre_map = {
    "행복 😊": [35, 10749],
    "우울 😔": [18, 35],
    "스트레스 😵": [16, 35],
    "지루함 😐": [878, 53],
    "설렘 💖": [10749, 18],
    "고독 🥀": [18, 10749],
}

# 🔹 더미 데이터 (API 키 없을 때 사용)
dummy_data = {
    "행복 😊": [
        {"title": "인사이드 아웃", "overview": "감정들이 주인공인 따뜻한 애니메이션", "poster": "https://image.tmdb.org/t/p/w500/aAmfIX3TT40zUHGcCKrlOZRKC7u.jpg", "cast": ["조이", "버럭이", "슬픔이"]},
        {"title": "라라랜드", "overview": "꿈과 사랑을 그린 뮤지컬 영화", "poster": "https://image.tmdb.org/t/p/w500/uDO8zWDhfWwoFdKS4fzkUJt0Rf0.jpg", "cast": ["라이언 고슬링", "엠마 스톤"]},
        {"title": "어바웃 타임", "overview": "시간여행으로 배우는 사랑과 가족 이야기", "poster": "https://image.tmdb.org/t/p/w500/iTQHKziZy9pAAY4hHEDCGPaOvFC.jpg", "cast": ["도널 글리슨", "레이첼 맥아담스"]}
    ],
    "우울 😔": [
        {"title": "월터의 상상은 현실이 된다", "overview": "평범한 직장인이 모험을 떠나는 이야기", "poster": "https://image.tmdb.org/t/p/w500/b9QJr2oblOu1grgOMUZF1xkUJdh.jpg", "cast": ["벤 스틸러"]},
        {"title": "포레스트 검프", "overview": "순수한 남자의 감동적인 삶", "poster": "https://image.tmdb.org/t/p/w500/saHP97rTPS5eLmrLQEcANmKrsFl.jpg", "cast": ["톰 행크스"]},
        {"title": "리틀 미스 선샤인", "overview": "엉뚱한 가족의 유쾌한 여정", "poster": "https://image.tmdb.org/t/p/w500/sySbO3WzUOXD3RtRKgYGpXn7Eu1.jpg", "cast": ["스티브 카렐"]}
    ],
    # 필요하다면 다른 mood도 채워 넣을 수 있음
}

def get_movies_from_tmdb(genre_ids, count=3):
    """TMDB API에서 장르 기반 영화 추천"""
    genre_param = ",".join(map(str, genre_ids))
    url = f"{BASE_URL}/discover/movie"
    params = {
        "api_key": API_KEY,
        "language": "ko-KR",
        "sort_by": "popularity.desc",
        "with_genres": genre_param,
        "page": random.randint(1, 5)
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        movies = response.json().get("results", [])
        return random.sample(movies, min(count, len(movies)))
    return []

def get_cast_from_tmdb(movie_id):
    """TMDB API로 출연 배우 불러오기"""
    url = f"{BASE_URL}/movie/{movie_id}/credits"
    params = {"api_key": API_KEY, "language": "ko-KR"}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        cast = response.json().get("cast", [])
        return [c["name"] for c in cast[:3]]
    return []

# 버튼 클릭 시 영화 추천
if st.button("영화 추천 받기 🎥"):
    if API_KEY:  # API 키 있으면 실시간 TMDB 사용
        if genre:
            genre_ids = [genre_map[g] for g in genre]
        else:
            genre_ids = mood_genre_map[mood]

        movies = get_movies_from_tmdb(genre_ids, count=3)

        if movies:
            for movie in movies:
                title = movie["title"]
                overview = movie.get("overview", "줄거리 없음")
                poster = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}" if movie.get("poster_path") else None
                cast = get_cast_from_tmdb(movie["id"])

                st.subheader(f"🎬 {title}")
                if poster:
                    st.image(poster, width=250)
                st.write(f"**줄거리**: {overview}")
                if cast:
                    st.write(f"👥 주요 출연진: {', '.join(cast)}")
                st.markdown("---")
        else:
            st.warning("😢 조건에 맞는 영화를 찾을 수 없어요.")
    else:  # API 키 없으면 더미 데이터 사용
        if mood in dummy_data:
            for movie in dummy_data[mood]:
                st.subheader(f"🎬 {movie['title']}")
                if movie["poster"]:
                    st.image(movie["poster"], width=250)
                st.write(f"**줄거리**: {movie['overview']}")
                st.write(f"👥 주요 출연진: {', '.join(movie['cast'])}")
                st.markdown("---")
        else:
            st.warning("😢 준비된 더미 데이터가 없어요. 다른 기분을 선택해보세요!")
