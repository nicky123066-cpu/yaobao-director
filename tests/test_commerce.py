import io,json,uuid
from pathlib import Path
import pytest
from commerce import Commerce,command,probe
from desktop_core import ManualEngine
from engine import ffmpeg_path
from store import Store,Conflict

@pytest.fixture
def work(tmp_path):
 store=Store(tmp_path,seed=False);return store,Commerce(store),ManualEngine(store,workers=0)

def goods(**changes):
 return dict(name='测试保温杯',selling_points='500毫升，杯盖可拆洗',price='59元',audience='日常随身饮水',cta='查看商品规格',mode='real',ratio='9:16',duration=3,start=0,media_ids=[],**changes)

@pytest.fixture
def media(work,tmp_path):
 store,commerce,engine=work;ffmpeg=ffmpeg_path()
 if not ffmpeg:pytest.skip('FFmpeg required for media acceptance')
 source=tmp_path/'source.mp4'
 command([ffmpeg,'-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=640x360:rate=24','-f','lavfi','-i','sine=frequency=880:sample_rate=24000','-t','4','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(source)])
 with source.open('rb') as stream:item=commerce.upload(stream,source.stat().st_size,'真人素材.mp4')
 return item

def test_draft_persistence_and_no_automatic_generation(work):
 store,commerce,engine=work;first=commerce.save(goods());assert first['revision']==1
 assert Commerce(Store(store.root,seed=False)).get(first['id'])==first
 assert not store.snapshot()['jobs']
 with pytest.raises(Conflict):commerce.save({**first,'revision':0})
 with pytest.raises(ValueError):commerce.save({**goods(),'duration':float('nan')})
 assert len(commerce.summary()['drafts'])==1

def test_outline_uses_only_provided_product_facts(work):
 _,commerce,_=work
 result=commerce.script({'name':'杯子','selling_points':'可拆洗杯盖'})
 assert '可拆洗杯盖' in result['script'] and '59' not in result['script'] and '全网' not in result['script']
 assert result['mode']=='本地资料整理，未调用模型'

def test_avatar_is_not_downgraded_to_fake_talking_video(work):
 _,commerce,engine=work;draft=commerce.save({**goods(),'mode':'avatar'})
 with pytest.raises(ValueError,match='数字人'):engine.submit(draft['id'],'commerce',{'manual_action':True,'revision':1},'avatar-test')

def test_upload_rejects_nonmedia_and_traversal_reference(work):
 _,commerce,_=work
 with pytest.raises(ValueError):commerce.upload(io.BytesIO(b'<html>unsafe</html>'),19,'a.mp4')
 with pytest.raises(ValueError):commerce.media('../../secret')
 assert not commerce.summary()['media']

def test_real_video_preserves_audio_and_output_dimensions(work,media):
 store,commerce,engine=work
 draft=commerce.save({**goods(),'media_ids':[media['id']],'subtitles':'商品规格请核对'})
 with pytest.raises(ValueError,match='点击生成'):engine.submit(draft['id'],'commerce',{'revision':1},'not-manual')
 payload={'manual_action':True,'revision':1};jid=engine.submit(draft['id'],'commerce',payload,'real-export')
 assert engine.submit(draft['id'],'commerce',payload,'real-export')==jid
 engine.process_job(engine.claim(jid));job=next(j for j in store.snapshot()['jobs'] if j['id']==jid)
 assert job['state']=='SUCCEEDED',job.get('error')
 result=job['result'];info=probe(store.root/'media'/Path(result['video']).name)
 assert info['audio'] and abs(info['duration']-3)<.2
 assert result['qa']['audio']=='保留真人原声' and result['qa']['width']==1080 and result['qa']['height']==1920
 assert result['qa']['avatar_generated'] is False

def test_stale_export_is_rejected_without_publishing_a_video(work,media):
 store,commerce,engine=work;draft=commerce.save({**goods(),'media_ids':[media['id']]})
 jid=engine.submit(draft['id'],'commerce',{'manual_action':True,'revision':1},'stale-export')
 commerce.save({**draft,'price':'65元'})
 engine.process_job(engine.claim(jid))
 job=next(j for j in store.snapshot()['jobs'] if j['id']==jid)
 assert job['state']=='FAILED' and not job['result'].get('video')

def test_source_time_bounds_are_checked_before_queueing(work,media):
 _,commerce,engine=work;draft=commerce.save({**goods(),'media_ids':[media['id']],'duration':5})
 with pytest.raises(ValueError,match='时长不足'):engine.submit(draft['id'],'commerce',{'manual_action':True,'revision':1},'too-long')
