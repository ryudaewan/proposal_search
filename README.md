# Proposal Search

Azure Functions v2 Python 앱. Blob Storage에 제안서 pptx 파일이 올라올 때마다 RAG를 위한 임베딩을 만들어 벡터 DB에 저장합니다.

## 아키텍처

| 함수명 | 트리거 | 경로 |
|--------|--------|------|
| `blob_trigger` | Blob | `raw-proposal/{name}` |

`raw-proposal` 컨테이너에 파일이 업로드되면 `blob_trigger` 함수가 자동으로 실행됩니다.

## 로컬 개발 환경 설정

### 사전 요구사항

- Python + `uv`
- Node.js + `pnpm`
- Azure Functions Core Tools (`brew install azure-functions-core-tools@4`)
- Azure CLI (`brew install azure-cli`)
- Azurite (`pnpm add -g azurite`)

### 의존성 설치

```bash
uv pip install -r requirements.txt
```

### 로컬 실행

**1. Azurite 실행** (Azure Storage 에뮬레이터)

```bash
azurite --skipApiVersionCheck
```

> `--skipApiVersionCheck` 옵션 필수. Azure CLI 최신 버전(2.87.0+)은 Azurite와 API 버전이 맞지 않아 이 옵션 없이는 요청이 실패합니다.

**2. Azure Functions 실행** (별도 터미널)

```bash
func start
```

## 함수 테스트

### 컨테이너 생성 (최초 1회)

```bash
az storage container create \
  --name raw-proposal \
  --connection-string "UseDevelopmentStorage=true"
```

### 파일 업로드 → 함수 트리거

```bash
az storage blob upload \
  --container-name raw-proposal \
  --file ./파일.pptx \        # 로컬 파일 경로
  --name 파일명.pptx \        # Blob Storage 안에서 저장될 이름 (생략 시 --file 파일명 사용)
  --connection-string "UseDevelopmentStorage=true"
```

업로드가 완료되면 `func start` 터미널에 아래 로그가 출력됩니다:

```
[정보] Blob trigger: name=raw-proposal/파일명.pptx, size=... bytes
```

> 연결 문자열은 반드시 `"UseDevelopmentStorage=true"` 단축 형식을 사용하세요.  
> 명시적 연결 문자열(`DefaultEndpointsProtocol=http;...`)은 인증 오류가 발생합니다.

## 환경 변수

`local.settings.json` 파일에 로컬 환경 변수를 설정합니다. (git에 커밋하지 않음)

| 변수명 | 값 | 설명 |
|--------|-----|------|
| `FUNCTIONS_WORKER_RUNTIME` | `python` | Python 런타임 지정 |
| `AzureWebJobsStorage` | `UseDevelopmentStorage=true` | 로컬 Azurite 연결 |
