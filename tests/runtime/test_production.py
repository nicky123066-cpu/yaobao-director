import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from domain import uid
from engine import Engine,ffmpeg_path,run_process
from production import Production,decode_media,encode_multipart
from store import Store,Conflict,dumps

PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jXioAAAAASUVORK5CYII=')

class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(self.temp.name,seed=False)
        self.project=self.store.new_project('制作测试',premise='测试场景',episodes=1)
        self.chapter=self.store.snapshot()['projects'][0]['chapters'][0]
        self.engine=Engine(self.store);self.production=Production(self.store)
    def tearDown(self):self.temp.cleanup()
    def asset(self,name='角色甲',kind='characters',locked=False):
        identifier=uid('as_')
        with self.store.connection() as conn:conn.execute('INSERT INTO assets VALUES(?,?,?,?,?,?,?)',(identifier,self.project,kind,name,int(locked),1,dumps({'name':name,'aliases':[],'identity':'角色设定'})))
        return identifier
    def snapshot(self):return self.production.enrich(self.store.snapshot())
    def submit(self,kind,targets=None,**extra):
        payload={'chapter_id':self.chapter['id'],'revision':self.chapter['revision'],**extra}
        if targets is not None:payload['target_ids']=targets
        return self.engine.submit(self.project,kind,payload,uid('test_'))
    def run_job(self,identifier):
        job=self.engine.claim(identifier);self.engine.process_job(job)
        with self.store.connection() as conn:return dict(conn.execute('SELECT * FROM jobs WHERE id=?',(identifier,)).fetchone())

    def test_codes_remain_the_same_after_names_change_and_new_assets_arrive(self):
        first=self.asset();other=self.asset('庭院','scenes')
        self.assertEqual([a['code'] for a in self.snapshot()['projects'][0]['assets']],['R0001','C0001'])
        self.production.save_asset(first,{'revision':1,'data':{'name':'角色乙','aliases':['旧称']}})
        self.asset('另一角色')
        self.assertEqual([a['code'] for a in self.snapshot()['projects'][0]['assets']],['R0001','C0001','R0002'])

    def test_import_skips_locked_assets_and_merges_only_the_given_revision(self):
        locked=self.asset('锁定角色',locked=True);other=self.asset('可编辑角色')
        result=self.production.import_assets({'project_id':self.project,'strategy':'merge','revisions':{other:1},'assets':[{'type':'characters','name':'锁定角色','data':{'identity':'不能覆盖'}},{'type':'characters','name':'可编辑角色','data':{'appearance':'黑发'}},{'type':'props','name':'玉佩','data':{'description':'青玉'}}]})
        self.assertEqual(result,dict(created=1,updated=1,skipped=1))
        self.assertEqual(next(a for a in self.store.assets(self.project) if a['id']==locked)['data']['identity'],'角色设定')

    def test_ambiguous_import_rolls_back_the_entire_batch(self):
        self.asset('甲');self.asset('乙')
        with self.assertRaises(Conflict):self.production.import_assets({'project_id':self.project,'assets':[{'type':'props','name':'不能留下','data':{}},{'type':'characters','name':'混合角色','data':{'aliases':['甲','乙']}}]})
        self.assertEqual(len(self.store.assets(self.project)),2)

    def test_import_rejects_duplicate_aliases_before_writing(self):
        with self.assertRaises(Conflict):self.production.import_assets({'project_id':self.project,'assets':[{'type':'characters','name':'甲','data':{'aliases':['共同名']}},{'type':'characters','name':'乙','data':{'aliases':['共同名']}}]})
        self.assertFalse(self.store.assets(self.project))

    def test_reference_upload_is_local_versioned_and_preserves_locked_definition(self):
        identifier=self.asset(locked=True)
        first=self.production.add_reference(identifier,dict(revision=1,content=base64.b64encode(PNG).decode(),name='front.png',view='front'))
        self.assertEqual(first['kind'],'image')
        asset=self.snapshot()['projects'][0]['assets'][0]
        self.assertEqual(asset['revision'],2);self.assertTrue(asset['locked']);self.assertEqual(asset['media'][0]['view'],'front')
        with self.assertRaises(Conflict):self.production.add_reference(identifier,dict(revision=1,content=base64.b64encode(PNG).decode(),view='side'))
        self.assertEqual(len(self.snapshot()['projects'][0]['assets'][0]['media']),1)

    def test_upload_does_not_accept_svg_html_or_executable_disguised_as_image(self):
        for raw in [b'<svg onload="alert(1)"></svg>',b'<html>private</html>',b'MZ executable data']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):decode_media(base64.b64encode(raw).decode(),'image.png')

    def test_selection_cannot_use_another_assets_reference(self):
        first=self.asset('甲');second=self.asset('乙')
        media=self.production.add_reference(second,dict(revision=1,content=base64.b64encode(PNG).decode(),view='side'))
        with self.assertRaises(ValueError):self.production.select_reference(first,{'revision':1,'media_id':media['id']})

    def test_pending_pause_survives_a_new_engine_and_resume_keeps_the_same_job(self):
        targets=[self.asset('甲'),self.asset('乙')];job=self.submit('asset_images',targets,mode='local')
        self.production.control(job,'pause');self.assertIsNone(Engine(self.store).claim(job))
        self.assertEqual(self.snapshot()['jobs'][0]['state'],'PAUSED')
        self.production.control(job,'resume');result=self.run_job(job)
        self.assertEqual(result['state'],'SUCCEEDED');self.assertEqual(len(json.loads(result['checkpoint'])),2)

    def test_running_pause_saves_current_item_then_resume_does_not_generate_it_twice(self):
        from artwork import artwork
        targets=[self.asset('甲'),self.asset('乙')];identifier=self.submit('asset_images',targets,mode='local');calls=[]
        def drawing(variant):
            calls.append(variant)
            if len(calls)==1:self.production.control(identifier,'pause')
            return artwork(variant)
        with patch('artwork.artwork',side_effect=drawing):
            first=self.run_job(identifier);self.assertEqual(first['state'],'PAUSED');self.assertEqual(len(json.loads(first['checkpoint'])),1)
            self.production.control(identifier,'resume');second=self.run_job(identifier)
        self.assertEqual(second['state'],'SUCCEEDED');self.assertEqual(len(calls),2)
        self.assertEqual([len(a['media']) for a in self.snapshot()['projects'][0]['assets']],[1,1])

    def test_child_submitted_after_pause_is_also_paused(self):
        parent=self.submit('episode',None,mode='local')
        self.production.control(parent,'pause')
        child=self.engine.submit(self.project,'extract',{'chapter_id':self.chapter['id'],'revision':self.chapter['revision'],'parent_job_id':parent,'mode':'local'},uid('child_'))
        self.assertIsNone(self.engine.claim(child))
        self.production.control(parent,'resume');self.assertIsNotNone(self.engine.claim(child))

    def test_pause_retains_a_reserved_budget(self):
        targets=[self.asset('甲'),self.asset('乙')]
        with self.store.connection() as conn:
            c=self.store.settings();c.update(remote_enabled=True,image_price=2.5,budget=100,key_env='MANJU_API_KEY');conn.execute('UPDATE settings SET data=?',(dumps(c),))
        with patch.dict(os.environ,{'MANJU_API_KEY':'fixture-key-not-real'}):identifier=self.submit('asset_images',targets)
        self.production.control(identifier,'pause');self.assertEqual(self.store.snapshot()['reserved'],5)

    def test_local_asset_images_are_never_reported_as_ai_character_sheets(self):
        identifier=self.submit('asset_images',[self.asset()],mode='local');self.assertEqual(self.run_job(identifier)['state'],'SUCCEEDED')
        media=self.snapshot()['projects'][0]['assets'][0]['media'][0]
        self.assertEqual(media['mode'],'local');self.assertIn('非定妆图',media['name'])

    def test_uploaded_reference_requires_a_real_reference_adapter(self):
        identifier=self.asset();self.production.add_reference(identifier,dict(revision=1,content=base64.b64encode(PNG).decode(),view='front'))
        with self.store.connection() as conn:
            c=self.store.settings();c.update(remote_enabled=True,key_env='MANJU_API_KEY');conn.execute('UPDATE settings SET data=?',(dumps(c),))
        with patch.dict(os.environ,{'MANJU_API_KEY':'fixture-key-not-real'}):job=self.submit('asset_images',[identifier])
        with patch.object(self.engine,'remote',side_effect=AssertionError('Must not pretend text generation consumed a reference')):result=self.run_job(job)
        self.assertEqual(result['state'],'FAILED');self.assertIn('参考图通道',result['error'])

    def test_reference_generation_really_passes_the_local_image_as_multipart_input(self):
        identifier=self.asset();self.production.add_reference(identifier,dict(revision=1,content=base64.b64encode(PNG).decode(),view='front'))
        with self.store.connection() as conn:
            c=self.store.settings();c.update(remote_enabled=True,key_env='MANJU_API_KEY',image_reference_mode='openai_edits');conn.execute('UPDATE settings SET data=?',(dumps(c),))
        with patch.dict(os.environ,{'MANJU_API_KEY':'fixture-key-not-real'}):job=self.submit('asset_images',[identifier])
        captured=[]
        def remote(job,endpoint,data,files=None):captured.append((endpoint,data,files));return {'data':[{'b64_json':base64.b64encode(PNG).decode()}]}
        with patch.object(self.engine,'remote',side_effect=remote):result=self.run_job(job)
        self.assertEqual(result['state'],'SUCCEEDED');self.assertEqual(captured[0][0],'/images/edits');self.assertEqual(captured[0][2][0][2],PNG)
        body,mime=encode_multipart(captured[0][1],captured[0][2]);self.assertIn(PNG,body);self.assertIn('multipart/form-data',mime)
        self.assertEqual(self.snapshot()['projects'][0]['assets'][0]['media'][0]['mode'],'provider_reference')

    def test_locked_asset_data_still_rejects_definition_overwrite(self):
        identifier=self.asset(locked=True)
        with self.assertRaises(Conflict):self.production.save_asset(identifier,{'revision':1,'data':{'name':'覆盖'}})

    @unittest.skipUnless(os.name=='nt' and ffmpeg_path(),'Windows media runtime required')
    def test_imported_moving_video_is_really_composed_with_static_shots(self):
        self.chapter=self.store.update_chapter(self.chapter['id'],'1-1 日 外 庭院\n△ 云影掠过石阶。\n△ 一束阳光照亮花朵。',self.chapter['revision'])
        self.assertEqual(self.run_job(self.submit('compile'))['state'],'SUCCEEDED')
        shots=self.store.shots(self.project)
        self.assertEqual(self.run_job(self.submit('images',[s['id'] for s in shots],mode='local'))['state'],'SUCCEEDED')
        source=Path(self.temp.name)/'moving.mp4'
        run_process([ffmpeg_path(),'-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=360x640:rate=24','-t','1','-c:v','libx264','-pix_fmt','yuv420p',str(source)])
        self.production.shot_media(shots[0]['id'],{'revision':shots[0]['revision'],'name':'moving.mp4','content':base64.b64encode(source.read_bytes()).decode()})
        result=self.run_job(self.submit('export',[s['id'] for s in shots],auto_frames=True))
        self.assertEqual(result['state'],'SUCCEEDED',result['error'])
        output=json.loads(result['result']);self.assertEqual(output['qa']['video_shots'],1)
        self.assertTrue(output['source']['shots'][0]['video']);self.assertEqual(output['source']['chapter_revision'],self.chapter['revision'])
        self.assertAlmostEqual(output['qa']['duration'],8,delta=.1)
        self.assertTrue((self.store.root/'media'/Path(output['video']).name).is_file())

if __name__=='__main__':unittest.main()
