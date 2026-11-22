import io
import json
import zipfile
from unittest.mock import patch
import httpx
import pytest
from desktop_core import ManualEngine,pause_unfinished,serve,shutdown
from store import Store,dumps

@pytest.fixture
def project(tmp_path):
    store=Store(tmp_path,seed=False);pid=store.new_project('手动流程测试')
    chapter=store.snapshot()['projects'][0]['chapters'][0]
    chapter=store.update_chapter(chapter['id'],'第1集\n1-1 日 内 办公室\n人物：小夏\n△ 小夏推开窗户。\n',chapter['revision'])
    return store,pid,chapter

def payload(chapter,**extra):return dict(chapter_id=chapter['id'],revision=chapter['revision'],**extra)

def test_default_dynamic_video_is_jimeng_seedance_25_without_auto_generation(project):
    from model_workflow import role_config,ARK_BASE,require_capability
    store,_,_=project;config=role_config(store.settings(),'video')
    assert config['provider']=='ark' and config['provider_url']==ARK_BASE
    assert require_capability(config,'video')=='doubao-seedance-2-5-260628'
    assert config['remote_enabled'] is False and not store.snapshot()['jobs']

def test_manual_generation_requires_an_explicit_action(project):
    store,pid,ch=project;engine=ManualEngine(store,workers=0)
    with pytest.raises(ValueError,match='点击生成'):engine.submit(pid,'compile',payload(ch),'without-click')
    identifier=engine.submit(pid,'compile',payload(ch,manual_action=True),'clicked')
    engine.execute(engine.claim(identifier))
    assert len(store.shots(pid))==1
    assert [j['kind'] for j in store.snapshot()['jobs']]==['compile']

@pytest.mark.parametrize('kind,extra',[('episode',{}),('images',{'parent_job_id':'job_fake'})])
def test_automatic_pipeline_is_blocked_even_with_manual_flag(project,kind,extra):
    store,pid,ch=project;engine=ManualEngine(store,workers=0)
    with pytest.raises(ValueError,match='手动制作'):engine.submit(pid,kind,payload(ch,manual_action=True,**extra),'automatic')
    assert not store.snapshot()['jobs']

def test_reopening_pauses_unfinished_work_without_losing_uncertain_marker(project):
    store,pid,ch=project;engine=ManualEngine(store,workers=0)
    identifier=engine.submit(pid,'compile',payload(ch,manual_action=True),'clicked')
    with store.connection() as db:db.execute("UPDATE jobs SET state='RUNNING',result=? WHERE id=?",(dumps({'inflight':'unknown-provider-request'}),identifier))
    with patch.object(engine,'remote',side_effect=AssertionError('must not call provider')):
        assert pause_unfinished(store)==1
        assert engine.claim() is None
    job=store.snapshot()['jobs'][0]
    assert job['state']=='PAUSED' and job['result']['inflight']=='unknown-provider-request'

@pytest.fixture
def client(project):
    store,_,_=project;server,engine,url,_=serve(store,workers=0)
    c=httpx.Client(base_url='http://127.0.0.1:'+str(server.server_port),trust_env=False,follow_redirects=False)
    try:yield c,url,store,engine
    finally:c.close();shutdown(server,engine)

def test_desktop_authentication_and_foreign_origin_are_enforced(client):
    c,url,store,engine=client
    assert c.get('/api/state').status_code==403
    assert c.get('/desktop/open?ticket=wrong').status_code==403
    response=c.get(url)
    assert response.status_code==302 and 'HttpOnly' in response.headers['set-cookie']
    assert c.get('/api/state').status_code==200
    assert c.get('/api/state',headers={'Origin':'https://example.test'}).status_code==403

def test_http_api_cannot_launch_automatic_episode(client,project):
    c,url,store,engine=client;_,pid,ch=project;c.get(url)
    request=dict(project_id=pid,kind='episode',payload=payload(ch,manual_action=True),idempotency_key='no-auto')
    assert c.post('/api/jobs',json=request).status_code==400
    request.update(kind='extract',idempotency_key='manual-extract')
    assert c.post('/api/jobs',json=request).status_code==202
    assert len(store.snapshot()['jobs'])==1
    assert store.snapshot()['jobs'][0]['kind']=='extract'

def test_historical_automatic_task_cannot_be_resumed_from_controls(client,project):
    c,url,store,engine=client;_,pid,ch=project;c.get(url)
    identifier=engine.submit(pid,'extract',payload(ch,manual_action=True),'fixture')
    with store.connection() as db:db.execute("UPDATE jobs SET kind='episode',state='PAUSED' WHERE id=?",(identifier,))
    assert c.post('/api/jobs/'+identifier+'/resume',json={}).status_code==400
    assert c.post('/api/jobs/'+identifier+'/retry',json={}).status_code==400

def test_project_archive_includes_imported_or_generated_video(client,project):
    c,url,store,engine=client;_,pid,ch=project;c.get(url)
    identifier=engine.submit(pid,'compile',payload(ch,manual_action=True),'compile')
    engine.execute(engine.claim(identifier));shot=store.shots(pid)[0]
    path=store.root/'media/video_fixture.mp4';path.write_bytes(b'fixture-video')
    shot['video']='/media/video_fixture.mp4'
    with store.connection() as db:db.execute('UPDATE shots SET data=? WHERE id=?',(dumps(shot),shot['id']))
    response=c.get('/api/download/'+pid+'?format=zip')
    assert response.status_code==200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:assert archive.read('media/video_fixture.mp4')==b'fixture-video'
