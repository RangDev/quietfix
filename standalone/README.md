# oneM2M 전용 실행 구성

처음 설치한다면 [통합 배포 가이드](../docs/DEPLOYMENT.md)를 먼저 따릅니다. ML 학습과 전체 서비스 start/stop/status/logs를 포함합니다. 아래는 개별 CSE·AE를 직접 운영할 때의 안내입니다.

MEC Sandbox·Kubernetes·OAuth·ingress 없이 ACME IN/MN을 호스트 Python 프로세스로 실행한다. Linux와 Python 3.12 기준, ACME 2025.11 고정이다. DB는 CSE별 TinyDB 파일로 보존한다. 개발용 loopback HTTP/CAdmin 기준선이며 외부 공개용 보안 구성은 아니다.

## 준비

저장소 루트에서:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r standalone/requirements.txt
.venv/bin/python standalone/manage.py prepare
```

기존 VM의 MEC 설치나 DB는 건드리지 않는다. 8081/8082/9090/8090/8091/8092 포트 충돌 여부를 먼저 확인한다. 기존 앱과 새 앱을 동시에 동일 포트/수집기 ID로 실행하지 않는다. prepare는 기존 acme.ini와 session.env를 덮어쓰지 않는다. 모델 파일은 저장소 버전으로 복사한다. runtime 경로를 이동하거나 venv를 재설치하면 acme.ini의 resourcesPath도 확인한다.

## 실행

각 명령을 별도 터미널에서 실행한다. IN을 먼저 실행하고 MN을 실행한다.

```bash
.venv/bin/python standalone/manage.py in
.venv/bin/python standalone/manage.py mn
.venv/bin/python standalone/manage.py check
```

check는 실제 CSE 유형과 IN에서 Mcc 경유 MN 조회를 확인한다. 등록 직후 실패하면 MN/IN 로그를 확인하고 등록 완료 후 다시 실행한다. 다음 앱 터미널마다 저장소 루트에서 환경을 읽는다.

```bash
source runtime/standalone/session.env
```

최초 실행 및 기존 버전 업그레이드 때, 워커를 중지하고 관리자 신원으로 다음을 먼저 실행한다.

```bash
.venv/bin/python apps/setup_resources.py
```

이는 IN archive의 권한에 MN이 전달하는 SP-relative 신원을 허용한다. 실제 데이터 저장 위치는 IN-CSE DB이다. 기존 session.env에는 `QF_IN_CSE_ID=/id-quietfix-in`, `QF_MN_CSE_ID=/id-quietfix-mn`을 추가한다. CSEBase 이름과 CSE-ID는 서로 다른 값이다.

그 뒤 아래 명령을 각각 별도 터미널에서 실행한다.

```bash
.venv/bin/python apps/analyzer_ae.py
.venv/bin/python apps/backup_ae.py
.venv/bin/python apps/dashboard.py
.venv/bin/python apps/collector_ae.py
```

대시보드는 http://127.0.0.1:8090 이다. Windows에서 VM을 사용할 경우 SSH 터널을 이용한다. 기본 8대·A/B 각 4대 구역을 유지한다. 백업 관리 AE는 MN-CSE에만 Mca로 접속한다. 중앙 사본 요청은 MN-CSE가 Mcc로 IN-CSE에 전달한다.

종료: 수집기 → 분석기/백업 관리 AE/대시보드 → MN → IN 순으로 각 터미널 Ctrl+C. 재실행도 같은 순서를 역순으로 따른다. runtime/standalone 아래 CSE DB와 앱 state를 삭제하지 않는다. 백업은 앱과 CSE를 정상 종료한 뒤 해당 폴더 전체를 복사한다. 기존 MEC 메모리 DB의 데이터 자동 이관은 제공하지 않는다.

## 선택 기능

- ACP: 환경을 읽고 apps/access_control.py --apply 실행 후 모든 앱에서 QF_ACP_ENABLED=1을 지정한다. apps/ACP.md 참조.
- FCNT/의미 정보: prepare가 각 CSE의 init에 모델을 복사한다. 로딩 확인 후 apps/FLEX.md와 SEMANTICS.md의 옵션·권한 설정을 따른다.
- MQTT/mTLS: 독립 기능으로 유지된다. MQTT는 별도 브로커와 ACME 바인딩 설정이 필요하다. manage.py 실행은 기본 --no-mqtt이므로 MQTT 시험 시 이 플래그를 제거하고 인증·CA·브로커 설정을 적용해야 한다. HTTP 게이트웨이는 loopback backend와 사용할 수 있다. CSE의 MQTT/알림 발신 인증서 지원 제약은 MEC 제거만으로 해결되지 않는다. apps/MQTT.md와 security/README.md 참조.
- 계획된 전환: manage.py backup으로 별도 MN을 실행하고 apps/HANDOVER.md에 따라 공용 QF_ROUTE_FILE·ACP를 준비한다. A가 살아 있을 때 B로 이전한다. 자동 장애 승계가 아니다.

실제 알림·권한·8대 데이터 경로는 앱 로그와 sample_id로 확인한다. 단위 테스트와 실제 CSE 통합 시험은 별도로 수행한다.

## 재현 가능한 검증

기존 CSE를 종료한 뒤 `.venv/bin/python standalone/smoke_test.py`를 실행한다. 8081/9090이 사용 중이면 시험을 거부한다. 임시 폴더에 새 IN/MN과 DB를 만들고 실제 CSE 유형·Mcc 원격 조회·기본 8대의 저장/분석/중앙 사본/대시보드 API를 검사한 뒤 종료한다. 개발용 관리자 신원의 Mcc 시험이며 역할별 보안 검증과는 구분한다. 일반 회귀는 `.venv/bin/python -m unittest discover -s tests -v`이다. 이 시험은 장시간 처리량, 재부팅 보존, 모든 TLS 기능이나 UI 상호작용 검증을 의미하지 않는다.


## 백업 관리 AE와 Mcc

현장 MN 장비에서 AE 분석과 AE 백업 관리를 별도 프로세스로 실행한다. 분석은 측정값 판정과 현장 결과 저장만 담당한다. 백업 관리는 측정 원본·설비/센서 목록·분석 결과를 읽고 독립된 중앙 사본 생성과 재시도를 담당한다.

경로: AE 백업 관리 → Mca → MN-CSE → Mcc → IN-CSE. IN의 archive는 저장용 AE 리소스이며 별도 실행 프로그램이 아니다. MN과 IN 사이에 AE의 직접 Mca 연결을 두지 않는다. 대시보드는 중앙 장비에서 IN에 Mca로 접속한다. 관리자 초기 설정은 두 CSE에 직접 접속하지만 백업 런타임 경로와는 구분된다.

실행 파일은 `apps/backup_ae.py`이다. `forwarder_ae.py`는 같은 Mcc 실행을 호출하는 호환 진입점이다. 기존 리소스/ACP/구독/상태의 연속성을 위해 내부 AE 이름 `forwarder`, 신원 `Cqfforwarder`, `QF_FORWARDER_*`, `state/forwarder.sqlite3`를 유지한다. 두 진입점을 동시에 실행하지 않는다. 알림/주기 보완 조회 및 성공 후 체크포인트와 결정적 CIN 이름으로 재시도를 유지한다. 통신 중단 중에는 MN에 보존된 데이터만 나중에 복사할 수 있으므로 보존 한도 초과 전 복구해야 한다.

ACP 모드에서는 `access_control.py --apply`가 로컬 읽기 신원과 IN의 `/id-quietfix-mn/Cqfforwarder` 권한을 준비한다. 사용자 지정 MN ID는 `QF_MN_CSE_ID`로 맞춘다. MN 전환 시 대상 MN의 SP-relative 백업 신원도 IN ACP에 미리 허용해야 한다. TLS를 쓸 경우 백업 AE의 HTTP 상대는 MN이므로 해당 신원 인증서를 MN 게이트웨이에 연결한다.
