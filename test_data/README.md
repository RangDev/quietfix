# 테스트 데이터

기본 실행은 test_data_timeline.json을 사용합니다. 40초 주기로 총 8대가 시작부터 등장합니다. collector-01 기준 A 구역 머신 1~4, B 구역 머신 5~8입니다. 구역 배정은 apps/dashboard_sections.json에서 관리합니다.

- test_data_timeline.json: 기본 8대, 13프레임. 머신 3·6·8의 이상/회복과 압력 센서 미판정을 포함합니다.
- test_data_dynamic_timeline.json: 기존 4대 지연 등장/센서 추가 시나리오, 5프레임. 회귀 테스트에서도 사용합니다.
- test_data.json: 기존 2대 순차 재생, 10행. --mode replay의 기본 파일입니다.
- test_data_expanded.json: 기존 4대 센서 확장 재생, 5행.

저장소 루트에서 실행: python apps/collector_ae.py
명시적 재생: python apps/collector_ae.py --mode replay --dataset test_data/test_data_expanded.json
JSON 변경 후 수집기를 재시작합니다. 이동 전 apps/test_data*.json 경로를 지정한 명령은 새 test_data/ 경로로 바꿉니다.
