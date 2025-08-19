# app.py
# 헤이 전용: 심리 프로파일링 + 영화 추천 Streamlit 앱
# 기능:
# - 다차원 심리 설문 → 점수화/해석
# - TMDB API로 포스터/출연/줄거리 불러오기 (실패 시 로컬 큐레이션)
# - 어떤 응답이든 항상 영화 추천 제공
# - 개인 북마크 / 검색 / 기록 관리

import os
import time
import textwrap
from datetime import datetime
import requests
import streamlit as st
from dotenv import load_dotenv

# -------------------------------
# 초기 설정
# -------------------------------
load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "").strip()

st.set_page_config(
    page_title="마음 필름 – 심리×영화 추천",
    page_icon="🎬",
    layout="wide",
)

# 세션 스토리지
if "responses" not in st.session_state:
    st.session_state.responses = {}
if "profile" not in st.session_state:
    st.session_state.profile = None
if "recommendations" not in st.session_state:
    st.session_state.recommendations = []
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []
if "history" not in st.session_state:
    st.session_state.history = []

# -------------------------------
# 유틸
# -------------------------------
def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))

def wrap(text, width=80):
    return "\n".join(textwrap.wrap(text, width=width))

@st.cache_data(show_spinner=False, ttl=3600)
def tmdb_search_movie(query, year=None, lang="ko-KR"):
    if not TMDB_API_KEY:
        return []
    url = "https://api.themoviedb.org/3/search/movie"
    params = {"api_key": TMDB_API_KEY, "query": query, "language": lang, "include_adult": "false"}
    if year:
        params["year"] = year
    r = requests.get(url, params=params, timeout=10)
    if r.status_code != 200:
        return []
    data = r.json().get("results", [])
    return data

@st.cache_data(show_spinner=False, ttl=3600)
def tmdb_movie_details(movie_id, lang="ko-KR"):
    if not TMDB_API_KEY:
        return {}
    url = f"https://api.themoviedb.org/3/movie/{movie_id}"
    params = {"api_key": TMDB_API_KEY, "language": lang, "append_to_response": "credits"}
    r = requests.get(url, params=params, timeout=10)
    if r.status_code != 200:
        return {}
    return r.json()

def fetch_movie_by_title(title, prefer_year=None):
    # 1) 검색
    results = tmdb_search_movie(title, year=prefer_year)
    if not results:
        results = tmdb_search_movie(title, year=None)
    if not results:
        return None

    # 2) 상세
    first = results[0]
    details = tmdb_movie_details(first["id"])
    if not details:
        return None

    # 3) 가공
    poster = details.get("poster_path")
    poster_url = f"https://image.tmdb.org/t/p/w500{poster}" if poster else None
    overview = details.get("overview") or first.get("overview") or "줄거리 정보가 준비 중이에요."
    cast_list = []
    credits = details.get("credits", {})
    cast = credits.get("cast", [])[:5]
    for c in cast:
        name = c.get("name")
        character = c.get("character")
        if name and character:
            cast_list.append(f"{name} ({character})")
        elif name:
            cast_list.append(name)

    year = (details.get("release_date") or "")[:4]
    return {
        "title": details.get("title") or first.get("title") or title,
        "year": year,
        "overview": overview.strip(),
        "poster_url": poster_url,
        "cast": cast_list,
        "tmdb_id": details.get("id"),
    }

# 로컬 백업 큐레이션 (API 없이도 항상 추천)
LOCAL_POOL = [
    {
        "title": "리틀 포레스트",
        "overview": "도시 생활에 지친 주인공이 고향으로 돌아와 사계절을 살며 자신을 회복해가는 이야기.",
        "poster_url": "https://mblogthumb-phinf.pstatic.net/20180303_71/with_at_1519992865993S0hgu_JPEG/IMG_0815.JPG?type=w800",
        "cast": ["김태리", "류준열", "진기주"],
        "year": "2018",
    },
    {
        "title": "월터의 상상은 현실이 된다",
        "overview": "평범했던 삶을 벗어나 모험을 떠나는 월터의 성장기.",
        "poster_url": "https://mblogthumb-phinf.pstatic.net/20140124_64/kiriko73_1390539319895cO0AS_JPEG/20140124_112705.jpg?type=w800",
        "cast": ["Ben Stiller", "Kristen Wiig"],
        "year": "2013",
    },
    {
        "title": "말할 수 없는 비밀",
        "overview": "피아노 선율 속 시간과 사랑을 넘나드는 청춘 로맨스.",
        "poster_url": "https://mblogthumb-phinf.pstatic.net/20160509_69/yhlee0109_1462798268309h2nU2_JPEG/1.jpg?type=w800",
        "cast": ["주걸륜", "계륜미"],
        "year": "2008",
    },
    {
        "title": "인사이드 아웃",
        "overview": "머릿속 감정들의 분투기. 감정을 이해하고 받아들이는 여정.",
        "poster_url": "https://mblogthumb-phinf.pstatic.net/20150714_43/dnjscl_1436862296523dZyXh_JPEG/insideoutposter.jpg?type=w800",
        "cast": ["Amy Poehler", "Phyllis Smith"],
        "year": "2015",
    },
]

