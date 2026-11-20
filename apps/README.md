# QuietFix 분리 버전 · 동적 머신/센서 등록

최초 설치·학습·전체 실행은 [배포 가이드](../docs/DEPLOYMENT.md)를 따릅니다. 현재 분석은 머신별 Isolation Forest와 기존 임계값을 함께 사용합니다. [ML 안내](ML.md)를 참고하세요.

수집기 하나가 여러 머신을 관리하고, 각 머신에는 여러 센서가 연결되는 구조입니다. 독립 ACME MN-CSE/IN-CSE를 사용합니다. 기본 서버 실행은 [standalone 가이드](../standalone/README.md)를 따릅니다. CSE 서버를 이 코드로 대체하지 않습니다.

## 등록과 데이터 흐름

| 시점 | 수행 주체와 동작 |
|---|---|
| 수집기 시작 | `QF_COLLECTOR_ID` 이름의 AE를 MN에 등록. 이미 있으면 재사용 |
| 새 머신의 첫 측정값 | 수집기가 자신의 AE 아래 머신 컨테이너, telemetry, metadata를 자동 생성 |
| 새 센서의 첫 측정값 | 센서 ID·종류·표시명·단위를 머신 metadata에 추가 |
| 분석기 폴링 | MN의 `quietfix-machine-v3` 라벨을 검색, 발견한 모든 머신의 샘플을 분석 |
| 백업 관리 AE 폴링 | 머신·센서 목록과 원본을 IN에 전달, 저장 공간도 자동 생성 |
| 대시보드 폴링 | IN에서 머신을 검색, 머신 카드와 센서 항목을 자동 구성 |

머신/센서별로 코드나 고정 목록을 수정할 필요가 없습니다. 센서는 AE가 아니며 머신도 컨테이너로 표현합니다. 실제 물리 센서의 USB·무선 연결 탐지/드라이버는 포함하지 않습니다. 현재는 JSON 어댑터가 읽은 `machine_id`와 `sensors`로 장치 인식을 모사합니다.

## 리소스 경로

기본 수집기 ID는 `collector-01`입니다. 머신 컨테이너 이름에는 기존 리소스와 충돌하지 않도록 `machine-` 접두사를 붙입니다.

| 위치 | 리소스 예시 |
|---|---|
| MN 수집기 AE | `<MN_BASE>/collector-01` |
| MN 머신 컨테이너 | `<MN_BASE>/collector-01/machine-machine-03` |
| MN 원본 CIN | 위 컨테이너의 `telemetry` 아래 |
| MN 센서 목록 CIN | 위 컨테이너의 `metadata` 아래 |
| MN 분석 결과 CIN | `<MN_BASE>/analyzer/results` 아래 |
| IN 원본/목록 | `<IN_BASE>/archive/collector-01/machine-machine-03/{telemetry,metadata}` |
| IN 분석 결과 CIN | `<IN_BASE>/archive/results` 아래 |

IN에서도 수집기 ID를 경로에 포함하므로 서로 다른 수집기에 같은 머신 ID가 있어도 구분합니다. 분석과 알림 역시 `(collector_id, machine_id, sample_id)`로 연결합니다. 머신이 다른 수집기로 이동하면 별도 등록으로 취급합니다.

새 telemetry/results 컨테이너는 각각 CIN 최대 1,000개, metadata는 최신 1개를 보관합니다. 기존 컨테이너의 설정을 덮어쓰지 않습니다. 센서 목록은 과거 등록 센서를 합쳐 보존하며 자동 삭제하지 않습니다.

## 적용 및 실행

폴더명이 `apps_split`에서 `apps`로 변경되었습니다. 기본 상태 경로를 사용하던 환경은 앱을 모두 중지한 뒤, Git 갱신 후 남아 있는 `apps_split/state/`를 `apps/state/`로 옮기면 진행 상태를 이어갈 수 있습니다. 대상 상태 폴더가 이미 있다면 덮어쓰지 마세요. `QF_STATE_DIR`를 별도 지정했다면 기존 경로를 유지합니다. 서비스/스크립트의 실행 경로도 `apps/`로 수정하세요.

