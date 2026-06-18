# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 언어

사용자와의 모든 대화는 **한국어**로 진행합니다.

## 패키지 매니저

- **Python**: `uv` 사용 (pip, poetry 사용 금지)

## 개발 명령어

```bash
# 의존성 설치
uv pip install -r requirements.txt

# Azure Functions 로컬 실행 (Azurite가 먼저 실행되어 있어야 함)
func start

# Azurite 실행 (로컬 Azure Storage 에뮬레이터) — 전역 설치: pnpm add -g azurite
azurite --skipApiVersionCheck
# --skipApiVersionCheck 필수: Azure CLI 2.87.0+는 Azurite와 API 버전 불일치로 이 옵션 없이는 요청 실패
```

## 아키텍처

**Azure Functions v2 Python** 앱으로, 데코레이터 기반 프로그래밍 모델을 사용합니다.

- `function_app.py` — 단일 진입점. 모든 함수는 `app = func.FunctionApp()` 인스턴스에 데코레이터로 등록됩니다.
- `host.json` — 런타임 설정 (extension bundle v4).
- `local.settings.json` — 로컬 환경 변수. `AzureWebJobsStorage`는 로컬 개발 시 Azurite를 가리킵니다.

### 현재 등록된 함수

| 함수명 | 트리거 | 경로 |
|--------|--------|------|
| `blob_trigger` | Blob | `raw-proposal/{name}` |

새 함수는 `function_app.py`의 `app` 객체에 데코레이터 메서드로 추가합니다.

## 로컬 스토리지 연결 문자열

Azurite 연결 시 반드시 단축 형식을 사용합니다.

```text
UseDevelopmentStorage=true
```

명시적 연결 문자열(`DefaultEndpointsProtocol=http;...`)은 인증 오류가 발생합니다.

## 프로젝트 요구사항

이 프로젝트의 요구사항은 아래 Google Sheets 문서에서 관리됩니다.

- [proposal_search 요구사항](https://docs.google.com/spreadsheets/d/13WgVSmCVQo-nU0e74_wpPPJ9npKO8F9ZsxWfHi9KHrI/edit?gid=215011539#gid=215011539)

기능 구현, 설계 결정, 우선순위 판단 시 이 문서의 요구사항을 기준으로 합니다.

## 프로젝트 WBS

이 프로젝트의 작업 분류 체계(WBS)는 아래 Google Sheets 문서에서 관리됩니다.

- [proposal_search WBS](https://docs.google.com/spreadsheets/d/1WZObPhi_-C_ZAF8WZLcE-G9S73DH991HN6_DDmjSCw8/edit?gid=1467812860#gid=1467812860)

작업 범위, 일정, 진행 상황 등 프로젝트 전반적인 계획을 확인할 때 참고합니다.
