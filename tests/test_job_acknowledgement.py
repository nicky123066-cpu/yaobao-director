from app import create_handler
from engine import Engine
from store import Store

def test_cancellation_is_committed_before_success_is_returned(tmp_path):
    store=Store(tmp_path,seed=False)
    project=store.new_project('取消事务验收')
    chapter=store.snapshot()['projects'][0]['chapters'][0]
    engine=Engine(store,workers=0)
    payload={'chapter_id':chapter['id'],'revision':chapter['revision'],'mode':'local'}
    parent=engine.submit(project,'episode',payload,'parent')
    child=engine.submit(project,'extract',{**payload,'parent_job_id':parent},'child')
    handler_type=create_handler(store,engine,8765)
    handler=object.__new__(handler_type)
    checked=[]
    def reply(body,*args,**kwargs):
        with store.connection() as db:
            states={row['id']:row['state'] for row in db.execute('SELECT id,state FROM jobs')}
        assert states[parent]=='CANCELED'
        assert states[child]=='CANCELED'
        checked.append(True)
    handler.reply=reply
    handler.route_mutation('POST','/api/jobs/'+parent+'/cancel',{})
    assert checked==[True]
