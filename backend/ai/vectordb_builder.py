"""
벡터DB 구축 스크립트 — 임대차보호법 텍스트를 ChromaDB에 색인한다.

실행 방법:
    python -m backend.ai.vectordb_builder
    또는
    python backend/ai/vectordb_builder.py

    # 샘플 데이터로 테스트 (실제 법령 파일 없이도 동작)
    python backend/ai/vectordb_builder.py --sample

    # 실제 법령 PDF 색인
    python backend/ai/vectordb_builder.py --pdf path/to/law.pdf

환경변수:
    OPENAI_API_KEY       — 임베딩 생성에 사용
    CHROMA_PERSIST_DIR   — ChromaDB 저장 경로 (기본: ./chroma_data)
    CHROMA_HOST          — 원격 ChromaDB 서버 주소 (설정 시 원격 사용)
    CHROMA_PORT          — 원격 ChromaDB 포트 (기본: 8001)
    CHROMA_COLLECTION_NAME — 컬렉션명 (기본: lease_law)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 주택임대차보호법 샘플 데이터 (실제 법령 색인 전 테스트용)
# ---------------------------------------------------------------------------

SAMPLE_LAW_ARTICLES = [
    {
        "article": "제1조",
        "title": "목적",
        "text": (
            "제1조(목적) 이 법은 주거용 건물의 임대차(賃貸借)에 관하여 「민법」에 대한 특례를 규정함으로써 "
            "국민 주거생활의 안정을 보장함을 목적으로 한다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제2조",
        "title": "적용 범위",
        "text": (
            "제2조(적용 범위) 이 법은 주거용 건물(이하 \"주택\"이라 한다)의 전부 또는 일부의 임대차에 관하여 "
            "적용한다. 그 임차주택(賃借住宅)의 일부가 주거 외의 목적으로 사용되는 경우에도 또한 같다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제3조",
        "title": "대항력 등",
        "text": (
            "제3조(대항력 등) ① 임대차는 그 등기(登記)가 없는 경우에도 임차인(賃借人)이 주택의 인도(引渡)와 "
            "주민등록을 마친 때에는 그 다음 날부터 제3자에 대하여 효력이 생긴다. "
            "이 경우 전입신고를 한 때에 주민등록이 된 것으로 본다. "
            "② 임차주택의 양수인(讓受人)(그 밖에 임대할 권리를 승계한 자를 포함한다)은 "
            "임대인(賃貸人)의 지위를 승계한 것으로 본다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제3조의2",
        "title": "보증금의 회수",
        "text": (
            "제3조의2(보증금의 회수) ① 임차인은 임차주택에 대하여 「민사집행법」에 따른 경매를 신청하는 경우와 "
            "국세징수법」에 따른 공매(公賣)를 하는 경우에는 법원에 배당요구를 하여 임차인으로서의 우선순위에 따라 "
            "보증금을 받을 수 있다. "
            "② 제1항에 따라 우선변제를 받을 임차인은 제3조 제1항의 요건을 갖추고 임대차계약증서(臨貸借契約證書)상의 "
            "확정일자(確定日字)를 갖추어야 한다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제4조",
        "title": "임대차 기간 등",
        "text": (
            "제4조(임대차 기간 등) ① 기간을 정하지 아니하거나 2년 미만으로 정한 임대차는 그 기간을 2년으로 본다. "
            "다만, 임차인은 2년 미만으로 정한 기간이 유효함을 주장할 수 있다. "
            "② 임대차가 종료한 경우에도 임차인이 보증금을 반환받을 때까지는 임대차 관계가 존속되는 것으로 본다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제6조",
        "title": "계약의 갱신",
        "text": (
            "제6조(계약의 갱신) ① 임대인이 임대차기간이 끝나기 6개월 전부터 2개월 전까지의 기간에 "
            "임차인에게 갱신거절(更新拒絶)의 통지를 하지 아니하거나 계약조건을 변경하지 아니하면 "
            "갱신하지 아니한다는 뜻의 통지를 하지 아니한 경우에는 그 기간이 끝난 때에 "
            "전 임대차와 동일한 조건으로 다시 임대차한 것으로 본다. "
            "② 제1항의 경우 임대차의 존속기간은 2년으로 본다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제6조의3",
        "title": "계약갱신 요구 등",
        "text": (
            "제6조의3(계약갱신 요구 등) ① 제6조에도 불구하고 임차인은 계약기간이 끝나기 6개월 전부터 "
            "2개월 전까지의 기간에 계약갱신을 요구할 수 있다. 이 경우 임대인은 정당한 사유 없이 "
            "거절하지 못한다. "
            "② 임차인은 제1항에 따른 계약갱신요구권을 1회에 한하여 행사할 수 있다. "
            "이 경우 갱신되는 임대차의 존속기간은 2년으로 본다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제7조",
        "title": "차임 등의 증감청구권",
        "text": (
            "제7조(차임 등의 증감청구권) ① 당사자는 약정한 차임이나 보증금이 임차주택에 관한 조세, 공과금, "
            "그 밖의 부담의 증감이나 경제사정의 변동으로 인하여 적절하지 아니하게 된 때에는 장래에 대하여 "
            "그 증감을 청구할 수 있다. "
            "② 증액청구는 약정한 차임이나 보증금의 20분의 1의 금액을 초과하지 못한다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제8조",
        "title": "보증금 중 일정액의 보호",
        "text": (
            "제8조(보증금 중 일정액의 보호) ① 임차인은 보증금 중 일정액을 다른 담보물권자(擔保物權者)보다 "
            "우선하여 변제받을 권리가 있다. 이 경우 임차인은 주택에 대한 경매신청의 등기 전에 "
            "제3조 제1항의 요건을 갖추어야 한다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제9조",
        "title": "주택 임차권의 승계",
        "text": (
            "제9조(주택 임차권의 승계) ① 임차인이 상속인 없이 사망한 경우에는 그 주택에서 가정공동생활을 하던 "
            "사실상의 혼인 관계에 있는 자가 임차인의 권리와 의무를 승계한다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "제10조",
        "title": "강행규정",
        "text": (
            "제10조(강행규정) 이 법에 위반된 약정(約定)으로서 임차인에게 불리한 것은 그 효력이 없다."
        ),
        "law_name": "주택임대차보호법",
    },
    {
        "article": "민법 제618조",
        "title": "임대차의 의의",
        "text": (
            "민법 제618조(임대차의 의의) 임대차는 당사자 일방이 상대방에게 목적물을 사용, 수익하게 할 것을 약정하고 "
            "상대방이 이에 대하여 차임을 지급할 것을 약정함으로써 그 효력이 생긴다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제623조",
        "title": "임대인의 의무",
        "text": (
            "민법 제623조(임대인의 의무) 임대인은 목적물을 임차인에게 인도하고 계약 존속중 그 사용, "
            "수익에 필요한 상태를 유지하게 할 의무를 부담한다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제634조",
        "title": "임차인의 상환청구권",
        "text": (
            "민법 제634조(임차인의 상환청구권) 임차인이 임차물의 보존에 관한 필요비를 지출한 때에는 "
            "임대인에 대하여 그 상환을 청구할 수 있다."
        ),
        "law_name": "민법",
    },
    {
        "article": "민법 제654조",
        "title": "준용규정",
        "text": (
            "민법 제654조(준용규정) 제610조 제1항, 제615조 내지 제617조의 규정은 임대차에 준용한다. "
            "임차인은 임대인의 동의 없이 임차권을 양도하거나 임차물을 전대하지 못한다."
        ),
        "law_name": "민법",
    },
]


# ---------------------------------------------------------------------------
# 벡터DB 구축 함수
# ---------------------------------------------------------------------------

def build_vectordb(articles: Optional[List[dict]] = None, use_sample: bool = False) -> int:
    """
    법령 텍스트를 ChromaDB에 색인한다.

    Parameters
    ----------
    articles : List[dict], optional
        색인할 법령 조항 목록. None이면 SAMPLE_LAW_ARTICLES 사용.
    use_sample : bool
        True이면 SAMPLE_LAW_ARTICLES만 사용.

    Returns
    -------
    int
        색인된 문서 수
    """
    if articles is None or use_sample:
        articles = SAMPLE_LAW_ARTICLES
        logger.info("샘플 법령 데이터 사용 (%d개 조항)", len(articles))

    try:
        import chromadb  # type: ignore
    except ImportError:
        logger.error("chromadb 패키지 미설치. pip install chromadb")
        raise

    # ChromaDB 클라이언트 초기화
    chroma_host = os.environ.get("CHROMA_HOST", "")
    chroma_port = int(os.environ.get("CHROMA_PORT", "8001"))
    persist_dir = os.environ.get("CHROMA_PERSIST_DIR", "./chroma_data")
    collection_name = os.environ.get("CHROMA_COLLECTION_NAME", "lease_law")

    if chroma_host:
        client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
        logger.info("ChromaDB 원격 서버: %s:%d", chroma_host, chroma_port)
    else:
        client = chromadb.PersistentClient(path=persist_dir)
        logger.info("ChromaDB 로컬: %s", persist_dir)

    # 컬렉션 생성 또는 재사용
    try:
        collection = client.get_collection(name=collection_name)
        existing_count = collection.count()
        if existing_count > 0:
            logger.info(
                "기존 컬렉션 '%s' 발견 (%d개). 초기화 후 재색인합니다.",
                collection_name,
                existing_count,
            )
            client.delete_collection(name=collection_name)
    except Exception:
        pass  # 컬렉션이 없으면 새로 생성

    # 임베딩 함수 설정 (OpenAI API 키 없으면 stub 사용 — ONNX 다운로드 방지)
    embedding_fn = _get_embedding_function()
    is_openai = os.environ.get("OPENAI_API_KEY", "") != ""

    collection = client.create_collection(
        name=collection_name,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("%s 임베딩 사용", "OpenAI" if is_openai else "stub (텍스트 검색 전용)")

    # 문서 준비
    ids = []
    documents = []
    metadatas = []

    for i, article in enumerate(articles):
        doc_id = f"article_{i:04d}_{article.get('article', '').replace(' ', '_')}"
        ids.append(doc_id)
        documents.append(article["text"])
        metadatas.append(
            {
                "law_name": article.get("law_name", "주택임대차보호법"),
                "article": article.get("article", ""),
                "title": article.get("title", ""),
            }
        )

    # 배치 삽입 (한 번에 많으면 속도 저하)
    batch_size = 50
    total_indexed = 0
    for start in range(0, len(documents), batch_size):
        end = min(start + batch_size, len(documents))
        collection.add(
            ids=ids[start:end],
            documents=documents[start:end],
            metadatas=metadatas[start:end],
        )
        total_indexed += end - start
        logger.info(
            "색인 중... %d / %d", total_indexed, len(documents)
        )

    final_count = collection.count()
    logger.info(
        "ChromaDB 색인 완료. 컬렉션 '%s': %d개 문서",
        collection_name,
        final_count,
    )
    return final_count


class _StubEmbeddingFunction:
    """
    OpenAI API 키 없을 때 사용하는 최소 임베딩 stub.
    실제 벡터 유사도 검색 없이 ChromaDB peek 기반 검색만 사용.
    정확도가 낮으므로 OPENAI_API_KEY 설정을 권장.
    """

    def name(self) -> str:  # ChromaDB 1.x 필수 메서드
        return "stub"

    def __call__(self, input):  # noqa: A002
        return [[0.0] * 384 for _ in input]


def _get_embedding_function():
    """OpenAI 임베딩 함수를 반환. API 키 없으면 stub 반환."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning(
            "OPENAI_API_KEY 미설정 — 텍스트 기반 검색으로 동작합니다. "
            "정확도를 높이려면 OPENAI_API_KEY를 설정하세요."
        )
        return _StubEmbeddingFunction()

    try:
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction  # type: ignore

        return OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name="text-embedding-3-small",
        )
    except ImportError:
        logger.warning("chromadb OpenAIEmbeddingFunction을 불러올 수 없습니다. stub 사용.")
        return _StubEmbeddingFunction()
    except Exception as exc:
        logger.warning("임베딩 함수 초기화 실패: %s — stub 사용", exc)
        return _StubEmbeddingFunction()