실행 중인 기존 분리 앱 4개(수집기·분석기·백업 관리 AE·대시보드)를 Ctrl+C로 중지하고 저장소를 갱신합니다. 기존 통합본도 동시에 실행하지 마세요. 기존 CSE는 계속 실행합니다.

```bash
git pull --ff-only
source session.env
export QF_COLLECTOR_ID=collector-01
.venv/bin/python -m pip install -r apps/requirements.txt
# 선택 사항: 공통 리소스를 미리 준비. 각 앱도 필요한 리소스를 자동 생성합니다.
.venv/bin/python apps/setup_resources.py
```

각 터미널에서 저장소 디렉터리로 이동하고 `source session.env`를 실행한 뒤 아래 명령을 하나씩 실행합니다. 기본 ID가 아닌 수집기는 그 터미널에서 `export QF_COLLECTOR_ID=gateway-west`처럼 지정하세요.

```bash
.venv/bin/python apps/analyzer_ae.py
.venv/bin/python apps/backup_ae.py
.venv/bin/python apps/dashboard.py
.venv/bin/python apps/collector_ae.py --dataset test_data/test_data_expanded.json --interval 5 --replay-id dynamic01
```

대시보드: http://127.0.0.1:8090/ (`/api`는 프로그램용 JSON).

`test_data_expanded.json`에는 머신 1·2, 신규 머신 3, 머신 3에 뒤늦게 추가되는 압력 센서, 압력 센서만 있는 머신 4가 들어 있습니다. 머신 3은 4개 센서의 이상 상태에서 5개 센서의 회복 상태로 바뀝니다. 마지막 머신 4는 미판정입니다. 목록을 반복하므로 센서 추가 전 샘플에서는 압력 센서가 ‘이번 샘플 미수신’으로 보일 수 있습니다.

한 바퀴만 보내려면 `--cycles 1`, 같은 데이터셋을 처음부터 다시 보내려면 새로운 `--replay-id`를 지정합니다. 같은 ID와 파일은 재시작 시 중단 위치부터 이어갑니다. 기본은 무한 반복이며 전송 직전에 UTC 시각을 생성합니다. 실패한 행은 같은 ID·시각으로 재시도합니다.

JSON 파일은 수집기 시작 시 읽습니다. 파일에 머신/센서를 추가한 경우 **수집기만 재시작**하면 됩니다. 분석기·백업 관리 AE·대시보드는 실행 중인 채 새 목록을 다음 폴링에 반영합니다. 실제 드라이버를 연결할 때는 `resource_registry.publish(client, sample)`에 같은 형식의 샘플을 넘깁니다.

## JSON 형식

기존 `test_data.json`의 `temperature_c`, `vibration_rms_mm_s`, `current_a` 형식도 지원합니다. 새 센서/동종 센서 여러 개는 다음 형식을 사용하세요.

```json
[
  {
    "machine_id": "machine-03",
    "machine_name": "기계 3",
    "sensors": [
      {"sensor_id": "motor-temp", "type": "temperature", "label": "모터 온도", "value": 65, "unit": "°C"},
      {"sensor_id": "bearing-temp", "type": "temperature", "label": "베어링 온도", "value": 78, "unit": "°C"},
      {"sensor_id": "pressure", "type": "pressure", "label": "압력", "value": 2.4, "unit": "bar"}
    ]
  }
]
```

각 행은 **한 머신의 현재 센서 스냅샷**입니다. 센서별 이벤트를 한 행씩 보내는 형식이 아닙니다. ID는 영문·숫자로 시작하는 영문·숫자·`-`·`_` 1~64자이며, 센서 ID는 머신 안에서 중복되면 안 됩니다. 값은 유한한 숫자입니다. `sensors`가 있으면 기존 평면 필드 대신 이를 사용합니다. `collector_id`, `sample_id`, `timestamp`, `simulated`는 수집기가 생성합니다.

목록에 등록됐지만 이번 스냅샷에 빠진 센서는 값을 `—`, 상태를 ‘이번 샘플 미수신’으로 표시합니다. 이전 측정값을 현재 값처럼 재사용하지 않습니다. 센서의 종류·단위가 바뀌면 새 센서 ID 사용을 권장합니다.

## 분석과 화면

