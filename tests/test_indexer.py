from unittest.mock import MagicMock, patch

import pytest

import indexer
from indexer import get_embedding, index_slides, make_doc_id, search_proposals

FAKE_VECTOR = [0.1] * 1536
UPLOADED_AT = "2024-01-01T00:00:00+00:00"


@pytest.fixture(autouse=True)
def reset_singletons():
    """싱글턴 클라이언트를 테스트마다 초기화."""
    indexer._openai_client = None
    indexer._search_client = None
    yield
    indexer._openai_client = None
    indexer._search_client = None


# ── make_doc_id ───────────────────────────────────────────────────────────────

def test_make_doc_id_simple():
    assert make_doc_id("test.pptx", 0) == "test_pptx_000"


def test_make_doc_id_slide_index_padding():
    assert make_doc_id("a.pptx", 5) == "a_pptx_005"
    assert make_doc_id("a.pptx", 100) == "a_pptx_100"


def test_make_doc_id_spaces_become_underscores():
    assert make_doc_id("my proposal.pptx", 1) == "my_proposal_pptx_001"


def test_make_doc_id_only_safe_chars():
    result = make_doc_id("제안서 (최종).pptx", 0)
    assert all(c.isalnum() or c in "_-" for c in result)
    assert result.endswith("_000")


# ── get_embedding ─────────────────────────────────────────────────────────────

def test_get_embedding_returns_vector(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "test-model")

    mock_client = MagicMock()
    mock_client.embeddings.create.return_value.data = [MagicMock(embedding=FAKE_VECTOR)]

    with patch("indexer._get_openai_client", return_value=mock_client):
        result = get_embedding("테스트 텍스트")

    assert result == FAKE_VECTOR


def test_get_embedding_passes_text_and_model(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "my-embedding-model")

    mock_client = MagicMock()
    mock_client.embeddings.create.return_value.data = [MagicMock(embedding=FAKE_VECTOR)]

    with patch("indexer._get_openai_client", return_value=mock_client):
        get_embedding("hello")

    mock_client.embeddings.create.assert_called_once_with(
        input="hello",
        model="my-embedding-model",
    )


# ── index_slides ──────────────────────────────────────────────────────────────

def test_index_slides_empty_list():
    mock_search = MagicMock()
    with patch("indexer._get_search_client", return_value=mock_search):
        count = index_slides("test.pptx", "제목", UPLOADED_AT, [])

    assert count == 0
    mock_search.upload_documents.assert_not_called()


def test_index_slides_all_empty_slides():
    mock_search = MagicMock()
    with patch("indexer._get_search_client", return_value=mock_search):
        with patch("indexer.get_embedding", return_value=FAKE_VECTOR):
            count = index_slides("test.pptx", "제목", UPLOADED_AT, [[], []])

    assert count == 0
    mock_search.upload_documents.assert_not_called()


def test_index_slides_returns_indexed_count():
    slides = [["슬라이드 1"], ["슬라이드 2"], ["슬라이드 3"]]
    mock_search = MagicMock()

    with patch("indexer._get_search_client", return_value=mock_search):
        with patch("indexer.get_embedding", return_value=FAKE_VECTOR):
            count = index_slides("test.pptx", "슬라이드 1", UPLOADED_AT, slides)

    assert count == 3


def test_index_slides_skips_empty_preserves_original_index():
    slides = [[], ["두 번째 슬라이드"], []]
    mock_search = MagicMock()

    with patch("indexer._get_search_client", return_value=mock_search):
        with patch("indexer.get_embedding", return_value=FAKE_VECTOR):
            count = index_slides("test.pptx", "제목", UPLOADED_AT, slides)

    assert count == 1
    doc = mock_search.upload_documents.call_args[0][0][0]
    assert doc["slide_index"] == 1


