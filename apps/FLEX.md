# FlexContainer 센서 모델과 발견

## 구현 계획

센서별 수치·단위·종류·샘플 식별자를 타입이 명시된 `qf:sensorReading` FlexContainer로 제공한다. `ty=28`, `cnd=org.quietfix.sensorReading.v1`, 라벨을 사용한 발견 결과에서 머신과 센서 목록을 구성한다. 분석기와 대시보드는 샘플 ID·시각·머신·수집기가 모두 맞는 완전한 센서 집합만 사용한다. CIN은 이력과 재전송 및 부분 갱신 중 일관성 유지용으로 보존한다.

## 구현

- `models/quietfix.fcp`: ACME에 설치할 버전 1 모델. `value`는 float, `unit`과 `sensorType`은 명시적인 문자열이다. 온도 °C, 진동 mm/s, 전류 A를 그대로 표현한다. 표준 SDT 모델이라는 주장은 하지 않는다.
- `apps/flex_model.py`: 모델 생성·갱신, 실제 FCNT 발견, 검증과 동일 샘플 결합. 과거 시각의 샘플로 최신 FCNT를 덮어쓰지 않는다.
- 수집기와 전달기가 MN/IN에 모델을 작성한다. 모델을 사용하도록 설정했는데 서버가 지원하지 않으면 오류를 표시한다. 지원되지 않는 요청을 성공으로 간주하지 않는다.
- 분석기와 대시보드가 발견한 모델을 사용한다. 과거 CIN이나 센서 갱신 중 일부만 일치하는 경우는 CIN으로 처리하여 시점을 섞지 않는다. 사용한 샘플에는 `data_model`을 표시한다.
- FCNT에 전용 ACP를 적용한다. 수집기/전달기만 해당 측의 FCNT 값을 갱신하고 분석기/대시보드는 조회한다. 기존 CNT의 UPDATE 권한을 확대하지 않는다.

## 적용

1. MN-CSE와 IN-CSE의 **각 실행 환경**에 `models/quietfix.fcp`를 설치한다. ACME 2025.11에서는 runtime base directory 아래 `init/quietfix.fcp`에 두고 재시작하면 추가 모델로 읽는다. 기존 기본 init 파일이나 설정을 교체하지 않는다. 컨테이너 환경에서는 이 파일을 영속 볼륨 또는 이미지로 배포한다. 사용 중인 버전의 추가 모델 경로를 확인한다.
2. 기존 `session.env`를 읽고 `python apps/access_control.py --apply`를 다시 실행하여 FCNT 정책을 생성한다. 초기 ACP가 없는 AE의 첫 정책 연결은 AE 소유자 신원으로 수행하고, 이후 변경은 ACP의 관리자 PVS를 사용한다. 인증을 적용한 환경은 해당 AE 소유자의 초기 설정 권한도 필요하다.
3. 워커와 대시보드 환경에 다음을 지정하고 기존 명령으로 재시작한다.

```bash
export QF_FLEX_ENABLED=1
export QF_ACP_ENABLED=1
```

기존 JSON과 판정 조건은 변경하지 않는다. 과거 머신에 대한 FCNT는 수집기 또는 중앙 이력 전달이 새로 수행될 때 생성된다. 기존 완료 체크포인트는 재전송을 막으므로, 과거 데이터 전체를 새 모델로 이관하려면 별도 상태 디렉터리에서 재처리한다. 현재 설정은 기본 OFF이며 되돌릴 때는 `QF_FLEX_ENABLED=0`으로 앱을 재시작한다. 생성된 FCNT는 남으며 기존 CIN을 삭제하지 않는다.

## 검증

```bash
python -m unittest discover -s tests -v
# 별도 개발 환경에 acmecse==2025.11과 프로젝트 의존성을 설치한 뒤
QF_RUN_LIVE_ACME=1 python -m unittest discover -s tests -p test_live_acme.py -v
```

라이브 테스트는 사용자 서버 대신 임시 디렉터리와 사용 가능한 로컬 포트를 사용하는 독립된 메모리 ACME 두 개를 실행하고 종료한다. ACME 2025.11에서 네 머신의 센서 모델 생성·갱신, cnd 질의 발견, 분석과 중앙 복제, 실제 그룹 fan-out과 대시보드 조회가 통과했다. 분석기와 대시보드의 FCNT UPDATE는 HTTP 403으로 거부되었다. 단위 불일치 센서는 기존처럼 미평가 처리한다.

단위 테스트는 모델 스키마, 시각 역행 방지, 불완전·다른 샘플 결합 방지, 명시적 ACP, 쿼리 파라미터와 기존 데이터 호환성을 검증한다. 사용자 Sandbox의 실제 ACME 버전에는 모델 설치 후 별도 실행 확인이 필요하다.

## 참고

- ACME FlexContainer 예제와 모델 형식: https://github.com/ankraft/ACME-oneM2M-CSE/blob/master/tests/testFCNT.py
- 추가 모델 설치: https://acmecse.net/help/FAQ/
