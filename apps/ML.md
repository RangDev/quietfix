# 머신별 Isolation Forest 분석

온도 °C, 진동 RMS mm/s, 전류 A를 입력으로 사용한다. 수집기 ID + 머신 ID마다
모델을 분리한다. 센서 종류마다 정확히 한 값이 있어야 ML 판정이 가능하다.
다른 센서는 기존 등록 구조에 남지만 ML 입력에는 포함하지 않는다.
현재값 3개를 쓰며 시간 구간 평균·변화량은 아직 추가하지 않았다.

## 실행
저장소 루트에서 기존 실행 환경을 활성화하고 session.env를 불러온다.

```bash
pip install -r apps/requirements.txt
python apps/ml_manage.py generate --dataset ml_data/normal.json --seed 42
python apps/ml_manage.py train --dataset ml_data/normal.json
python apps/ml_manage.py generate-test --dataset ml_data/test.json --seed 123
python apps/ml_manage.py evaluate --dataset ml_data/test.json
python apps/collector_ae.py --help
python apps/analyzer_ae.py
```

생성기는 collector-01 또는 QF_COLLECTOR_ID 아래 machine-01, machine-02의
정상 가동 패턴을 생성한다. 다른 ID는 --collector-id 또는 생성 코드의 프로필을
변경한다. 위 시험 파일은 기존 수집기 --dataset 인자로 재생할 수 있다.
정상 데이터 80%로 학습하고 나머지 20%로 이상 점수의 99백분위 기준을 정한다.
머신당 100개는 실행을 위한 데모 최소치이며 실제 설비의 충분한 데이터량을 뜻하지 않는다.
시험 파일은 반드시 다른 시드/실행으로 생성한다. generate-test는 정상, 조합 급변,
완만한 증가, 정상 복귀를 포함한다. 정상과 이상 라벨은 시나리오로 부여하며 기존
임계값으로 생성하지 않는다. 정지·기동은 현재 학습 범위 밖이다.

## 운영
- QF_ML_MODEL_DIR: 모델 폴더, 기본 QF_STATE_DIR/ml_models.
- QF_ML_CONSECUTIVE: 연속 이상 샘플 수, 기본 3. 실제 지연은 전송 주기에 좌우된다.
- 모델 없는 머신은 collecting_baseline으로 표시하고 임계값 감시를 유지한다.
  이 상태는 준비가 필요하다는 뜻이며, 라이브 데이터를 자동 수집·학습하지 않는다.
- 학습은 train 명령으로만 실행한다. 정상 확인된 데이터만 명시적으로 제공한다.
- 모델은 원자적으로 저장하며 다음 샘플부터 변경 파일을 읽는다. joblib은 신뢰하는
  로컬 학습 파일만 사용한다. scikit-learn 버전이 다르면 재학습한다.
- ML 판정은 머신 전체 조합에 대한 결과다. 개별 센서의 status는 기존 임계값 판정이며
  전류는 개별 임계값이 없어 unassessed다. 점수는 고장 확률이 아니다.
- 기존 75°C 또는 7mm/s 초과 경보는 즉시 유지한다. ML만으로 발생한 징후는
  연속 3회부터 abnormal이다. 정상/입력 누락/모델 없음은 연속 횟수를 초기화한다.
- 기존 처리 완료 샘플은 재분석하지 않는다. 모델 적용 후 새 샘플을 전송한다.
  전송 실패 재시도는 저장된 판정 결과를 재사용하며 같은 샘플로 횟수를 늘리지 않는다.

## 검증과 한계
시험 도구는 머신별 원시 ML 판정과 기존 임계값의 TP/FP/TN/FN, 탐지율, 오탐률을
출력한다. 연속 판정 경보 및 네트워크 전송 지연을 포함한 종단 간 성능 수치는 아니다.
단위 테스트에서 연속 경보·정상 복귀·모델 재로딩·ID 분리·미등록 머신·입력 검증을
확인한다. 실제 운전에서는 경보 시각과 이상 시작 시각을 별도로 기록해 지연을 측정한다.
단일 센서만 벗어나는 이상은 다른 센서 조합의 이상보다 놓칠 수 있으며 실제 시험에서도
탐지율 차이가 관찰되었다. 합성 데이터 성능을 실제 설비 성능이나 고장 예측으로 설명하지 않는다.
