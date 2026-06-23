# Flex Consumption + Blob 트리거 + Managed Identity 설정 가이드

## 개요

Blob Trigger 만들 때 Azure에서 권장하는 방식인 Flex Consumption 플랜에서 Blob 트리거는 **Event Grid 방식만 지원**합니다.
일반 Consumption의 폴링 방식과 다르므로 Event Grid System Topic 및 이벤트 구독 설정이 필요합니다.

---

## 1. 코드 (`function_app.py`)

```python
import azure.functions as func
import logging

app = func.FunctionApp()

@app.blob_trigger(
    arg_name="pptx",
    path="raw-proposal/{name}",
    connection="PptxRepoConnection",
    source="EventGrid"  # Flex Consumption 필수. func.BlobTriggerSource.EVENT_GRID 는 버전에 따라 없을 수 있음
)
def blob_trigger(pptx: func.InputStream):
    logging.info(f"Blob trigger: name={pptx.name}, size={pptx.length} bytes")
```

> ⚠️ `func.BlobTriggerSource.EVENT_GRID` 는 `azure-functions >= 1.20.0` 에서만 동작.
> 버전 불확실하면 문자열 `"EventGrid"` 사용.

---

## 2. 앱 설정 (환경 변수)

Function App → 설정 → 환경 변수에서 설정.

```
# Functions 런타임 내부용 (AzureWebJobsStorage 연결 문자열 대신)
AzureWebJobsStorage__blobServiceUri   = https://<STORAGE>.blob.core.windows.net
AzureWebJobsStorage__queueServiceUri  = https://<STORAGE>.queue.core.windows.net
AzureWebJobsStorage__tableServiceUri  = https://<STORAGE>.table.core.windows.net
AzureWebJobsStorage__credential       = managedidentity
AzureWebJobsStorage__clientId         = <UAMI 클라이언트 ID>

# 업무용 Blob 스토리지 연결
PptxRepoConnection__blobServiceUri    = https://<STORAGE>.blob.core.windows.net
PptxRepoConnection__credential        = managedidentity
PptxRepoConnection__clientId          = <UAMI 클라이언트 ID>
```

> ⚠️ `AzureWebJobsStorage` 단일 연결 문자열이 있으면 제거. 위 3개(`__blobServiceUri`, `__queueServiceUri`, `__tableServiceUri`)로 교체.

---

## 3. UAMI IAM 롤 설정

스토리지 계정 → 액세스 제어(IAM) → 역할 할당에서 UAMI에 아래 3개 롤 부여.

| 롤 | 용도 |
|---|---|
| Storage Blob Data Owner | Blob 읽기/쓰기 + 트리거 lease 포함 |
| Storage Queue Data Contributor | Functions 런타임 내부 큐 |
| Storage Table Data Contributor | Functions 런타임 내부 테이블 |

> ⚠️ `Storage Blob Data Contributor` 는 트리거 lease 권한이 없어 Blob 트리거 동작 안 함. 반드시 **Owner** 로.
> ⚠️ `Storage Table Delegator` 는 테이블 읽기/쓰기 권한 없음. **Contributor** 로.

---

## 4. Function App에 UAMI 연결

```
Function App → 설정 → ID → 사용자 할당 탭
→ UAMI 추가
```

---

## 5. Event Grid System Topic 생성

```
스토리지 계정 → 이벤트 → System Topic 생성
  Topic Type : Storage Accounts (Blob & GPv2)
  Resource   : <스토리지 계정>
  Region     : 스토리지 계정과 동일 리전
```

> ℹ️ Microsoft.EventGrid 리소스 공급자가 등록되어 있어야 함.
> 포털: 구독 → 리소스 공급자 → Microsoft.EventGrid → 등록

---

## 6. 이벤트 구독 생성 (CLI 필수)

포털에서 생성 시 `MinimumTlsVersion` 에러 발생. **CLI로만 생성 가능**.

### 사전 준비

```bash
# Owner 권한 있는 구독으로 전환
az account set --subscription <SUBSCRIPTION_ID>

# 현재 구독 확인
az account show --query "{subscriptionId:id, name:name}" --output table

# blobs_extension 키 가져오기
# (Function App → 앱 키 → 시스템 키 → blobs_extension 에서도 복사 가능)
export BLOBS_EXTENSION_KEY=$(az functionapp keys list \
  --name <FUNCTION_APP_NAME> \
  --resource-group <RG_NAME> \
  --query "systemKeys.blobs_extension" \
  --output tsv)

# Function App 실제 URL 확인 (Flex Consumption은 URL 형식이 다름)
az functionapp show \
  --name <FUNCTION_APP_NAME> \
  --resource-group <RG_NAME> \
  --query "defaultHostName" \
  --output tsv
```

### 이벤트 구독 생성

```bash
az eventgrid system-topic event-subscription create \
  --name <구독이름> \
  --system-topic-name <SYSTEM_TOPIC_NAME> \
  --resource-group <RG_NAME> \
  --endpoint "https://<FUNCTION_APP_DEFAULT_DOMAIN>/runtime/webhooks/blobs?functionName=Host.Functions.<함수명>&code=${BLOBS_EXTENSION_KEY}" \
  --endpoint-type webhook \
  --included-event-types Microsoft.Storage.BlobCreated \
  --subject-begins-with /blobServices/default/containers/<컨테이너명>/blobs/
```

> ⚠️ `az eventgrid event-subscription` 아님. System Topic은 반드시 `az eventgrid system-topic event-subscription` 사용.

---

## 7. 동작 확인

```
Function App → 함수 → <함수명> → Invocations and more → 실행 클릭 → Logs
```

또는 실시간 확인:

```
Function App → Log stream
```

---

## ⚠️ 주요 삽질 포인트

| 포인트 | 내용 |
|---|---|
| Flex Consumption URL 형식 | `<앱명>.azurewebsites.net` 아님. 포털 개요의 **Default domain** 에서 확인 |
| `source="EventGrid"` | Flex Consumption에서 필수. 없으면 함수 에러 |
| `func.BlobTriggerSource.EVENT_GRID` | `azure-functions >= 1.20.0` 필요. 불확실하면 문자열 `"EventGrid"` 사용 |
| 포털 이벤트 구독 생성 | `MinimumTlsVersion` 에러로 불가. **CLI로만 생성** |
| CLI 구독 ID | 클라우드쉘 기본 구독과 리소스 구독이 다를 수 있음. 항상 확인 후 전환 |
| EventGrid 공급자 등록 | Owner 권한 있는 구독에서만 가능 |
| `az eventgrid event-subscription` | System Topic 구독은 이 명령어로 안 됨. `system-topic event-subscription` 사용 |
| Blob Data Owner vs Contributor | 트리거에는 **Owner** 필요. Contributor는 lease 권한 없음 |
| Table Delegator vs Contributor | **Contributor** 필요. Delegator는 읽기/쓰기 권한 없음 |
| 포털 코드 편집 | Flex Consumption은 포털에서 코드 저장 불가. **GitHub Actions 등으로 배포** |