| 센서 종류 / 단위 | 판정 |
|---|---|
| `temperature` / `°C` | 75 이상이면 abnormal |
| `vibration_rms` / `mm/s` | 7 이상이면 abnormal |
| 그 외 종류 또는 다른 단위 | unassessed(미판정). 저장·전달·표시는 수행 |

같은 머신의 동종 센서도 각각 판정합니다. 하나라도 이상이면 머신은 ABNORMAL, 판정 가능한 센서가 모두 정상이면 NORMAL입니다. 미판정 센서가 함께 있으면 문구로 표시하고, 판정 가능한 센서가 하나도 없으면 머신도 ‘미판정’입니다. 전류·압력 등에 임의 기준을 추가하지 않았습니다. 머신별 Isolation Forest 판정은 [ML 안내](ML.md)를 따릅니다.

기존 카드 UI, 현재 시각, 이상 시 붉은 테두리, 알림 최대 10개를 유지합니다. 알림에는 수집기와 이상 센서 이름도 표시합니다. 같은 분석 샘플은 중복 등록하지 않으며 알림은 서버 메모리만 사용합니다. 재시작 시 IN에 보존된 결과에서 최근 알림을 구성합니다. 대시보드는 3초마다, 분석·전달은 기본 2초마다 조회하므로 즉시 동시에 바뀌지는 않습니다.

## 호환성과 상태 파일

기존 `<MN_BASE>/collector-01/telemetry`, `collector-02/telemetry`, IN의 직접 머신 컨테이너는 삭제하지 않습니다. 새 앱은 라벨이 붙은 v3 머신만 처리/표시하며 **기존 원본 데이터의 자동 이관은 하지 않습니다**. 새 수집기를 실행하면 새 경로에 데이터가 쌓입니다. 공유 results에 남은 이전 이상 이력은 기존 알림으로 표시될 수 있습니다.

수집기 상태 파일은 `state/collector-<수집기ID>.sqlite3`, 샘플/체크포인트 키는 v3로 구분합니다. 따라서 업그레이드 첫 실행은 기존 데이터셋도 처음부터 전송합니다. 분석기와 백업 관리 AE는 기존 SQLite를 재사용하되 v3 키로 구분합니다. `.venv`, `session.env`, `state/`, 실행 DB는 Git에 올리지 않습니다. CSE DB를 초기화했다면 앱을 모두 중지한 뒤 새 `QF_STATE_DIR`와 replay-id를 사용하세요.

여러 수집기는 서로 다른 `QF_COLLECTOR_ID`를 사용해야 합니다. 같은 수집기 ID의 프로세스를 동시에 여러 개 실행하지 마세요. 실제 배포에서는 앱별 권한/ACP와 인증이 필요하며 현재 CAdmin 설정은 개발용입니다. 수집기/백업 관리 AE가 신규 리소스를 만들 권한, 분석기/대시보드가 등록 리소스를 검색·조회할 권한이 있어야 합니다.

## 검증과 한계

```bash
python3 -m unittest discover -s tests -v
```

로컬 HTTP oneM2M 테스트 서버로 등록 → 분석 → IN 전달 → 대시보드 API 데이터 구성을 검증합니다. 실제 ACME/물리 센서 연동 테스트를 대체하지 않습니다. 검증 범위는 `VALIDATION.txt`에 기록합니다. 소규모 폴링 프로토타입이며 검색 상한 10,000개와 CSE 보존 설정에 따라 미처리 데이터가 누락될 수 있습니다. 장기·대량 운용, 등록 해제, 센서별 개별 이벤트 수집, 핫 리로드는 별도 범위입니다.

## 파일 역할

| 파일 | 책임 |
|---|---|
| `collector_ae.py` / `sensor_simulator.py` | 수집기 AE 등록·JSON 입력·머신/센서 등록·전송 |
| `device_model.py` | 센서 스키마 검증, 기존 형식 변환, 센서 판정 규칙 |
| `resource_registry.py` | AE/컨테이너 준비, 머신/센서 목록, 동적 검색 |
| `analyzer_ae.py` | 등록된 머신 조회·샘플별 분석 |
| `backup_ae.py` | 머신/센서 목록·원본·분석 결과를 IN에 복사 |
| `dashboard.py` | IN만 조회·동적 카드/센서 항목·알림 |
| `onem2m_client.py` | 공용 HTTP 및 oneM2M 요청 |
| `worker_state.py` | SQLite에 로컬 진행 상태·전송 대기 기록 |
| `setup_resources.py` | 선택적인 공통 리소스 초기화 |

