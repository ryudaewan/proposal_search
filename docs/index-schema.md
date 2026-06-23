# Azure AI Search 인덱스 스키마 설계

## 개요

인덱스 이름: `proposal-slides` (환경변수 `AZURE_SEARCH_INDEX_NAME`으로 변경 가능)

PPTX 파일을 **슬라이드 단위**로 분해하여 저장한다. 파일 단위가 아닌 슬라이드 단위로 쪼개는 이유는, 제안서 한 파일이 수십 장의 슬라이드로 구성되어 있고 사용자는 특정 주제가 담긴 슬라이드를 찾고 싶기 때문이다. 파일 단위로 색인하면 검색 결과가 지나치게 뭉뚱그려져서 "어느 슬라이드에 있었는지"를 알 수 없다.

---

## 필드 정의

| 필드명 | 타입 | 속성 | 설명 |
|---|---|---|---|
| `id` | `String` | key | 문서 고유 식별자 |
| `blob_name` | `String` | filterable | 원본 PPTX 파일명 |
| `title` | `String` | searchable, filterable, sortable | 프레젠테이션 제목 |
| `slide_index` | `Int32` | filterable, sortable | 슬라이드 순서 (0-based) |
| `slide_text` | `String` | searchable | 슬라이드 전체 텍스트 |
| `uploaded_at` | `DateTimeOffset` | filterable, sortable | 파일 업로드 시각 (UTC) |
| `content_vector` | `Collection(Single)` | searchable | 슬라이드 텍스트의 임베딩 벡터 (1536차원) |

---

## 각 필드의 설계 이유

### `id` — `{blob_name}_{slide_index:03d}`

`blob_name`의 특수문자를 `_`로 치환한 뒤 슬라이드 번호를 3자리 zero-padding으로 붙인다.

- Azure AI Search의 key 필드는 영숫자·하이픈·언더스코어만 허용하므로 특수문자를 치환한다.
- 슬라이드 번호를 key에 포함시켜 **같은 파일을 재업로드할 때 upsert가 자연스럽게 동작**하도록 한다. 동일한 `id`로 `upload_documents`를 호출하면 기존 문서가 덮어써지므로 중복 없이 갱신된다.
- 3자리 zero-padding은 정렬 시 사전순과 숫자순이 일치하도록 하기 위함이다.

### `blob_name` — filterable

원본 파일명을 그대로 저장한다.

- 특정 파일의 슬라이드만 조회하거나 삭제할 때 `$filter=blob_name eq '...'`로 범위를 좁힐 수 있다.
- 검색 결과에서 "어느 파일의 슬라이드인지"를 사용자에게 보여주는 용도로도 사용된다.

### `title` — searchable + filterable + sortable

첫 번째 슬라이드의 첫 번째 텍스트를 제목으로 사용한다 (`function_app.py`의 `blob_trigger` 참조).

- 제목은 프레젠테이션 전체를 대표하는 텍스트이므로 **모든 슬라이드 문서에 동일하게 복제**한다. 비정규화처럼 보이지만, Azure AI Search는 JOIN이 없는 문서 지향 스토어이기 때문에 이 방식이 표준적이다.
- `searchable`로 설정해 키워드 검색 시 제목도 매칭 대상에 포함되도록 한다.
- `sortable`로 설정해 제목 가나다순 정렬 기능을 지원한다.

### `slide_index` — filterable + sortable

0-based 슬라이드 순서를 저장한다.

- 검색 결과에 포함된 슬라이드가 파일 내 어느 위치인지 사용자에게 알려주기 위해 필요하다.
- `filterable`로 설정해 "앞부분 슬라이드만" 같은 범위 필터를 지원한다.
- `sortable`로 설정해 같은 파일 내 슬라이드를 순서대로 정렬할 수 있다.

### `slide_text` — searchable

슬라이드의 모든 텍스트박스·단락을 공백으로 이어붙인 평문이다.

- 벡터 검색의 임베딩 원본이기도 하고, 키워드 검색의 대상이기도 하다.
- 슬라이드별로 텍스트를 합치는 단위를 **단락(paragraph)** 으로 삼은 이유는, python-pptx에서 `shape.text`를 바로 쓰면 줄바꿈이 섞여 임베딩 품질이 떨어질 수 있기 때문이다. 단락별로 공백 strip 후 빈 단락을 제거(`pptx_parser.py`)하여 노이즈를 줄인다.

### `uploaded_at` — filterable + sortable

파일이 Blob Storage에 도착한 시각(UTC ISO 8601)을 기록한다.

- "최근 업로드된 제안서"를 내림차순으로 정렬하는 UX를 지원하기 위해 필요하다.
- Blob 자체의 `lastModified` 대신 인덱싱 시점을 사용한다. 재색인 시 덮어써지는 것이 의도된 동작이다.

### `content_vector` — 1536차원 HNSW

`slide_text`를 Azure OpenAI Embeddings(text-embedding-ada-002 기준 1536차원)로 변환한 벡터다.

- **1536차원**: text-embedding-ada-002의 고정 출력 차원. 다른 모델로 교체하면 이 값도 함께 바꿔야 한다.
- **HNSW(Hierarchical Navigable Small World)**: Azure AI Search가 지원하는 ANN(근사 최근접 이웃) 알고리즘. 정확도와 검색 속도의 균형이 좋고, 소~중규모 데이터셋에서 exhaustive KNN보다 효율적이다.

---

## 검색 방식: 하이브리드 시맨틱 검색

`indexer.py`의 `search_proposals`는 세 가지를 동시에 활용한다.

```
키워드 검색 (BM25)
    + 벡터 검색 (HNSW ANN)
    + 시맨틱 재랭킹 (Semantic Search)
```

| 레이어 | 역할 |
|---|---|
| 키워드(BM25) | 정확한 용어 매칭. "Azure Functions"처럼 고유 명사에 강하다. |
| 벡터(HNSW) | 의미 기반 매칭. "클라우드 배포 자동화"로 "CI/CD 파이프라인" 슬라이드를 찾을 수 있다. |
| 시맨틱 재랭킹 | Microsoft의 언어 모델로 상위 결과를 재정렬. `title`을 title_field, `slide_text`를 content_field로 설정해 제목 가중치를 부여한다. |

이 세 레이어를 조합하는 이유는, 키워드 검색만 쓰면 동의어·맥락 검색이 약하고, 벡터 검색만 쓰면 고유 명사 매칭이 불안정하기 때문이다. 하이브리드 방식이 실무 제안서 검색에서 체감 품질이 가장 높다.

---

## 데이터 흐름 요약

```
Blob Storage (raw-proposal/*.pptx)
    ↓ EventGrid 트리거
blob_trigger() in function_app.py
    ↓ parse_slides()
pptx_parser.py  →  list[list[str]]  (슬라이드별 단락 목록)
    ↓ index_slides()
indexer.py  →  임베딩 생성 → Azure AI Search에 upsert
```
