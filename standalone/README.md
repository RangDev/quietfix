# oneM2M 전용 실행 구성

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

그 뒤 아래 명령을 각각 별도 터미널에서 실행한다.

```bash
.venv/bin/python apps/analyzer_ae.py
.venv/bin/python apps/forwarder_ae.py
.venv/bin/python apps/dashboard.py
.venv/bin/python apps/collector_ae.py
```

대시보드는 http://127.0.0.1:8090 이다. Windows에서 VM을 사용할 경우 SSH 터널을 이용한다. 기본 8대·A/B 각 4대 구역을 유지한다. 현재 forwarder의 IN 사본 저장도 유지한다. MEC 제거와 IN 백업 제거는 독립된 변경이며 이 브랜치는 후자를 수행하지 않는다.

종료: 수집기 → 분석기/전달기/대시보드 → MN → IN 순으로 각 터미널 Ctrl+C. 재실행도 같은 순서를 역순으로 따른다. runtime/standalone 아래 CSE DB와 앱 state를 삭제하지 않는다. 백업은 앱과 CSE를 정상 종료한 뒤 해당 폴더 전체를 복사한다. 기존 MEC 메모리 DB의 데이터 자동 이관은 제공하지 않는다.

## 선택 기능

- ACP: 환경을 읽고 apps/access_control.py --apply 실행 후 모든 앱에서 QF_ACP_ENABLED=1을 지정한다. apps/ACP.md 참조.
- FCNT/의미 정보: prepare가 각 CSE의 init에 모델을 복사한다. 로딩 확인 후 apps/FLEX.md와 SEMANTICS.md의 옵션·권한 설정을 따른다.
- MQTT/mTLS: 독립 기능으로 유지된다. MQTT는 별도 브로커와 ACME 바인딩 설정이 필요하다. manage.py 실행은 기본 --no-mqtt이므로 MQTT 시험 시 이 플래그를 제거하고 인증·CA·브로커 설정을 적용해야 한다. HTTP 게이트웨이는 loopback backend와 사용할 수 있다. CSE의 MQTT/알림 발신 인증서 지원 제약은 MEC 제거만으로 해결되지 않는다. apps/MQTT.md와 security/README.md 참조.
- 계획된 전환: manage.py backup으로 별도 MN을 실행하고 apps/HANDOVER.md에 따라 공용 QF_ROUTE_FILE·ACP를 준비한다. A가 살아 있을 때 B로 이전한다. 자동 장애 승계가 아니다.

MEC 관련 배포·서비스 활용 평가 근거는 이 브랜치에 없다. 기존 main의 이력은 보존한다. 실제 알림·권한·8대 데이터 경로 시험은 앱 로그와 sample_id로 확인하고 독립 unittest 성공과 구분한다.

## 재현 가능한 검증

기존 CSE를 종료한 뒤 `.venv/bin/python standalone/smoke_test.py`를 실행한다. 8081/9090이 사용 중이면 시험을 거부한다. 임시 폴더에 새 IN/MN과 DB를 만들고 실제 CSE 유형·Mcc 원격 조회·기본 8대의 저장/분석/중앙 사본/대시보드 API를 검사한 뒤 종료한다. 개발용 관리자 신원의 Mcc 시험이며 역할별 보안 검증과는 구분한다. 일반 회귀는 `.venv/bin/python -m unittest discover -s tests -v`이다. 이 시험은 장시간 처리량, 재부팅 보존, 모든 TLS 기능이나 UI 상호작용 검증을 의미하지 않는다.