# -------------------------------
# 설문 구성
# -------------------------------
# 각 문항은 1~5점 (전혀 아니다 ~ 매우 그렇다)
SECTIONS = {
    "감정 상태": [
        "요즘 이유 없이 마음이 가라앉는다.",
        "감정 기복이 눈에 띄게 크다.",
        "최근 일주일간 불안하거나 초조했다.",
        "잠들기 전 생각이 과하게 많아진다.",
    ],
    "스트레스 대처": [
        "압박이 와도 우선순위를 정하고 실행한다.",
        "감정이 올라오면 적절히 표현/해소한다.",
        "힘든 일을 작은 단위로 나눠 처리한다.",
        "도움이 필요할 때 주변에 요청한다.",
    ],
    "애착/관계": [
        "사람들과 있을 때도 묘한 외로움을 느낀다.",
        "거절이 어려워 내 마음을 미룬다.",
        "상대 반응에 과도하게 민감해진다.",
        "관계에서 경계(선)를 잘 지킨다.",
    ],
    "동기·회복탄력": [
        "일단 시작하면 끝까지 밀어붙이는 편이다.",
        "실패를 학습 기회로 삼는다.",
        "에너지 레벨을 스스로 관리한다.",
        "목표를 기록하고 점검한다.",
    ],
    "몰입·창의": [
        "시간 가는 줄 모르고 빠져드는 경험이 있다.",
        "문제를 새로운 방식으로 풀어보려 한다.",
        "혼자만의 상상/아이디어 시간이 필요하다.",
        "작은 디테일도 즐긴다.",
    ],
}

REVERSE_KEYS = {
    # 높을수록 건강한 척도로 뒤집기
    "스트레스 대처": [0, 1, 2, 3],
    "동기·회복탄력": [0, 1, 2, 3],
    "몰입·창의": [0, 1, 2, 3],
}
NEGATIVE_SECTIONS = ["감정 상태", "애착/관계"]  # 높을수록 어려움

def score_profile(responses):
    # 섹션별 평균(0~100 환산)
    section_scores = {}
    for sec, items in SECTIONS.items():
        vals = []
        for i in range(len(items)):
            key = f"{sec}_{i}"
            val = responses.get(key, 3)
            # 역채점
            if sec in REVERSE_KEYS and i in REVERSE_KEYS[sec]:
                # 긍정 문항: 1(낮음)~5(높음) 그대로
                # 이미 긍정이므로 뒤집지 않음
                pass
            vals.append(val)
        avg = sum(vals) / max(1, len(vals))
        pct = clamp((avg - 1) / 4 * 100, 0, 100)
        section_scores[sec] = round(pct, 1)

    # 방향성 조정: 부정 섹션은 '편안함' 점수로 변환(낮을수록 어려움 → 낮으면 빨간 신호)
    comfort_map = {}
    for sec, pct in section_scores.items():
        if sec in NEGATIVE_SECTIONS:
            comfort = 100 - pct  # 감정 편안함/관계 안정감
            comfort_map[sec] = round(comfort, 1)
        else:
            comfort_map[sec] = pct

    # 종합 지표
    mood = comfort_map["감정 상태"]
    coping = comfort_map["스트레스 대처"]
    attach = comfort_map["애착/관계"]
    drive = comfort_map["동기·회복탄력"]
    flow = comfort_map["몰입·창의"]

    profile = {
        "감정 편안함": mood,
        "스트레스 대처력": coping,
        "관계 안정감": attach,
        "동기·회복탄력": drive,
        "몰입·창의": flow,
    }
    return profile

