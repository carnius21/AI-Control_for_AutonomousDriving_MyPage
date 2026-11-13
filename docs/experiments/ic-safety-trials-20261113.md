# 충돌 진단 후 보상 독립 비교

상태: planned_trials_complete

기존 저수요800k 결과를 대조군으로 보존한다. 동일한 무교통 조합600064 가중치(seed11/22/33)에서 다시 시작하며 optimizer 새 초기화, 각800k, 맵/교통/관측47/행동/PPO 고정. 강제보정 없음.
GAP15: 기존 고정6m 근접 기준만 2.5+속도×1.5초로 변경. 기존0.1벌점 유지. COLLISION20: 충돌벌점만5→20. 두항목을 섞지 않음.
사전 관측검사→각2048스텝 실행검증→6개독립 학습→10만마다320회평가→경로별분석→보고서순으로 자동진행. 모델선택/후속수요 진행은 결과확인전 하지않음. ZIP/기본수요실패는 미해결로 유지.

|실험|평가|완주|충돌|경로별통과|
|---|---|---:|---:|---|
|COLLISION20-11|eval-100352.summary|85/320|213|False|
|COLLISION20-11|eval-200704.summary|74/320|183|False|
|COLLISION20-11|eval-301056.summary|55/320|213|False|
|COLLISION20-11|eval-401408.summary|55/320|205|False|
|COLLISION20-11|eval-501760.summary|43/320|162|False|
|COLLISION20-11|eval-600064.summary|66/320|94|False|
|COLLISION20-11|eval-700416.summary|42/320|63|False|
|COLLISION20-11|eval-800000.summary|63/320|135|False|
|COLLISION20-11|evaluation.summary|63/320|135|False|
|COLLISION20-11|initial-eval.summary|66/320|253|False|
|COLLISION20-22|eval-100352.summary|59/320|121|False|
|COLLISION20-22|eval-200704.summary|89/320|172|False|
|COLLISION20-22|eval-301056.summary|39/320|119|False|
|COLLISION20-22|eval-401408.summary|61/320|161|False|
|COLLISION20-22|eval-501760.summary|21/320|111|False|
|COLLISION20-22|eval-600064.summary|13/320|108|False|
|COLLISION20-22|eval-700416.summary|14/320|139|False|
|COLLISION20-22|eval-800000.summary|0/320|78|False|
|COLLISION20-22|evaluation.summary|0/320|78|False|
|COLLISION20-22|initial-eval.summary|67/320|253|False|
|COLLISION20-33|eval-100352.summary|79/320|94|False|
|COLLISION20-33|eval-200704.summary|13/320|147|False|
|COLLISION20-33|eval-301056.summary|18/320|164|False|
|COLLISION20-33|eval-401408.summary|9/320|164|False|
|COLLISION20-33|eval-501760.summary|0/320|43|False|
|COLLISION20-33|eval-600064.summary|0/320|34|False|
|COLLISION20-33|eval-700416.summary|0/320|43|False|
|COLLISION20-33|eval-800000.summary|0/320|6|False|
|COLLISION20-33|evaluation.summary|0/320|6|False|
|COLLISION20-33|initial-eval.summary|66/320|254|False|
|GAP15-11|eval-100352.summary|55/320|133|False|
|GAP15-11|eval-200704.summary|39/320|158|False|
|GAP15-11|eval-301056.summary|49/320|130|False|
|GAP15-11|eval-401408.summary|39/320|181|False|
|GAP15-11|eval-501760.summary|60/320|131|False|
|GAP15-11|eval-600064.summary|85/320|119|False|
|GAP15-11|eval-700416.summary|80/320|129|False|
|GAP15-11|eval-800000.summary|82/320|107|False|
|GAP15-11|evaluation.summary|82/320|107|False|
|GAP15-11|initial-eval.summary|66/320|253|False|
|GAP15-22|eval-100352.summary|42/320|170|False|
|GAP15-22|eval-200704.summary|101/320|189|False|
|GAP15-22|eval-301056.summary|114/320|194|False|
|GAP15-22|eval-401408.summary|97/320|139|False|
|GAP15-22|eval-501760.summary|82/320|171|False|
|GAP15-22|eval-600064.summary|146/320|140|False|
|GAP15-22|eval-700416.summary|131/320|96|False|
|GAP15-22|eval-800000.summary|98/320|150|False|
|GAP15-22|evaluation.summary|98/320|150|False|
|GAP15-22|initial-eval.summary|67/320|253|False|
|GAP15-33|eval-100352.summary|87/320|118|False|
|GAP15-33|eval-200704.summary|86/320|84|False|
|GAP15-33|eval-301056.summary|76/320|81|False|
|GAP15-33|eval-401408.summary|45/320|178|False|
|GAP15-33|eval-501760.summary|62/320|144|False|
|GAP15-33|eval-600064.summary|85/320|95|False|
|GAP15-33|eval-700416.summary|60/320|73|False|
|GAP15-33|eval-800000.summary|41/320|129|False|
|GAP15-33|evaluation.summary|41/320|129|False|
|GAP15-33|initial-eval.summary|66/320|254|False|
|smoke-COLLISION20-11|eval-2048.summary|57/320|245|False|
|smoke-COLLISION20-11|evaluation.summary|57/320|245|False|
|smoke-GAP15-11|eval-2048.summary|72/320|248|False|
|smoke-GAP15-11|evaluation.summary|72/320|248|False|
