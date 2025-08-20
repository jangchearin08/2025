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

# 환경변수 로드 (.env 파일이 없어도 오류 없이 지나감)
load_dotenv()

# -------------------------------------
# 전역 변수 설정 (함수 바깥에서 한 번만 초기화)
# -------------------------------------
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p/"
NETFLIX_PROVIDER_ID = 8 # Netflix provider id (TMDB 기준)

# -------------------------------------
# Streamlit 페이지 설정 (코드 맨 위에서 한 번만 호출)
# -------------------------------------
st.set_page_config(
    page_title="MoodFlix | 심리 상태 기반 넷플릭스 추천",
    page_icon="EMOJI_2",
    layout="wide",
)

# === TMDB API Key 관련 함수들 ===
def get_api_key():
    # session_state, secrets.toml, 환경변수(os.getenv) 순으로 API 키를 찾습니다.
    # 사용자가 직접 입력한 키가 가장 우선시됩니다.
    k = st.session_state.get("TMDB_API_KEY")
    if not k:
        k = st.secrets.get("TMDB_API_KEY", None) if hasattr(st, "secrets") else None
    if not k:
        k = os.getenv("TMDB_API_KEY")
    return (k or "").strip()

# tmdb_get 함수는 직접 UI에서 TMDB 키를 테스트할 때만 사용하며,
# 주된 TMDB 통신은 아래 tmdb_request 함수를 사용합니다.
def tmdb_get(path, params=None, api_key=None, lang="ko-KR"):
    if params is None:
        params = {}
    params["api_key"] = api_key # 요청에 API 키 포함
    params["language"] = lang # 요청 언어 설정
    try:
        r = requests.get(f"{TMDB_BASE}{path}", params=params, timeout=15)
        r.raise_for_status() # HTTP 오류가 발생하면 예외 발생
        return r.json()
    except requests.exceptions.RequestException as e:
        if r.status_code == 401:
            st.error("TMDb API 키가 유효하지 않아. 키를 다시 확인해줘.")
            st.stop() # 유효하지 않은 키는 앱 실행을 중단시킴
        else:
            raise e # 다른 종류의 요청 오류는 다시 발생시킴

# === TMDB 요청 헬퍼 함수 ===
@st.cache_data(show_spinner=False, ttl=60 * 30) # 데이터 캐싱으로 성능 향상
def tmdb_request(endpoint: str, params: Optional[dict] = None) -> dict:
    """TMDB API 호출 헬퍼 (오류 내성 포함)."""
    url = f"{TMDB_BASE}{endpoint}" # URL 경로 조합
    headers = {"accept": "application/json"} # JSON 응답 요청 헤더
    params = params.copy() if params else {} # 매개변수 딕셔너리 복사 (원본 유지)
    params["api_key"] = st.session_state.get("TMDB_API_KEY", os.getenv("TMDB_API_KEY", "")) # API 키 추가

    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        r.raise_for_status() # HTTP 오류 (4xx, 5xx) 발생 시 예외 처리
        return r.json()
    except requests.exceptions.RequestException as e:
        # TMDB 요청 시 발생할 수 있는 네트워크 또는 HTTP 오류를 처리
        st.warning(f"TMDB 요청 오류: {endpoint} → {e}")
        return {} # 오류 발생 시 빈 딕셔너리 반환하여 앱 중단 방지

@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_genre_maps() -> Tuple[Dict[int, str], Dict[int, str]]:
    # 영화 및 TV 프로그램 장르 목록 가져오기
    movie = tmdb_request("genre/movie/list", {"language": "ko-KR"}).get("genres", [])
    tv = tmdb_request("genre/tv/list", {"language": "ko-KR"}).get("genres", [])
    return (
        {g["id"]: g["name"] for g in movie},
        {g["id"]: g["name"] for g in tv},
    )

@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_configuration() -> dict:
    # TMDB API 설정 정보 가져오기 (예: 이미지 베이스 URL 등)
    return tmdb_request("configuration")

@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_provider_regions() -> List[str]:
    # 시청 제공자 서비스 가능한 지역 목록 가져오기
    data = tmdb_request("watch/providers/regions").get("results", [])
    # ISO 3166-1 코드 목록 정렬하여 반환
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
    assert kind in ("movie", "tv") # 유효한 kind 값인지 확인
    endpoint = f"discover/{kind}"
    params = {
        "language": language,
        "sort_by": "popularity.desc", # 인기도 기준으로 정렬
        "include_adult": "false", # 성인물 포함 여부
        "page": page,
    }
    if with_genres:
        params["with_genres"] = ",".join(map(str, with_genres)) # 장르 ID를 쉼표로 연결
    data = tmdb_request(endpoint, params)
    return data.get("results", [])