def interpret_profile(profile):
    mood = profile["감정 편안함"]
    coping = profile["스트레스 대처력"]
    attach = profile["관계 안정감"]
    drive = profile["동기·회복탄력"]
    flow = profile["몰입·창의"]

    highlights = []
    cautions = []
    suggestions = []

    # 하이라이트
    if drive >= 60:
        highlights.append("밀어붙이는 저력과 회복탄력이 살아있어. 파고들면 성과 난다.")
    if flow >= 60:
        highlights.append("몰입감이 좋아. 창의 모드 켜면 시간 순삭되는 타입.")
    if coping >= 60:
        highlights.append("스트레스 설계가 가능해. 우선순위·분할·표현 루틴이 작동 중.")

    # 주의 영역
    if mood < 50:
        cautions.append("감정 파도가 잦아. 수면·호흡·루틴 정비가 필요해.")
    if attach < 50:
        cautions.append("관계 피로 누적. 경계 세우기와 솔직한 한 줄 표현 연습이 도움돼.")
    if coping < 40:
        cautions.append("대처력이 바닥까지 떨어지면 체력부터 회수하자. 최소 루틴으로 재부팅.")

    # 제안
    suggestions.extend([
        "수면 고정: 취침/기상 7일 연속 고정, 낮잠은 20분 컷.",
        "호흡 4-7-8, 3세트. 불안감 올라올 때 즉시 실행.",
        "30분 타임박싱(작게 쪼개서 바로 시작) + 끝나면 5분 보상.",
        "관계 경계 문장 3개 미리 준비: ‘지금은 어려워’, ‘다음에 이야기하자’, ‘내 페이스로 갈게’",
        "아이디어 배출 10개/일, 평가 금지. 주 1회만 선별.",
    ])

    # 오늘의 한 줄 처방
    if mood < 50 and coping < 50:
        today = "몸 먼저 살리고, 일은 작게. 오늘은 ‘완벽’ 대신 ‘시작’."
    elif drive >= 60 and flow >= 60:
        today = "바람 불 때 돛 올려. 지금은 실행 모드 ON."
    else:
        today = "작게라도 한 칸. 리듬이 곧 안정이야."

    return {
        "highlights": highlights,
        "cautions": cautions,
        "suggestions": suggestions,
        "today": today,
    }

# -------------------------------
# 심리 → 영화 테마 매핑
# -------------------------------
def derive_themes(profile):
    themes = []
    if profile["감정 편안함"] < 50:
        themes += ["힐링", "정서 회복"]
    if profile["스트레스 대처력"] < 50:
        themes += ["성장", "재기", "작은 용기"]
    if profile["관계 안정감"] < 50:
        themes += ["우정", "자기 경계", "진심 소통"]
    if profile["동기·회복탄력"] >= 60:
        themes += ["모험", "도전"]
    if profile["몰입·창의"] >= 60:
        themes += ["상상력", "예술", "독특한 서사"]
    if not themes:
        themes = ["기분 좋은 여운", "밸런스 좋은 서사"]
    return list(dict.fromkeys(themes))  # 중복 제거, 순서 유지

def curate_titles_by_themes(themes):
    # 테마 기반 후보 타이틀 (한국어 중심, 안정적 큐레이션)
    bank = {
        "힐링": ["리틀 포레스트", "코코", "인사이드 아웃"],
        "정서 회복": ["원더", "웡카", "업"],
        "성장": ["월터의 상상은 현실이 된다", "굿 윌 헌팅", "세상의 모든 계절"],
        "재기": ["라라랜드", "위대한 쇼맨", "인턴"],
        "작은 용기": ["소울", "빌리 엘리어트", "파수꾼"],
        "우정": ["스탠 바이 미", "하이큐!!", "우리들"],
        "자기 경계": ["설국열차", "벌새", "미스 리틀 선샤인"],
        "진심 소통": ["말할 수 없는 비밀", "이터널 선샤인", "라라랜드"],
        "모험": ["인터스텔라", "듄", "탑건: 매버릭"],
        "도전": ["위플래쉬", "포드 V 페라리", "보헤미안 랩소디"],
        "상상력": ["에브리씽 에브리웨어 올 앳 원스", "이터널 선샤인", "이상한 나라의 수학자"],
        "예술": ["비긴 어게인", "퍼스트맨", "블랙스완"],
        "독특한 서사": ["메멘토", "인셉션", "히든 피겨스"],
        "기분 좋은 여운": ["리틀 포레스트", "어바웃 타임", "플립"],
        "밸런스 좋은 서사": ["그랜드 부다페스트 호텔", "컨택트", "마션"],
    }
    titles = []
    for t in themes:
        titles += bank.get(t, [])
    # 항상 최소 6편 보장 위해 로컬 풀 보강
    if len(titles) < 6:
        titles += [m["title"] for m in LOCAL_POOL]
    # 중복 제거
    titles = list(dict.fromkeys(titles))
    return titles[:9]  # 너무 많으면 과부하 → 9편

def enrich_movie(title):
    # TMDB 시도 → 실패 시 로컬 백업
    info = fetch_movie_by_title(title)
    if info:
        return info
    # 로컬에서 타이틀 매칭
    for m in LOCAL_POOL:
        if m["title"] == title:
            return m
    # 로컬 임의 반환
    return LOCAL_POOL[0]

# -------------------------------
# UI
# -------------------------------
with st.sidebar:
    st.title("마음 필름 🎬")
    st.caption("네 심리를 읽고, 지금 딱 맞는 영화로 연결해줄게.")
    if TMDB_API_KEY:
        st.success("TMDB 연결 OK")
    else:
        st.warning("TMDB 키가 없어서 포스터/출연 정보가 제한될 수 있어. 환경변수 TMDB_API_KEY를 설정해줘.")
    st.divider()
    st.subheader("내 리스트")
    if st.session_state.watchlist:
        for i, m in enumerate(st.session_state.watchlist):
            st.write(f"• {m['title']} ({m.get('year','')})")
    else:
        st.caption("아직 담은 영화가 없어.")

