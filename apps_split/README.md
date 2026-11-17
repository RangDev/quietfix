# QuietFix 역할 분리 버전

기존 MEC Sandbox와 ACME MN-CSE/IN-CSE는 그대로 사용합니다. 이 파일들은 ACME 서버를 대체하지 않습니다. 기존 quietfix.py의 run/serve 프로세스는 중지하고 새 프로그램을 실행하세요. 기존 quietfix-in 서비스는 유지합니다.

## 파일과 책임

|파일|실행 방식과 책임|
|---|---|
|sensor_simulator.py|collector가 import. JSON 배열을 순서대로 읽음. 네트워크 서버 없음|
|collector_ae.py|독립 프로세스. 한 행씩 MN telemetry에 전송. 두 설비를 한 프로세스로 모사|
|analyzer_ae.py|독립 프로세스. MN telemetry 조회 → 규칙 판정 → MN results|
|forwarder_ae.py|독립 프로세스. MN telemetry/results 조회 → IN archive 복사|
|dashboard.py|독립 HTTP 서버. IN만 조회. 데이터 생성·전송·분석 안 함|
|onem2m_client.py|공용 HTTP/oneM2M 모듈|
|config.py|환경변수 로딩. 장치마다 별도 설정 가능|
|worker_state.py|프로세스별 로컬 SQLite 진행 상태 저장|
|setup_resources.py|AE·container 초기 생성. 서버 시작이나 Mcc 설정은 안 함|

## 설치 및 첫 테스트

다운로드한 파일을 모두 같은 디렉터리에 두세요. 다음 예시는 기존 프로젝트 아래 apps_split에 압축을 푼 경우입니다. 기존 apps/quietfix.py를 덮어쓸 필요는 없습니다.

```bash
cd ~/MPL-QuietFix/quietfix_type_c
mkdir -p apps_split
# 다운로드한 ZIP을 apps_split에 압축 해제한 후:
source session.env
.venv/bin/python -m pip install -r apps_split/requirements.txt
.venv/bin/python apps_split/setup_resources.py
.venv/bin/python apps_split/collector_ae.py --dataset apps_split/test_data.json --interval 1 --cycles 1 --replay-id test01
.venv/bin/python apps_split/analyzer_ae.py --once
.venv/bin/python apps_split/forwarder_ae.py --once
.venv/bin/python apps_split/dashboard.py
```

VM 브라우저에서 http://127.0.0.1:8090/api 를 열어 machine별 telemetry/analysis의 sample_id가 같은지 확인합니다. `/`는 웹 화면입니다. 마지막 행은 두 설비 모두 회복 상태이므로 최종 화면에는 normal이 표시됩니다. 이상 판정을 보려면 아래처럼 순차 전송 중 화면을 보거나 IN archive/results의 전체 기록을 조회하세요.

## 실행 중 흐름 관찰

각 터미널에서 프로젝트 디렉터리로 이동하고 `source session.env`를 먼저 실행하세요.

터미널 1:
```bash
.venv/bin/python apps_split/analyzer_ae.py
```
터미널 2:
```bash
.venv/bin/python apps_split/forwarder_ae.py
```
터미널 3:
```bash
.venv/bin/python apps_split/dashboard.py
```
터미널 4:
```bash
.venv/bin/python apps_split/collector_ae.py --dataset apps_split/test_data.json --interval 8 --replay-id test02
```

collector의 SENT → analyzer의 ANALYZED → forwarder의 FORWARDED에서 같은 sample_id를 추적합니다. 대시보드는 3초마다 조회하며 분석 결과가 아직 전달되지 않았으면 waiting_for_analysis를 표시합니다. 종료는 각 터미널에서 Ctrl+C. 같은 역할은 한 번에 한 프로세스만 실행하세요. Windows에서 보려면 기존 SSH 포트 전달을 이용하거나, VM에서 `dashboard.py --host 0.0.0.0`으로 실행 후 VM_IP:8090으로 접속합니다. 기본값은 VM 로컬만 수신합니다.

## 반복 전송과 현재 시각 (v2)

