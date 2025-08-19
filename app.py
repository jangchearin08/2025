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
    # === 끝 ===

if __name__ == "__main__":
    main()
except Exception:
    pass

TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p/"

# Netflix provider id (TMDB 기준)
NETFLIX_PROVIDER_ID = 8

# -------------------------------------
# 유틸: TMDB 요청
# -------------------------------------

def tmdb_request(endpoint: str, params: Optional[dict] = None) -> dict:
    """TMDB API 호출 헬퍼 (오류 내성 포함)."""
    url = f"{TMDB_BASE}/{endpoint.lstrip('/')}"
    headers = {"accept": "application/json"}
    params = params.copy() if params else {}
    params["api_key"] = st.session_state.get("TMDB_API_KEY", TMDB_API_KEY)

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
    "행복", "호기심", "설렘(로맨틱)", "두려움(스릴)", "위로/힐링", "몰입/도전"
]

# 각 심리에 연결할 장르/키워드 후보 (가중치 기반)
MOOD_TO_GENRES = {
    "불안": {"movie": [53, 9648], "tv": [80, 9648]},          # 스릴러, 미스터리 / 범죄
    "우울": {"movie": [18, 10749], "tv": [18]},               # 드라마, 로맨스
    "스트레스": {"movie": [35, 16], "tv": [35, 16]},          # 코미디, 애니
    "외로움": {"movie": [18, 10749], "tv": [18]},             # 드라마/로맨스
    "분노": {"movie": [28, 80], "tv": [10759, 80]},           # 액션, 범죄
    "무기력": {"movie": [12, 14, 878], "tv": [10765, 10759]},# 모험, 판타지, SF / Sci-Fi & Fantasy, 액션&모험
    "행복": {"movie": [35, 10402], "tv": [35]},              # 코미디, 음악
    "호기심": {"movie": [99, 36], "tv": [99, 36]},           # 다큐, 역사
    "설렘(로맨틱)": {"movie": [10749, 35], "tv": [10766, 35]},# 로맨스, 코미디(일일연속극 대체: Soap=10766)
    "두려움(스릴)": {"movie": [27, 53], "tv": [9648, 80]},     # 공포, 스릴러 / 미스터리
    "위로/힐링": {"movie": [16, 12, 10751], "tv": [16, 10751]},# 애니, 가족
    "몰입/도전": {"movie": [18, 28], "tv": [18, 10759]},      # 드라마, 액션&모험
}

# -------------------------------------
# TMDB 탐색/필터링
# -------------------------------------

@st.cache_data(show_spinner=False, ttl=60 * 30)
def discover_titles(kind: str, with_genres: List[int], page: int = 1, language: str = "ko-KR") -> List[dict]:
    """영화/TV discover 결과 반환."""
    assert kind in ("movie", "tv")
    endpoint = f"discover/{kind}"
    params = {
        "language": language,
        "sort_by": "popularity.desc",
        "include_adult": "false",
        "page": page,
    }
    if with_genres:
        params["with_genres"] = ",".join(map(str, with_genres))
    data = tmdb_request(endpoint, params)
    return data.get("results", [])

@st.cache_data(show_spinner=False, ttl=60 * 30)
def get_watch_providers(kind: str, tmdb_id: int) -> dict:
    return tmdb_request(f"{kind}/{tmdb_id}/watch/providers")

@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_credits(kind: str, tmdb_id: int) -> dict:
    return tmdb_request(f"{kind}/{tmdb_id}/credits", {"language": "ko-KR"})

@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_details(kind: str, tmdb_id: int) -> dict:
    return tmdb_request(f"{kind}/{tmdb_id}", {"language": "ko-KR"})

@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_videos(kind: str, tmdb_id: int) -> List[dict]:
    data = tmdb_request(f"{kind}/{tmdb_id}/videos", {"language": "ko-KR"})
    results = data.get("results", [])
    # 한글이 없으면 영어 트레일러라도 추가로 시도
    if not results:
        results = tmdb_request(f"{kind}/{tmdb_id}/videos", {"language": "en-US"}).get("results", [])
    return results

# -------------------------------------
# Netflix 제공 여부 확인
# -------------------------------------

def is_on_netflix(provider_data: dict, region: str) -> bool:
    if not provider_data:
        return False
    results = provider_data.get("results", {})
    if not results or region not in results:
        return False
    region_info = results.get(region, {})
    for key in ("flatrate", "ads", "buy", "rent"):
        offers = region_info.get(key) or []
        for o in offers:
            if o.get("provider_id") == NETFLIX_PROVIDER_ID:
                return True
    return False

# -------------------------------------
# 추천 로직
# -------------------------------------

