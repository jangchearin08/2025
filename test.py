import streamlit as st
import requests
import random

st.set_page_config(page_title="심리 기반 영화 추천 🎬", page_icon="🎭")

st.title("🎬 내 마음을 위한 영화 추천기")
st.write("당신의 심리에 딱 맞는 영화를 찾아드릴게요 🍿")

# 🔑 TMDB API 키 (없으면 빈 문자열 "" 그대로 두세요)
API_KEY = ""  # << 여기에 본인 TMDB 키를 넣으면 실시간 추천 가능
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

# 더미 데이터 (API 실패 시 fallback)
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
    "스트레스 😵": [
        {"title": "업", "overview": "하늘을 나는 집에서 시작되는 모험", "poster": "https://image.tmdb.org/t/p/w500/7sgpDeFT7GV1WvCmyEoG3O4Ocmk.jpg", "cast": ["에드워드 애즈너"]},
        {"title": "주토피아", "overview": "다양한 동물들의 도시에서 펼쳐지는 이야기", "poster": "https://image.tmdb.org/t/p/w500/sM33SANp9z6rXW8Itn7NnG1GOEs.jpg", "cast": ["지니퍼 굿윈", "제이슨 베이트먼"]},
        {"title": "박물관이 살아있다", "overview": "박물관 전시물이 살아난다!", "poster": "https://image.tmdb.org/t/p/w500/tYfijzolzgoMOtegh1Y7j2Enorg.jpg", "cast": ["벤 스틸러"]}
    ]
}

def get_movies_from_tmdb(genre_ids, count=3):
    """TMDB API에서 장르 기반 영화 추천"""
    try:
        genre_param = ",".join(map(str, genre_ids))
        url = f"{BASE_URL}/discover/movie"
        params = {
            "api_key": API_KEY,
            "language": "ko-KR",
            "sort_by": "popularity.desc",
            "wit
