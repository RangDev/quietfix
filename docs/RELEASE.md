# 최종 배포본 게시 안내

권장 태그: `v1.0.0-onem2m`  
권장 제목: `QuietFix v1.0.0 — oneM2M final prototype`

검증한 onem2m-only 커밋을 대상으로 GitHub Release를 작성합니다.
기존 태그가 있으면 이동하거나 덮어쓰지 말고 새 버전을 선택합니다.
이 문서가 존재한다는 사실은 실제 Release 게시 완료를 뜻하지 않습니다.

## 게시 본문

oneM2M 기반 설비 모니터링 최종 프로토타입입니다. 독립 ACME MN/IN-CSE,
AE 수집·분석·백업 관리 및 중앙 대시보드를 포함합니다. 중앙 사본은 MN에서
Mcc로 IN에 요청합니다. 머신별 Isolation Forest와 임계값 감시를 함께 사용합니다.

- 배포 절차: docs/DEPLOYMENT.md
- 검증 환경 및 결과: docs/VALIDATION.md
- 전체 실행 관리: standalone/service.py start / stop / status / logs
- 학습 모델: 정상 데이터로 명시적으로 생성. Git에 모델/DB/환경 파일 미포함
- 기본 구성: 단일 Linux 호스트 HTTP 개발 환경
- 합성 데이터 기반 검증이며 실제 설비 고장 예측 성능을 의미하지 않음
- MEC·Kubernetes·AI Agents/MCP·연합학습은 구현 범위에서 제외

## 게시 전 확인

최종 커밋을 선택하고 검증 기록을 확인합니다. 기사·영상이 게시되면 README에
실제 URL을 추가합니다. 심사자가 저장소를 열람할 수 있도록 기존 접근 권한을
확인합니다. 기본 브랜치와 공개 설정은 별도 관리 결정입니다.
