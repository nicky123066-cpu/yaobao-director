import base64,json,os,unittest
from unittest.mock import patch
import test_production as fixtures
PNG=fixtures.PNG
from domain import prompt_for
from store import Conflict

class DirectorToolsTests(unittest.TestCase):
    setUp=fixtures.ProductionTests.setUp
    tearDown=fixtures.ProductionTests.tearDown
    asset=fixtures.ProductionTests.asset
    snapshot=fixtures.ProductionTests.snapshot
    submit=fixtures.ProductionTests.submit
    run_job=fixtures.ProductionTests.run_job
    def compile(self):
        self.chapter=self.store.update_chapter(self.chapter['id'],'1-1 日 外 庭院\n△ 风吹过树梢。\n△ 日光洒落。',self.chapter['revision'])
        self.run_job(self.submit('compile'));return self.store.shots(self.project)
    def batch(self,shots,values,**extra):
        return self.production.batch_shots(dict(project_id=self.project,chapter_id=self.chapter['id'],shot_ids=[s['id'] for s in shots],revisions={s['id']:s['revision'] for s in shots},values=values,**extra))
    def test_batch_changes_all_selected_and_marks_new_camera_stale(self):
        shots=self.compile();self.batch(shots,{'camera':'环绕升降','duration':6.5})
        self.assertTrue(all(s['camera']=='环绕升降' and s['duration']==6.5 and s['asset_changed'] and s['revision']==2 for s in self.store.shots(self.project)))
    def test_conflicting_last_shot_rolls_back_first_shot(self):
        shots=self.compile();self.batch([shots[-1]],{'duration':7})
        with self.assertRaises(Conflict):self.batch(shots,{'duration':9})
        self.assertEqual([s['duration'] for s in self.store.shots(self.project)],[4,7])
    def test_cross_project_batch_rolls_back(self):
        shots=self.compile();other=self.store.new_project('另一项目')
        body=dict(project_id=other,chapter_id=self.chapter['id'],shot_ids=[shots[0]['id']],revisions={shots[0]['id']:1},values={'duration':8})
        with self.assertRaises(ValueError):self.production.batch_shots(body)
        self.assertEqual(self.store.shots(self.project)[0]['duration'],4)
    def test_prompt_templates_persist_and_require_revision_for_overwrite(self):
        body=dict(project_id=self.project,name='一致性',body='服装与空间保持连续')
        result=self.production.template(body);template=self.snapshot()['projects'][0]['prompt_templates'][0]
        self.assertEqual(template['id'],result['id'])
        with self.assertRaises(Conflict):self.production.template({**body,**result, 'revision':0})
        self.production.template({**body,**result,'revision':1,'body':'新版约束'})
        self.assertEqual(self.snapshot()['projects'][0]['prompt_templates'][0]['revision'],2)
    def test_applied_prompt_keeps_source_and_enters_provider_prompt(self):
        shots=self.compile();original=shots[0]['action'];self.batch([shots[0]],{'prompt_override':'镜头沿地面推进'})
        shot=self.store.shots(self.project)[0]
        self.assertEqual(shot['action'],original);self.assertIn('镜头沿地面推进',prompt_for(shot,[]));self.assertEqual(shot['source_line_ids'],shots[0]['source_line_ids'])
    def test_video_only_shot_can_be_reviewed(self):
        shots=self.compile();shot=shots[0];shot['video']='/media/fixture.mp4'
        self.assertEqual(self.production.edit_shot(shot,{'status':'已定稿'})['status'],'已定稿')
    def test_stale_content_cannot_be_approved(self):
        shots=self.compile();shot=shots[0];shot.update(image='/api/art/0.svg',image_versions=[{'url':'/api/art/0.svg'}],asset_changed=True)
        with self.assertRaises(ValueError):self.production.edit_shot(shot,{'status':'已定稿'})
    def test_queued_image_edit_is_rejected_before_provider_charge(self):
        shots=self.compile();job=self.submit('images',[shots[0]['id']],mode='local');self.batch([shots[0]],{'duration':7})
        with patch.object(self.engine,'remote',side_effect=AssertionError('No stale paid request')):result=self.run_job(job)
        self.assertEqual(result['state'],'FAILED');self.assertIn('排队期间',result['error'])

    def test_overlapping_queued_or_paused_targets_cannot_be_dispatched_twice(self):
        shots=self.compile();job=self.submit('images',[shots[0]['id']],mode='local')
        with self.assertRaises(Conflict):self.submit('images',[shots[0]['id']],mode='local')
        self.production.control(job,'pause')
        with self.assertRaises(Conflict):self.submit('images',[shots[0]['id']],mode='local')
        self.assertTrue(self.submit('images',[shots[1]['id']],mode='local'))

    def test_unknown_provider_result_blocks_a_new_job_with_a_new_idempotency_key(self):
        shots=self.compile();job=self.submit('images',[shots[0]['id']],mode='local')
        with self.store.connection() as conn:conn.execute("UPDATE jobs SET state='FAILED',result=? WHERE id=?",(json.dumps({'inflight':{'request':'unresolved'}}),job))
        with self.assertRaises(Conflict):self.submit('images',[shots[0]['id']],mode='local')

    def test_saving_unchanged_asset_links_does_not_invalidate_a_shot(self):
        shots=self.compile();result=self.production.shot_assets(shots[0]['id'],{'revision':1,'asset_ids':shots[0]['asset_ids']})
        self.assertFalse(result['changed']);self.assertEqual(self.store.shots(self.project)[0]['revision'],1)
    def test_shot_generation_sends_actual_reference_bytes_and_prompt(self):
        shots=self.compile();asset=self.asset();self.production.add_reference(asset,dict(revision=1,content=base64.b64encode(PNG).decode(),view='front'))
        self.production.shot_assets(shots[0]['id'],{'revision':1,'asset_ids':[asset]});shot=self.store.shots(self.project)[0]
        self.batch([shot],{'prompt_override':'缓慢推进保持服装一致'})
        with self.store.connection() as conn:
            config=self.store.settings();config.update(remote_enabled=True,image_model='fixture-image',key_env='MANJU_API_KEY',image_reference_mode='openai_edits');conn.execute('UPDATE settings SET data=?',(json.dumps(config),))
        with patch.dict(os.environ,{'MANJU_API_KEY':'fixture-not-real'}):job=self.submit('images',[shot['id']])
        captured=[]
        def remote(job,endpoint,body,files=None):captured.append((endpoint,body,files));return {'data':[{'b64_json':base64.b64encode(PNG).decode()}]}
        with patch.object(self.engine,'remote',side_effect=remote):result=self.run_job(job)
        self.assertEqual(result['state'],'SUCCEEDED',result['error']);self.assertEqual(captured[0][0],'/images/edits');self.assertEqual(captured[0][2][0][2],PNG);self.assertIn('保持服装一致',captured[0][1]['prompt'])
