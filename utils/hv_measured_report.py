"""Publish compact measured-envelope results; require every run to finish."""
import csv
import json
from pathlib import Path
from utils.hv_measured_traffic import ROOT, OUT

def main():
    status=json.loads((OUT/'status.json').read_text())
    assert status['stage']=='complete',status
    records=[];routes=[]
    for p in sorted((OUT/'runs').glob('*/complete.json')):
        d=json.loads(p.read_text());r=list(d['routes'].values());n=sum(v['planned'] for v in r)
        arrived=sum(v['arrived'] for v in r)
        samples=json.loads((p.parent/'samples.json').read_text())
        row=dict(case=d['mode'],seed=d['seed'],planned=n,inserted=sum(v['inserted'] for v in r),arrived=arrived,
            arrival_pct=100*arrived/n,collisions=d['collisions'],teleports=d['teleports'],pending=len(d['pending']),active=len(d['leftovers']),
            peak_pending=max(s['pending'] for s in samples),peak_stopped=max(s['stopped'] for s in samples),
            mean_depart_delay=sum(v['arrived']*v['mean_depart_delay'] for v in r)/max(1,arrived),
            mean_wait=sum(v['arrived']*v['mean_wait'] for v in r)/max(1,arrived),ended=d['ended'],passed=d['passed'],run=str(p.parent.relative_to(ROOT)))
        records.append(row)
        for k,v in d['routes'].items():routes.append(dict(case=d['mode'],seed=d['seed'],route=k,**v))
    assert len(records)==18
    for name,data in [('road-hourly-hv-results',records),('road-hourly-hv-routes',routes)]:
        with (ROOT/f'docs/experiments/{name}-20261113.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    text='\n### 최종 실측 범위 시험 결과 (18회)\n\n| 조건 | 유입 계획/회 | 2시간 내 도착률 | 충돌 | 종료 시 미투입 | 종료 시 도로 내 잔류 | 평균 진입 지연(초) | 통과 |\n|---|---:|---:|---:|---:|---:|---:|---:|\n'
    def rng(a,key,dec=0):
        vs=[v[key] for v in a];lo,hi=min(vs),max(vs)
        return f'{lo:,.{dec}f}' if lo==hi else f'{lo:,.{dec}f}–{hi:,.{dec}f}'
    for mode in ['night_low','night_high','morning_low','morning_high','evening_low','evening_high']:
        a=[r for r in records if r['case']==mode]
        text+=f"| {mode} | {a[0]['planned']:,} | {rng(a,'arrival_pct',2)}% | {rng(a,'collisions')} | {rng(a,'pending')} | {rng(a,'active')} | {rng(a,'mean_depart_delay',1)} | {sum(r['passed'] for r in a)}/3 |\n"
    text+='\n모든 조건은 1시간 유입 후 최대 1시간 추가 배출 관찰이다. 도착률의 분모는 **계획 차량 수**로, 미투입도 제외하지 않았다. 평균 진입 지연/정지 시간은 도착 차량 기준이며 미완료 차량은 별도 열로 표시한다. 유량 범위로 만든 가정 시나리오이므로 실제 도로의 완주율·사고율로 해석하지 않는다.\n\n[실행별 상세 CSV](road-hourly-hv-results-20261113.csv), [16경로별 상세 CSV](road-hourly-hv-routes-20261113.csv). seed 6101/6102/6103. 입력과 실행 코드 해시는 각 로컬 manifest 참조.\n'
    p=ROOT/'docs/experiments/ic-measured-traffic-20261113.md';s=p.read_text(encoding='utf8');s=s.split('\n### 최종 실측 범위 시험 결과')[0];p.write_text(s+text,encoding='utf8')
    print(text)
if __name__=='__main__':main()
