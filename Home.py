import streamlit as st
from langchain_community.document_loaders import YoutubeLoader
from langchain.chains.summarize import load_summarize_chain
from langchain_openai import ChatOpenAI
from utils.llm_utils import (
    TranscriptRefiner,
    RecipeAnalyzer,
    get_video_description,
    get_caption,
)

from dotenv import load_dotenv
import os

# 환경변수 로드
load_dotenv()

# 페이지 설정
st.set_page_config(page_title="LangChain App", page_icon="🦜", layout="wide")

# LLM 초기화
llm = ChatOpenAI(
    temperature=0.7, api_key=os.environ.get("OPENAI_API_KEY"), model="gpt-4o"
)

refiner = TranscriptRefiner()


# 자막 내용 자연스럽게 처리
def process_youtube_transcript(transcript: str):
    if isinstance(transcript[0].page_content, str):
        # 전체 텍스트로 처리
        refined_text = refiner.refine_transcript(transcript[0].page_content)
        return refined_text
    else:
        # 세그먼트별 처리
        segments = transcript[0].page_content
        refined_segments = refiner.process_transcript_segments(segments)
        return refined_segments


st.title("YouTube 영상 분석기")

url = st.text_input("YouTube URL을 입력하세요:")

if url:
    desc = get_video_description(url)
    st.write(desc)
    # language, caption = get_caption(url)
    # st.write(f"{language} ({caption})")

    # try:
    #     # 자막 로드
    #     loader = YoutubeLoader.from_youtube_url(
    #         url,
    #         language=["ko", "en"],
    #     )
    #     transcript = loader.load()
    #     st.write(transcript)

    #     # RecipeAnalyzer로 요리 레시피 정리
    #     analyzer = RecipeAnalyzer()
    #     try:
    #         result = analyzer.analyze_recipe(transcript)
    #         st.write(result.content)
    #     except Exception as e:
    #         st.error(f"분석 중 오류가 발생했습니다: {str(e)}")

    # refine_transcript = process_youtube_transcript(transcript)
    # st.write(refine_transcript)

    # 요약 생성
    # if st.button("영상 내용 요약"):
    #     chain = load_summarize_chain(llm, chain_type="map_reduce")
    #     summary = chain.invoke(transcript)
    #     st.write("요약:", summary)

    # except Exception as e:
    #     st.error(f"오류 발생: {str(e)}")
