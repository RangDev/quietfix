# QuietFix

oneM2M 기반 설비 모니터링 개발 프로토타입입니다.

- `legacy/quietfix.py`: 기존 Type C 통합본
- `apps/`: 역할별 분리 코드와 최신 대시보드
- 실행 절차: [apps/README.md](apps/README.md)

수집기 하나가 여러 머신과 센서를 관리하며, 새 머신·센서는 등록 후 분석·전달·대시보드에 자동 반영됩니다. 확장 테스트: `apps/test_data_expanded.json`.

현재 분석은 온도 75°C 이상 또는 진동 RMS 7 mm/s 이상이면 이상으로 판정하는 규칙 방식입니다. 실제 ACME·MEC 환경의 연동 검증은 별도로 필요합니다.

환경 설정 파일, 실행 DB, 가상환경은 Git에 포함하지 않습니다.

## 시작하기

기존 ACME MN-CSE·IN-CSE가 실행 중이어야 합니다. 이미 사용하는 `session.env`가 있으면 그대로 사용하세요. 새 환경에서는 `.env.example`을 `session.env`로 복사하고 실제 주소와 CSEBase를 입력합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r apps/requirements.txt
source session.env
.venv/bin/python apps/setup_resources.py
```

각 터미널에서 `source session.env`를 실행한 뒤 분석기, 전달기, 대시보드, 수집기를 각각 실행합니다.

```bash
.venv/bin/python apps/analyzer_ae.py
.venv/bin/python apps/forwarder_ae.py
.venv/bin/python apps/dashboard.py
.venv/bin/python apps/collector_ae.py --dataset apps/test_data_expanded.json --interval 5 --replay-id dynamic01
```

대시보드: http://127.0.0.1:8090/

상세 안내의 기존 VM 경로는 자신의 clone 위치로 바꿔 사용하세요. 통합본과 분리 버전을 동시에 실행하지 마세요. 기존 통합본의 IN 포트 기본값은 8080, 분리 버전은 9090이므로 실제 주소를 환경변수로 지정하세요.

이 저장소는 보존된 통합본과 최신 분리본을 처음 등록한 것이며, 개발 당시의 모든 중간 버전·커밋 이력을 재현하지는 않습니다.

기존 버전에서 갱신할 때는 앱 4개를 중지하고 전체 `apps/` 파일을 함께 갱신하세요. 새 버전은 머신별 경로를 사용하고 기존 원본을 자동 이관하지 않습니다. 적용·JSON 센서 형식·호환성 안내는 [상세 문서](apps/README.md)를 참고하세요.

구독 알림을 켜려면 `QF_ANALYZER_NOTIFY_URL`과 `QF_FORWARDER_NOTIFY_URL`을 MN-CSE에서 도달 가능한 VM 주소로 지정하세요. 알림 모드는 30초 보완 조회를 병행합니다. 전달기는 IN의 telemetry 그룹을 자동 관리하고 대시보드는 그룹 최신값 조회를 사용합니다. 설정 예시와 폴링 호환 모드는 [apps/README.md](apps/README.md)에 있습니다.
