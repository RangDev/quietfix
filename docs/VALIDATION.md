# 검증 기록

검증일: 2026-11-20. 최종 문서·실행 관리·주석 제거 변경에 대해 수행했습니다.

## 환경

- Debian GNU/Linux 13.7 (Linux), Python 3.12.14
- ACME 2025.11, scikit-learn 1.8.0, joblib 1.5.3
- 전체 Python 패키지 버전: [requirements-lock.txt](../standalone/requirements-lock.txt)
- Ubuntu 24.04는 배포 대상이며 이번 세션에서 직접 검증한 OS는 Debian입니다.
- 기본 HTTP/CAdmin loopback 구성. TLS·UI·선택적 실환경 테스트는 아래 회귀 결과의 skip과 구분합니다.

## 결과

| 검증 | 결과 |
|---|---|
| Python 구문 컴파일 | apps/standalone/tests 통과 |
| 전체 unittest | 66개 중 63개 통과, 선택적 3개 skip |
| 기존 Python 44개 실행 구문 비교 | AST에서 docstring을 제외하면 변경 전후 동일. 문자열 값도 보존 |
| 전체 Python 46개 정적 확인 | 주석 토큰·docstring·한글 원문 0개 |
| 실제 ACME smoke test | IN/MN 유형·Mcc 조회·8대 원본/분석/중앙 사본·대시보드 snapshot 통과 |
| 백업 경로 | MN만 직접 HTTP 접속, Mcc 중앙 사본 일치·재시작 중복 방지·그룹·역할 ACP 확인 |
| 관리 도구 실행 | 6개 서비스 기동·상태·분석 로그 조회 통과 |
| ML 종단 간 확인 | 2대의 API model_state=ready, 측정값과 분석 결과 sample_id 일치 |
| 종료·재시작 | 기존 DB·학습 모델·체크포인트를 보존한 종료/재기동 통과 |
| 충돌 방지 | 중복 start 및 사용 중인 대시보드 포트 거부 확인 |

관리 도구 시험은 동일 Linux 프로세스 환경에서 start → status → API 조회 →
중복 start 거부 → logs → stop → status → 재시작 → stop → 포트 충돌 거부 순서로 수행했습니다.
ML 재생 주기는 행당 5초를 사용했습니다. CI 워크플로는 추가했으며 GitHub Actions의
원격 실행 결과는 이 로컬 검증 기록에 포함하지 않습니다.

## 재현 명령

```bash
.venv/bin/python -m compileall -q apps standalone tests
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python standalone/smoke_test.py
```

실제 서비스 실행·ML 데이터 생성·평가·API 확인은 [배포 가이드](DEPLOYMENT.md)를 따릅니다.
smoke test는 기존 8081/9090 CSE를 종료한 상태에서 실행합니다.
선택적 시험을 켜지 않은 결과를 브라우저 UI·TLS 전체 검증으로 설명하지 않습니다.

## 합성 ML 평가 예시

정상 데이터는 seed=42, 머신당 1,000개로 생성해 학습했습니다.
별도 시험은 seed=123, count=100으로 생성했으며 머신당 정상 50개·이상 50개입니다.

| 머신 | TP | FP | TN | FN | 탐지율 | 오탐률 |
|---|---:|---:|---:|---:|---:|---:|
| machine-01 | 49 | 0 | 50 | 1 | 98% | 0% |
| machine-02 | 47 | 1 | 49 | 3 | 94% | 2% |

이는 작은 합성 시험의 원시 ML 판정 결과입니다. 연속 3회 경보·네트워크·백업 지연을
포함한 성능 또는 실제 설비의 고장 예측 성능이 아닙니다. 데이터 수나 시드를 바꾸면 결과도 달라집니다.

## 한계

0.1초/행의 빠른 반복 재생 시험에서는 최신 원본에 분석·중앙 사본이 따라오지 못해
API의 waiting_for_analysis가 지속되는 현상이 관찰됐습니다. 정상 처리량을 보장하는
시험이 아니며, 발표에서는 가이드의 기본 주기를 사용하고 실제 sample_id 연결을 확인합니다.
프로세스 RUNNING과 HTTP 응답만으로 데이터 처리 완료를 판단하지 않습니다.
재부팅 자동 시작·장시간 부하·분산 장비·실제 물리 센서 시험은 수행하지 않았습니다.

Python의 한글 문자열은 유니코드 이스케이프로 표현했으므로 기존 화면과 문자열 값은
유지됩니다. 코드 설명은 Markdown 문서에서 제공합니다.
