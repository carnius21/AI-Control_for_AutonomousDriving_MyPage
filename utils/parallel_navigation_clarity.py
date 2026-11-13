"""Migrate a live sequential run at a completed-run boundary, never mid-training."""
import argparse
import ctypes
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/navigation_clarity_v1'


def alive(pid):
    kernel=ctypes.windll.kernel32
    kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:return False
    code=ctypes.c_ulong()
    try:
        if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):raise RuntimeError('Cannot query legacy process')
        return code.value==259
    finally:kernel.CloseHandle(handle)


def main():
    p=argparse.ArgumentParser();p.add_argument('--legacy-pid',type=int,required=True);args=p.parse_args()
    marker=OUT/'legacy-publisher.active'
    if marker.exists():raise RuntimeError('Handoff already active')
    marker.write_text(str(args.legacy_pid))
    workers={}
    def start(seed):
        out=open(OUT/f'worker-{seed}.stdout.log','w',encoding='utf8');err=open(OUT/f'worker-{seed}.stderr.log','w',encoding='utf8')
        workers[seed]=subprocess.Popen([sys.executable,'-X','utf8','-m','utils.train_navigation_clarity','--seed',str(seed)],cwd=ROOT,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
        out.close();err.close()
    def state(stage,**kw):
        data=dict(stage=stage,updated=time.time(),workers={str(s):dict(pid=w.pid,exit_code=w.poll()) for s,w in workers.items()},**kw)
        (OUT/'parallel-status.json').write_text(json.dumps(data,indent=2),encoding='utf8')
    start(22);start(33);state('handoff_wait',legacy_pid=args.legacy_pid)
    while alive(args.legacy_pid):
        state('handoff_wait',legacy_pid=args.legacy_pid);time.sleep(3)
    # The old runner completes/evaluates/publishes the active run, then its hash guard
    # detects the orchestration update. Refuse to migrate if that active run is partial.
    if not (OUT/'runs/validity-11/complete.json').exists():
        state('handoff_error',reason='Legacy current run did not finish');marker.unlink();return
    marker.unlink();start(11)
    while any(w.poll() is None for w in workers.values()):
        state('parallel_running');time.sleep(5)
    stage='complete' if all(w.returncode==0 for w in workers.values()) else 'error'
    state(stage)
    (OUT/'status.json').write_text(json.dumps(dict(stage=stage,updated=time.time(),details='parallel-status.json'),indent=2),encoding='utf8')


if __name__=='__main__':main()
