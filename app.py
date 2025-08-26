import os
from typing import Optional, List, Dict, Any
import time

import requests
import streamlit as st

# TMDB 기본값
TMDB_BASE = "https://api.themoviedb.org/3"
DEFAULT_LANG = "ko-KR"

# === TMDB API Key / Access Token ===
def get_api_key() -> str:
    # session_state > secrets > env 우선순위
    k = st.session_state.get("TMDB_API_KEY")
    if not k and hasattr(st, "secrets"):
        k = st.secrets.get("TMDB_API_KEY", None)
    if not k:
        k = os.getenv("TMDB_API_KEY")
    return (k or "").strip()

def get_access_token() -> str:
    # v4 Bearer 토큰
    t = st.session_state.get("TMDB_ACCESS_TOKEN")
    if not t and hasattr(st, "secrets"):
        t = st.secrets.get("TMDB_ACCESS_TOKEN", None)
    if not t:
        t = os.getenv("TMDB_ACCESS_TOKEN")
    return (t or "").strip()


# === 공통 요청 헬퍼: 예외 안 던지고, 안전하게 {} 반환 ===
def _is_json_response(r: requests.Response) -> bool:
    ct = r.headers.get("content-type", "")
    return "application/json" in ct.lower()

def _build_headers() -> Dict[str, str]:
    headers = {
        "accept": "application/json",
        "User-Agent": "tmdb-client/1.0 (+streamlit)",
    }
    v4 = get_access_token()
    if v4:
        headers["Authorization"] = f"Bearer {v4}"
    return headers

def _attach_auth_params(params: Dict[str, Any]) -> Dict[str, Any]:
    # v4 있으면 헤더 인증, v3 없으면 쿼리 인증
    v4 = get_access_token()
    v3 = get_api_key()
    if v4:
        # v4 쓰면 api_key 파라미터 절대 
