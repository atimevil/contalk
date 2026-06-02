"""
RAG 모듈 — ChromaDB 벡터 검색 + GPT-4o 법령 근거 생성

흐름:
    1. ChromaDB에서 조항 관련 법령 텍스트 검색 (top-k)
    2. 검색 결과를 컨텍스트로 포함하여 GPT-4o 호출
    3. ChromaDB 비어있으면 GPT-4o 단독 판단 폴백
"""
from __future__ import annotations

import json
import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

# ChromaDB 컬렉션명 (config.py와 동기화)
_COLLECTION_NAME = os.environ.get("CHROMA_COLLECTION_NAME", "lease_law")
_CHROMA_PERSIST_DIR = os.environ.get("CHROMA_PERSIST_DIR", "./chroma_data")
_OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4")
_TOP_K = 3  # 검색 결과 상위 K개


# ---------------------------------------------------------------------------
# 공개 인터페이스
# ---------------------------------------------------------------------------

def explain_risk(clause_text: str, risk_level: str) -> dict:
    """
    비정상(non-normal) 조항에 대한 법령 근거와 설명을 생성한다.

    Parameters
    ----------
    clause_text : str
        분석할 조항 원문
    risk_level : str
        "high" | "medium" | "caution"

    Returns
    -------
    dict
        {
            "law_ref":       str,   # 관련 법령 조항 (예: "주택임대차보호법 제6조 제1항")
            "law_summary":   str,   # 법령 내용 한 줄 요약
            "explanation":   str,   # 위험 이유 쉬운 설명
            "tenant_action": str,   # 임차인이 취할 수 있는 행동
            "severity_reason": str, # 위험도 분류 이유
            "context_used":  bool,  # ChromaDB 컨텍스트 사용 여부
        }
    """
    from .prompts import build_risk_analysis_prompt, SYSTEM_PROMPT

    # 1) ChromaDB에서 관련 법령 검색
    law_context = _retrieve_law_context(clause_text, risk_level)

    # 2) GPT-4o 호출
    user_prompt = build_risk_analysis_prompt(clause_text, risk_level, law_context)
    raw_response = _call_gpt4o(SYSTEM_PROMPT, user_prompt)

    # 3) JSON 파싱
    result = _parse_json_response(raw_response)
    result["context_used"] = bool(law_context.strip())

    return result


# ---------------------------------------------------------------------------
# ChromaDB 벡터 검색
# ---------------------------------------------------------------------------

_chroma_client = None
_chroma_collection = None


class _StubEmbeddingFunction:
    """vectordb_builder와 동일한 stub — ONNX 자동 다운로드 방지."""

    def name(self) -> str:  # ChromaDB 1.x 필수 메서드
        return "stub"

    def __call__(self, input):  # noqa: A002
        return [[0.0] * 384 for _ in input]


