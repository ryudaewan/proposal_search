"""Azure AI Search 인덱스 생성 스크립트 (일회성 실행)

사용법:
    uv run create_index.py
    uv run create_index.py --recreate  # 기존 인덱스 삭제 후 재생성
"""

import argparse
import json
import os
import sys

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    SearchableField,
    VectorSearch,
    VectorSearchProfile,
)


def build_index(name: str) -> SearchIndex:
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="blob_name", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="title", type=SearchFieldDataType.String, filterable=True, sortable=True),
        SimpleField(name="slide_index", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
        SearchableField(name="slide_text", type=SearchFieldDataType.String),
        SimpleField(name="uploaded_at", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="hnsw-profile",
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw-algo")],
        profiles=[VectorSearchProfile(name="hnsw-profile", algorithm_configuration_name="hnsw-algo")],
    )

    semantic_search = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name="semantic-config",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="title"),
                    content_fields=[SemanticField(field_name="slide_text")],
                ),
            )
        ]
    )

    return SearchIndex(
        name=name,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recreate", action="store_true", help="기존 인덱스 삭제 후 재생성")
    args = parser.parse_args()

    endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    api_key = os.environ["AZURE_SEARCH_API_KEY"]
    index_name = os.environ.get("AZURE_SEARCH_INDEX_NAME", "proposal-slides")

    client = SearchIndexClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))

    existing = [idx.name for idx in client.list_indexes()]

    if index_name in existing:
        if args.recreate:
            client.delete_index(index_name)
            print(f"기존 인덱스 '{index_name}' 삭제 완료")
        else:
            print(f"인덱스 '{index_name}' 가 이미 존재합니다. 재생성하려면 --recreate 옵션을 사용하세요.")
            sys.exit(0)

    index = build_index(index_name)
    client.create_index(index)
    print(f"인덱스 '{index_name}' 생성 완료")


if __name__ == "__main__":
    main()
