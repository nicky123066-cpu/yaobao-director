"""Single-user loopback API and built React app. Python 3.10+, standard library only."""
import argparse
import base64
import csv
import io
import json
import math
import mimetypes
import os
import re
import struct
import sys
import threading
import time
import urllib.parse
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from artwork import artwork
from domain import fingerprint, parse_script, prompt_for, srt_for, uid, utf16_index
from engine import APP_ROOT, Engine, ffmpeg_path, run_process
from store import Conflict, Store, dumps
from gateway import KEY_NAMES, PROVIDERS, api_key, auto_settings, probe, profiles
from model_workflow import ROLE_FIELDS,validate as validate_models,role_config,catalog as model_catalog,preflight as model_preflight
from credentials import CredentialStore, supported as secure_storage_supported
from production import Production
from creative import catalog,save_visual,dimensions

_DOTENV_KEYS=set()


def read_env():
    path = APP_ROOT / ".env"
    configured={}
    if path.is_file():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                if key.strip() in KEY_NAMES|{"MANJU_FFMPEG", "MANJU_DATA_DIR"}:
                    configured[key.strip()]=value.strip().strip('"').strip("'")
    for key in _DOTENV_KEYS-set(configured):
        os.environ.pop(key,None)
    _DOTENV_KEYS.intersection_update(configured)
    for key,value in configured.items():
        if key not in os.environ or not os.environ[key] or key in _DOTENV_KEYS:
            os.environ[key]=value;_DOTENV_KEYS.add(key)