def _get_embedding_function():
    """OpenAI 임베딩 함수 반환. API 키 없으면 stub 반환."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return _StubEmbeddingFunction()
    try:
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction  # type: ignore

        return OpenAIEmbeddingFunction(api_key=api_key, model_name="text-embedding-3-small")
    except Exception:
        return _StubEmbeddingFunction()


def _get_collection():
    """ChromaDB 컬렉션을 싱글톤으로 반환. 실패 시 None."""
    global _chroma_client, _chroma_collection

    if _chroma_collection is not None:
        return _chroma_collection

    try:
        import chromadb  # type: ignore

        # 원격 서버 우선 (ChromaDB HTTPClient)
        chroma_host = os.environ.get("CHROMA_HOST", "")
        chroma_port = int(os.environ.get("CHROMA_PORT", "8001"))

        if chroma_host:
            client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
            logger.info("ChromaDB 원격 서버 연결: %s:%d", chroma_host, chroma_port)
        else:
            # 로컬 퍼시스턴트 스토리지
            client = chromadb.PersistentClient(path=_CHROMA_PERSIST_DIR)
            logger.info("ChromaDB 로컬 퍼시스턴트: %s", _CHROMA_PERSIST_DIR)

        # 컬렉션 가져오기 — 생성 시와 동일한 임베딩 함수 사용
        try:
            collection = client.get_collection(
                name=_COLLECTION_NAME,
                embedding_function=_get_embedding_function(),
            )
            count = collection.count()
            if count == 0:
                logger.warning(
                    "ChromaDB 컬렉션 '%s'가 비어있습니다. "
                    "vectordb_builder.py를 실행하여 법령을 색인하세요.",
                    _COLLECTION_NAME,
                )
                return None
            logger.info("ChromaDB 컬렉션 '%s' 로드 완료 (%d 문서)", _COLLECTION_NAME, count)
            _chroma_client = client
            _chroma_collection = collection
            return collection
        except Exception:
            logger.warning(
                "ChromaDB 컬렉션 '%s'가 존재하지 않습니다. "
                "vectordb_builder.py를 먼저 실행하세요.",
                _COLLECTION_NAME,
            )
            return None

    except ImportError:
        logger.warning("chromadb 패키지 미설치 — GPT-4o 단독 판단 사용")
        return None
    except Exception as exc:
        logger.warning("ChromaDB 연결 실패: %s — GPT-4o 단독 판단 사용", exc)
        return None


def _retrieve_law_context(clause_text: str, risk_level: str) -> str:
    """
    ChromaDB에서 관련 법령 텍스트를 검색하여 컨텍스트 문자열로 반환한다.
    컬렉션이 비어있거나 연결 불가 시 빈 문자열 반환.
    """
    collection = _get_collection()
    if collection is None:
        return ""

    try:
        # OpenAI 임베딩으로 쿼리 벡터 생성
        query_embedding = _embed_text(clause_text)
        if query_embedding is not None:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(_TOP_K, collection.count()),
                include=["documents", "metadatas", "distances"],
            )
        else:
            # API 키 없음 — 전체 문서를 peek 후 반환 (벡터 검색 불가)
            peeked = collection.peek(limit=_TOP_K)
            results = {
                "documents": [peeked.get("documents", [])],
                "metadatas": [peeked.get("metadatas", [])],
            }

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        if not documents:
            return ""

        # 컨텍스트 포맷팅
        context_parts = []
        for i, (doc, meta) in enumerate(zip(documents, metadatas)):
            article = meta.get("article", "")
            law_name = meta.get("law_name", "주택임대차보호법")
            source = f"{law_name} {article}".strip()
            context_parts.append(f"[{i + 1}] {source}\n{doc}")

        return "\n\n".join(context_parts)

    except Exception as exc:
        logger.warning("ChromaDB 검색 실패: %s — 컨텍스트 없이 진행", exc)
        return ""


# ---------------------------------------------------------------------------
# OpenAI 임베딩
# ---------------------------------------------------------------------------

def _embed_text(text: str) -> Optional[List[float]]:
    """text-embedding-3-small으로 텍스트를 임베딩한다."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None

    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key)
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:500],  # 임베딩은 500자로 제한
        )
        return response.data[0].embedding

    except ImportError:
        logger.warning("openai 패키지 미설치")
        return None
    except Exception as exc:
        logger.warning("임베딩 생성 실패: %s", exc)
        return None


# ---------------------------------------------------------------------------
# GPT-4o 호출
# ---------------------------------------------------------------------------

