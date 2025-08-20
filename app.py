import os
import random
import time
from typing import Dict, List, Tuple, Optional

import requests
import streamlit as st
from dotenv import load_dotenv

# -------------------------------------
# 기본 설정
# -------------------------------------
st.set_page_config(
    page_title="MoodFlix | 심리 상태 기반 넷플릭스 추천",
    page_icon="🎬",
    layout="wide",
)

# 환경변수 로드 (.env 없으면 무시)
try:
    load_dotenv()
    # app.py
import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

TMDB_BASE = "https://api.themoviedb.org/3"

# === 여기부터 붙여넣기 (함수들) ===
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

def sidebar_ui():
    st.sidebar.subheader("설정")
    api_key_input = st.sidebar.text_input(
        "TMDb API Key",
        value=st.session_state.get("TMDB_API_KEY", ""),
        type="password",
        help="여기 입력하거나 secrets/.env로도 설정 가능"
    )
    if api_key_input:
        st.session_state["TMDB_API_KEY"] = api_key_input.strip()

    if st.sidebar.button("키 확인"):
        key = get_api_key()
        if not key:
            st.sidebar.warning("키가 비어 있어.")
        else:
            try:
                ping = requests.get(f"{TMDB_BASE}/configuration", params={"api_key": key}, timeout=10)
                st.sidebar.success("키 정상!" if ping.status_code == 200 else f"실패: {ping.status_code}")
            except Exception as e:
                st.sidebar.error(f"오류: {e}")
# === 여기까지 함수들 ===

def main():
    st.set_page_config(page_title="넷플릭스 추천", page_icon="🎬", layout="wide")
    st.title("넷플릭스 기반 심리-무드 추천 🎬")

    # 사이드바 먼저
    sidebar_ui()

    # 여기서 키 확보
    TMDB_API_KEY = get_api_key()
    if not TMDB_API_KEY:
        st.warning("TMDB API Key가 필요해. 사이드바에 입력하거나 secrets/.env로 설정해줘.")
        st.stop()

    # === 여기 아래에 네가 만든 추천 로직 그대로 ===
    # 예: discover 호출, 무드 계산, 결과 렌더링 등
    # data = tmdb_get("/discover/movie", {"with_watch_providers": 8, "watch_region": "KR"}, api_key=TMDB_API_KEY)
    # st.write(data)