## 구독·알림 및 그룹 최신값 조회

분석기와 백업 관리 AE는 HTTP 알림으로 깨어나 보존된 미처리 샘플을 처리할 수 있습니다. 알림은 처리 시작 신호이며, 실제 데이터는 CSE에서 조회합니다. 기존 SQLite 중복 방지를 유지하고 30초마다 전체 보완 조회를 하므로 알림 누락 시에도 CSE에 남은 데이터를 처리합니다. 이미 삭제된 데이터까지 복구하지는 못합니다. 새 머신 발견·구독 생성도 이 보완 주기에 수행하며, 구독 전 들어온 샘플은 조회로 처리합니다.

`session.env`에 **MN-CSE 컨테이너에서 도달할 수 있는 VM 주소**를 지정하세요. 다음 VM_IP는 실제 주소로 바꿔야 합니다.

```bash
export QF_ANALYZER_NOTIFY_URL=http://VM_IP:8091/notify
export QF_FORWARDER_NOTIFY_URL=http://VM_IP:8092/notify
export QF_RECONCILE_SECONDS=30
```

이후 각 터미널에서 환경을 다시 읽고 기존 명령으로 분석기·백업 관리 AE를 재시작합니다. 기본 수신 주소는 0.0.0.0, 포트는 각각 8091·8092입니다. 포트 변경은 `QF_ANALYZER_NOTIFY_PORT`, `QF_FORWARDER_NOTIFY_PORT`와 URL을 함께 수정하세요. MN 컨테이너 안의 127.0.0.1은 VM에서 실행하는 앱을 가리키지 않습니다. 해당 포트에 접근할 수 있어야 하고 구독 생성 권한이 필요합니다. 수신기는 구독 생성 전에 시작되며 CSE의 검증 알림에도 응답합니다. URL을 변경하면 다음 구독 확인에서 갱신합니다.

URL을 지정하지 않으면 경고 로그를 남기고 기존 `QF_POLL_SECONDS` 간격의 폴링을 사용합니다. URL을 지정했지만 구독 생성이 실패하면 로그를 남기고 30초 보완 조회는 계속합니다. `--once`는 수신 서버나 구독 없이 한 차례 처리합니다. 알림 모드에서는 같은 역할을 한 프로세스로 실행하세요. 알림 수신 포트는 개발 환경의 신뢰할 수 있는 네트워크에만 노출하세요.

분석기는 각 머신 telemetry를, 백업 관리 AE는 각 머신 telemetry와 MN analyzer/results를 구독합니다. 백업 관리 AE는 IN의 `archive/telemetryGroup`(ty=9)을 자동 생성·갱신하며, 모든 머신의 telemetry 컨테이너를 멤버로 유지합니다. 대시보드는 `GET <IN_BASE>/archive/telemetryGroup/fopt/la`로 최신 CIN들을 일괄 조회합니다. 그룹이 아직 없거나 일부 멤버가 비어 있으면 해당 머신만 개별 조회합니다. 센서별 판정은 같은 sample_id에만 연결하며 머신 상태는 마지막 분석 결과를 유지합니다. 그룹 조회가 분석기·백업 관리 AE의 전체 샘플 처리를 대체하지 않습니다. 대시보드는 3초 갱신을 유지합니다.

그룹은 백업 관리 AE가 관리하므로 대시보드는 IN을 읽기만 합니다. CSE 내부에서는 멤버별로 요청을 수행하며 같은 측정 시각이나 원자적 스냅샷을 보장하지 않습니다. 그룹 생성·갱신이 실패하면 백업 관리 AE는 오류를 기록하고 데이터 전달을 계속합니다. 이 기능은 별도 DB·MQTT 브로커 없이 HTTP로 동작합니다.

## 머신별 적응형 수집 (v4 · 기본 실행)