def _call_gpt4o(system_prompt: str, user_prompt: str) -> str:
    """GPT 모델을 호출하고 응답 텍스트를 반환한다."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("OPENAI_API_KEY 미설정 — 분석 건너뜀")
        return _make_unavailable_response()

    logger.info("GPT 호출 시작 (model=%s, key=sk-...%s)", _OPENAI_MODEL, api_key[-4:])
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=_OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,       # 법령 분석은 일관성 우선
            max_completion_tokens=4096,
            response_format={"type": "json_object"},  # JSON 모드 강제
        )
        logger.info("GPT 호출 성공 (model=%s)", _OPENAI_MODEL)
        return response.choices[0].message.content or "{}"

    except ImportError:
        logger.error("openai 패키지 미설치. pip install openai")
        return _make_unavailable_response()
    except Exception as exc:
        # 모델명 오류, 인증 실패, 네트워크 오류 등 — 실제 오류를 로그에 남긴다
        logger.error("GPT 호출 실패 (model=%s): %s", _OPENAI_MODEL, exc, exc_info=True)
        return _make_api_error_response()


def _make_unavailable_response() -> str:
    """API 키 미설정 시 반환할 중립 JSON (사용자에게 기술 메시지 노출 없음)."""
    return json.dumps(
        {
            "law_ref": "주택임대차보호법",
            "law_summary": "법령 데이터베이스를 확인하세요.",
            "is_favorable": None,
            "explanation": "해당 조항에 대한 상세 분석을 준비 중입니다.",
            "tenant_action": "중요한 계약 조항은 전문 법률가에게 추가 확인을 받으시기 바랍니다.",
            "severity_reason": "분석 서비스 준비 중",
            "special_clause_draft": None,
        },
        ensure_ascii=False,
    )


def _make_api_error_response() -> str:
    """API 호출 실패(모델 오류, 네트워크 등) 시 반환할 중립 JSON."""
    return json.dumps(
        {
            "law_ref": "주택임대차보호법",
            "law_summary": "법령 분석 중 일시적 오류가 발생했습니다.",
            "is_favorable": None,
            "explanation": "AI 분석 중 일시적인 오류가 발생했습니다. 위험도 분류 결과를 참고해 주세요.",
            "tenant_action": "중요한 계약 조항은 전문 법률가에게 추가 확인을 받으시기 바랍니다.",
            "severity_reason": "분석 오류",
            "special_clause_draft": None,
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# JSON 응답 파싱
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS = [
    "law_ref",
    "law_summary",
    "is_favorable",
    "explanation",
    "tenant_action",
    "severity_reason",
    "special_clause_draft",
]


def _parse_json_response(raw: str) -> dict:
    """GPT-4o 응답을 파싱하고 필수 필드를 검증한다."""
    # JSON 코드블록 제거
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # 첫 줄(```json)과 마지막 줄(```) 제거
        inner = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        cleaned = inner.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("JSON 파싱 실패: %s\n응답: %s", exc, raw[:200])
        data = {}

    # 필수 필드 보완 — 타입별 안전한 기본값 사용
    _FIELD_DEFAULTS: dict = {
        "law_ref": "주택임대차보호법",
        "law_summary": "",
        "is_favorable": None,
        "explanation": "분석 결과를 가져올 수 없습니다.",
        "tenant_action": "",
        "severity_reason": "",
        "special_clause_draft": None,
    }
    for field in _REQUIRED_FIELDS:
        if field not in data:
            data[field] = _FIELD_DEFAULTS.get(field)

    return data


# ---------------------------------------------------------------------------
# 독립 테스트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    print("=== RAG 모듈 독립 테스트 ===\n")
    print(f"OPENAI_API_KEY: {'설정됨' if os.environ.get('OPENAI_API_KEY') else '미설정 (더미 응답)'}")
    print(f"CHROMA_PERSIST_DIR: {_CHROMA_PERSIST_DIR}")
    print(f"CHROMA_HOST: {os.environ.get('CHROMA_HOST', '(미설정 — 로컬 사용)')}\n")

    test_cases = [
        {
            "clause_text": "임대인 동의 없이 전대하거나 임차권을 양도할 수 없다. 위반 시 즉시 계약 해지된다.",
            "risk_level": "high",
        },
        {
            "clause_text": "수선 책임은 소모성 부품을 포함하여 임차인이 전부 부담한다.",
            "risk_level": "medium",
        },
    ]

    for case in test_cases:
        print(f"[테스트] {case['risk_level']} | {case['clause_text'][:50]}...")
        result = explain_risk(case["clause_text"], case["risk_level"])
        print(f"  law_ref:       {result.get('law_ref', '')}")
        print(f"  explanation:   {result.get('explanation', '')[:100]}...")
        print(f"  tenant_action: {result.get('tenant_action', '')}")
        print(f"  context_used:  {result.get('context_used', False)}")
        print()

    print("RAG 모듈 테스트 완료.")
