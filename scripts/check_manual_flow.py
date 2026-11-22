"""Exercise each manual stage separately with local resources, no remote API."""
import json
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
os.environ['MANJU_RUNTIME_ROOT']=str(ROOT/'runtime')
sys.path[:0]=[str(ROOT),str(ROOT/'runtime')]
from store import Store
from desktop_core import ManualEngine

def main():
    (ROOT/'validation').mkdir(exist_ok=True)
    workspace=ROOT/'.build'/('manual-flow-'+str(int(time.time())))
    store=Store(workspace,seed=False);pid=store.new_project('手动制作流程本地核验','9:16')
    chapter=store.snapshot()['projects'][0]['chapters'][0]
    chapter=store.update_chapter(chapter['id'],'第1集\n1-1 日 内 办公室\n人物：小夏\n△ 小夏走到窗边。\n[00:04] 小夏（自然）：开始拍摄吧。\n',chapter['revision'])
    engine=ManualEngine(store,workers=0);stages=[]
    for kind in ['extract','compile','images','voices','export']:
        before=len(store.snapshot()['jobs'])
        body={'chapter_id':chapter['id'],'revision':chapter['revision'],'manual_action':True,'mode':'local'}
        if kind=='images':body['native_images']=True
        if kind=='export':body['auto_frames']=True
        jid=engine.submit(pid,kind,body,'manual-local-'+kind)
        engine.process_job(engine.claim(jid))
        snapshot=store.snapshot();job=next(j for j in snapshot['jobs'] if j['id']==jid)
        assert job['state']=='SUCCEEDED',(kind,job.get('error'))
        assert len(snapshot['jobs'])==before+1,'A following stage was automatically queued'
        stages.append({'kind':kind,'state':job['state'],'following_stage_not_started':True})
    output=job['result'];path=workspace/'media'/Path(output['video']).name
    assert path.is_file() and path.stat().st_size>1024
    report={'manual_local_flow_passed':True,'stages':stages,'output':str(path),'qa':output['qa'],'remote_calls':0,'video_generation_tested':False}
    (ROOT/'validation/manual-local-flow.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