최신 기본 실행은 전체 JSON 한 행당 대기하는 대신 모든 활성 머신을 각각 1초마다 측정합니다. 정상/미판정 유지 시 5초마다, 이상 유지 시 1초마다 전송 대기열에 넣습니다. 첫 측정·이상 진입·정상 회복·기타 판정 상태 변경은 해당 측정 직후 대기열에 넣습니다. ‘즉시’는 측정 간격 이내에 인식하여 전송 대상으로 만든다는 뜻이며 통신 지연이나 장애 중 전달 완료까지 보장하지 않습니다. 같은 상태에서 값이 바뀌어도 정상 정기 전송까지 기다립니다.

```bash
source session.env
.venv/bin/python apps/collector_ae.py --replay-id adaptive01
# 기본 데이터셋: test_data/test_data_timeline.json
# 조정 예시:
.venv/bin/python apps/collector_ae.py --mode adaptive --replay-id adaptive02 \
  --measure-period 1 --normal-period 5 --abnormal-period 1
```

환경 기본값은 QF_MEASURE_PERIOD=1, QF_NORMAL_PERIOD=5, QF_ABNORMAL_PERIOD=1입니다. CLI가 환경값보다 우선합니다. 1초는 이미 계산된 온도/RMS 등의 상태값을 읽는 주기이며 진동·교류 원시 파형의 샘플링 속도가 아닙니다. 실제 드라이버는 대상 대역에 맞게 별도로 구현해야 합니다. 수집기와 분석기는 device_model.py의 동일 판정 규칙을 사용합니다. 분석기의 결과가 기존대로 화면 판정을 결정합니다.

새 시간 기반 JSON은 duration_seconds와 frames 배열로 구성합니다. 각 frame은 at_seconds와 머신별 센서 스냅샷입니다. 프레임은 다음 프레임까지 유지됩니다. 최초 프레임 시각에 머신이 등장합니다. 기본 파일은 0초부터 머신 8대가 등장하며 A 구역은 1~4, B 구역은 5~8입니다. 머신 3은 20초에 회복/압력 추가, 머신 6·8은 10초 이상 및 25초 회복을 거치며 40초마다 반복합니다. 기존 지연 등장 시나리오는 test_data/test_data_dynamic_timeline.json에 보존했습니다. 회차 처음에 아직 등장하지 않은 머신은 새 측정값을 만들지 않고 CSE/대시보드의 이전 값은 남습니다. --cycles 1이면 시나리오 한 바퀴를 측정한 뒤 대기열 전송을 마치고 종료합니다. 연결이 끊겨 있으면 복구를 기다리므로 Ctrl+C로 종료할 수 있습니다.

경과 시간은 저장된 측정 tick으로 진행하며 재시작 시 중단된 시나리오 위치부터 이어갑니다. 정지한 동안 시나리오는 진행하지 않습니다. 파일/replay-id/주기 설정이 바뀌면 별도 진행 상태로 시작합니다. 실제 스케줄러는 monotonic 시계를 사용하고, 로컬 처리 지연 시 과거 측정을 몰아서 생성하지 않습니다. 매우 많은 머신/느린 디스크에서는 정확한 1초를 보장하지 않습니다.

기존 배열 JSON은 순차 재생 모드로 계속 지원합니다. --interval 지정도 순차 재생을 선택합니다. 위쪽의 기존 --interval 예시는 여전히 순차 재생이며 적응형 테스트에는 위 명령을 사용하세요.

```bash
.venv/bin/python apps/collector_ae.py --mode replay --dataset test_data/test_data_expanded.json --interval 5
```

측정 루프와 HTTP 전송 스레드는 독립적이며 각각 SQLite 연결을 사용합니다. 로컬 파일 state/adaptive-<수집기ID>.sqlite3에 시나리오 진행 상태와 FIFO 전송 대기열을 원자적으로 보관합니다. 서버 응답을 받은 뒤에만 대기열에서 삭제합니다. 재전송 시 sample_id/측정 시각/최초 전송 시도 시각을 유지하므로 기존 CIN 중복 방지를 활용합니다. 실행 중 DB 파일을 복사한다면 WAL까지 고려해야 하므로 앱을 중지한 뒤 옮기세요. 같은 수집기 ID의 프로세스는 한 개만 실행합니다. 순차 재생의 기존 체크포인트를 적응형으로 자동 이관하지 않습니다.