@st.cache_data(show_spinner=False, ttl=60 * 30)
def get_watch_providers(kind: str, tmdb_id: int) -> dict:
    # 특정 작품의 시청 제공자 정보 가져오기
    return tmdb_request(f"{kind}/{tmdb_id}/watch/providers")

@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_credits(kind: str, tmdb_id: int) -> dict:
    # 특정 작품의 출연진/제작진 정보 가져오기
    return tmdb_request(f"{kind}/{tmdb_id}/credits", {"language": "ko-KR"})

@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_details(kind: str, tmdb_id: int) -> dict:
    # 특정 작품의 상세 정보 가져오기
    return tmdb_request(f"{kind}/{tmdb_id}", {"language": "ko-KR"})

@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_videos(kind: str, tmdb_id: int) -> List[dict]:
    # 특정 작품의 비디오 (예고편 등) 정보 가져오기
    data = tmdb_request(f"{kind}/{tmdb_id}/videos", {"language": "ko-KR"})
    results = data.get("results", [])
    # 한글 트레일러가 없으면 영어 트레일러라도 시도
    if not results:
        results = tmdb_request(f"{kind}/{tmdb_id}/videos", {"language": "en-US"}).get("results", [])
    return results

# -------------------------------------
# Netflix 제공 여부 확인
# -------------------------------------

def is_on_netflix(provider_data: dict, region: str) -> bool:
    # 특정 지역에서 넷플릭스 제공 여부 확인
    if not provider_data:
        return False
    results = provider_data.get("results", {})
    if not results or region not in results:
        return False
    region_info = results.get(region, {})
    # 평생 이용, 광고 포함, 구매, 대여 등 모든 옵션에서 넷플릭스가 있는지 확인
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
    # 점수 계산식: 평점 60% + 인기도 40%
    def score(x):
        return (x.get("vote_average", 0) * 0.6) + (x.get("popularity", 0) * 0.4)
    ranked = sorted(candidates, key=score, reverse=True) # 계산된 점수 기준으로 내림차순 정렬
    return ranked[:k] # 상위 k개만 반환

def build_recommendations(
    moods: List[str],
    country: str,
    include_tv: bool,
    include_movie: bool,
    intensity: Dict[str, int],  # 각 무드 강도(1~5)
    allow_non_netflix: bool,
    pages: int = 3,
) -> List[Tuple[str, dict]]:
    random.seed(42) # 재현성을 위해 시드 고정
    movie_genres_map, tv_genres_map = get_genre_maps() # 장르 ID-이름 매핑 가져오기

    # 무드에 따른 장르별 가중치 계산
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
        # 가중치가 높은 장르부터 discover 호출하여 후보 목록 수집
        ordered = [gid for gid, _ in sorted(genre_weight.items(), key=lambda kv: kv[1], reverse=True)]
        collected: List[dict] = []
        for gid in ordered:
            for p in range(1, pages + 1):
                items = discover_titles(kind, [gid], page=p)
                collected.extend(items)
        # 중복된 항목 제거 (ID 기반)
        uniq = { (x.get("id")): x for x in collected }
        return list(uniq.values())

    all_candidates: List[Tuple[str, dict]] = []

    if include_movie:
        movies = gather("movie", movie_genres_weight)
        for m in rank_and_pick(movies, k=60): # 영화 후보군 수집
            all_candidates.append(("movie", m))
    if include_tv:
        tvs = gather("tv", tv_genres_weight)
        for t in rank_and_pick(tvs, k=60): # TV 프로그램 후보군 수집
            all_candidates.append(("tv", t))

    # Netflix 제공 여부 필터링
    filtered: List[Tuple[str, dict]] = []
    fallback: List[Tuple[str, dict]] = [] # 넷플릭스에 없지만 대체할 수 있는 목록
    for kind, item in all_candidates:
        providers = get_watch_providers(kind, item["id"]) or {}
        on_nf = is_on_netflix(providers, country)
        if on_nf:
            filtered.append((kind, item)) # 넷플릭스에서 제공하는 경우
        else:
            fallback.append((kind, item)) # 넷플릭스 외 다른 플랫폼에서 제공하거나 제공 정보가 없는 경우

    if not filtered and allow_non_netflix:
        filtered = fallback # 넷플릭스 추천이 없을 때 대체 허용 옵션이 켜져 있으면 대체 목록 사용

    # 최종 추천 목록을 랜덤하게 섞고 필요한 개수만큼 반환
    random.shuffle(filtered)
    return filtered[:18] # 최대 18개까지 추천