st.title("심리 × 영화 추천")
st.write("오늘 너 상태, 내가 예리하게 읽어줄게. 대신 솔직히만 답해. 어떤 답을 하든 영화는 무조건 추천해줄 거니까 걱정 노.")

tab1, tab2, tab3 = st.tabs(["심리 설문", "결과 & 추천", "상담 기록"])

with tab1:
    st.subheader("빠르게, 하지만 깊게")
    st.caption("각 문항에 1(전혀 아님) ~ 5(매우 그러함)으로 체크해줘.")

    with st.form("survey"):
        for sec, items in SECTIONS.items():
            st.markdown(f"#### {sec}")
            cols = st.columns(4, gap="small")
            for i, q in enumerate(items):
                # 한 줄에 하나씩 보여주면 길어지니 2열 구성
                c = cols[i % 4]
                st.session_state.responses[f"{sec}_{i}"] = c.slider(
                    q, min_value=1, max_value=5, value=3, key=f"{sec}_{i}_slider"
                )
        submitted = st.form_submit_button("분석하기")
    if submitted:
        st.session_state.profile = score_profile(st.session_state.responses)
        interp = interpret_profile(st.session_state.profile)
        themes = derive_themes(st.session_state.profile)
        titles = curate_titles_by_themes(themes)

        # 추천 생성/저장
        recs = []
        with st.spinner("네 무드에 맞는 필름을 고르고 있어…"):
            for t in titles:
                recs.append(enrich_movie(t))
                time.sleep(0.05)
        st.session_state.recommendations = recs

        # 히스토리 저장
        st.session_state.history.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "profile": st.session_state.profile,
            "themes": themes,
            "recs": [r["title"] for r in recs],
        })
        st.success("분석 완료! 결과 탭에서 확인해봐.")

with tab2:
    st.subheader("네 심리 리포트")
    if not st.session_state.profile:
        st.info("먼저 ‘심리 설문’에서 분석을 진행해줘.")
    else:
        prof = st.session_state.profile
        interp = interpret_profile(prof)
        themes = derive_themes(prof)

        # 점수 카드
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("감정 편안함", f"{prof['감정 편안함']} / 100")
        c2.metric("스트레스 대처력", f"{prof['스트레스 대처력']} / 100")
        c3.metric("관계 안정감", f"{prof['관계 안정감']} / 100")
        c4.metric("동기·회복탄력", f"{prof['동기·회복탄력']} / 100")
        c5.metric("몰입·창의", f"{prof['몰입·창의']} / 100")

        st.markdown("#### 요점 정리")
        if interp["highlights"]:
            st.write("• 강점: " + " / ".join(interp["highlights"]))
        if interp["cautions"]:
            st.write("• 주의: " + " / ".join(interp["cautions"]))
        st.write("• 오늘의 한 줄: " + interp["today"])

        st.markdown("#### 다음 7일 액션 가이드")
        for s in interp["suggestions"]:
            st.write(f"- {s}")

        st.markdown("#### 너에게 핏한 테마")
        st.write(", ".join(themes))

        st.divider()
        st.subheader("영화 추천 리스트")

        # 필터
        query = st.text_input("타이틀 검색(선택)", "")
        cols = st.columns(3)
        shown = 0
        for m in st.session_state.recommendations:
            if query and query.strip() not in m["title"]:
                continue
            with cols[shown % 3]:
                st.markdown(f"**{m['title']}** ({m.get('year','')})")
                if m.get("poster_url"):
                    st.image(m["poster_url"], use_column_width=True)
                st.caption("주요 출연: " + (", ".join(m.get("cast", [])[:5]) or "정보 준비 중"))
                st.write(wrap(m.get("overview", "줄거리 정보가 준비 중이에요.")))
                add_key = f"add_{m['title']}"
                if st.button("내 리스트 담기", key=add_key):
                    if m not in st.session_state.watchlist:
                        st.session_state.watchlist.append(m)
                        st.success("담았어.")
            shown += 1

with tab3:
    st.subheader("지난 기록")
    if not st.session_state.history:
        st.caption("히스토리가 아직 없어.")
    else:
        for h in reversed(st.session_state.history[-10:]):
            st.write(f"- {h['timestamp']} | 테마: {', '.join(h['themes'])} | 추천: {', '.join(h['recs'][:3])} ...")

st.divider()
st.caption("팁: TMDB API 키를 설정하면 포스터/출연/줄거리가 더 풍성해져.")


# 끝.