def test_index_slides_document_structure():
    slides = [["제목", "내용"]]
    mock_search = MagicMock()

    with patch("indexer._get_search_client", return_value=mock_search):
        with patch("indexer.get_embedding", return_value=FAKE_VECTOR):
            index_slides("my.pptx", "제목", UPLOADED_AT, slides)

    doc = mock_search.upload_documents.call_args[0][0][0]
    assert doc["id"] == "my_pptx_000"
    assert doc["blob_name"] == "my.pptx"
    assert doc["title"] == "제목"
    assert doc["slide_index"] == 0
    assert doc["slide_text"] == "제목 내용"
    assert doc["uploaded_at"] == UPLOADED_AT
    assert doc["content_vector"] == FAKE_VECTOR


def test_index_slides_upload_called_once():
    slides = [["슬1"], ["슬2"], ["슬3"]]
    mock_search = MagicMock()

    with patch("indexer._get_search_client", return_value=mock_search):
        with patch("indexer.get_embedding", return_value=FAKE_VECTOR):
            index_slides("test.pptx", "슬1", UPLOADED_AT, slides)

    mock_search.upload_documents.assert_called_once()
    assert len(mock_search.upload_documents.call_args[0][0]) == 3


# ── search_proposals ──────────────────────────────────────────────────────────

def _make_search_result(**kwargs) -> dict:
    defaults = {
        "blob_name": "test.pptx",
        "title": "제목",
        "slide_index": 0,
        "slide_text": "슬라이드 내용",
        "uploaded_at": UPLOADED_AT,
        "@search.score": 0.95,
    }
    return {**defaults, **kwargs}


def test_search_proposals_returns_results():
    mock_search = MagicMock()
    mock_search.search.return_value = [_make_search_result()]

    with patch("indexer._get_search_client", return_value=mock_search):
        with patch("indexer.get_embedding", return_value=FAKE_VECTOR):
            results = search_proposals("테스트 쿼리")

    assert len(results) == 1


def test_search_proposals_result_structure():
    mock_search = MagicMock()
    mock_search.search.return_value = [_make_search_result(slide_index=2, score=0.88)]

    with patch("indexer._get_search_client", return_value=mock_search):
        with patch("indexer.get_embedding", return_value=FAKE_VECTOR):
            results = search_proposals("쿼리")

    r = results[0]
    assert r["blob_name"] == "test.pptx"
    assert r["title"] == "제목"
    assert r["slide_index"] == 2
    assert r["slide_text"] == "슬라이드 내용"
    assert r["uploaded_at"] == UPLOADED_AT
    assert r["score"] == 0.95  # @search.score → score


def test_search_proposals_passes_top():
    mock_search = MagicMock()
    mock_search.search.return_value = []

    with patch("indexer._get_search_client", return_value=mock_search):
        with patch("indexer.get_embedding", return_value=FAKE_VECTOR):
            search_proposals("쿼리", top=10)

    call_kwargs = mock_search.search.call_args.kwargs
    assert call_kwargs["top"] == 10


def test_search_proposals_uses_hybrid_search():
    from azure.search.documents.models import VectorizedQuery

    mock_search = MagicMock()
    mock_search.search.return_value = []

    with patch("indexer._get_search_client", return_value=mock_search):
        with patch("indexer.get_embedding", return_value=FAKE_VECTOR):
            search_proposals("쿼리")

    call_kwargs = mock_search.search.call_args.kwargs
    assert call_kwargs["search_text"] == "쿼리"
    assert call_kwargs["query_type"] == "semantic"
    vector_queries = call_kwargs["vector_queries"]
    assert len(vector_queries) == 1
    assert isinstance(vector_queries[0], VectorizedQuery)


def test_search_proposals_empty_results():
    mock_search = MagicMock()
    mock_search.search.return_value = []

    with patch("indexer._get_search_client", return_value=mock_search):
        with patch("indexer.get_embedding", return_value=FAKE_VECTOR):
            results = search_proposals("없는 내용")

    assert results == []