# ---------------------------------------------------------------------------
# PDF 법령 텍스트 파싱 (실제 법령 PDF 색인용)
# ---------------------------------------------------------------------------

def load_articles_from_pdf(pdf_path: str) -> List[dict]:
    """
    PDF 법령 파일에서 조항을 파싱한다.

    Parameters
    ----------
    pdf_path : str
        PDF 파일 경로

    Returns
    -------
    List[dict]
        파싱된 법령 조항 목록
    """
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        logger.error("pdfplumber 미설치. pip install pdfplumber")
        raise

    import re

    try:
        pages_text = []
        with pdfplumber.open(pdf_path) as pdf:
            law_name = os.path.splitext(os.path.basename(pdf_path))[0]
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text.strip())

        full_text = "\n\n".join(pages_text)
    except Exception as exc:
        logger.error("PDF 읽기 실패: %s", exc)
        raise

    # 조항 분리 (제N조 패턴)
    article_pattern = re.compile(
        r"(제\s*\d+\s*조(?:\s*의\s*\d+)?(?:\s*[\(\（][^\)\）]{0,40}[\)\）])?)",
        re.MULTILINE,
    )

    matches = list(article_pattern.finditer(full_text))
    articles = []

    for i, match in enumerate(matches):
        article_label = re.sub(r"\s+", "", match.group(1))
        # 괄호 안의 제목 추출
        title_match = re.search(r"[\(\（]([^\)\）]+)[\)\）]", match.group(1))
        title = title_match.group(1).strip() if title_match else ""

        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        text_body = full_text[start:end].strip()

        # 너무 짧은 조항 제외
        if len(text_body) < 20:
            continue

        articles.append(
            {
                "article": article_label,
                "title": title,
                "text": text_body[:1000],  # 최대 1000자 (임베딩 제한)
                "law_name": law_name,
            }
        )

    logger.info("PDF '%s'에서 %d개 조항 파싱 완료", pdf_path, len(articles))
    return articles


