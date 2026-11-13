"""Independent HV departure-speed diagnostic, original demand retained."""
import concurrent.futures,shutil,xml.etree.ElementTree as ET
from utils import resume_validation as r
OUT=r.f.ROOT/'results/hv_departure_diagnostic_20261112'
def one(seed):
 r.b.torch.set_num_threads(1);r.f.OUT=OUT;r.f.state=lambda *a,**kw:None
 r.f.prepare=lambda load,hv=False:OUT/'traffic'/'run.sumocfg'
 return seed,r.f.hv_case('base',seed)
def main():
 OUT.mkdir(parents=True,exist_ok=True);d=OUT/'traffic';d.mkdir(exist_ok=True)
 source=r.OUT/'traffic_v2/base-hv'
 for n in ['network.net.xml','highway.rou.xml','run.sumocfg']:shutil.copy2(source/n,d/n)
 tree=ET.parse(d/'highway.rou.xml')
 for x in tree.getroot().findall('flow'):x.set('departSpeed','5')
 tree.write(d/'highway.rou.xml',encoding='utf8',xml_declaration=True)
 r.save(OUT/'manifest.json',dict(change='departSpeed max -> 5 m/s only',source=str(source),map_sha=r.b.digest(d/'network.net.xml'),commit=r.b.COMMIT))
 with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:results=list(pool.map(one,[1001,1002,1003]))
 r.save(OUT/'status.json',dict(stage='complete',results=results,does_not_replace_original_gate=True))
if __name__=='__main__':main()