# -------------------------------------
# UI 렌더링을 위한 메인 함수
# -------------------------------------
def main():
    st.title("EMOJI_3 MoodFlix")
    st.caption("나의 지금 심리 상태를 바탕으로 Netflix에서 볼만한 작품을 추천해드려요.")

    # 사이드바 UI 구성
    with st.sidebar:
        st.header("EMOJI_4 API & 환경 설정")
        # TMDB API 키 입력 필드
        api_in = st.text_input(
            "TMDb API Key",
            value=get_api_key(), # 현재 설정된 키값으로 초기화
            type="password",
            help=".env 파일에 TMDB_API_KEY로 저장하거나 여기에 직접 입력해주세요."
        )
        if api_in:
            st.session_state["TMDB_API_KEY"] = api_in # 세션 상태에 키 저장

        # API 키 유효성 검사 및 앱 중단 로직
        current_api_key = get_api_key()
        if not current_api_key:
            st.warning("TMDB API Key가 필요해요. 사이드바에 입력하거나 secrets/.env로 설정해줘.")
            st.stop() # 키가 없으면 앱 실행을 중단하여 불필요한 오류 방지

        # TMDB 키 확인 버튼 (개발/디버깅용)
        if st.button("키 확인"):
            try:
                # 간단한 API 호출로 키 유효성 확인
                _ = tmdb_get("/configuration", api_key=current_api_key)
                st.success("키 정상 작동!")
            except Exception as e:
                st.error(f"키 확인 실패: {e}")

        # 시청 국가 선택 드롭다운
        regions = get_provider_regions()
        default_region = "KR" if "KR" in regions else (regions[0] if regions else "KR")
        country = st.selectbox(
            "시청 국가 (Netflix 제공 지역)",
            options=regions or ["KR", "US"], # 지역 목록이 없을 경우 기본값 제공
            index=(regions.index(default_region) if default_region in regions else 0)
        )

        st.markdown("---")
        st.subheader("⚙️ 추천 옵션")
        # 영화, TV 시리즈 포함 여부 체크박스
        include_movie = st.checkbox("영화 포함", value=True)
        include_tv = st.checkbox("TV 시리즈 포함", value=True)
        # 넷플릭스 외 작품 추천 허용 여부 체크박스
        allow_non_netflix = st.checkbox("넷플릭스에 없으면 대체(비넷플릭스)도 허용", value=False)
        # 탐색 범위 슬라이더 (추천 후보군 검색 깊이 조절)
        pages = st.slider("탐색 범위(깊이)", 1, 5, 3, help="클수록 더 많은 후보를 훑어 더 다양한 추천이 가능하지만 시간이 오래 걸릴 수 있습니다.")

    st.markdown("""
    ### EMOJI_5 지금 심리 체크
    아래 문항을 선택하면 해당 무드(감정) 강도를 반영해 작품을 고릅니다. (모두 복수 선택 가능)
    """)

    # 심리 상태 선택 및 강도 조절 UI
    cols = st.columns(4)
    selected_moods: List[str] = []
    intensity: Dict[str, int] = {}
    for i, mood in enumerate(MOODS):
        with cols[i % 4]: # 4열로 나누어 표시
            on = st.toggle(f"{mood}", key=f"m_{i}")
            if on:
                selected_moods.append(mood)
                intensity[mood] = st.slider(f"{mood} 강도", 1, 5, 3, key=f"s_{i}") # 각 심리별 강도 슬라이더

    # 선택된 무드가 없을 경우 기본값 제공 (인기 콘텐츠 추천)
    if not selected_moods:
        st.info("무드를 하나도 선택하지 않으셨어요. 기본 추천(지금 인기 콘텐츠)으로 보여드릴게요 ✨")
        selected_moods = ["행복", "호기심"] # 기본 무드 설정
        intensity = {"행복": 3, "호기심": 3} # 기본 강도 설정

    run = st.button("EMOJI_6 추천 보기") # 추천 실행 버튼

    # 추천 버튼 클릭 시 로직
    if run:
        # 스피너로 사용자에게 대기 메시지 표시
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

        # 추천 결과 출력
        if not recs:
            st.warning("조건에 맞는 작품을 찾지 못했어요. 옵션을 넓혀보거나 '대체 허용'을 켜보세요.")
        else:
            st.subheader("EMOJI_7 추천 결과")
            st.caption(f"선택 무드: {', '.join(selected_moods)} | 국가: {country} | 작품 수: {len(recs)}개")

            # 추천된 작품을 카드 형태로 그리드에 표시
            ncol = 3 # 한 줄에 표시할 카드 개수
            rows = (len(recs) + ncol - 1) // ncol # 필요한 줄 수 계산
            for r in range(rows):
                ccols = st.columns(ncol)
                for ci in range(ncol):
                    idx = r * ncol + ci
                    if idx >= len(recs):
                        continue # 모든 작품을 표시했으면 종료
                    kind, item = recs[idx] # 작품 종류와 상세 정보
                    title = item.get("title") or item.get("name") # 영화/TV 시리즈 제목
                    poster_path = item.get("poster_path")
                    vote = item.get("vote_average", 0)
                    tmdb_id = item.get("id")

                    with ccols[ci]: # 각 열(카드) 내부 UI 구성
                        with st.container(border=True): # 카드 경계선
                            # 포스터 이미지 표시
                            if poster_path:
                                st.image(f"{TMDB_IMG}w500{poster_path}", use_column_width=True)
                            else:
                                st.write("(포스터 없음)") # 포스터가 없을 경우 메시지

                            st.markdown(f"#### {'EMOJI_8' if kind=='movie' else 'EMOJI_9'} {title}") # 제목과 아이콘
                            st.caption(f"평점 ★ {vote:.1f} | TMDB ID: {tmdb_id}") # 평점 및 TMDB ID

                            # 상세 줄거리 표시
                            details = get_details(kind, tmdb_id) or {}
                            overview = details.get("overview") or item.get("overview") or "줄거리 정보가 아직 없어요."
                            st.write(overview)

                            # 출연진 정보 표시
                            credits = get_credits(kind, tmdb_id) or {}
                            cast = credits.get("cast", [])
                            if cast:
                                top_cast = ", ".join([c.get("name", "") for c in cast[:5]]) # 상위 5명
                                st.caption(f"EMOJI_10 출연: {top_cast}")

                            # 넷플릭스 제공 여부 표시
                            providers = get_watch_providers(kind, tmdb_id) or {}
                            on_nf = is_on_netflix(providers, country)
                            if on_nf:
                                st.success(f"✅ 이 작품은 {country} 지역 Netflix에서 제공 중일 가능성이 높아요.")
                            else:
                                st.warning("❌ 현재 지역 Netflix 제공 정보가 없어요 (TMDB 기준).")

                            # 트레일러 버튼
                            vids = [v for v in get_videos(kind, tmdb_id) if v.get("site") in ("YouTube", "Vimeo")]
                            if vids:
                                yt = next((v for v in vids if v.get("type") in ("Trailer", "Teaser")), vids[0]) # 예고편 우선, 없으면 첫번째 비디오
                                key = yt.get("key")
                                site = yt.get("site")
                                if site == "YouTube" and key:
                                    st.link_button("▶️ 트레일러 보기 (YouTube)", f"https://www.youtube.com/watch?v={key}")
                                elif site == "Vimeo" and key:
                                    st.link_button("▶️ 트레일러 보기 (Vimeo)", f"https://vimeo.com/{key}")

                            # 세부 정보 (장르, 상영 시간/시즌 등) 토글
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

# --- 앱 푸터 ---
st.markdown("""
---
Made with ❤️ by MoodFlix · 데이터 출처: TMDB (The Movie Database)
""")

# --- 앱 실행 진입점 ---
if __name__ == "__main__":
    try:
        main() # Streamlit 앱의 메인 함수 실행
    except Exception as e:
        # 예상치 못한 최상위 오류가 발생했을 경우 사용자에게 표시하고 앱 중단
        st.error(f"으악, 앱 실행 중 예상치 못한 오류가 발생했어: {e}")
        st.stop()
