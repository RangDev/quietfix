# 배포본 정보

oneM2M 기반 설비 모니터링 프로토타입입니다. 구현 브랜치는 `onem2m-only`입니다.
독립 ACME MN/IN-CSE, AE 수집·분석·백업 관리 및 중앙 대시보드를 포함합니다.
중앙 사본 저장 요청은 MN-CSE에서 Mcc를 통해 IN-CSE로 전달됩니다.
머신별 Isolation Forest와 임계값 감시를 함께 사용합니다.

## 실행 및 검증

- [배포 절차](DEPLOYMENT.md)
- [검증 환경 및 결과](VALIDATION.md)
- 전체 실행 관리: `standalone/service.py start / stop / status / logs`
- 학습 모델: 정상 데이터로 명시적으로 생성
- 기본 구성: 단일 Linux 호스트의 loopback HTTP 개발 환경

모델·DB·환경 파일은 Git에 포함하지 않습니다.
성능 검증은 합성 데이터 기준이며 실제 설비의 고장 예측 성능을 검증하지 않았습니다.
