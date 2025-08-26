# === TMDB API Key / Access Token ===
def get_api_key() -> str:
    # session_state > secrets > env 우선순위
    k = st.session_state.get("TMDB_API_KEY")
    if not k:
        k = st.secrets.get("TMDB_API_KEY", None) if hasattr(st, "secrets") else None
    if not k:
        k = os.getenv("TMDB_API_KEY")
    return (k or "").strip()

def get_access_token() -> str:
    # 선택: v4 Bearer 토큰을 쓰고 싶을 때
    t = st.session_state.get("TMDB_ACCESS_TOKEN")
    if not t:
        t = st.secrets.get("TMDB_ACCESS_TOKEN", None) if hasattr(st, "secrets") else None
    if not t:
        t = os.getenv("TMDB_ACCESS_TOKEN")
    return (t or "").strip()

# tmdb_get: UI에서 직접 키 테스트용(가벼운 확인 목적)
def tmdb_get(path: str, params: Optional[dict] = None, api_key: Optional[str] = None, lang: str = "ko-KR"):
    params = (params or {}).copy()
    k = (api_key or get_api_key())
    if not k:
        st.error("TMDb API Key가 비어 있어. 키를 먼저 입력/설정해줘.")
        st.stop()

    params["api_key"] = k
    params["language"] = lang

    url = f"{TMDB_BASE}{path}"
    try:
        r = requests.get(url, params=params, headers={"accept": "application/json"}, timeout=15)
        # 응답을 먼저 문자열로 받아서 상태/공백/HTML 등을 분기
        raw = r.text
        if not r.ok:
            # 401이면 키 문제 가능성 높음
            if r.status_code == 401:
                st.error("TMDb API 키가 유효하지 않아. 키를 다시 확인해줘.")
                st.stop()
            # 다른 에러는 본문 스니펫을 함께 보여줘
            raise requests.exceptions.HTTPError(f"TMDB {r.status_code} {r.reason}: {raw[:200]}")
        if not raw or raw.strip() == "":
            # 빈 응답 방지
            return {}
        try:
            return r.json()
        except ValueError:
            # JSON 파싱 실패 시 스니펫 표시
            raise ValueError(f"JSON 파싱 실패: 시작 120자 -> {raw[:120]}")
    except requests.exceptions.RequestException as e:
        # r가 생성되기 전 예외 대비해 e만 사용
        st.warning(f"TMDB 요청 오류: {path} → {e}")
        return {}

# === TMDB 요청 헬퍼 (캐시 + 견고한 파서) ===
@st.cache_data(show_spinner=False, ttl=60 * 30)
def tmdb_request(endpoint: str, params: Optional[dict] = None, lang: str = "ko-KR") -> dict:
    """
    TMDB API 호출 헬퍼.
    - v4 토큰이 있으면 Bearer 방식 사용
    - 없으면 v3 api_key 파라미터 사용
    - 응답은 먼저 text로 받고 상태/공백/JSON 파싱 실패를 분기
    """
    url = f"{TMDB_BASE}/{endpoint.lstrip('/')}"
    params = (params or {}).copy()
    headers = {"accept": "application/json"}

    v4 = get_access_token()
    v3 = get_api_key()

    if v4:
        headers["Authorization"] = f"Bearer {v4}"
        # v4 쓰면 api_key 파라미터는 절대 넣지 않음(중복 인증 금지)
    else:
        if not v3:
            st.error("TMDb 인증 정보가 없어. API Key 또는 v4 토큰 중 하나는 꼭 설정해야 해.")
            return {}
        params["api_key"] = v3

    # 언어 파라미터 기본값
    if "language" not in params and lang:
        params["language"] = lang

    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        raw = r.text

        if not r.ok:
            # 에러일 때도 본문 스니펫을 보여줘 원인 파악 쉽게
            st.warning(f"TMDB {r.status_code} {r.reason} @ {endpoint} → {raw[:200]}")
            return {}

        if not raw or raw.strip() == "":
            # 204 또는 공백 응답 대비
            return {}

        try:
            return r.json()
        except ValueError:
            st.warning(f"JSON 파싱 실패 @ {endpoint} → {raw[:120]}")
            return {}
    except requests.exceptions.RequestException as e:
        st.warning(f"TMDB 요청 오류 @ {endpoint} → {e}")
        return {}

@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_provider_regions() -> List[str]:
    """
    시청 제공자(Watch Providers) 지역 코드 목록(ISO 3166-1) 반환.
    - 응답이 빈 값/HTML이어도 안전하게 처리
    - 중복 제거 후 정렬
    """
    data = tmdb_request("watch/providers/regions", params={"language": "en-US"})  # 언어 영향 최소화
    results = data.get("results") if isinstance(data, dict) else None
    if not results or not isinstance(results, list):
        return []
    codes = {x.get("iso_3166_1", "") for x in results if isinstance(x, dict) and x.get("iso_3166_1")}
    return sorted(codes)
