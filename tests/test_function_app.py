import json
from unittest.mock import patch

import azure.functions as func
import pytest

from function_app import search

FAKE_RESULTS = [
    {
        "blob_name": "proposal.pptx",
        "title": "제안서 제목",
        "slide_index": 1,
        "slide_text": "핵심 내용",
        "uploaded_at": "2024-01-01T00:00:00+00:00",
        "score": 0.95,
    }
]


def make_get_request(params: dict) -> func.HttpRequest:
    return func.HttpRequest(
        method="GET",
        url="/api/search",
        params=params,
        body=b"",
    )


def make_post_request(body: dict) -> func.HttpRequest:
    return func.HttpRequest(
        method="POST",
        url="/api/search",
        body=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )


# ── GET 요청 ──────────────────────────────────────────────────────────────────

def test_get_returns_results():
    with patch("function_app.search_proposals", return_value=FAKE_RESULTS):
        resp = search(make_get_request({"q": "클라우드 제안"}))

    assert resp.status_code == 200
    data = json.loads(resp.get_body())
    assert data["query"] == "클라우드 제안"
    assert data["count"] == 1
    assert len(data["results"]) == 1


def test_get_missing_query_returns_400():
    resp = search(make_get_request({}))
    assert resp.status_code == 400
    data = json.loads(resp.get_body())
    assert "error" in data


def test_get_empty_query_returns_400():
    resp = search(make_get_request({"q": "   "}))
    assert resp.status_code == 400


def test_get_custom_top():
    with patch("function_app.search_proposals", return_value=[]) as mock_search:
        search(make_get_request({"q": "쿼리", "top": "3"}))

    mock_search.assert_called_once_with("쿼리", top=3)


def test_get_invalid_top_returns_400():
    resp = search(make_get_request({"q": "쿼리", "top": "abc"}))
    assert resp.status_code == 400


def test_get_top_out_of_range_returns_400():
    resp = search(make_get_request({"q": "쿼리", "top": "100"}))
    assert resp.status_code == 400


# ── POST 요청 ─────────────────────────────────────────────────────────────────

def test_post_returns_results():
    with patch("function_app.search_proposals", return_value=FAKE_RESULTS):
        resp = search(make_post_request({"query": "클라우드 제안"}))

    assert resp.status_code == 200
    data = json.loads(resp.get_body())
    assert data["query"] == "클라우드 제안"
    assert data["count"] == 1


def test_post_missing_query_returns_400():
    resp = search(make_post_request({}))
    assert resp.status_code == 400


def test_post_invalid_json_returns_400():
    req = func.HttpRequest(
        method="POST",
        url="/api/search",
        body=b"not json",
        headers={"Content-Type": "application/json"},
    )
    resp = search(req)
    assert resp.status_code == 400


def test_post_custom_top():
    with patch("function_app.search_proposals", return_value=[]) as mock_search:
        search(make_post_request({"query": "쿼리", "top": 7}))

    mock_search.assert_called_once_with("쿼리", top=7)


# ── 응답 형식 ─────────────────────────────────────────────────────────────────

def test_response_content_type_is_json():
    with patch("function_app.search_proposals", return_value=[]):
        resp = search(make_get_request({"q": "쿼리"}))

    assert "application/json" in resp.mimetype


def test_response_body_is_valid_json():
    with patch("function_app.search_proposals", return_value=FAKE_RESULTS):
        resp = search(make_get_request({"q": "쿼리"}))

    data = json.loads(resp.get_body())
    assert "query" in data
    assert "count" in data
    assert "results" in data
