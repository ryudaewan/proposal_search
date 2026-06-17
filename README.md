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

# Azure 배포

### 사전 준비 (Azure 리소스 생성)

```bash
# 리소스 그룹
az group create --name <rg-이름> --location koreacentral

# Storage Account (Function App 필수)
az storage account create \
  --name <storage-이름> \
  --resource-group <rg-이름> \
  --sku Standard_LRS  # 동일 데이터센터 3중 복제. 가장 저렴. ZRS(가용영역), GRS(타 리전) 대비 비용 우선 시 선택

# Function App 생성 (Python 3.11 기준)
az functionapp create \
  --resource-group <rg-이름> \
  --consumption-plan-location koreacentral \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --name <앱-이름> \
  --storage-account <storage-이름> \
  --os-type linux
```

### 배포

```bash
func azure functionapp publish <앱-이름>
```

코드 패키징 + 업로드 + 재시작까지 자동으로 처리됩니다.

### 환경 변수 설정

`local.settings.json`은 배포되지 않으므로 프로덕션 환경 변수는 별도로 설정합니다.

```bash
az functionapp config appsettings set \
  --name <앱-이름> \
  --resource-group <rg-이름> \
  --settings "AzureWebJobsStorage=<실제-연결문자열>"
```

## Azure 로그

### 실시간 스트리밍

```bash
func azure functionapp logstream <앱-이름>
```

### Application Insights (권장)

```bash
# Application Insights 리소스 생성
az monitor app-insights component create \
  --app <insights-이름> \
  --resource-group <rg-이름> \
  --location koreacentral

# Function App에 연결
az monitor app-insights component connect-function \
  --resource-group <rg-이름> \
  --app <insights-이름> \
  --function <앱-이름>
```

연결 후 Azure Portal → Function App → **Monitor** 탭에서 각 실행 내역과 `logging.info()` 출력을 조회할 수 있습니다.

```bash
# CLI로 최근 로그 쿼리
az monitor app-insights query \
  --app <insights-이름> \
  --resource-group <rg-이름> \
  --analytics-query "traces | order by timestamp desc | take 50"
```

## 비고

### Azure CLI 연결

`az` 명령을 Azure 계정과 연결합니다.

```bash
# 1. 로그인 (브라우저 열림)
az login

# 2. 구독 목록 확인
az account list --output table

# 3. 사용할 구독 선택 (구독이 여러 개인 경우)
az account set --subscription "<구독-ID 또는 이름>"

# 4. 연결 확인
az group list --output table
```

| 상황 | 해결 |
|------|------|
| 토큰 만료 | `az login` 재실행 |
| 구독이 바뀐 경우 | `az account set` 재실행 |
| 회사 계정(SSO) | `az login --use-device-code` 사용 |

토큰은 수 시간~수일 유지되므로 매번 로그인할 필요는 없습니다.
