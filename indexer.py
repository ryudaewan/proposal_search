import os
import re

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AzureOpenAI

_openai_client: AzureOpenAI | None = None
_search_client: SearchClient | None = None


def _get_openai_client() -> AzureOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AzureOpenAI(
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version="2024-02-01",
        )
    return _openai_client


def _get_search_client() -> SearchClient:
    global _search_client
    if _search_client is None:
        _search_client = SearchClient(
            endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
            index_name=os.environ["AZURE_SEARCH_INDEX_NAME"],
            credential=AzureKeyCredential(os.environ["AZURE_SEARCH_API_KEY"]),
        )
    return _search_client


def get_embedding(text: str) -> list[float]:
    response = _get_openai_client().embeddings.create(
        input=text,
        model=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
    )
    return response.data[0].embedding


def make_doc_id(blob_name: str, slide_index: int) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", blob_name)
    return f"{safe}_{slide_index:03d}"


def index_slides(blob_name: str, title: str, uploaded_at: str, slides: list[list[str]]) -> int:
    documents = []
    for i, texts in enumerate(slides):
        if not texts:
            continue
        slide_text = " ".join(texts)
        documents.append({
            "id": make_doc_id(blob_name, i),
            "blob_name": blob_name,
            "title": title,
            "slide_index": i,
            "slide_text": slide_text,
            "uploaded_at": uploaded_at,
            "content_vector": get_embedding(slide_text),
        })

    if documents:
        _get_search_client().upload_documents(documents)

    return len(documents)


def search_proposals(query: str, top: int = 5) -> list[dict]:
    vector = get_embedding(query)
    results = _get_search_client().search(
        search_text=query,
        vector_queries=[
            VectorizedQuery(vector=vector, k_nearest_neighbors=top, fields="content_vector")
        ],
        query_type="semantic",
        semantic_configuration_name="semantic-config",
        top=top,
        select=["blob_name", "title", "slide_index", "slide_text", "uploaded_at"],
    )
    return [
        {
            "blob_name": r["blob_name"],
            "title": r["title"],
            "slide_index": r["slide_index"],
            "slide_text": r["slide_text"],
            "uploaded_at": r["uploaded_at"],
            "score": r["@search.score"],
        }
        for r in results
    ]