대기열 기본 상한은 QF_OUTBOX_LIMIT=10000건입니다. 가득 차면 기존 대기 데이터를 덮어쓰지 않고 신규 샘플을 거절하며 오류 로그 및 schedule의 dropped 누적 횟수에 기록합니다. 이때 측정 시나리오는 진행하므로 일시적인 이상·회복 이벤트도 유실될 수 있습니다. 전송 성공 여부를 기준으로 주기를 잡지 않고 대기열 등록 시점을 기준으로 주기를 잡아 장애 중 무제한 생성을 제한합니다. 복구 후 FIFO로 보내므로 과거 샘플이 먼저 표시될 수 있습니다. 실패한 선두 샘플은 뒤 샘플 전송도 지연시킵니다.

대시보드는 측정 시각과 최초 전송 시도 시각, 전송 사유를 표시합니다. 최초 전송 시도는 CSE 수신 시각이 아닙니다. 정상 전송 사이에는 마지막 수신값을 유지하며 화면 갱신은 여전히 3초입니다. 이 버전은 stale/offline 자동 판정이나 UI 수신 지연 경보를 추가하지 않습니다.

## 선택적 역할별 ACP

기존 개발·데이터셋 흐름은 기본 설정에서 유지됩니다. CSE 권한을 적용한 뒤 `QF_ACP_ENABLED=1`로 실행하면 앱별 Originator와 제한된 ACP를 사용합니다. 적용·라이브 검증·복원 및 보안 범위는 [ACP.md](ACP.md)를 따르세요. 새 게이트웨이 AE는 관리자 초기 설정이 필요하며 등록된 게이트웨이 아래의 머신은 자동 등록됩니다.

## 선택적 FlexContainer 모델

`QF_FLEX_ENABLED=1`로 센서 타입·단위·값을 명시한 모델을 생성하고 FCNT 질의 기반 발견을 사용합니다. 양쪽 CSE의 모델 설치와 ACP 재적용이 필요합니다. [FLEX.md](FLEX.md)에 모델 설정·검증·전환 절차가 있습니다.

## 선택적 수집기 MQTT 바인딩

`QF_COLLECTOR_PROTOCOL=mqtt`로 수집기–MN-CSE 구간만 oneM2M MQTT 바인딩을 사용합니다. 사전 AE 등록과 ACP 모드, MQTT 브로커 및 ACME MQTT 설정이 필요합니다. [MQTT.md](MQTT.md)에 통신 구조·검증·실행 방법이 있습니다. 기본 HTTP 동작과 다른 앱의 HTTP 통신은 유지됩니다.

## Authenticated transport, semantic discovery and controlled transfer

- [Authenticated HTTPS/MQTTS and Originator/topic binding](../security/README.md)
- [SAREF descriptors and explicit unit mapping](SEMANTICS.md)
- [Controlled MN-CSE transfer and retained-state restoration](HANDOVER.md)

These features require separate configuration.

## 구역별 대시보드

머신 카드는 정상·이상 등 상태만 표시하고 선택한 머신의 센서값·속성은 상세 패널에서 확인합니다. 구역 배정은 dashboard_sections.json 또는 QF_DASHBOARD_SECTIONS 설정으로 관리하며 기존 센서 JSON은 유지됩니다. [대시보드 안내](DASHBOARD.md)를 참고하세요.


## oneM2M 전용 브랜치의 백업 경로

`backup_ae.py`는 MN 장비에서 실행하며 측정 원본과 분석 결과를 MN에서 읽는다. IN 사본 저장 요청도 MN URL의 `~/IN-CSE-ID/IN-CSEBase/...`로 보낸다. MN이 Mcc로 전달하므로 백업 AE와 IN 사이에 직접 Mca 연결은 없다. 분석 AE와 백업 AE는 별도 프로그램이다. 초기 권한 설정과 사용자 지정 CSE-ID는 [standalone 가이드](../standalone/README.md)를 따른다. 이전 `forwarder_ae.py` 명령도 같은 백업 실행으로 연결되며 기존 신원·구독·SQLite 상태를 재사용한다.

