# app.py
import os
import time
from typing import Optional, List, Dict, Any

import requests
import streamlit as st

# 페이지 기본 설정
st.set_page_config(page_title="TMDB Regions Demo", page_icon="🎬", layout="centered")

# TMDB 기본값
TMDB_BASE = "https://api.themoviedb.org/3"
DEFAULT_LANG = "ko-KR"

# ========================= ADI(API) 키(하드코드 기본값) =========================
# 여기 값으로 앱 시작 시 자동 입력돼. 배포/공유 시엔 secrets 또는 환경변수 사용 추천.
HARDCODED_TMDB_V3_KEY = "98eaf6d20dad569fcbf4dd59ab8cc47e"
HARDCODED_TMDB_V4_TOKEN = ""  # 있으면 여기에 넣어두면 시작 시 자동 입력됨
# ============================================================================


# === 초기 세션 기본값 주입(앱 실행 시 자동 채움) ===
def init_session_defaults():
    # v3 API Key
    if "TMDB_API_KEY" not in st.session_state:
        # 우선순위: 하드코드 -> secrets -> 환경변수
        v3 = HARDCODED_TMDB_V3_KEY or ""
        if not v3 and hasattr(st, "secrets"):
            v3 = st.secrets.get("TMDB_API_KEY", "") or ""
        if not v3:
            v3 = os.getenv("TMDB_API_KEY", "") or ""
        st.session_state["TMDB_API_KEY"] = v3.strip()

    # v4 Access Token
    if "TMDB_ACCESS_TOKEN" not in st.session_state:
        # 우선순위: 하드코드 -> secrets -> 환경변수
        v4 = HARDCODED_TMDB_V4_TOKEN or ""
        if not v4 and hasattr(st, "secrets"):
            v4 = st.secrets.get("TMDB_ACCESS_TOKEN", "") or ""
        if not v4:
            v4 = os.getenv("TMDB_ACCESS_TOKEN", "") or ""
        st.session_state["TMDB_ACCESS_TOKEN"] = v4.strip()

    if "APP_LANG" not in st.session_state:
        st.session_state["APP_LANG"] = DEFAULT_LANG

init_session_defaults()


# === 키/토큰 읽기 ===
def get_api_key() -> str:
    return (st.session_state.get("TMDB_API_KEY") or "").strip()

def get_access_token() -> str:
    return (st.session_state.get("TMDB_ACCESS_TOKEN") or "").strip()


# === 요청 헬퍼(안전판) ===
def _is_json_response(r: requests.Response) -> bool:
    ct = (r.headers.get("content-type") or "").lower()
    return "application/json" in ct

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
    v4 = get_access_token()
    v3 = get_api_key()
    if v4:
        return params  # v4 사용 시 api_key 추가 금지
    if v3:
        p = params.copy()
        p["api_key"] = v3
        return p
    return params

def tmdb_request(
    endpoint: str,
    params: Optional[dict] = None,
    lang: str = DEFAULT_LANG,
    timeout: int = 15,
    retries: int = 2,
    backoff_sec: float = 0.6,
) -> dict:
    """
    TMDB API 호출(안전판).
    - v4 토큰 있으면 헤더 인증, 없으면 v3 쿼리 인증
    - 항상 text로 받은 후 JSON 여부 확인 후 파싱
    - JSON 아님/빈 응답이면 {} 반환
    - 429/5xx 재시도
    """
    url = f"{TMDB_BASE}/{endpoint.lstrip('/')}"
    params = (params or {}).copy()
    if "language" not in params and lang:
        params["language"] = lang

    headers = _build_headers()
    params = _attach_auth_params(params)

    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=timeout)
            raw = r.text or ""

            if r.status_code in (429, 500, 502, 503, 504):
                if attempt < retries:
                    st.info(f"TMDB {r.status_code} 재시도 중... ({attempt+1}/{retries})")
                    time.sleep(backoff_sec * (attempt + 1))
                    continue

            if not r.ok:
                if r.status_code == 401:
                    st.warning("TMDb 인증 실패(401). 키/토큰을 확인해줘.")
                else:
                    st.warning(f"TMDB {r.status_code} {r.reason} @ {endpoint} → {raw[:200]}")
                return {}

            if not raw.strip():
                return {}

            if not _is_json_response(r):
                st.warning(f"JSON 아님 @ {endpoint} → {raw[:120]}")
                return {}

            try:
                return r.json()
            except ValueError:
                st.warning(f"JSON 파싱 실패 @ {endpoint} → {raw[:120]}")
                return {}

        except requests.exceptions.RequestException as e:
            if attempt < retries:
                time.sleep(backoff_sec * (attempt + 1))
                continue
            st.warning(f"TMDB 요청 오류 @ {endpoint} → {e}")
            return {}

    return {}


