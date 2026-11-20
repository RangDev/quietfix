# 테스트 데이터

기본 실행은 test_data_timeline.json을 사용합니다. 300초(5분) 주기로 시작 시 8대가 등장하고, 120초에 머신 9가 추가됩니다. collector-01 기준 A 구역 머신 1~4, B 구역 머신 5~8입니다. 구역 배정은 apps/dashboard_sections.json에서 관리합니다.

- test_data_timeline.json: 총 9대, 19프레임. 온도·진동·전류 센서와 분당 1대의 이상/회복 시나리오입니다.
- test_data_dynamic_timeline.json: 기존 4대 지연 등장/센서 추가 시나리오, 5프레임. 회귀 테스트에서도 사용합니다.
- test_data.json: 기존 2대 순차 재생, 10행. --mode replay의 기본 파일입니다.
- test_data_expanded.json: 기존 4대 센서 확장 재생, 5행.

저장소 루트에서 실행: python apps/collector_ae.py
명시적 재생: python apps/collector_ae.py --mode replay --dataset test_data/test_data_expanded.json
JSON 변경 후 수집기를 재시작합니다. 이동 전 apps/test_data*.json 경로를 지정한 명령은 새 test_data/ 경로로 바꿉니다.


## 5분 시연 일정

| 경과 시간 | 이벤트 |
|---|---|
| 0:00 | A 구역 1~4, B 구역 5~8 정상 시작 |
| 0:30~0:45 | 머신 3 이상 후 회복 |
| 1:30~1:45 | 머신 6 이상 후 회복 |
| 2:00 | 머신 9 등장·자동 등록, 미배정 구역 표시 |
| 2:30~2:45 | 머신 9 이상 후 회복 |
| 3:30~3:45 | 머신 4 이상 후 회복 |
| 4:30~4:45 | 머신 8 이상 후 회복 |
| 5:00 | 기본 실행은 다음 회차 반복 |

동시에 이상값을 내는 머신은 최대 한 대입니다. 이상 구간의 온도는 82°C,
진동은 8.5 mm/s, 전류는 6.5 A이며 15초 후 정상값으로 복귀합니다.
머신 9는 구역 배정 목록에 없으며, 수집기가 첫 측정값을 처리하면 oneM2M에 자동 등록됩니다.
반복 회차에서도 등록된 리소스와 마지막 화면 데이터는 유지됩니다.
정확히 한 회차만 측정하려면 다음 명령을 사용합니다.

```bash
python apps/collector_ae.py --mode adaptive --dataset test_data/test_data_timeline.json --cycles 1 --replay-id demo5min01
```

기존 CSE에 저장된 머신과 이력은 데이터 파일 변경으로 삭제되지 않습니다.
화면의 이상 표시·회복 시점에는 분석 및 중앙 사본 처리 지연이 포함됩니다.
