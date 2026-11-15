# LJJ 로컬 학습·평가·결과 전달

대상은 `scenarios/hv_high15000_entryprep/run.sumocfg`로 고정한다. 실행기는 이 파일과 원본 net/route를 읽으며 도로·HV 파일을 재생성하지 않는다. 기존 `python train.py`는 다른 환경이므로 이번 실험에 사용하지 않는다.

## 설치 (Windows CMD, 최초 한 번)

빈 작업 폴더에서 실행한다. Python 3.10 이상, Git이 필요하다.

```bat
git clone --branch ljj_aftermid --single-branch https://github.com/carnius21/AI-Control_for_AutonomousDriving_MyPage.git
cd AI-Control_for_AutonomousDriving_MyPage
py -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt eclipse-sumo==1.27.1 sumo-data==1.27.1
python -m pip check
git rev-parse HEAD
```

기존 공식 SUMO 설치의 `SUMO_HOME`이 있으면 사용한다. 없으면 실행기가 pip SUMO 경로를 설정한다. GPU·libsumo·과거 모델·로컬 results는 필수가 아니다. PyTorch 버전과 SUMO 버전은 기준/변경 실험에서 동일하게 유지한다.

## 첫 실행: 시간 측정

```bat
python -m utils.ljj_experiment train --mode baseline --steps 2048 --threads 2 --out results\ljj-benchmark
```

이는 속도/동작 점검이며 80만 스텝 성능 실험이 아니다. 콘솔과 `progress.json`의 실제 시간·예상 80만 시간을 확인한다. CPU 2스레드로 시작하며 다른 무거운 작업 없이 전원 연결 상태에서 측정한다. 과거 고속도로 20만=4시간을 새 고밀도 시나리오에 그대로 적용하지 않는다. 매 reset의 HV 900초 warmup 비용 때문에 특히 느릴 수 있다.

## 학습·평가·수집

```bat
python -m utils.ljj_experiment train --mode baseline --out results\ljj-baseline-s0
python -m utils.ljj_experiment eval --mode baseline --model results\ljj-baseline-s0\model.pt --count 1 --out results\ljj-baseline-s0-eval
python -m utils.ljj_experiment collect --mode baseline --model results\ljj-baseline-s0\model.pt --count 1 --out results\ljj-baseline-s0-data
```

학습 기본 예산은 정확히800000스텝, 알고리즘/HP는 `train.HPARAMS`를 사용한다(실행 장치CPU, seed0). 47관측·경로 안내·900초 warmup·AV 출발best/max·주행/삽입 한도10800초는 새 맵 배포 점검에 맞춘다. `--count 1` 평가는16경로 각1회이므로 진단일 뿐이다. 최종 평가는 `--count 20` 등으로 반복하되 시간을 먼저 측정한다. 결과 분모는 예정 사례 수이며 삽입실패·텔레포트도 성공으로 세지 않는다.

학습 중 약2만 스텝마다 `policy-실제스텝.pt`, 매 update에 `latest.pt`와 CSV를 저장한다. 최종 `model.pt`와 `complete.json`이 있어야 전체 학습 완료다. `latest.pt`는 평가할 수 있지만 optimizer/RNG까지 이어 학습하는 재개 기능은 이번 실행기에 없다. 중간 모델 평가는 실제 스텝을 기록하고 최종80만 결과와 구분한다. 기존 결과 폴더는 덮어쓰지 않는다.

모델의 manifest와 같은 `--mode`, 동일 입력 해시만 평가·수집을 허용한다. 학습/평가/수집을 동시에 띄우지 않는다. 학습 중 Git pull도 하지 않는다.

## 변경 후보: 한 범주씩

| mode | 기준 대비 변경 | 해석 |
|---|---|---|
| baseline | AV 동작 변경 없음 | 새 시나리오용 공통 실행 대조군 |
| observation | 기존 빈 입력에 경로안내 유효성, 앞차 존재, 역TTC, 필요감속도, 겹침, 차로 제한속도; 인접/동일차로 음수gap 관측 유지 | 관측 묶음의 효과. 개별 특징의 기여는 분리하지 못함 |
| action | 기존 차로변경 안전 게이트 활성화 | 규칙으로 명령을 거부하는 효과. 정책 자체가 안전을 학습했다는 증거와 구분 |
| reward | 기존 근접벌점 기준만 `2.5+속도×1.5초`로 변경 | 과거 개선 미확인 후보의 독립 재검증; 우선순위 낮음 |

변경 예시는 다음과 같다. 같은 seed/예산/평가사례를 사용한다.

```bat
python -m utils.ljj_experiment train --mode observation --out results\ljj-observation-s0
python -m utils.ljj_experiment eval --mode observation --model results\ljj-observation-s0\model.pt --count 1 --out results\ljj-observation-s0-eval
```

