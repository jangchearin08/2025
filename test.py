import streamlit as st
import random

st.set_page_config(page_title="심리 기반 영화 추천 🎬", page_icon="🎭")

st.title("🎬 내 마음을 위한 영화 추천기")
st.write("당신의 현재 심리 상태를 선택하면, 어울리는 영화를 추천해드릴게요! 💡")

# 심리 상태 선택
mood = st.radio(
    "지금 기분은 어떤가요? 😌",
    ["행복 😊", "우울 😔", "스트레스 😵", "지루함 😐", "설렘 💖", "고독 🥀"]
)

energy = st.selectbox(
    "오늘의 에너지 상태는 어떤가요? 🔋",
    ["넘치는 편 ⚡", "보통 🙂", "지친 상태 💤"]
)

genre = st.multiselect(
    "좋아하는 장르를 선택해주세요 🍿",
    ["로맨스 💕", "코미디 😂", "드라마 🎭", "스릴러 🔪", "SF 🚀", "애니메이션 🐭"]
)

# 간단한 추천 로