# === 캐시 무효화를 위한 인증 지문 ===
def auth_fingerprint() -> str:
    return f"{len(get_api_key())}-{len(get_access_token())}"


# === 기능 함수들 ===
@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_provider_regions(_fp: str, lang: str = "en-US") -> List[str]:
    """
    시청 제공자 지역 코드 목록(ISO 3166-1).
    - _fp: 인증 지문(캐시 무효화용)
    """
    data = tmdb_request("watch/providers/regions", params={"language": lang})
    results = data.get("results") if isinstance(data, dict) else None
    if not results or not isinstance(results, list):
        return []
    codes = {x.get("iso_3166_1", "") for x in results if isinstance(x, dict) and x.get("iso_3166_1")}
    return sorted(codes)

@st.cache_data(show_spinner=False, ttl=30 * 60)
def tmdb_healthcheck_cached(_fp: str) -> dict:
    return tmdb_request("configuration/countries", params={"language": "en-US"})


# === 사이드바 UI(앱 시작 시 자동으로 값 채워짐) ===
with st.sidebar:
    st.header("TMDB 설정")

    api_key_input = st.text_input(
        "TMDB API Key (v3)",
        value=st.session_state.get("TMDB_API_KEY", ""),
        type="password",  # 화면에서 키는 가려짐
        help="v3 키. 배포 시엔 하드코드 대신 secrets/환경변수 사용 권장.",
    )

    access_token_input = st.text_input(
        "TMDB Access Token (v4 Bearer)",
        value=st.session_state.get("TMDB_ACCESS_TOKEN", ""),
        type="password",
        help="v4 토큰이 있으면 v4 우선, v3와 동시에 쓰지 않아.",
    )

    lang_input = st.selectbox(
        "기본 언어",
        options=["ko-KR", "en-US"],
        index=0 if st.session_state.get("APP_LANG", DEFAULT_LANG) == "ko-KR" else 1,
    )

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("저장/적용"):
            st.session_state["TMDB_API_KEY"] = (api_key_input or "").strip()
            st.session_state["TMDB_ACCESS_TOKEN"] = (access_token_input or "").strip()
            st.session_state["APP_LANG"] = lang_input
            st.cache_data.clear()
            st.success("저장 완료. 아래 기능에 즉시 반영됐어.")

    with col_b:
        st.caption(
            f"상태: v3={len(st.session_state.get('TMDB_API_KEY',''))}자, "
            f"v4={len(st.session_state.get('TMDB_ACCESS_TOKEN',''))}자"
        )


# === 메인 영역 ===
st.title("🎬 TMDB Regions Demo")
st.write("앱 켜면 네 ADI(API) 키가 자동으로 입력돼. 필요하면 사이드바에서 수정하고 저장하면 즉시 반영!")

with st.expander("연결 상태 점검(Health Check)", expanded=True):
    hc = tmdb_healthcheck_cached(auth_fingerprint())
    if hc:
        st.success("TMDB 연결 OK (configuration/countries)")
        st.caption(f"응답 국가 수: {len(hc) if isinstance(hc, list) else 'N/A'}")
    else:
        st.warning("TMDB 연결 불가 또는 빈 응답. 키/토큰/네트워크를 확인해줘.")

st.divider()

st.subheader("Watch Provider 지역 코드 불러오기")
col1, col2 = st.columns([1, 3])
with col1:
    use_lang = st.selectbox("조회 언어", ["en-US", "ko-KR"], index=0, help="지역 코드는 en-US가 가장 안정적이야.")
with col2:
    if st.button("지역 코드 가져오기"):
        regions = get_provider_regions(auth_fingerprint(), lang=use_lang)
        if regions:
            st.success(f"총 {len(regions)}개 지역 코드")
            st.write(regions)
        else:
            st.warning("가져온 지역 코드가 없어. 인증/네트워크 또는 레이트 리밋을 확인해줘.")
        