기본 실행은 5초 간격으로 1→2→…→10→1→…을 무한 반복합니다. Ctrl+C로 중지합니다.

```bash
.venv/bin/python apps_split/collector_ae.py --interval 5 --replay-id loop01
```

한 바퀴만 보낼 때는 `--cycles 1`, 두 바퀴는 `--cycles 2`를 추가합니다. cycles는 해당 replay-id에서 누적 목표 회차이며 재시작할 때마다 추가하는 회차 수가 아닙니다. 같은 replay-id 재실행은 중단 지점부터 이어갑니다. 처음부터 다시 하려면 새 replay-id를 지정하세요.

각 행을 보내기 직전에 UTC 현재 시각을 timestamp에 넣습니다. JSON에 timestamp가 있어도 덮어쓰며 없어도 됩니다. cycle(1부터), dataset_index(0부터), sequence(0부터)를 함께 기록합니다. 회차가 바뀌면 sample_id도 달라져 CSE에 새 데이터로 저장됩니다. timestamp는 최초 전송 시도 시각이며 CSE 도착 시각은 아닙니다. 재시도 시에는 응답 유실에 따른 중복 생성을 막기 위해 저장된 sample_id와 timestamp를 유지합니다.

첫 샘플은 즉시 전송하며 이후 정상 통신에서는 전송 시작 사이를 5초로 맞춥니다. 네트워크 지연·장애가 길면 그 이상 걸릴 수 있으며 실패한 행이 성공하기 전에는 다음 행으로 넘어가지 않습니다. 중단·재시작 시 간격 타이머는 새로 시작합니다.

v1 체크포인트와 충돌하지 않도록 v2 상태 키를 사용합니다. 업그레이드 첫 실행은 1번부터 시작합니다. state/의 pending에는 전송 대기 데이터까지 보관하므로 임의 삭제하지 마세요. 상태를 삭제하면 중복 방지 보장이 사라집니다.

## JSON 데이터셋

`test_data.json`은 10행입니다. 두 설비의 정상 → 기계 2 이상 → 회복 순서이며 한 행씩 전송합니다. 각 행은 필수 필드 machine_id, temperature_c, vibration_rms_mm_s, current_a를 포함합니다. timestamp는 전송 직전에 생성하며 전송 간격은 --interval로 지정합니다. 테스트 데이터가 시뮬레이션임을 simulated=true로 표시합니다.

샘플 판정은 temperature_c >= 75 또는 vibration_rms_mm_s >= 7이면 abnormal, 그 외 normal입니다. current_a는 저장하되 현재 판정에 사용하지 않습니다. AI 모델 구현이 아닙니다.

## 재시작·재전송

- dataset 내용과 replay-id가 같으면 진행 위치부터 이어 보냅니다. 기본 무한 반복에서는 계속 다음 회차를 보냅니다. 유한 cycles 목표를 완료한 실행은 종료합니다.
- 새 테스트 실행은 --replay-id test03처럼 새 이름을 지정합니다.
- sample_id는 데이터셋 파일 내용·replay-id·전체 순번(반복 회차 포함)으로 생성합니다. 입력 JSON의 sample_id는 source_sample_id로 보관합니다. JSON 파일의 공백만 바꿔도 새로운 데이터셋으로 인식합니다.
- CIN 이름을 sample_id로 결정하여 응답 유실 후 재시도 시 중복 생성을 막습니다. 처리 성공 후에만 체크포인트를 저장합니다.
- state/는 진행 상태이므로 보존하세요. 실제 장치를 분리하면 각 앱과 공용 모듈을 필요한 장치에 복사하고 환경변수 주소를 변경합니다. 각 장치의 state/는 로컬에 둡니다.
- MN/IN DB를 초기화했으면 기존 체크포인트가 그 초기화를 알 수 없으므로 모든 앱을 중지하고 새 QF_STATE_DIR를 지정한 다음 리소스 설정과 새 replay-id로 시작합니다.

## 기존 환경과의 연결

