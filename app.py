# MoodFlix: 심리 상태 기반 넷플릭스(Netflix) 추천 앱
# - TMDB API를 이용해 포스터/줄거리/출연진/트레일러를 가져옵니다.
# - "시청 제공사(Watch Providers)" 정보로 지역별 Netflix 제공 여부를 확인합니다.
# - 영화와 TV 시리즈 모두 지원, 어떤 입력 조합에도 동작.
# - 오류를 줄이기 위해 긴 설명은 주석(#)으로만 표기합니다.

import os
import random
import time
from typing import Dict, List, Tuple, Optional

import requests
import streamlit as st
from dotenv import load_dotenv

# 환경변수 로드 (.env 없으면 무시)
load_dotenv()

# -------------------------------------
# 기본 설정
# -------------------------------------
st.set_page_config(
    page_title="MoodFlix | 심리 상태 기반 넷플릭스 추천",
    page_icon="EMOJI_2",
    layout="wide",
)

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p/"

# Netflix provider id (TMDB 기준)
NETFLIX_PROVIDER_ID = 8

# === 함수들 시작 ===
def get_api_key():
    k = st.session_state.get("TMDB_API_KEY")
    if not k:
        k = st.secrets.get("TMDB_API_KEY", None) if hasattr(st, "secrets") else None
    if not k:
        k = os.getenv("TMDB_API_KEY")
    return (k or "").strip()

def tmdb_get(path, params=None, api_key=None, lang="ko-KR"):
    if params is None:
        params = {}
    params["api_key"] = api_key
    params["language"] = lang
    r = requests.get(f"{TMDB_BASE}{path}", params=params, timeout=15)
    if r.status_code == 401:
        st.error("TMDb API 키가 유효하지 않아. 키를 다시 확인해줘.")
        st.stop()
    r.raise_for_status()
    return r.json()

# -------------------------------------
# 유틸: TMDB 요청
# -------------------------------------

def tmdb_request(endpoint: str, params: Optional[dict] = None) -> dict:
    """TMDB API 호출 헬퍼 (오류 내성 포함)."""
    url = f"{TMDB_BASE}/{endpoint.lstrip('/')}"
    headers = {"accept": "application/json"}
    params = params.copy() if params else {}
    params["api_key"] = st.session_state.get("TMDB_API_KEY", os.getenv("TMDB_API_KEY", ""))

    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.warning(f"TMDB 요청 오류: {endpoint} → {e}")
        return {}

@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_genre_maps() -> Tuple[Dict[int, str], Dict[int, str]]:
    movie = tmdb_request("genre/movie/list", {"language": "ko-KR"}).get("genres", [])
    tv = tmdb_request("genre/tv/list", {"language": "ko-KR"}).get("genres", [])
    return (
        {g["id"]: g["name"] for g in movie},
        {g["id"]: g["name"] for g in tv},
    )

@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_configuration() -> dict:
    return tmdb_request("configuration")

@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_provider_regions() -> List[str]:
    data = tmdb_request("watch/providers/regions").get("results", [])
    # ISO 3166-1 code 목록
    return sorted({x.get("iso_3166_1", "") for x in data if x.get("iso_3166_1")})

# -------------------------------------
# 심리 → 추천 파이프라인 설정
# -------------------------------------

MOODS = [
    "불안", "우울", "스트레스", "외로움", "분노", "무기력",
    "행복", "호