def create_handler(store, engine, port):
    production=Production(store)
    from commerce import Commerce
    commerce=Commerce(store)
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            if args and str(args[0]).startswith("GET /api/events"):
                return
            # Deliberately omit request bodies, authorization headers and provider responses.

        def reply(self, value, status=200, content_type="application/json; charset=utf-8", headers=None):
            raw = dumps(value).encode() if content_type.startswith("application/json") else value
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            if self.close_connection:
                self.send_header("Connection", "close")
            for key, val in (headers or {}).items():
                self.send_header(key, val)
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def security(self):
            marker=store.root/'.yabo-gateway.json'
            if marker.is_file() and urllib.parse.urlsplit(self.path).path!='/api/health':
                import secrets
                expected=json.loads(marker.read_text('utf-8'))['key']
                if not secrets.compare_digest(self.headers.get('X-Yabo-Director',''),expected):raise PermissionError('请从Yabo工作台登录后打开导演台。')
            host = self.headers.get("Host", "")
            if host not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
                raise PermissionError("仅允许本机工作台访问")
            origin = self.headers.get("Origin")
            allowed = {f"http://127.0.0.1:{port}", f"http://localhost:{port}", "http://127.0.0.1:5173", "http://localhost:5173"}
            if origin and origin not in allowed:
                raise PermissionError("来源不被允许")

        def do_GET(self):
            try:
                self.security()
                parsed = urllib.parse.urlsplit(self.path)
                path, query = parsed.path, urllib.parse.parse_qs(parsed.query)
                if path == "/api/health":
                    return self.reply({"app":"mujian-workbench","version":"0.4.0",**({"workspace_path":str(store.root)} if query.get("integration")==["1"] else {})})
                if path=='/api/models/workflow':
                    return self.reply(model_preflight(store,query.get('project_id',[''])[0],query.get('chapter_id',[''])[0]))
                if path=='/api/models/recommendations':return self.reply(model_catalog(store.settings(),store.root))
                if path == "/api/commerce":return self.reply(commerce.summary())
                if path == "/api/state":
                    data = production.enrich(store.snapshot())
                    data["creative"] = catalog()
                    data["app"] = "mujian-workbench"
                    data["version"] = "0.4.0"
                    data["providers"] = profiles(store.root)
                    data["model_workflow"] = model_catalog(data["settings"],store.root)
                    data["capabilities"] = {"ffmpeg":bool(ffmpeg_path()), "tts":sys.platform == "win32", "api_key":bool(api_key(data["settings"],store.root)), "secure_storage":secure_storage_supported(),
                        "mode":"local", "voices":["Microsoft Huihui Desktop","Microsoft Huihui","Microsoft Kangkang","Microsoft Yaoyao","Microsoft Zira Desktop"] if sys.platform == "win32" else []}
                    for project in data["projects"]:
                        for shot in project["shots"]:
                            shot["prompt"] = prompt_for(shot, project["assets"])
                    return self.reply(data)
                if path == "/api/events":
                    return self.events()
                if match := re.fullmatch(r"/api/art/(\d+)\.svg", path):
                    return self.reply(artwork(int(match[1])).encode(), content_type="image/svg+xml; charset=utf-8")
                if match := re.fullmatch(r"/api/chapters/([a-z0-9_]+)/versions", path):
                    with store.connection() as conn:
                        versions = [dict(r) for r in conn.execute("SELECT * FROM versions WHERE chapter_id=? ORDER BY created DESC LIMIT 50", (match[1],))]
                    return self.reply(versions)
                if match := re.fullmatch(r"/api/jobs/([a-z0-9_]+)/events", path):
                    with store.connection() as conn:
                        events = [dict(r) for r in conn.execute("SELECT * FROM job_events WHERE job_id=? ORDER BY id", (match[1],))]
                    return self.reply(events)
                if match := re.fullmatch(r"/api/download/([a-z0-9_]+)", path):
                    return self.download(match[1], query.get("format", ["md"])[0])
                if path.startswith("/media/"):
                    return self.file(store.root / "media", urllib.parse.unquote(path[len("/media/"):]))
                if path.startswith("/api/"):
                    return self.reply({"error":"接口不存在"}, 404)
                if path == "/yabo":
                    return self.reply(b"",302,"text/plain",{"Location":"/yabo/"})
                if path.startswith("/yabo/"):
                    return self.file(APP_ROOT/"integrations"/"yabo",urllib.parse.unquote(path[len("/yabo/"):]) or "index.html")
                root = APP_ROOT / "static"
                relative = urllib.parse.unquote(path.lstrip("/")) or "index.html"
                target = (root / relative).resolve()
                if not target.is_relative_to(root.resolve()):
                    raise PermissionError("路径不被允许")
                if not target.is_file():
                    relative = "index.html"
                return self.file(root, relative)
            except Exception as exc:
                self.error(exc)

        def file(self, root, name):
            root = root.resolve(); path = (root / name).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                return self.reply({"error":"文件不存在"}, 404)
            size = path.stat().st_size
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            start, end, code = 0, size-1, 200
            if header := self.headers.get("Range"):
                match = re.fullmatch(r"bytes=(\d+)-(\d*)", header)
                if not match or int(match[1]) >= size:
                    return self.reply(b"", 416, mime, {"Content-Range":f"bytes */{size}"})
                start = int(match[1]); end = min(size-1,int(match[2]) if match[2] else size-1); code=206
                if end < start:
                    return self.reply(b"", 416, mime)
            with path.open("rb") as stream:
                stream.seek(start); raw = stream.read(end-start+1)
            headers={"Accept-Ranges":"bytes"}
            if code == 206:
                headers["Content-Range"] = f"bytes {start}-{end}/{size}"
            self.reply(raw, code, mime, headers)

        def events(self):
            last = self.headers.get("Last-Event-ID", "0")
            try:
                last = int(last)
            except ValueError:
                last = 0
            self.send_response(200)
            self.send_header("Content-Type","text/event-stream; charset=utf-8")
            self.send_header("Cache-Control","no-cache")
            self.send_header("Connection","close")
            self.end_headers()
            self.close_connection = True
            started = time.time()
            try:
                self.wfile.write(b": connected\n\n"); self.wfile.flush()
                while time.time()-started < 25:
                    with store.connection() as conn:
                        rows=conn.execute("SELECT * FROM job_events WHERE id>? ORDER BY id LIMIT 200",(last,)).fetchall()
                    for row in rows:
                        self.wfile.write((f"id: {row['id']}\ndata: {dumps(dict(row))}\n\n").encode())
                        last = row["id"]
                    self.wfile.write(b": heartbeat\n\n"); self.wfile.flush()
                    time.sleep(.2)
            except (OSError, ValueError):
                pass

        def error(self, exc):
            code = 409 if isinstance(exc, Conflict) else 403 if isinstance(exc, PermissionError) else 400 if isinstance(exc, (ValueError,KeyError,TypeError)) else 500
            self.reply({"error":str(exc)[:700] if code != 500 else "服务处理失败，请查看控制台或检查输入"},code)
            if code == 500:
                import traceback
                traceback.print_exc()

        def do_POST(self):
            if urllib.parse.urlsplit(self.path).path=='/api/commerce/upload':
                try:
                    self.security()
                    if self.headers.get('Content-Type')!='application/octet-stream':raise ValueError('素材上传格式无效。')
                    size=int(self.headers.get('Content-Length','0'));name=urllib.parse.unquote(self.headers.get('X-File-Name',''))
                    return self.reply(commerce.upload(self.rfile,size,name))
                except Exception as exc:
                    self.close_connection=True;return self.error(exc)
            self.mutate("POST")

        def do_PUT(self):
            self.mutate("PUT")

        def mutate(self, method):
            try:
                self.security()
                if not self.headers.get("Content-Type", "").startswith("application/json"):
                    raise ValueError("请求必须使用 JSON")
                size = int(self.headers.get("Content-Length", "0"))
                if size < 0 or size > 40*1024*1024:
                    raise ValueError("请求过大，请分批导出镜头")
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError("请求格式无效")
                return self.route_mutation(method, urllib.parse.urlsplit(self.path).path, body)
            except Exception as exc:
                # Validation/auth may reject before consuming the request body.
                # Do not parse those remaining bytes as the next HTTP request.
                self.close_connection = True
                self.error(exc)

        def route_mutation(self, method, path, body):
            if method=='POST' and path=='/api/commerce/save':return self.reply(commerce.save(body))
            if method=='POST' and path=='/api/commerce/script':return self.reply(commerce.script(body))
            if method=='POST' and path=='/api/commerce/export':return self.reply({'id':engine.submit(body.get('id'),'commerce',body,body.get('idempotency_key'))})
            if method=='POST' and path=='/api/catalog/replica':
                from replica_import import import_replica
                return self.reply(import_replica(store,body))
            if method=='PUT' and (match:=re.fullmatch(r"/api/projects/([a-z0-9_]+)/visual",path)):return self.reply(save_visual(store,match[1],body))
            if path=='/api/catalog/templates':return self.reply(production.template(body))
            if path=='/api/catalog/shots/batch':return self.reply(production.batch_shots(body))
            if path=='/api/catalog/import':return self.reply(production.import_assets(body))
            if match:=re.fullmatch(r'/api/catalog/assets/([a-z0-9_]+)/(reference|select)',path):
                return self.reply(production.add_reference(match[1],body) if match[2]=='reference' else production.select_reference(match[1],body))
            if match:=re.fullmatch(r'/api/catalog/shots/([a-z0-9_]+)/media',path):return self.reply(production.shot_media(match[1],body))
            if match:=re.fullmatch(r'/api/catalog/shots/([a-z0-9_]+)/assets',path):return self.reply(production.shot_assets(match[1],body))
            if match:=re.fullmatch(r'/api/catalog/shots/([a-z0-9_]+)/video',path):return self.reply(production.select_video(match[1],body))
            if match:=re.fullmatch(r'/api/jobs/([a-z0-9_]+)/(pause|resume)',path):return self.reply(production.control(match[1],match[2]))
            if method == "POST" and path == "/api/projects":
                dimensions(body.get("ratio", "9:16"))
                episodes=int(body.get("episodes",12))
                if not 1 <= episodes <= 200:
                    raise ValueError("集数需为 1–200")
                return self.reply({"id":store.new_project(str(body.get("name","")),body.get("ratio","9:16"),str(body.get("style","电影国漫")),str(body.get("premise","")),episodes,body.get("style_id",""),body.get("style_notes",""))},201)
            if method == "POST" and path == "/api/chapters":
                return self.reply({"id":store.add_chapter(body["project_id"],str(body.get("title","新章节"))[:100],str(body.get("body",""))[:500000])},201)
            if method == "POST" and path == "/api/chapters/reorder":
                with store.connection(immediate=True) as conn:
                    ids=[r[0] for r in conn.execute("SELECT id FROM chapters WHERE project_id=?",(body["project_id"],))]
                    if len(body["ids"]) != len(ids) or set(body["ids"]) != set(ids):
                        raise ValueError("章节顺序包含遗漏或重复")
                    for index, chapter_id in enumerate(body["ids"]):
                        conn.execute("UPDATE chapters SET position=? WHERE id=?",(index,chapter_id))
                return self.reply({"ok":True})
            if method == "POST" and path == "/api/assets":
                asset_type=body.get("type","characters");name=str(body.get("name","")).strip()[:80]
                if asset_type not in {"characters","scenes","props","references","frames","groups"} or not name:
                    raise ValueError("需要有效的资产类型和名称")
                with store.connection(immediate=True) as conn:
                    if not conn.execute("SELECT id FROM projects WHERE id=?",(body["project_id"],)).fetchone(): raise ValueError("项目不存在")
                    if any(a["type"]==asset_type and (a["name"]==name or name in a["data"].get("aliases",[])) for a in store.assets(body["project_id"],conn)):
                        raise Conflict("该名称已存在，请编辑已有资产")
                    asset_id=uid("as_")
                    conn.execute("INSERT INTO assets VALUES(?,?,?,?,?,?,?)",(asset_id,body["project_id"],asset_type,name,0,1,dumps({"name":name,"aliases":[],"description":""})))
                return self.reply({"id":asset_id},201)
            if match := re.fullmatch(r"/api/chapters/([a-z0-9_]+)",path):
                if method != "PUT":
                    raise ValueError("请使用 PUT 保存章节")
                return self.reply(store.update_chapter(match[1],body["body"],body["revision"],body.get("title")))
            if match := re.fullmatch(r"/api/chapters/([a-z0-9_]+)/restore",path):
                with store.connection() as conn:
                    version=conn.execute("SELECT * FROM versions WHERE id=? AND chapter_id=?",(body["version_id"],match[1])).fetchone()
                    if not version: raise ValueError("历史版本不存在")
                return self.reply(store.update_chapter(match[1],version["body"],body["revision"],label="恢复历史版本"))
            if match := re.fullmatch(r"/api/chapters/([a-z0-9_]+)/replace",path):
                chapter=store.chapter(match[1])
                start,end=utf16_index(chapter["body"],body["start"]),utf16_index(chapter["body"],body["end"])
                if start >= end: raise ValueError("请先选择需要替换的文字")
                replacement=str(body["replacement"])
                return self.reply(store.update_chapter(match[1],chapter["body"][:start]+replacement+chapter["body"][end:],body["revision"],label="局部替换"))
            if match := re.fullmatch(r"/api/assets/([a-z0-9_]+)",path):
                return self.reply(production.save_asset(match[1],body))
            if match := re.fullmatch(r"/api/shots/([a-z0-9_]+)",path):
                with store.connection(immediate=True) as conn:
                    row=conn.execute("SELECT data FROM shots WHERE id=?",(match[1],)).fetchone()
                    if not row: raise ValueError("镜头不存在")
                    shot=json.loads(row[0])
                    if body["revision"] != shot.get("revision",1): raise Conflict("镜头已有新版本，请刷新")
                    shot=production.edit_shot(shot,body)
                    conn.execute("UPDATE shots SET data=? WHERE id=?",(dumps(shot),match[1]))
                return self.reply({"ok":True})
            if path == "/api/jobs":
                return self.reply({"id":engine.submit(body["project_id"],body["kind"],body["payload"],body.get("idempotency_key",""))},202)
            if match := re.fullmatch(r"/api/jobs/([a-z0-9_]+)/(cancel|retry)",path):
                with store.connection(immediate=True) as conn:
                    job=conn.execute("SELECT * FROM jobs WHERE id=?",(match[1],)).fetchone()
                    if not job: raise ValueError("任务不存在")
                    if match[2] == "cancel":
                        if job["state"] not in {"PENDING","RUNNING","PAUSED"}: raise Conflict("任务已结束")
                        conn.execute("UPDATE jobs SET state='CANCELED',updated=? WHERE id=?",(time.time(),job["id"]))
                        store.event(conn,job["id"],"已停止继续派发；在途调用仍会结算")
                        if job["kind"]=="episode":
                            conn.execute("UPDATE jobs SET state='CANCELED',updated=? WHERE json_extract(payload,'$.parent_job_id')=? AND state IN ('PENDING','RUNNING','PAUSED')",(time.time(),job["id"]))
                        return self.reply({"ok":True})
                    if job["state"] not in {"FAILED","CANCELED"}: raise Conflict("该任务无需重试")
                    if job['kind']=='videos' and engine.video_tasks.recoverable(job['id']):
                        conn.execute("UPDATE jobs SET state='PENDING',error=NULL,token=NULL,lease_until=0,updated=? WHERE id=?",(time.time(),job['id']))
                        store.event(conn,job['id'],'继续查询原供应商视频任务，不创建新付费任务')
                        return self.reply({'id':job['id'],'resumed_provider_task':True},202)
                    if json.loads(job["result"]).get("inflight"): raise Conflict("供应商结果待核对，已禁止直接重试以避免重复收费")
                    if job["kind"]=="episode":
                        conn.execute("UPDATE job_controls SET paused=0 WHERE job_id=? OR job_id IN (SELECT id FROM jobs WHERE json_extract(payload,'$.parent_job_id')=?)",(job['id'],job['id']))
                        current_shots=[s for s in store.shots(job["project_id"],conn) if s["chapter_id"]==json.loads(job["payload"])["chapter_id"]]
                        if any(s.get("asset_changed") for s in current_shots):
                            raise Conflict("资产设定已有新版本，请重新发起本集流程，或先更新受影响画面后单独合成")
                        pending=conn.execute("SELECT * FROM jobs WHERE json_extract(payload,'$.parent_job_id')=? AND state IN ('FAILED','CANCELED')",(job["id"],)).fetchall()
                        if any(json.loads(child["result"]).get("inflight") and not (child["kind"]=="videos" and engine.video_tasks.recoverable(child["id"])) for child in pending):raise Conflict("存在未核对的外部请求，请先确认供应商结果")
                        for child in pending:conn.execute("UPDATE jobs SET state='PENDING',error=NULL,lease_until=0,token=NULL WHERE id=?",(child["id"],))
                        conn.execute("UPDATE jobs SET state='PENDING',error=NULL,lease_until=0,token=NULL WHERE id=?",(job["id"],))
                        store.event(conn,job["id"],"从已完成阶段继续本集流程")
                        return self.reply({"id":job["id"]},202)
                    payload=json.loads(job["payload"])
                    for key in ("_config","shot_revisions"): payload.pop(key,None)
                    if payload.get("target_ids"):
                        done=json.loads(job["checkpoint"]);payload["target_ids"]=[i for i in payload["target_ids"] if i not in done]
                        if not payload["target_ids"]: raise ValueError("所有子项均已完成")
                return self.reply({"id":engine.submit(job["project_id"],job["kind"],payload,uid("retry_"))},202)
            if match:=re.fullmatch(r'/api/jobs/([a-z0-9_]+)/provider-status',path):
                return self.reply(engine.video_tasks.inspect(match[1],cancel=body.get('cancel') is True))
            if path == "/api/settings":
                config=store.settings()
                previous_revision=config.get("config_revision",0)
                if "config_revision" in body and body["config_revision"]!=previous_revision:raise Conflict("模型配置已在其他页面更新，请刷新后再保存")
                before=fingerprint({k:config.get(k) for k in ("provider_url","key_env","text_model","image_model")})
                for key in ("provider","key_env","provider_url","text_model","image_model","image_price","text_price","budget","remote_enabled","image_reference_mode",*ROLE_FIELDS):
                    if key in body: config[key]=body[key]
                if config.get('image_reference_mode','disabled') not in {'disabled','openai_edits','ark_images'}:raise ValueError('参考图接口类型无效')
                parsed=urllib.parse.urlsplit(config["provider_url"])
                if parsed.scheme != "https" and not(parsed.scheme=="http" and parsed.hostname in {"127.0.0.1","localhost"}): raise ValueError("模型地址需为 HTTPS 或本机 HTTP")
                if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment: raise ValueError("模型地址不能包含凭据、查询或片段")
                for key in ("image_price","text_price","budget"):
                    value=float(config.get(key,.02))
                    if not math.isfinite(value) or value<0 or value>1000000: raise ValueError("价格或预算无效")
                    config[key]=value
                if config.get("key_env","MANJU_API_KEY") not in KEY_NAMES:raise ValueError("密钥环境变量无效")
                validate_models(config)
                if type(config["remote_enabled"]) is not bool:raise ValueError("真实生成开关无效")
                if config["remote_enabled"] and not any(api_key(role_config(config,r),store.root) for r in ["text","image","video"]): raise ValueError("当前供应商尚未配置密钥，请先加密保存或配置环境变量")
                if before!=fingerprint({k:config.get(k) for k in ("provider_url","key_env","text_model","image_model")}):config.pop("last_connection",None)
                config["config_revision"]=previous_revision+1
                with store.connection(immediate=True) as conn:
                    latest=json.loads(conn.execute("SELECT data FROM settings WHERE id=1").fetchone()[0])
                    if latest.get("config_revision",0)!=previous_revision:raise Conflict("模型配置已更新，请刷新后再保存")
                    conn.execute("UPDATE settings SET data=? WHERE id=1",(dumps(config),))
                return self.reply({"ok":True,"settings":config})
            if path == "/api/models/credentials":
                provider=next((p for p in PROVIDERS if p["id"]==body.get("provider")),None)
                if not provider:raise ValueError("供应商不存在")
                CredentialStore(store.root).set(provider["key_env"],body.get("api_key",""))
                with store.connection(immediate=True) as conn:
                    config=json.loads(conn.execute("SELECT data FROM settings WHERE id=1").fetchone()[0])
                    if provider["key_env"] in {role_config(config,r).get("key_env","MANJU_API_KEY") for r in ["text","image","video"]}:
                        config.pop("last_connection",None)
                        config["config_revision"]=config.get("config_revision",0)+1
                        conn.execute("UPDATE settings SET data=? WHERE id=1",(dumps(config),))
                return self.reply({"saved":True,"provider":provider["id"],"config_revision":config.get("config_revision",0),"key_source":"encrypted","message":"密钥已通过 Windows 当前用户加密保存，未写入明文配置"})
            if path in {"/api/models/auto","/api/models/test"}:
                read_env();config=store.settings()
                original_revision=config.get("config_revision",0)
                if path.endswith("/auto"):
                    config,result=auto_settings(config,store.root)
                    if result is None:
                        result=probe(config,store.root);config["remote_enabled"]=False
                else:
                    for key in ("provider","key_env","provider_url","text_model","image_model"):
                        if key in body:config[key]=body[key]
                    url=urllib.parse.urlsplit(config["provider_url"])
                    if url.scheme!="https" and not(url.scheme=="http" and url.hostname in {"127.0.0.1","localhost"}):raise ValueError("仅支持 HTTPS 或本机兼容接口")
                    if not url.hostname or url.username or url.password or url.query or url.fragment:raise ValueError("请使用不含凭据或查询参数的 API 地址")
                    if config.get("key_env","MANJU_API_KEY") not in KEY_NAMES:raise ValueError("密钥环境变量无效")
                    result=probe(config,store.root)
                result["checked_at"]=time.time()
                with store.connection(immediate=True) as conn:
                    latest=json.loads(conn.execute("SELECT data FROM settings WHERE id=1").fetchone()[0])
                    if latest.get("config_revision",0)!=original_revision:raise Conflict("检测期间模型设置已有变化，请重新检测")
                    if path.endswith("/auto"):
                        config["last_connection"]=result;config["config_revision"]=original_revision+1
                        conn.execute("UPDATE settings SET data=? WHERE id=1",(dumps(config),))
                    elif all(config.get(k)==latest.get(k) for k in ("provider_url","key_env","text_model","image_model")):
                        latest["last_connection"]=result
                        conn.execute("UPDATE settings SET data=? WHERE id=1",(dumps(latest),))
                return self.reply({**result,"settings":config} if path.endswith("/auto") else result)
            if path == "/api/frames":
                frames={}
                if not 1<=len(body.get("frames",[]))<=60: raise ValueError("一次支持 1–60 镜")
                for frame in body["frames"]:
                    raw=base64.b64decode(frame["png"].split(",")[-1],validate=True)
                    if len(raw)>3*1024*1024 or not raw.startswith(b"\x89PNG\r\n\x1a\n") or len(raw)<24: raise ValueError("画面需为 3MB 内 PNG")
                    width,height=struct.unpack(">II",raw[16:24])
                    if (width,height) not in {(720,1280),(1280,720),(960,960)}: raise ValueError("导出画面尺寸无效")
                    name=uid("frame_")+".png";(store.root/"media"/name).write_bytes(raw);frames[frame["id"]]=name
                return self.reply({"frames":frames})
            if path == "/api/import":
                results=[]
                if len(body["entries"])>200: raise ValueError("一次最多导入 200 集")
                for entry in body["entries"]:
                    name=str(entry["name"])[:250];text=str(entry["body"])
                    if not text.strip() or len(text)>500000: raise ValueError("导入剧本不能为空或超过 50 万字")
                    source_key=fingerprint(name.casefold())
                    with store.connection(immediate=True) as conn:
                        existing=conn.execute("SELECT * FROM chapters WHERE project_id=? AND source_key=?",(body["project_id"],source_key)).fetchone()
                        if not existing:
                            chapter_id=store.add_chapter(body["project_id"],Path(name).stem,text,source_key,conn)
                            results.append({"id":chapter_id,"action":"新增"});continue
                        chapter_id=existing["id"]
                        if body.get("strategy") != "replace" or existing["body"] == text:
                            results.append({"id":chapter_id,"action":"跳过重复"});continue
                        expected=body.get("revisions",{}).get(chapter_id)
                        if expected != existing["revision"]: raise Conflict("替换目标已更新，请刷新并重新确认")
                    store.update_chapter(chapter_id,text,expected,label="导入替换")
                    results.append({"id":chapter_id,"action":"替换"})
                return self.reply({"results":results})
            return self.reply({"error":"接口不存在"},404)

        def download(self, project_id, format_name):
            snapshot=production.enrich(store.snapshot()); project=next((p for p in snapshot["projects"] if p["id"]==project_id),None)
            if not project: raise ValueError("项目不存在")
            filename="manju-"+project_id
            if format_name == "json":
                return self.reply(dumps(project).encode(),content_type="application/octet-stream",headers={"Content-Disposition":f'attachment; filename="{filename}.json"'})
            if format_name == "srt":
                raw=srt_for(project["shots"]).encode("utf-8-sig");ext="srt"
            elif format_name == "csv":
                stream=io.StringIO(newline=""); writer=csv.writer(stream)
                writer.writerow(["镜头","场景","人物","时长","景别","运镜","动作","台词","资产引用","来源行 ID"])
                for s in project["shots"]:
                    # Prefix spreadsheet formula-like user text on export.
                    values=[s["number"],s["location"],"、".join(s["characters"]),s["duration"],s["size"],s["camera"],s["action"],s["dialogue"],";".join(s["asset_ids"]),";".join(s["source_line_ids"])]
                    writer.writerow([("'"+v) if isinstance(v,str) and v.startswith(("=","+","-","@")) else v for v in values])
                raw=stream.getvalue().encode("utf-8-sig");ext="csv"
            elif format_name == "zip":
                output=io.BytesIO()
                with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("project.json",dumps(project))
                    archive.writestr("script.md","\n\n".join(ch["body"] for ch in project["chapters"]))
                    archive.writestr("subtitles.srt",srt_for(project["shots"]))
                    for shot in project["shots"]:
                        for key in ("image","audio","video"):
                            url=shot.get(key,"") or ""
                            if url.startswith("/media/"):
                                file=store.root/"media"/Path(url).name
                                if file.is_file(): archive.write(file,"media/"+file.name)
                            elif url.startswith("/api/art/"):
                                archive.writestr("media/concept-"+shot["id"]+".svg",artwork(int(url.rsplit("/",1)[1].split(".")[0])))
                raw=output.getvalue();ext="zip"
            else:
                raw="\n\n".join(ch["body"] for ch in project["chapters"]).encode("utf-8-sig");ext="md"
            return self.reply(raw,content_type="application/octet-stream",headers={"Content-Disposition":f'attachment; filename="{filename}.{ext}"'})
    return Handler


def main():
    read_env()
    parser=argparse.ArgumentParser(description="幺爆导演台 · 本地漫剧工作台")
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--data",default=os.environ.get("MANJU_DATA_DIR",str(APP_ROOT/"data")))
    parser.add_argument("--open",action="store_true")
    parser.add_argument("--no-seed",action="store_true")
    args=parser.parse_args()
    store=Store(args.data,seed=not args.no_seed);engine=Engine(store)
    server=ThreadingHTTPServer(("127.0.0.1",args.port),create_handler(store,engine,args.port))
    server.daemon_threads=True;engine.start()
    url=f"http://127.0.0.1:{args.port}"
    print(f"Heli Director Desk: {url}\nLocal data: {store.root}",flush=True)
    if args.open: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: engine.stop.set();server.server_close()


if __name__ == "__main__":
    main()
