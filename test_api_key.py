import requests
import os
from dotenv import load_dotenv

# .env 파일에서 키를 로드할 수도 있고, 아니면 아래 YOUR_TMDB_API_KEY에 직접 붙여넣어도 됨
load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "여기에_네_TMDB_API_키를_직접_붙여넣기") # <- 네 키로 바꿔!

TMDB_BASE = "https://api.themoviedb.org/3"

try:
    # 가장 기본적인 API 엔드포인트 중 하나인 /configuration에 요청
    response = requests.get(
        f"{TMDB_BASE}/configuration",
        params={"api_key": TMDB_API_KEY},
        timeout=10
    )
    response.raise_for_status()

    if response.status_code == 200:
        print("🎉 API 키 정상 작동! 모든 준비 완료!")
    else:
        print(f"❌ API 키 유효성 확인 실패. 상태 코드: {response.status_code}")
        print(f"응답 내용: {response.json()}")

except requests.exceptions.RequestException as e:
    print(f"🚫 API 요청 중 오류 발생: {e}")
    if "401 Client Error: Unauthorized" in str(e):
        print("이는 주로 API 키가 유효하지 않거나 인증에 문제가 있을 때 발생합니다.")
except Exception as e:
    print(f"알 수 없는 오류 발생: {e}")
