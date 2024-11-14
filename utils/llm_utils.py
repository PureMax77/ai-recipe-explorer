from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from typing import List
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from googleapiclient.discovery import build
from google.oauth2 import service_account

from dotenv import load_dotenv
import os

# 환경변수 로드
load_dotenv()

# LLM 초기화
llm = ChatOpenAI(
    temperature=0.7, api_key=os.environ.get("OPENAI_API_KEY"), model="gpt-4o"
)

# YouTube API 클라이언트 생성

# 현재 파일의 위치를 기준으로 루트 디렉토리의 파일 경로를 찾음
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
service_account_file = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "google-oauth.json"
)

credentials = service_account.Credentials.from_service_account_file(
    service_account_file, scopes=SCOPES
)
youtube = build("youtube", "v3", credentials=credentials)
# youtube = build("youtube", "v3", developerKey=os.environ.get("GOOGLE_API_KEY"))


class TranscriptRefiner:
    def __init__(self):
        self.llm = llm

        # 문장 교정을 위한 프롬프트
        self.correction_prompt = PromptTemplate(
            template="""
            다음은 YouTube 영상의 자동 생성된 한국어 자막입니다. 
            문법적 오류나 부자연스러운 표현을 수정해주세요.

            규칙:
            1. 절대로 내용을 요약하지 마세요
            2. 수정이 필요없는 부분은 그대로 두세요

            원본 텍스트:
            {text}

            수정된 텍스트:
            """,
            input_variables=["text"],
        )

        # 문맥 확인을 위한 프롬프트
        self.context_prompt = PromptTemplate(
            template="""
            다음은 연속된 자막 구간입니다. 문맥을 고려하여 가운데 문장을 자연스럽게 수정해주세요.

            이전 문장: {previous}
            현재 문장: {current}
            다음 문장: {next}

            수정된 현재 문장:
            """,
            input_variables=["previous", "current", "next"],
        )

        self.correction_chain = self.correction_prompt | self.llm

        self.context_chain = self.context_prompt | self.llm

    def process_transcript_segments(self, segments: List[dict]) -> List[dict]:
        """자막 세그먼트들을 처리"""
        processed_segments = []

        for i, segment in enumerate(segments):
            # 문맥을 고려한 처리
            previous_text = segments[i - 1]["text"] if i > 0 else ""
            current_text = segment["text"]
            next_text = segments[i + 1]["text"] if i < len(segments) - 1 else ""

            # 먼저 기본 교정
            corrected_text = self.correction_chain.invoke(text=current_text)

            # 문맥 고려한 추가 교정
            final_text = self.context_chain.invoke(
                previous=previous_text, current=corrected_text, next=next_text
            )

            # 원본 타임스탬프 유지하면서 텍스트만 업데이트
            processed_segment = segment.copy()
            processed_segment["text"] = final_text
            processed_segments.append(processed_segment)

        return processed_segments

    def refine_transcript(self, transcript_text: str) -> str:
        """전체 자막 텍스트를 한 번에 처리"""
        return self.correction_chain.invoke({"text": transcript_text})


class RecipeAnalyzer:
    def __init__(self):
        self.llm = llm

        # 레시피 분석을 위한 프롬프트
        self.recipe_prompt = PromptTemplate(
            template="""
            다음은 요리 영상의 자막이야. 이 내용을 바탕으로 레시피를 정리해.

            자막 내용:
            {transcript}

            다음 형식으로 정리해주세요:
            1. 요리 이름:
            2. 필수 재료:
            - 재료명과 양 표시
            3. 선택 재료:
            - 재료명과 양 표시
            4. 필요한 도구:
            - 조리도구 목록
            5. 조리 순서:
            - 단계별로 자세히 설명
            6. 중요 팁:
            - 요리 과정에서 언급된 중요한 팁이나 주의사항
            7. 예상 소요 시간:
            - 준비 시간과 조리 시간 구분

            가능한 자세하고 정확하게 정리해.
            자막 내용에 없는 내용의 목차는 작성하면 안돼.
            절대로 없는 내용을 지어내지 말도록!
            """,
            input_variables=["transcript"],
        )

        self.chain = self.recipe_prompt | self.llm

    def analyze_recipe(self, transcript):
        return self.chain.invoke({"transcript": transcript})


def get_video_description(url: str) -> str:
    """YouTube API를 사용하여 영상 설명 가져오기"""
    try:
        # 비디오 ID 추출
        parsed_url = urlparse(url)
        video_id = parse_qs(parsed_url.query)["v"][0]

        # 비디오 정보 요청
        response = youtube.videos().list(part="snippet", id=video_id).execute()
        print(response)
        # 설명 추출
        if response["items"]:
            print(response["items"])
            return response["items"][0]["snippet"]["description"]
        else:
            return "영상을 찾을 수 없습니다."

    except Exception as e:
        return f"오류 발생: {str(e)}"


def get_caption(url: str) -> tuple[str, str]:
    """
    YouTube 동영상의 자막을 가져오는 함수

    Args:
        video_id (str): YouTube 동영상 ID
        api_key (str): YouTube Data API 키

    Returns:
        tuple[str, str]: (자막 언어 코드, 자막 텍스트)
        자막이 없는 경우 None 반환
    """
    try:
        # 비디오 ID 추출
        parsed_url = urlparse(url)
        video_id = parse_qs(parsed_url.query)["v"][0]

        # 자막 목록 가져오기
        captions_response = (
            youtube.captions().list(part="snippet", videoId=video_id).execute()
        )
        print(231, captions_response)
        # 사용 가능한 자막 목록
        available_captions = []

        # 자막 정보 필터링 (자동 생성된 자막 제외)
        for caption in captions_response.get("items", []):
            if not caption["snippet"].get("trackKind") == "asr":  # ASR = 자동 생성 자막
                language_code = caption["snippet"]["language"]
                caption_id = caption["id"]
                available_captions.append((language_code, caption_id))
        print(55, available_captions)
        if not available_captions:
            print(111)
            return None, "등록된 자막이 없습니다."

        # 언어 우선순위에 따라 자막 선택
        preferred_languages = ["ko", "en"]
        selected_caption = None

        for lang in preferred_languages:
            for caption in available_captions:
                if caption[0] == lang:
                    selected_caption = caption
                    break
            if selected_caption:
                break

        # 선호하는 언어의 자막이 없는 경우
        if not selected_caption:
            return None, "한국어 또는 영어 자막이 없습니다."
        print(123, selected_caption)
        # 자막 내용 가져오기
        caption_data = (
            youtube.captions().download(id=selected_caption[1], tfmt="srt").execute()
        )

        return selected_caption[0], caption_data

    except Exception as e:
        return None, f"에러가 발생했습니다: {str(e)}"
