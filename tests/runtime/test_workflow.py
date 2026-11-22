import base64
import io
import json
import os
import struct
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import wave
import zlib
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from app import create_handler
from domain import parse_script
from engine import Engine, ffmpeg_path
from store import Conflict, Store, dumps


def png_frame():
    def chunk(kind, data):
        return struct.pack(">I", len(data))+kind+data+struct.pack(">I", zlib.crc32(kind+data)&0xffffffff)
    return b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",720,1280,8,2,0,0,0))+chunk(b"IDAT",zlib.compress((b"\0"+bytes([82,116,142])*720)*1280))+chunk(b"IEND",b"")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(self.temp.name,seed=False)
        self.project=self.store.new_project("验收样片")
        self.chapter=self.store.snapshot()["projects"][0]["chapters"][0]
        self.chapter=self.store.update_chapter(self.chapter["id"],"第1集\n1-1 日 外 花园\n人物：小夏\n[00:00] 小夏（平静）：你好，世界。\n",1)
        self.engine=Engine(self.store,workers=0)

    def tearDown(self):
        self.temp.cleanup()

    def submit(self,kind,**extra):
        return self.engine.submit(self.project,kind,{"chapter_id":self.chapter["id"],"revision":self.chapter["revision"],**extra},kind+str(time.time_ns()))

    def execute(self,kind,**extra):
        job_id=self.submit(kind,**extra);job=self.engine.claim();self.assertEqual(job["id"],job_id);self.engine.execute(job)
        return next(j for j in self.store.snapshot()["jobs"] if j["id"]==job_id)

    def test_revision_conflict_preserves_edits(self):
        self.store.update_chapter(self.chapter["id"],self.chapter["body"]+"△ 风起\n",2)
        with self.assertRaises(Conflict):self.store.update_chapter(self.chapter["id"],"过期正文",2)
        self.assertIn("风起",self.store.chapter(self.chapter["id"])["body"])

    def test_versions_and_invalidation(self):
        self.execute("compile")
        self.store.update_chapter(self.chapter["id"],self.chapter["body"].replace("世界","朋友"),2)
        self.assertTrue(all(s["stale"] for s in self.store.shots(self.project)))
        with self.store.connection() as conn:self.assertEqual(conn.execute("SELECT COUNT(*) FROM versions WHERE chapter_id=?",(self.chapter["id"],)).fetchone()[0],3)

    def test_idempotent_submission_and_mismatched_payload(self):
        payload={"chapter_id":self.chapter["id"],"revision":2}
        a=self.engine.submit(self.project,"compile",payload,"same-key")
        b=self.engine.submit(self.project,"compile",payload,"same-key")
        self.assertEqual(a,b)
        with self.assertRaises(Conflict):self.engine.submit(self.project,"extract",payload,"same-key")

    def test_only_one_worker_can_claim(self):
        self.submit("compile");self.assertIsNotNone(self.engine.claim());self.assertIsNone(Engine(self.store).claim())

    def test_expired_lease_resumes_checkpoint(self):
        self.execute("compile");shots=self.store.shots(self.project)
        self.submit("images",target_ids=[s["id"] for s in shots]);first=self.engine.claim()
        with self.store.connection() as conn:conn.execute("UPDATE jobs SET lease_until=0 WHERE id=?",(first["id"],))
        resumed=Engine(self.store).claim();self.assertNotEqual(first["token"],resumed["token"])
        with self.store.connection() as conn:self.assertFalse(self.engine.active(conn,first))
        Engine(self.store).execute(resumed)
        self.assertTrue(self.store.shots(self.project)[0]["image"])

    def test_asset_extraction_deduplicates_and_preserves_lock(self):
        self.execute("extract")
        with self.store.connection() as conn:conn.execute("UPDATE assets SET locked=1 WHERE type='characters'")
        before=self.store.assets(self.project);self.execute("extract");after=self.store.assets(self.project)
        self.assertEqual(before,after)

    def test_local_workflow_no_model_cost(self):
        self.execute("extract");self.execute("compile");self.execute("images")
        data=self.store.snapshot();self.assertEqual(data["spent"],0);self.assertEqual(len(data["ledger"]),0)
        self.assertEqual(len(data["projects"][0]["shots"][0]["image_versions"]),1)

    def test_provider_rewrite_without_key_is_explicit(self):
        with self.assertRaisesRegex(ValueError,"模型未连接"):
            self.submit("rewrite",start=0,end=1,instruction="改写")

    def test_unsettled_external_request_not_replayed(self):
        job_id=self.submit("compile")
        with self.store.connection() as conn:conn.execute("UPDATE jobs SET state='RUNNING',lease_until=0,result=? WHERE id=?",(dumps({"inflight":"external"}),job_id))
        self.assertIsNone(self.engine.claim())
        job=self.store.snapshot()["jobs"][0];self.assertEqual(job["state"],"FAILED");self.assertIn("核对",job["error"])

    def test_remote_budget_checked_before_call(self):
        self.execute("compile")
        with self.store.connection() as conn:
            config=self.store.settings();config.update(remote_enabled=True,budget=0)
            conn.execute("UPDATE settings SET data=? WHERE id=1",(dumps(config),))
        with patch.dict(os.environ,{"MANJU_API_KEY":"test-only"}):
            with self.assertRaisesRegex(ValueError,"预算上限"):self.submit("images")

    def test_bill_persists_when_input_becomes_obsolete(self):
        self.execute("compile")
        config=self.store.settings();config.update(remote_enabled=True,budget=100)
        with self.store.connection() as conn:conn.execute("UPDATE settings SET data=? WHERE id=1",(dumps(config),))
        def provider(*args):
            self.store.update_chapter(self.chapter["id"],self.chapter["body"]+"\n△ 风吹过\n",2)
            return {"data":[{"b64_json":base64.b64encode(png_frame()).decode()}]}
        with patch.dict(os.environ,{"MANJU_API_KEY":"test-only"}),patch.object(self.engine,"remote",side_effect=provider):
            self.submit("images");job=self.engine.claim()
            with self.assertRaises(Conflict):self.engine.execute(job)
        self.assertEqual(len(self.store.snapshot()["ledger"]),1)
        self.assertEqual(self.store.snapshot()["spent"],.15)

    @unittest.skipUnless(os.name=="nt" and ffmpeg_path(),"Windows speech and FFmpeg required")
    def test_real_speech_and_mp4(self):
        self.execute("compile");self.execute("images");self.execute("voices")
        shot=self.store.shots(self.project)[0]
        self.assertGreater(shot["audio_duration"],.1)
        shot["duration"]=max(shot["duration"],shot["audio_duration"]+.2)
        with self.store.connection() as conn:conn.execute("UPDATE shots SET data=? WHERE id=?",(dumps(shot),shot["id"]))
        filename="frame_"+"f"*16+".png";(self.store.root/"media"/filename).write_bytes(png_frame())
        result=self.execute("export",target_ids=[shot["id"]],frames={shot["id"]:filename})
        self.assertEqual(result["state"],"SUCCEEDED")
        path=self.store.root/"media"/result["result"]["video"].rsplit("/",1)[-1]
        self.assertGreater(path.stat().st_size,1000)
        self.assertIn(b"ftyp",path.read_bytes()[:32])
        self.assertEqual(result["result"]["qa"]["black_frames"],"通过（FFmpeg 扫描）")

    @unittest.skipUnless(os.name=="nt" and ffmpeg_path(),"Windows speech and FFmpeg required")
    def test_one_click_generates_a_real_film_without_browser_frames(self):
        result=self.execute("episode",mode="local",fit_voice=True)
        self.assertEqual(result["state"],"SUCCEEDED")
        self.assertEqual(result["checkpoint"],["extract","compile","images","voices","export"])
        self.assertTrue(result["result"]["video"].endswith(".mp4"))
        jobs=self.store.snapshot()["jobs"]
        self.assertEqual(len(jobs),6);self.assertTrue(all(j["state"]=="SUCCEEDED" for j in jobs))
        self.assertEqual(self.store.snapshot()["spent"],0)


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.store=Store(cls.temp.name);cls.engine=Engine(cls.store,workers=0)
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),BaseHTTPRequestHandler)
        cls.server.daemon_threads=True;cls.port=cls.server.server_address[1]
        cls.server.RequestHandlerClass=create_handler(cls.store,cls.engine,cls.port)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.temp.cleanup()

    def request(self,path,body=None,method=None,origin=None):
        headers={"Content-Type":"application/json"}
        if origin:headers["Origin"]=origin
        req=urllib.request.Request(f"http://127.0.0.1:{self.port}"+path,data=dumps(body).encode() if body is not None else None,method=method,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=15) as response:return response.status,json.loads(response.read())
        except urllib.error.HTTPError as exc:
            try:return exc.code,json.loads(exc.read())
            finally:exc.close()

    def test_cross_origin_rejected(self):
        code,_=self.request("/api/state",origin="https://evil.example");self.assertEqual(code,403)

    def test_health_contains_only_service_identity(self):
        code,result=self.request("/api/health")
        self.assertEqual(code,200);self.assertEqual(result["app"],"mujian-workbench");self.assertNotIn("projects",result)

    @unittest.skipUnless(os.name=="nt","Windows DPAPI required")
    def test_saved_api_key_is_not_exposed_in_state_or_job_payloads(self):
        token="test-ark-secret-not-real"
        code,result=self.request("/api/models/credentials",{"provider":"ark","api_key":token})
        self.assertEqual(code,200);self.assertNotIn(token,str(result))
        code,state=self.request("/api/state")
        self.assertEqual(code,200);self.assertNotIn(token,dumps(state))
        self.assertTrue(next(p for p in state["providers"] if p["id"]=="ark")["key_available"])

    def test_model_settings_reject_a_stale_revision(self):
        config=self.store.settings();revision=config.get("config_revision",0)
        code,_=self.request("/api/settings",{"budget":123,"config_revision":revision})
        self.assertEqual(code,200)
        code,_=self.request("/api/settings",{"budget":456,"config_revision":revision})
        self.assertEqual(code,409);self.assertEqual(self.store.settings()["budget"],123)

    def test_yabo_preview_is_available(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/yabo/",timeout=10) as response:
            text=response.read().decode("utf-8")
        self.assertIn("director-integration.js",text);self.assertIn("Yabo工作台",text)

    def test_locked_asset_cannot_be_modified(self):
        asset=next(a for p in self.store.snapshot()["projects"] for a in p["assets"] if a["locked"])
        code,_=self.request("/api/assets/"+asset["id"],{"revision":asset["revision"],"data":{**asset["data"],"name":"被覆盖"}},"PUT")
        self.assertEqual(code,409)

    def test_asset_change_invalidates_in_flight_shot_revision(self):
        project=next(p for p in self.store.snapshot()["projects"] if p["name"]=="长安夜未央")
        asset=next(a for a in project["assets"] if a["name"]=="陆沉")
        before={s["id"]:s for s in project["shots"] if asset["id"] in s["asset_ids"]}
        code,_=self.request("/api/assets/"+asset["id"],{"revision":asset["revision"],"data":{**asset["data"],"appearance":"修改后的形象"}},"PUT")
        self.assertEqual(code,200)
        after=[s for s in self.store.shots(project["id"]) if s["id"] in before]
        self.assertTrue(after)
        self.assertTrue(all(s["asset_changed"] and s["revision"]==before[s["id"]]["revision"]+1 for s in after))

    def test_unicode_selection_only_replaces_chosen_range(self):
        project=self.store.new_project("选区验收")
        chapter=next(p for p in self.store.snapshot()["projects"] if p["id"]==project)["chapters"][0]
        chapter=self.store.update_chapter(chapter["id"],"前缀😀选区后缀",1)
        code,result=self.request("/api/chapters/"+chapter["id"]+"/replace",{"revision":2,"start":4,"end":6,"replacement":"替换"})
        self.assertEqual(code,200);self.assertEqual(result["body"],"前缀😀替换后缀")

    def test_import_same_source_twice_does_not_duplicate(self):
        project=self.store.new_project("导入验收");payload={"project_id":project,"entries":[{"name":"第01集.txt","body":"第1集\n1-1 日 外 湖畔\n△ 风吹过\n"}],"strategy":"append"}
        a=self.request("/api/import",payload)[1];b=self.request("/api/import",payload)[1]
        self.assertEqual(a["results"][0]["id"],b["results"][0]["id"])
        self.assertEqual(b["results"][0]["action"],"跳过重复")

    def test_stale_save_is_conflict(self):
        project=self.store.snapshot()["projects"][-1];chapter=project["chapters"][0]
        code,_=self.request("/api/chapters/"+chapter["id"],{"revision":-1,"body":"覆盖"},"PUT");self.assertEqual(code,409)

    def test_budget_rejects_before_dispatch(self):
        project=self.store.new_project("预算验收");chapter=self.store.snapshot()["projects"][0]["chapters"][0]
        # The local mode does not spend or reserve a cloud balance.
        code,data=self.request("/api/settings",{"budget":-1})
        self.assertEqual(code,400)

    def test_parent_cancel_cascades_to_pending_children(self):
        project=self.store.new_project("取消流程验收")
        chapter=next(p for p in self.store.snapshot()["projects"] if p["id"]==project)["chapters"][0]
        parent=self.engine.submit(project,"episode",{"chapter_id":chapter["id"],"revision":1,"mode":"local"},"cancel-parent")
        child=self.engine.submit(project,"extract",{"chapter_id":chapter["id"],"revision":1,"parent_job_id":parent},"cancel-child")
        code,_=self.request("/api/jobs/"+parent+"/cancel",{})
        self.assertEqual(code,200)
        jobs={j["id"]:j for j in self.store.snapshot()["jobs"]}
        self.assertEqual(jobs[parent]["state"],"CANCELED");self.assertEqual(jobs[child]["state"],"CANCELED")

    @unittest.skipUnless(os.name=="nt" and ffmpeg_path(),"Windows speech and FFmpeg required")
    def test_parent_retry_keeps_completed_compilation(self):
        project=self.store.new_project("流程恢复验收")
        chapter=next(p for p in self.store.snapshot()["projects"] if p["id"]==project)["chapters"][0]
        parent=self.engine.submit(project,"episode",{"chapter_id":chapter["id"],"revision":1,"mode":"local"},"recover-parent")
        job=self.engine.claim(parent)
        with patch.object(self.engine,"render_cards",side_effect=ValueError("测试中模拟媒体工作进程失败")):
            self.engine.process_job(job)
        before=self.store.shots(project);self.assertTrue(before)
        code,response=self.request("/api/jobs/"+parent+"/retry",{})
        self.assertEqual(code,202);self.assertEqual(response["id"],parent)
        self.engine.process_job(self.engine.claim(parent))
        after=self.store.shots(project)
        self.assertEqual([s["id"] for s in before],[s["id"] for s in after])
        result=next(j for j in self.store.snapshot()["jobs"] if j["id"]==parent)
        self.assertEqual(result["state"],"SUCCEEDED");self.assertIn("video",result["result"])


if __name__ == "__main__":unittest.main()