전체 Route는 기존 내비게이션 계산에 사용하며 안내범위300m는 고정한다. 관측 변경도 신경망47차원을 유지해 같은 seed의 초기 가중치를 맞춘다. 관측 전용 음수gap 처리는 보상/안전 검사에 적용하지 않는다. TTC/필요감속도는50m 안의 앞차 정보로 계산한 파생량이며 상수속도 가정이다. 단독으로 충돌회피를 보장하지 않는다.

보류: 연결된 모든 램프의 차량 탐색·합류 기준 투영거리·연속 횡방향 속도·방향지시등. 고가/교차도로 오인 및 현재 차선변경 모델의 횡이동 표현을 검증해야 한다. 단순 XY거리나 다른 lane_pos의 차이를 공통거리로 대체하지 않는다. 도로연장/HV 교착 가설은 과거 PDF의 맵에 대한 것이므로 새 맵에서 재현 전 적용하지 않는다.

## 데이터와 결과 전달

수집은 기존 POMDP 항목(episode/t/observation/action/reward/종료/state/next_state/감지차량)을 보존한다. JSONL의 event에 Route·seed·경로준비·램프·과속 등 기존IC 사건과 `risk_before_action`, `action_gate_enabled`를 추가한다. 원본state에는 절대좌표·속도·도로·차로 정보가 있다. NPZ는 기존 고정 배열을 유지하며 추가 사건은JSONL에서 확인한다. JSONL의 중간 next값은 기존 `iter_transitions`로 복원한다. 대량 수집 전에1에피소드 파일을 확인한다.

다음 명령으로 작은 기록만 ZIP으로 묶어 이 채팅에 첨부한다.

```bat
python -m utils.ljj_report --runs results\ljj-baseline-s0 results\ljj-baseline-s0-eval --output results\ljj-report.zip
```

벤치마크 결과부터 보낼 때는 `--runs results\ljj-benchmark`만 지정한다. 모델·TensorBoard·대용량 데이터는 ZIP에 포함하지 않는다. 실행 오류가 있으면 콘솔 오류 전문도 함께 전달한다. 수집 항목 검토에는JSONL 첫2~3개 transition만 별도 전달하면 된다. 노트북 결과는 채팅에서 자동으로 읽을 수 없으며, 전달받은 평가 수치를 확인한 뒤 [학습 기록장](ljj-learning-log.md)에 성공/실패·실제 조건을 기록한다.

## 약27시간 안의 우선순위

1. 설치·2048스텝 벤치마크·짧은 평가에 먼저 시간을 배정하고 새 환경의 속도를 확인한다.
2. 과거 속도 환산만으로도80만 두 번은약32시간이다. 4범주 각각80만 비교를27시간 안에 약속하지 않는다.
3. 사용자 선택: **같은 짧은 예산의 기준/관측 비교 우선**. 두 mode의2048스텝 벤치마크 후 남은 시간의 약60%를 학습에 배정하고, 나머지는 설치·평가·결과 전달·오류 대응에 남긴다. 두 조건의 초/스텝을 합해 학습 가용 초를 나누면 각 조건의 예산 상한이다. 초기 예상치는 학습 중 바뀔 수 있으므로 보수적으로 선택한다. 시간이 남으면 유망 조건의80만 실험은 별도 계획한다. 중간 예산 결과를80만 완료로 표시하지 않는다. 현재 실행기는 중단 후 정확한 재개를 지원하지 않으므로80만 실행을 중간 비교용 실행과 혼동하지 않는다.
4. 반드시80만 완료가 우선이면 시간 측정 후 한 조건을 선택하고, 다른 조건의80만 결과는 후속으로 남긴다. 이미 수집된1/16 결과는 과거 정책의 이전 점검이며 새 학습 대조군을 대신하지 않는다.
5. 최종 마감 전에는 평가·ZIP 전달 시간을 확보한다. 작은 표본의 개선은 잠정 결과이며 전체95%완주·5%미만 충돌 달성을 보장하지 않는다.

동일 예산의 짧은 비교 예시(시간 측정 후 `50000`을 조정):

```bat
python -m utils.ljj_experiment train --mode baseline --steps 50000 --out results\ljj-base-50k-s0
python -m utils.ljj_experiment eval --mode baseline --model results\ljj-base-50k-s0\model.pt --count 1 --out results\ljj-base-50k-s0-eval
python -m utils.ljj_experiment train --mode observation --steps 50000 --out results\ljj-obs-50k-s0
python -m utils.ljj_experiment eval --mode observation --model results\ljj-obs-50k-s0\model.pt --count 1 --out results\ljj-obs-50k-s0-eval
```

학습률/감마/클리핑 등은 그대로이며 예산만 두 조건에서 동일하게 줄인다. 하나의 seed·16회 평가에서는 관측 묶음의 효과를 잠정 비교할 수 있을 뿐, 관측이 행동/보상보다 가장 중요하다고 확정할 수 없다. 기존 timeout GAE 경계 처리도 이 실험에서 수정하지 않았으므로, 학습 정확성의 후속 검증 사항으로 남긴다.