QF_MN_URL/QF_MN_BASE/QF_IN_URL은 기존 session.env를 사용합니다. IN_BASE 기본값은 quietfix-in, IN_URL 기본값은 http://127.0.0.1:9090입니다. QF_LOCAL_INSECURE=1은 기존 로컬 Sandbox 자체서명 TLS 테스트용입니다.

리소스 경로는 기존과 같습니다:
- MN: <MN_BASE>/collector-01/telemetry, collector-02/telemetry, analyzer/results
- IN: quietfix-in/archive/machine-01, machine-02, results

forwarder가 실제 콘텐츠를 복사합니다. Mcc 등록만으로 데이터가 자동 복제되는 것은 아닙니다. setup은 기존 ACP를 수정하지 않고 신규 리소스는 기존 ACME 권한 설정을 상속합니다. 현재 기본 CAdmin은 개발용이며 장치별 배포에서는 AE별 Originator/ACP와 인증을 별도로 구성해야 합니다.

## 범위와 한계

이 버전은 소규모 데이터셋 검증용 폴링 구현입니다. /la 한 건만 처리하지 않고 보존된 CIN을 검색하므로 전송 후 분석을 실행해도 여러 샘플을 처리합니다. 신규 컨테이너 보존 개수는 1000개이고 검색 상한은 10000입니다. CSE가 별도로 결과 수를 제한하거나 처리 전에 데이터를 삭제하면 누락될 수 있습니다. 장기·대량 운용에는 검색 페이지 처리, 보존 정책, 구독/알림 및 장애 복구를 추가해야 합니다. 전달·분석·화면은 비동기이므로 순간적으로 결과가 대기 상태일 수 있습니다.

이 파일들이 실제 VM의 서비스나 MEC 앱으로 자동 설치되는 것은 아닙니다. 우선 기존 VM에서 위 명령으로 독립 프로세스를 실행하고 이후 각 역할별 서비스/컨테이너로 배치할 수 있습니다.

## 대시보드 카드 UI 업데이트

대시보드는 머신별 독립 카드에 온도(°C), 진동 RMS(mm/s), 전류(A), 측정 전송 시각과 분석 방식을 표시합니다. 현재 시각은 브라우저 현지 시간으로 매초 갱신합니다. 같은 sample_id의 분석 결과가 abnormal이면 카드 테두리가 붉게 표시되고 NORMAL/ABNORMAL 배지가 바뀝니다. 데이터나 분석 결과가 아직 없으면 대기 상태를 표시하며 통신 오류 시 마지막 조회 화면을 유지하고 상단에 오류를 표시합니다.

오른쪽 알림 목록은 IN-CSE에 전달된 새 abnormal 분석 샘플마다 한 건씩 등록합니다. 정상→이상 전환만을 기록하는 방식이 아니므로 연속 이상 샘플도 각각 등록됩니다. 같은 machine_id/sample_id는 반복 조회해도 중복 등록하지 않습니다. 새 알림이 들어오면 최신순으로 최대 10개만 유지하며 오래된 알림은 제거합니다. 알림 자체는 서버 메모리에만 저장하고 DB를 추가하지 않습니다. 브라우저 새로고침은 서버 목록을 유지하며 대시보드 서버를 재시작하면 IN-CSE에 보존된 결과에서 목록을 다시 구성합니다. 현재 비정상인 카드가 정상으로 회복해도 과거 알림은 남습니다.

서버가 3초마다 조회한 결과를 캐시하여 여러 브라우저가 같은 상태와 알림 목록을 공유합니다. IN-CSE 기록 검색 자체는 기존 소규모 폴링 방식이며 별도 대량 처리 최적화는 포함하지 않습니다.

이번 UI만 적용하려면 dashboard.py를 교체하고 실행 중인 대시보드를 Ctrl+C로 종료한 후 다시 실행합니다. 다른 AE나 CSE는 재시작할 필요가 없습니다.

```bash
cd ~/MPL-QuietFix/quietfix_type_c
source session.env
.venv/bin/python apps_split/dashboard.py
```

VM 브라우저에서 http://127.0.0.1:8090/ 를 여세요. /api는 프로그램용 JSON 응답을 유지합니다.
