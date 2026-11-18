# 수집기 oneM2M MQTT 바인딩

## 구현 계획

수집기와 MN-CSE 사이에 oneM2M TS-0010 JSON 요청·응답 바인딩을 추가한다. 센서 JSON을 임의의 MQTT 토픽에 발행하고 별도 브리지가 HTTP로 옮기는 구조가 아니다. ACME가 직접 MQTT 요청 primitive를 처리한다. 분석기·전달기·대시보드는 기존 HTTP를 유지한다.

지속 연결과 QoS 1을 사용하되, MQTT 발행 성공이나 PUBACK만으로 데이터 저장 성공으로 판단하지 않는다. 상관 ID `rqi`가 맞는 CSE의 최종 oneM2M 응답을 기다린다. 단절과 타임아웃은 기존 수집기 재시도·영속 outbox로 처리하며 HTTP로 자동 전환하지 않는다.

## 구현

- `mqtt_client.py`: 연결, SUBACK 확인, 요청 primitive 작성, 응답 토픽과 rqi 검사, oneM2M RSC 오류 변환, 타임아웃과 재연결·재구독. `paho-mqtt==2.1.0` 사용.
- `onem2m_client.collector_client()`: 명시적인 프로토콜 선택. 적응형 수집기가 반복 호출해도 MQTT 연결을 재사용하며 종료 시 연결을 닫는다.
- 기존 `ensure`, `put`, CIN 충돌 확인 등의 로직을 두 바인딩이 공유한다. 동일 sample_id 재전송은 같은 CIN 이름을 사용한다.
- MQTT 모드는 사전 AE 등록과 ACP 모드를 요구한다. MQTT 연결 중 관리자/다른 Originator로 신원을 바꾸는 요청은 허용하지 않는다.
- 응답 토픽은 `/oneM2M/resp/<AE-ID>/<CSE-ID>/json`, 요청은 `/oneM2M/req/<AE-ID>/<CSE-ID>/json`이다. ID에서 선행 `/`는 제거하고 내부 `/`는 `:`로 치환한다. 설정한 topicPrefix가 있으면 앞에 붙인다.

## 서버와 브로커 준비

1. MQTT 브로커를 배치하고 수집기와 MN-CSE 양쪽에서 접근 가능한 주소를 준비한다. ACME 자체가 브로커는 아니다.
2. MN-CSE에서 MQTT 바인딩을 켜고 같은 브로커에 연결한다. 다음은 검증한 ACME 2025.11 설정의 예시다. 실제 호스트와 포트로 바꾸고 재시작한다.

```ini
[mqtt]
enable=true
address=127.0.0.1
port=1883
```

컨테이너 안의 127.0.0.1은 그 컨테이너 자신이므로, 외부 브로커라면 실제로 접근 가능한 서비스 이름 또는 IP를 사용한다. 설치한 ACME 버전의 설정 이름과 MQTT 지원 여부를 확인한다.

3. 기존 관리자 HTTP 경로로 `python apps/access_control.py --apply`를 실행해 AE와 ACP를 준비한다. FlexContainer를 함께 사용한다면 양쪽 CSE에 모델을 먼저 설치한다.
4. `pip install -r apps/requirements.txt`로 의존성을 설치한다.

## 수집기 실행

기존 session.env를 읽은 뒤 **수집기 터미널**에 다음을 설정한다.

```bash
export QF_ACP_ENABLED=1
export QF_COLLECTOR_PROTOCOL=mqtt
export QF_MQTT_URL=mqtt://BROKER_HOST:1883
export QF_MQTT_CSE_ID=/ACTUAL_MN_CSE_ID
# 모델을 설치한 경우에만 추가
export QF_FLEX_ENABLED=1
python apps/collector_ae.py --dataset test_data/test_data_expanded.json --mode replay --cycles 1 --interval 0.1 --replay-id mqtt-demo
```

`QF_MQTT_CSE_ID`는 CSEBase의 실제 `csi` 값이다. 리소스 이름인 MN_BASE나 IP 주소가 아니다. 관리자 설정은 HTTP이고 실행 중 수집기의 CSE 요청은 MQTT다. 분석기·전달기·대시보드는 기존 실행 명령을 사용한다. 데이터 파일과 규칙 및 sample_id 형식은 바뀌지 않는다. 이전에 완료한 replay-id를 다시 쓰면 기존 체크포인트 때문에 전송을 건너뛸 수 있다.

HTTP로 돌아가려면 `QF_COLLECTOR_PROTOCOL=http`로 바꾸고 수집기를 재시작한다. 기본값은 HTTP다. 브로커 설정만 바꾼다고 실행 중인 프로세스의 환경변수가 바뀌지는 않는다.

## 인증과 TLS

원격 운영 브로커에는 사용자 인증과 토픽 ACL 및 TLS를 적용한다. `mqtts://HOST:8883`은 인증서 검증을 사용하고 필요하면 QF_MQTT_CA_FILE로 CA를 지정한다. 사용자명과 비밀번호는 URL에 넣지 않고 QF_MQTT_USERNAME과 QF_MQTT_PASSWORD로 제공한다. 저장소에는 실제 자격증명을 기록하지 않는다.

브로커 ACL은 수집기가 자기 요청 토픽에만 쓰고 자기 응답 토픽만 읽도록 제한한다. CSE는 자신의 요청·응답·등록 토픽에 필요한 권한을 가져야 한다. CSE 측 인증 설정도 별도로 구성한다. Originator 문자열과 ACP만으로 발신자의 신원 인증이 완성되는 것은 아니다. 이번 로컬 통합 검증은 loopback의 익명 브로커를 사용했으며 실제 인증·TLS 브로커 운영을 검증했다고 주장하지 않는다.

## 검증

일반 테스트:

```bash
python -m unittest discover -s tests -v
```

별도의 개발 환경에 ACME 2025.11, amqtt 0.11.3과 프로젝트 의존성을 설치하면 다음 시험은 실제 브로커와 두 ACME를 임시 포트·메모리 DB로 실행한다. 사용자 서버를 변경하지 않는다.

```bash
QF_RUN_LIVE_ACME=1 QF_RUN_MQTT=1 python -m unittest discover -s tests -p test_live_acme.py -v
```

확인 항목:

- 실제 oneM2M MQTT CREATE/RETRIEVE/UPDATE와 검색 파라미터 매핑
- 네 머신의 FlexContainer·CIN 저장 후 HTTP 분석·전달·그룹 조회·대시보드 표시
- 동일 데이터 재전송 시 CIN 중복 없음
- MQTT 저장으로 생성된 CIN의 실제 HTTP 구독 알림 수신
- 수집기의 분석 결과 생성 요청은 HTTP 호환 오류 403으로 변환
- 브로커 중단 시 타임아웃, 재시작 후 자동 재연결·재구독 및 정상 요청 복구
- 잘못된 응답 토픽·rqi·신원 무시, PUBACK만으로 성공 처리하지 않음, HTTP 모드 호환

사용자 VM에는 코드 배포 후 브로커와 ACME MQTT 설정을 적용하고 같은 경로를 별도로 검증해야 한다. 통신량·전력·지연 개선 수치는 측정하지 않았으며, 지속 연결이 유리한 수집기 구간에 MQTT를 선택했다는 설계 근거와 실제 동작을 평가 자료로 제시한다.

## 참고

- oneM2M MQTT primitive mapping: https://specifications.onem2m.org/ts/ts-0010/latest/6.5/
- ACME MQTT binding: https://github.com/ankraft/ACME-oneM2M-CSE/blob/master/acmecse/plugins/bindings/MQTTClient.py