def rank_and_pick(candidates: List[dict], k: int = 12) -> List[dict]:
    """평점/인기도를 혼합해 간단 랭킹 후 상위 k개 선택."""
    def score(x):
        return (x.get("vote_average", 0) * 0.6) + (x.get("popularity", 0) * 0.4)
    ranked = sorted(candidates, key=score, reverse=True)
    return ranked[:k]

def build_recommendations(
    moods: List[str],
    country: str,
    include_tv: bool,
    include_movie: bool,
    intensity: Dict[str, int],  # 각 무드 강도(1~5)
    allow_non_netflix: bool,
    pages: int = 3,
) -> List[Tuple[str, dict]]:
    random.seed(42)
    movie_genres_map, tv_genres_map = get_genre_maps()

    # 요청한 모든 경우 조합 반영: 무드별 장르 집합을 합산(강도 가중치)하여 우선순위 부여
    movie_genres_weight: Dict[int, int] = {}
    tv_genres_weight: Dict[int, int] = {}

    for m in moods:
        mapping = MOOD_TO_GENRES.get(m, {})
        if include_movie:
            for gid in mapping.get("movie", []):
                movie_genres_weight[gid] = movie_genres_weight.get(gid, 0) + max(1, intensity.get(m, 1))
        if include_tv:
            for gid in mapping.get("tv", []):
                tv_genres_weight[gid] = tv_genres_weight.get(gid, 0) + max(1, intensity.get(m, 1))

    def gather(kind: str, genre_weight: Dict[int, int]) -> List[dict]:
        if not genre_weight:
            return []
        # 가중치가 높은 장르부터 차례로 discover 호출
        ordered = [gid for gid, _ in sorted(genre_weight.items(), key=lambda kv: kv[1], reverse=True)]
        collected: List[dict] = []
        for gid in ordered:
            for p in range(1, pages + 1):
                items = discover_titles(kind, [gid], page=p)
                collected.extend(items)
        # 중복 제거 (id 기반)
        uniq = { (x.get("id")): x for x in collected }
        return list(uniq.values())

    all_candidates: List[Tuple[str, dict]] = []

    if include_movie:
        movies = gather("movie", movie_genres_weight)
        for m in rank_and_pick(movies, k=60):
            all_candidates.append(("movie", m))
    if include_tv:
        tvs = gather("tv", tv_genres_weight)
        for t in rank_and_pick(tvs, k=60):
            all_candidates.append(("tv", t))

    # Netflix 필터링
    filtered: List[Tuple[str, dict]] = []
    fallback: List[Tuple[str, dict]] = []
    for kind, item in all_candidates:
        providers = get_watch_providers(kind, item["id"]) or {}
        on_nf = is_on_netflix(providers, country)
        if on_nf:
            filtered.append((kind, item))
        else:
            fallback.append((kind, item))

    if not filtered and allow_non_netflix:
        filtered = fallback  # 넷플릭스 없으면 대체로 채우기

    # 최종 12~18개 정도 반환
    random.shuffle(filtered)
    return filtered[:18]

# -------------------------------------
# UI
# -------------------------------------

with st.sidebar:
    st.header("🔑 API & 환경 설정")
    api_in = st.text_input("TMDB API Key", value=TMDB_API_KEY, type="password", help=".env에 TMDB_API_KEY로 저장하거나 여기 입력")
    if api_in:
        st.session_state["TMDB_API_KEY"] = api_in

    regions = get_provider_regions()
    default_region = "KR" if "KR" in regions else (regions[0] if regions else "KR")
    country = st.selectbox("시청 국가 (Netflix 제공 지역)", options=regions or ["KR", "US"], index=(regions.index(default_region) if default_region in regions else 0))

    st.markdown("---")
    st.subheader("⚙️ 추천 옵션")
    include_movie = st.checkbox("영화 포함", value=True)
    include_tv = st.checkbox("TV 시리즈 포함", value=True)
    allow_non_netflix = st.checkbox("넷플릭스에 없으면 대체(비넷플릭스)도 허용", value=False)
    pages = st.slider("탐색 범위(깊이)", 1, 5, 3, help="클수록 더 많은 후보를 훑어 더 다양한 추천")

st.title("🎬 MoodFlix")
st.caption("나의 지금 심리 상태를 바탕으로 Netflix에서 볼만한 작품을 추천해드려요.")

st.markdown("""
### 🧠 지금 심리 체크
아래 문항을 선택하면 해당 무드(감정) 강도를 반영해 작품을 고릅니다. (모두 복수 선택 가능)
""")

cols = st.columns(4)
selected_moods: List[str] = []
intensity: Dict[str, int] = {}
for i, mood in enumerate(MOODS):
    with cols[i % 4]:
        on = st.toggle(f"{mood}", key=f"m_{i}")
        if on:
            selected_moods.append(mood)
            intensity[mood] = st.slider(f"{mood} 강도", 1, 5, 3, key=f"s_{i}")