# ---------------------------------------------------------------------------
# CLI 진입점
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="임대차 법령 텍스트를 ChromaDB에 색인합니다."
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        default=False,
        help="샘플 데이터로 테스트 색인 (실제 PDF 없이 동작)",
    )
    parser.add_argument(
        "--pdf",
        type=str,
        action="append",
        default=[],
        help="법령 PDF 파일 경로 (여러 번 지정 가능)",
    )
    parser.add_argument(
        "--persist-dir",
        type=str,
        default="",
        help="ChromaDB 저장 경로 (기본: ./chroma_data)",
    )
    args = parser.parse_args()

    if args.persist_dir:
        os.environ["CHROMA_PERSIST_DIR"] = args.persist_dir

    if args.pdf:
        all_articles: List[dict] = []
        for pdf_path in args.pdf:
            logger.info("PDF 법령 파일 파싱: %s", pdf_path)
            all_articles.extend(load_articles_from_pdf(pdf_path))
        logger.info("총 %d개 조항 수집", len(all_articles))
        count = build_vectordb(articles=all_articles)
    else:
        # 기본: 샘플 데이터 사용
        logger.info("샘플 데이터로 테스트 색인 시작")
        count = build_vectordb(use_sample=True)

    print(f"\n색인 완료: {count}개 법령 조항이 ChromaDB에 저장되었습니다.")


if __name__ == "__main__":
    main()
