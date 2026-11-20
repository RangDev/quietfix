# 배포 및 운영

## 지원 범위

Linux, Python 3.12, 단일 호스트 loopback HTTP 구성입니다. Ubuntu 24.04를
설치 대상 환경으로 삼습니다. 실제 이번 검증 환경과 결과는 [VALIDATION.md](VALIDATION.md)에 기록합니다.
ACME 2025.11과 앱 직접 의존성은 requirements 파일에 고정했습니다.
이번 Linux/Python 3.12 검증에 사용한 전체 의존성은 standalone/requirements-lock.txt에 기록했습니다.
가상환경을 이동하면 다시 만들고 CSE 설정의 resourcesPath를 확인하세요.
Windows에서는 Ubuntu VM 또는 WSL 안에서 실행합니다.

## 최초 설치

```bash
git clone --branch onem2m-only --single-branch https://github.com/RangDev/quietfix.git
cd quietfix
python3 -m venv .venv
.venv/bin/python -m pip install -r standalone/requirements-lock.txt
.venv/bin/python standalone/manage.py prepare
source runtime/standalone/session.env
```

비공개 저장소는 먼저 본인 Git 인증을 설정해야 합니다. Ubuntu에서 venv 모듈이
없으면 `sudo apt install python3-venv`로 설치합니다. 위 prepare는 기존 환경 파일과
CSE 설정을 덮어쓰지 않습니다. 기존 데이터를 삭제하거나 자동 이관하지 않습니다.

## ML 학습과 독립 평가

```bash
.venv/bin/python apps/ml_manage.py generate --dataset ml_data/normal.json --seed 42
.venv/bin/python apps/ml_manage.py train --dataset ml_data/normal.json
.venv/bin/python apps/ml_manage.py generate-test --dataset ml_data/test.json --seed 123
.venv/bin/python apps/ml_manage.py evaluate --dataset ml_data/test.json
```

기본 생성기는 collector-01의 machine-01·02에 대해서만 학습합니다.
정상 80% 학습과 20% 기준점 보정, 다른 시드의 시험 데이터를 사용합니다.
라이브 측정값을 자동으로 정상 학습하지 않습니다. 실제 장비는 정상임을 확인한
데이터를 해당 ID로 제공하고 train을 명시적으로 실행하세요.

## 실행: 두 가지 시연

### 기본 8대 모니터링

```bash
.venv/bin/python standalone/service.py start
```

기본 시간 기반 데이터로 8대를 표시합니다. 학습한 machine-01·02만 모델 준비 상태이며,
나머지 6대는 모델 없음 상태에서 임계값 감시를 수행합니다. 기본 8대 데이터의 분포는
위 학습 데이터와 동일하게 설계되지 않았으므로 이것으로 ML 정확도를 평가하지 마세요.

### 학습과 일치하는 2대 ML 시연

기존 서비스가 실행 중이면 먼저 stop합니다.

```bash
.venv/bin/python standalone/service.py stop
.venv/bin/python standalone/service.py start --dataset ml_data/test.json --interval 1 --replay-id ml-demo01
```

기본 1,000개 시점/머신 시험 데이터는 2대 합계 2,000행이므로 1회 재생에 약 33분이 걸립니다.
원시 ML 경보는 정상에서 조합 급변·완만한 변화·회복으로 전환합니다. 운영 경보는 연속
3회 이상을 적용하므로 evaluate 수치와 다릅니다. 시연 시간을 줄이려면
`generate-test --count 100`으로 별도 파일을 만들고 새 replay-id로 실행하세요.
동일 파일·replay-id는 재시작 시 이어서 전송합니다.

## 상태·로그·종료·재시작

```bash
.venv/bin/python standalone/service.py status
.venv/bin/python standalone/service.py logs --service analyzer
.venv/bin/python standalone/service.py logs --service backup
.venv/bin/python standalone/service.py stop
.venv/bin/python standalone/service.py start
```

관리 도구는 IN → MN → 리소스 준비 → 분석 → 백업 → 대시보드 → 수집 순서로 실행합니다.
기동 실패 시 이번에 시작한 프로세스를 정리합니다. stop은 역순으로 종료합니다.
status는 프로세스 생존 확인이며 데이터 경로 검증을 대신하지 않습니다.
다중 start와 사용 중인 포트는 거부합니다. 자동 재시작·재부팅 자동 실행은 제공하지 않습니다.
수동 실행한 서비스는 관리 대상이 아니므로 해당 터미널에서 종료해야 합니다.

대시보드: http://127.0.0.1:8090/ · API: http://127.0.0.1:8090/api
API의 machines[].analysis.ml.model_state가 ready인지, 원본과 결과 sample_id가
연결되는지 확인하세요. API의 error가 있거나 waiting_for_analysis 상태라면 로그를 확인합니다.
start 완료는 HTTP 준비 확인이며 모든 머신의 ML 판정 완료를 보장하지 않습니다.

| 항목 | 기본 위치/포트 |
|---|---|
| IN-CSE | 127.0.0.1:9090, quietfix-in |
| MN-CSE | 127.0.0.1:8081, quietfix-mn |
| 대시보드 | 127.0.0.1:8090 |
| 분석·백업 알림 | 8091 / 8092 |
| 환경 파일 | runtime/standalone/session.env |
| CSE 설정·DB | runtime/standalone/in 및 mn |
| AE 체크포인트 | runtime/standalone/state |
| 학습 모델 | 위 state/ml_models |
| 서비스 로그 | runtime/standalone/logs |

관리 도구는 기본 로컬 포트와 CSE 이름을 전제로 합니다. 사용자 지정 포트·분산 장비·
MQTT·TLS·ACP·전환 실험은 [수동 운영 가이드](../standalone/README.md)와 기능별 문서를 따르세요.
session.env의 단순 export KEY=value를 읽으며 셸 명령을 평가하지 않습니다.

## 검증과 보존

전체 서비스를 중지한 후 다음을 실행합니다.

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python standalone/smoke_test.py
```

smoke test는 임시 DB에서 실제 IN/MN·Mcc·8대 저장/분석/중앙 사본·API용 snapshot을
확인합니다. 관리 도구 실행과 학습 모델 적용 확인은 [별도 검증](VALIDATION.md)입니다.
선택적 브라우저·TLS 시험의 skip은 성공으로 계산하지 않습니다.

종료 후 runtime/standalone 전체를 복사하면 CSE DB·상태·모델·환경 파일을 함께 보존할 수 있습니다.
재실행 시 같은 위치와 가상환경을 사용하세요. 파일을 복사한 다른 호스트에서는
환경 주소·resourcesPath를 점검하고 services.json은 실행 상태 파일이므로 재사용하지 마세요.
VM 외부에서 보려면 SSH 포트 포워딩을 사용합니다. 기본 CAdmin/HTTP 구성은 외부 공개용이 아닙니다.

## 제출

검증 후 확정 커밋의 태그와 Release를 제출합니다. 기사·영상은 게시 후 실제 URL로 연결합니다.
기본 브랜치 변경과 저장소 공개 여부는 저장소 소유자가 결정하며, 제출 링크는
최종 브랜치 또는 Release를 직접 가리키게 합니다. MEC 관련 평가 근거로 이 구성을 제시하지 않습니다.