# 모든 경우의 수: 아무것도 선택하지 않아도 동작하도록 기본값 제공
if not selected_moods:
    st.info("무드를 하나도 선택하지 않으셨어요. 기본 추천(지금 인기 콘텐츠)으로 보여드릴게요 ✨")
    selected_moods = ["행복", "호기심"]
    intensity = {"행복": 3, "호기심": 3}

run = st.button("🔍 추천 보기")

if run:
    if not (st.session_state.get("TMDB_API_KEY") or TMDB_API_KEY):
        st.error("TMDB API Key가 필요해요. 사이드바에 입력해주세요.")
        st.stop()

    with st.spinner("당신의 무드에 딱 맞는 작품을 찾는 중…"):
        recs = build_recommendations(
            moods=selected_moods,
            country=country,
            include_tv=include_tv,
            include_movie=include_movie,
            intensity=intensity,
            allow_non_netflix=allow_non_netflix,
            pages=pages,
        )

    if not recs:
        st.warning("조건에 맞는 작품을 찾지 못했어요. 옵션을 넓혀보거나 '대체 허용'을 켜보세요.")
    else:
        st.subheader("🎯 추천 결과")
        st.caption(f"선택 무드: {', '.join(selected_moods)} | 국가: {country} | 작품 수: {len(recs)}")

        # 카드 그리드
        ncol = 3
        rows = (len(recs) + ncol - 1) // ncol
        for r in range(rows):
            ccols = st.columns(ncol)
            for ci in range(ncol):
                idx = r * ncol + ci
                if idx >= len(recs):
                    continue
                kind, item = recs[idx]
                title = item.get("title") or item.get("name")
                poster_path = item.get("poster_path")
                vote = item.get("vote_average", 0)
                tmdb_id = item.get("id")

                with ccols[ci]:
                    with st.container(border=True):
                        # 포스터
                        if poster_path:
                            st.image(f"{TMDB_IMG}w500{poster_path}", use_column_width=True)
                        else:
                            st.write("(포스터 없음)")

                        st.markdown(f"#### {'🎞️' if kind=='movie' else '📺'} {title}")
                        st.caption(f"평점 ★ {vote:.1f} | TMDB ID: {tmdb_id}")

                        # 상세/출연진
                        details = get_details(kind, tmdb_id) or {}
                        overview = details.get("overview") or item.get("overview") or "줄거리 정보가 아직 없어요."
                        st.write(overview)

                        credits = get_credits(kind, tmdb_id) or {}
                        cast = credits.get("cast", [])
                        if cast:
                            top_cast = ", ".join([c.get("name", "") for c in cast[:5]])
                            st.caption(f"👥 출연: {top_cast}")

                        # 시청 제공사 표기
                        providers = get_watch_providers(kind, tmdb_id) or {}
                        on_nf = is_on_netflix(providers, country)
                        if on_nf:
                            st.success(f"✅ 이 작품은 {country} 지역 Netflix에서 제공 중일 가능성이 높아요.")
                        else:
                            st.warning("❌ 현재 지역 Netflix 제공 정보가 없어요 (TMDB 기준).")

                        # 트레일러 버튼
                        vids = [v for v in get_videos(kind, tmdb_id) if v.get("site") in ("YouTube", "Vimeo")]
                        if vids:
                            yt = next((v for v in vids if v.get("type") in ("Trailer", "Teaser")), vids[0])
                            key = yt.get("key")
                            site = yt.get("site")
                            if site == "YouTube" and key:
                                st.link_button("▶️ 트레일러 보기 (YouTube)", f"https://www.youtube.com/watch?v={key}")
                            elif site == "Vimeo" and key:
                                st.link_button("▶️ 트레일러 보기 (Vimeo)", f"https://vimeo.com/{key}")

                        # 세부 정보 토글
                        with st.expander("세부 정보"):
                            if kind == "movie":
                                runtime = details.get("runtime")
                                release = details.get("release_date")
                                genres = ", ".join([g.get("name") for g in details.get("genres", [])])
                                st.write(f"개봉: {release or '-'} | 상영시간: {runtime or '-'}분 | 장르: {genres or '-'}")
                            else:
                                seasons = details.get("number_of_seasons")
                                episodes = details.get("number_of_episodes")
                                first_air = details.get("first_air_date")
                                last_air = details.get("last_air_date")
                                genres = ", ".join([g.get("name") for g in details.get("genres", [])])
                                st.write(f"방영: {first_air or '-'} ~ {last_air or '-'} | 시즌: {seasons or '-'} | 에피소드: {episodes or '-'} | 장르: {genres or '-'}")

# 푸터
st.markdown("""
---
Made with ❤️ by MoodFlix · 데이터 출처: TMDB (The Movie Database)
""")
