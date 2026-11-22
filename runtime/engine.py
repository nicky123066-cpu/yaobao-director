"""Durable local jobs, provider gateway, Windows speech and FFmpeg composition."""
import base64
import io
import json
import math
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

from artwork import artwork
from domain import compile_shots, extract_assets, fingerprint, prompt_for, srt_for, uid, utf16_index
from store import Conflict, dumps
from gateway import api_key
from model_workflow import role_config, require_capability, image_request, DEFAULTS as MODEL_DEFAULTS
from production import Production, pause_boundary, encode_multipart, motion_segments
from creative import dimensions,image_size,visual_style

APP_ROOT = Path(os.environ.get('MANJU_RUNTIME_ROOT',Path(__file__).resolve().parent))


def ffmpeg_path():
    configured = os.environ.get("MANJU_FFMPEG")
    if configured and Path(configured).is_file():
        return configured
    bundled = list((APP_ROOT / "vendor").glob("**/ffmpeg*.exe"))
    if bundled:
        return str(bundled[0])
    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        return None


def run_process(args, timeout=120):
    return subprocess.run(args, capture_output=True, timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=True)


class Engine:
    def __init__(self, store, workers=2):
        self.store, self.workers = store, workers
        self.stop = threading.Event()
        self.threads = []
        from video_tasks import VideoTasks
        self.video_tasks=VideoTasks(self)

    def start(self):
        for index in range(self.workers):
            thread = threading.Thread(target=self.loop, name=f"job-worker-{index}", daemon=True)
            thread.start(); self.threads.append(thread)

    def submit(self, project_id, kind, payload, idem):
        if kind not in {"extract", "compile", "images", "voices", "export", "rewrite", "episode", "asset_images", "videos"}:
            raise ValueError("不支持的任务类型")
        if not idem or len(idem) > 160:
            raise ValueError("需要有效的幂等键")
        digest = fingerprint([project_id, kind, payload])
        with self.store.connection(immediate=True) as conn:
            old = conn.execute("SELECT * FROM jobs WHERE idem=?", (idem,)).fetchone()
            if old:
                if old["digest"] != digest:
                    raise Conflict("同一幂等键不能用于不同输入")
                return old["id"]
            if not conn.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone():
                raise ValueError("项目不存在")
            chapter = self.store.chapter(payload.get("chapter_id"), conn)
            if chapter["project_id"] != project_id:
                raise ValueError("章节不属于当前项目")
            if chapter["revision"] != payload.get("revision"):
                raise Conflict("剧本已经更新，请刷新后重新提交")
            latest = json.loads(conn.execute("SELECT data FROM settings WHERE id=1").fetchone()[0])
            root_config={**MODEL_DEFAULTS,**latest}
            if payload.get('parent_job_id'):
                parent=conn.execute("SELECT payload,project_id,kind FROM jobs WHERE id=?",(payload['parent_job_id'],)).fetchone()
                if not parent or parent['kind']!='episode' or parent['project_id']!=project_id:raise ValueError('父流程不属于当前项目。')
                parent_payload=json.loads(parent['payload'])
                if parent_payload['chapter_id']!=chapter['id']:raise ValueError('子任务章节与父流程不一致。')
                root_config={**MODEL_DEFAULTS,**parent_payload.get('_root_config',parent_payload['_config'])}
                root_config['budget']=min(root_config['budget'],latest['budget'])
            role='image' if kind in {'images','asset_images'} else 'video' if kind=='videos' else 'text'
            config=role_config(root_config,role)
            project_data=json.loads(conn.execute('SELECT data FROM projects WHERE id=?',(project_id,)).fetchone()[0])
            config['_image_ratio']='1:1' if kind=='asset_images' else project_data.get('ratio','9:16')
            config['text_price']=config.get('text_price',.02)
            requested=bool(root_config.get('remote_enabled') and payload.get('mode')!='local')
            if payload.get('mode')=='remote' and not root_config.get('remote_enabled'):raise ValueError('请先在模型中心手动启用真实模型生成。')
            if kind in {'images','asset_images','videos','rewrite'} and (requested or payload.get('mode')=='remote'):
                if not api_key(config,self.store.root):raise ValueError('当前用途密钥未配置，请先在模型中心保存对应供应商密钥。')
                require_capability(config,role)
            if kind=='videos' and not requested:raise ValueError('动态视频需要显式启用真实模型生成，不能降级为静态示意。')
            config['remote_enabled']=requested and bool(api_key(config,self.store.root))
            payload={**payload,'_config':config,'_root_config':root_config}
            if kind == "episode":
                workflow=payload.get('workflow_mode','local_preview')
                if workflow not in {'local_preview','ai_images','ai_video'}:raise ValueError('制作流程无效。')
                payload['workflow_mode']=workflow
                if workflow!='local_preview':
                    if not root_config.get('remote_enabled'):raise ValueError('AI制作流程需要先手动启用真实模型生成。')
                    if payload.get('confirmed_generation') is not True:raise ValueError('请先核对AI制作预估费用并确认生成。')
                    for purpose in (['image','video'] if workflow=='ai_video' else ['image']):
                        effective=role_config(root_config,purpose);require_capability(effective,purpose)
                        if not api_key(effective,self.store.root):raise ValueError('请先配置'+purpose+'用途供应商密钥。')
                count=sum(n["type"] in {"action","dialogue"} for n in chapter["ast"]["nodes"])
                if not 1<=count<=60 or chapter["ast"]["stats"]["scenes"]==0:
                    raise ValueError("一键流程需要 1–60 个动作/台词镜头和至少一个场次，请先完善当前章剧本")
                if not ffmpeg_path() or os.name != "nt":
                    raise ValueError("本地一键流程需要 Windows 语音引擎和 FFmpeg")
                active=conn.execute("SELECT id FROM jobs WHERE project_id=? AND state IN ('PENDING','RUNNING','PAUSED') AND json_extract(payload,'$.chapter_id')=?",(project_id,chapter["id"])).fetchone()
                if active:
                    raise Conflict("本章已有任务在运行，请完成或取消后启动完整流程")
            shots = [s for s in self.store.shots(project_id, conn) if s["chapter_id"] == chapter["id"]]
            if kind in {"images", "voices", "export", "videos"}:
                ids = payload.get("target_ids", [s["id"] for s in shots])
                if not ids or len(ids) != len(set(ids)) or not set(ids) <= {s["id"] for s in shots}:
                    raise ValueError("请选择本章节中的有效镜头")
                selected = [s for s in shots if s["id"] in ids]
                if any(s.get("stale") for s in selected):
                    raise Conflict("剧本已变更，请先重新编译分镜")
                payload["target_ids"] = ids
                payload["shot_revisions"] = {s["id"]: s.get("revision", 1) for s in selected}
                if kind=='videos':
                    payload['video_first_frames']={s['id']:s.get('image') for s in selected}
                    if any(not s.get('image') or not re.fullmatch(r'/media/[A-Za-z0-9_.-]+\.(png|jpg|jpeg|webp)',s['image']) for s in selected):raise ValueError('请先为动态镜头准备PNG、JPEG或WebP首帧，不能用SVG示意图。')
                if kind == "voices" and not any(s.get("dialogue") for s in selected):
                    raise ValueError("选中的镜头没有台词")
                if kind == "export":
                    expected=payload.get("expected_shot_revisions",{})
                    if expected and any(expected.get(s["id"]) != s.get("revision",1) for s in selected):
                        raise Conflict("准备画面时镜头已被编辑，请重新发起导出")
                    expected_images=payload.get("expected_images",{})
                    if expected_images and any(expected_images.get(s["id"]) != s.get("image") for s in selected):
                        raise Conflict("准备画面时画面版本已变化，请重新发起导出")
                    payload["media_fingerprint"] = fingerprint([{k:s.get(k) for k in ("id","revision","image","audio","duration","stale","asset_changed")} for s in selected])
                    if not ffmpeg_path():
                        raise ValueError("未找到 FFmpeg，请配置 MANJU_FFMPEG")
                    if any(s.get("video") for s in selected):payload["auto_frames"]=True
                    for s in selected:
                        if s.get("asset_changed"):
                            raise Conflict("资产设定已更新，请先重生成受影响的镜头画面")
                        if not s.get("image") and not s.get("video"):
                            raise ValueError("请先为所有镜头生成或选择画面")
                        if s.get("dialogue") and not s.get("audio"):
                            raise ValueError("请先完成所有台词的配音")
                        if s.get("audio_duration", 0) > s["duration"] + .05:
                            raise ValueError("存在超长台词，请在配音台延长镜头后再导出")
                        if not payload.get("auto_frames"):
                            frame = self.store.root / "media" / (payload.get("frames", {}).get(s["id"], ""))
                            if frame.parent != self.store.root / "media" or not frame.is_file() or frame.suffix != ".png":
                                raise ValueError("缺少导出画面，请重新发起导出")
            if kind == "asset_images":
                assets=self.store.assets(project_id,conn)
                ids=payload.get("target_ids",[])
                if not isinstance(ids,list) or not 1<=len(ids)<=100 or len(set(ids))!=len(ids) or not set(ids)<={a['id'] for a in assets}:raise ValueError('请选择当前项目中的 1–100 项有效资产')
                payload['asset_revisions']={a['id']:a['revision'] for a in assets if a['id'] in ids}
            if kind == "rewrite" and not config["remote_enabled"]:
                raise ValueError("模型未连接：请在设置中启用服务端 MANJU_API_KEY，或使用手动局部替换")
            if kind == "rewrite" and not config.get("text_model"):
                raise ValueError("请先配置一个可用的文本模型或接入点 ID")
            if kind in {'images','asset_images','voices','rewrite','compile','export','videos'}:
                targets=set(payload.get('target_ids',[])) if kind in {'images','asset_images','voices','export','videos'} else {chapter['id']}
                for pending in conn.execute("SELECT payload FROM jobs WHERE project_id=? AND kind=? AND (state IN ('PENDING','RUNNING','PAUSED') OR json_extract(result,'$.inflight') IS NOT NULL)",(project_id,kind)):
                    previous=json.loads(pending['payload'])
                    previous_targets=set(previous.get('target_ids',[])) if kind in {'images','asset_images','voices','export','videos'} else {previous.get('chapter_id')}
                    if targets & previous_targets:raise Conflict('所选内容已有同类任务在排队、执行、暂停或等待核对，请先处理原任务，避免重复生成或收费')
            estimate = 0.0
            if kind in {"images","asset_images"} and config["remote_enabled"]:
                estimate = len(payload["target_ids"]) * config["image_price"]
            if kind == "rewrite":
                estimate = (len(chapter["body"].encode()) + 4000) / 1000 * config["text_price"]
            if kind=='videos':estimate=sum(max(4,math.ceil(s['duration']))*config.get('video_price',1) for s in selected)
            if kind=='episode' and payload['workflow_mode']!='local_preview':
                project=json.loads(conn.execute('SELECT data FROM projects WHERE id=?',(project_id,)).fetchone()[0])
                planned=compile_shots(chapter['ast'],chapter['id'],chapter['revision'],self.store.assets(project_id,conn),project['style'])
                assets=[a for a in extract_assets(chapter['ast']) if a['type'] in {'characters','scenes','props'}]
                estimate=(len(planned)+len(assets))*config.get('image_price',.15)
                if payload['workflow_mode']=='ai_video':estimate+=sum(max(4,math.ceil(s['duration']))*config.get('video_price',1) for s in planned)
            spent = conn.execute("SELECT COALESCE(SUM(amount),0) FROM ledger").fetchone()[0]
            held = conn.execute("SELECT COALESCE(SUM(MAX(0,estimate-(SELECT COALESCE(SUM(amount),0) FROM ledger WHERE ledger.job_id=jobs.id))),0) FROM jobs WHERE id<>? AND (state IN ('PENDING','RUNNING','PAUSED') OR (state IN ('FAILED','CANCELED') AND json_extract(result,'$.inflight') IS NOT NULL))",(payload.get('parent_job_id',''),)).fetchone()[0]
            if estimate and spent + held + estimate > config["budget"]:
                raise ValueError("已达到本地预算上限，请调整预算或减少镜头")
            job_id = uid("job_"); now = time.time()
            conn.execute("INSERT INTO jobs(id,project_id,kind,state,payload,idem,digest,estimate,created,updated) VALUES(?,?,?,'PENDING',?,?,?,?,?,?)",
                         (job_id, project_id, kind, dumps(payload), idem, digest, estimate, now, now))
            parent=payload.get('parent_job_id')
            if parent and conn.execute('SELECT 1 FROM job_controls WHERE job_id=? AND paused=1',(parent,)).fetchone():
                conn.execute("UPDATE jobs SET state='PAUSED' WHERE id=?",(job_id,));conn.execute('INSERT INTO job_controls VALUES(?,1)',(job_id,))
            self.store.event(conn, job_id, "已入队，输入版本和预算已确认")
        return job_id

    def claim(self, job_id=None):
        with self.store.connection(immediate=True) as conn:
            if job_id:
                row=conn.execute("SELECT * FROM jobs WHERE id=? AND (state='PENDING' OR (state='RUNNING' AND lease_until<?))",(job_id,time.time())).fetchone()
            else:
                row = conn.execute("SELECT * FROM jobs WHERE state='PENDING' OR (state='RUNNING' AND lease_until<?) ORDER BY created LIMIT 1", (time.time(),)).fetchone()
            if not row:
                return None
            result = json.loads(row["result"])
            if result.get("inflight") and not (row["kind"]=="videos" and conn.execute("SELECT 1 FROM provider_video_tasks WHERE job_id=? AND state IN ('queued','running','succeeded') LIMIT 1",(row["id"],)).fetchone()):
                conn.execute("UPDATE jobs SET state='FAILED',error=?,lease_until=0 WHERE id=?", ("外部调用结果待核对，为避免重复收费未自动重试。请在供应商处核对请求。", row["id"]))
                self.store.event(conn, row["id"], "恢复时发现未结算外部请求，已停止自动派发")
                return None
            token = uid("lease_")
            conn.execute("UPDATE jobs SET state='RUNNING',token=?,lease_until=?,attempts=attempts+1,updated=? WHERE id=?", (token, time.time()+30, time.time(), row["id"]))
            self.store.event(conn, row["id"], "开始执行" if row["attempts"] == 0 else "租约到期，正在从已提交断点恢复")
            return {**dict(row), "token": token, "payload": json.loads(row["payload"]), "checkpoint": json.loads(row["checkpoint"])}

    def active(self, conn, job):
        row = conn.execute("SELECT state,token FROM jobs WHERE id=?", (job["id"],)).fetchone()
        return row and row["state"] == "RUNNING" and row["token"] == job["token"]

    def loop(self):
        while not self.stop.is_set():
            job = self.claim()
            if not job:
                self.stop.wait(.25); continue
            self.process_job(job)

    def process_job(self, job):
        heartbeat_stop=threading.Event()
        def heartbeat():
            while not heartbeat_stop.wait(5):
                with self.store.connection() as conn:
                    conn.execute("UPDATE jobs SET lease_until=? WHERE id=? AND token=? AND state='RUNNING'",(time.time()+30,job["id"],job["token"]))
        threading.Thread(target=heartbeat,daemon=True).start()
        try:
            self.execute(job)
        except Exception as exc:
            message=str(exc)[:800]
            with self.store.connection(immediate=True) as conn:
                if self.active(conn,job):
                    conn.execute("UPDATE jobs SET state='FAILED',error=?,updated=?,lease_until=0 WHERE id=?",(message,time.time(),job["id"]))
                    self.store.event(conn,job["id"],"执行失败："+message)
        finally:
            heartbeat_stop.set()

    def remote(self, job, endpoint, request_data, files=None):
        config = job["payload"]["_config"]
        if job['kind'] in {'images','asset_images','videos','rewrite'} and not self.store.settings().get('remote_enabled'):raise ValueError('真实模型生成已关闭，未派发新的付费请求。')
        if endpoint=='/chat/completions' and config.get('text_protocol')=='responses':
            messages=request_data['messages'];endpoint='/responses'
            request_data=dict(model=request_data['model'],instructions='\n'.join(m['content'] for m in messages if m['role']=='system'),input=[m for m in messages if m['role']!='system'],max_output_tokens=request_data.get('max_tokens',1000),store=False)
        with self.store.connection(immediate=True) as conn:
            if not self.active(conn, job):
                raise ValueError("任务已经取消")
            conn.execute("UPDATE jobs SET result=? WHERE id=?", (dumps({"inflight": endpoint, "request_id": job["id"]}), job["id"]))
        raw,content_type=encode_multipart(request_data,files) if files else (dumps(request_data).encode(),'application/json')
        req = urllib.request.Request(config["provider_url"].rstrip("/") + endpoint,
            data=raw, headers={"Authorization": "Bearer " + api_key(config,self.store.root),
            "Content-Type": content_type, "Idempotency-Key": job["id"] + ":" + str(len(job["checkpoint"]))})
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                parsed=json.loads(response.read(30 * 1024 * 1024))
                if endpoint=='/responses':
                    if parsed.get('status')!='completed':raise ValueError('文本响应尚未完成。')
                    text=''.join(c['text'] for item in parsed.get('output',[]) if item.get('type')=='message' and item.get('role')=='assistant' for c in item.get('content',[]) if c.get('type')=='output_text')
                    if not text.strip():raise ValueError('文本接口没有返回完整正文。')
                    return {'choices':[{'message':{'content':text}}],'usage':parsed.get('usage',{})}
                return parsed
        except urllib.error.HTTPError as exc:
            if exc.code in {400,401,403,404,405,413,415,422}:
                with self.store.connection(immediate=True) as conn:
                    result=json.loads(conn.execute('SELECT result FROM jobs WHERE id=?',(job['id'],)).fetchone()[0]);result.pop('inflight',None)
                    conn.execute('UPDATE jobs SET result=? WHERE id=?',(dumps(result),job['id']))
            raise ValueError(f"供应商返回 HTTP {exc.code}，请核对模型配置和调用结果") from None
        except (OSError, ValueError):
            raise ValueError("供应商响应未确认，任务已停止；请核对供应商请求后操作，避免重复收费") from None

    def execute(self, job):
        payload, kind = job["payload"], job["kind"]
        chapter = self.store.chapter(payload["chapter_id"])
        if chapter["revision"] != payload["revision"]:
            raise Conflict("输入剧本已变更，请基于新版本重新提交")
        if kind == "episode":
            return self.execute_episode(job)
        if kind == "asset_images":return Production(self.store).generate_assets(self,job)
        targets = payload.get("target_ids", []) if kind in {"images", "voices", "videos"} else [chapter["id"]]
        for target in targets:
            if target in job["checkpoint"]:
                continue
            with self.store.connection() as conn:
                if not self.active(conn, job) or pause_boundary(self.store,conn,job):
                    return
            shot = next((s for s in self.store.shots(job["project_id"]) if s["id"] == target), None)
            output, charge = {}, None
            if kind == "images":
                if shot.get('revision',1)!=payload['shot_revisions'][target]:raise Conflict('排队期间镜头已编辑，请重新确认生成')
                if payload["_config"]["remote_enabled"]:
                    references=Production(self.store).shot_references(shot,payload['_config'])
                    with self.store.connection() as image_conn:direction=json.loads(image_conn.execute('SELECT data FROM projects WHERE id=?',(job['project_id'],)).fetchone()[0])
                    endpoint,body,uploads=image_request(payload['_config'],prompt_for(shot,self.store.assets(job['project_id']))+'\n目标画幅：'+direction['ratio']+'；为后期裁切保留主体安全边距。',references)
                    if payload['_config'].get('image_protocol')!='ark_images' and 'seedream' not in payload['_config'].get('image_model','').lower():body['size']=image_size(direction['ratio'])
                    response=self.remote(job,endpoint,body,**({'files':uploads} if uploads else {}))
                    image = response["data"][0]
                    if image.get("b64_json"):
                        raw = base64.b64decode(image["b64_json"], validate=True)
                    else:
                        url = image.get("url", "")
                        if not url.startswith("https://"):
                            raise ValueError("供应商未返回有效 HTTPS 图片地址")
                        with urllib.request.urlopen(url, timeout=60) as result:
                            raw = result.read(20*1024*1024 + 1)
                    if len(raw) > 20*1024*1024 or not (raw.startswith(b"\x89PNG") or raw.startswith(b"\xff\xd8") or raw[8:12] == b"WEBP"):
                        raise ValueError("供应商返回的图片格式或大小无效，请核对供应商调用记录")
                    suffix = ".png" if raw.startswith(b"\x89PNG") else ".jpg" if raw.startswith(b"\xff\xd8") else ".webp"
                    path = self.store.root / "media" / (uid("image_") + suffix); path.write_bytes(raw)
                    output = {"image": "/media/" + path.name, "mode": "provider_reference" if references else "provider"}
                    charge = (payload["_config"]["image_model"], payload["_config"]["image_price"], {"units":1,"unit":"image","basis":"configured_unit_price"})
                else:
                    if payload.get("native_images"):
                        path=self.store.root/"media"/(uid("concept_")+".png")
                        self.render_cards([{"output":str(path),"width":960,"height":640,"variant":sum(ord(x) for x in shot["id"])%6,"compose":False}])
                    else:
                        path = self.store.root / "media" / (uid("concept_") + ".svg")
                        path.write_text(artwork(sum(ord(x) for x in shot["id"]) % 6), encoding="utf-8")
                    output = {"image": "/media/" + path.name, "mode": "local"}
            elif kind=='videos':
                if shot.get('revision',1)!=payload['shot_revisions'][target] or shot.get('image')!=payload['video_first_frames'][target]:raise Conflict('首帧或镜头已修改，请基于当前版本生成视频。')
                output=self.video_tasks.run(job,shot)
                if output is None:return
            elif kind == "voices":
                if not shot.get("dialogue"):
                    output = {}
                else:
                    path = self.store.root / "media" / (uid("voice_") + ".wav")
                    request = {"voice": shot.get("voice", "Microsoft Huihui Desktop"), "rate":shot.get("voice_rate", 0), "text":shot["dialogue"], "output":str(path)}
                    request_path = self.store.root / (uid("speech_") + ".json")
                    request_path.write_text(dumps(request), encoding="utf-8-sig")
                    try:
                        run_process(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "RemoteSigned", "-File", str(APP_ROOT / "speech.ps1"), "-RequestPath", str(request_path)], timeout=90)
                    except subprocess.CalledProcessError as exc:
                        raise ValueError("本地配音失败，请确认已安装所选 Windows 音色：" + exc.stderr.decode("utf-8", "replace")[-350:]) from None
                    finally:
                        request_path.unlink(missing_ok=True)
                    with wave.open(str(path), "rb") as wav:
                        duration = wav.getnframes()/wav.getframerate()
                    output = {"audio":"/media/"+path.name, "audio_duration":round(duration, 3)}
            elif kind == "export":
                output = self.render(job)
            elif kind == "rewrite":
                start, end = utf16_index(chapter["body"], payload["start"]), utf16_index(chapter["body"], payload["end"])
                if start >= end:
                    raise ValueError("请先选择需要改写的文字")
                selected = chapter["body"][start:end]
                response = self.remote(job, "/chat/completions", {"model":payload["_config"]["text_model"], "max_tokens":1000,
                    "messages":[{"role":"system","content":"你是剧本编辑。只输出改写后的选区正文，保留 DSL 结构，不添加说明或代码围栏。选区以外内容由程序保护。"},
                    {"role":"user","content":dumps({"instruction":payload.get("instruction", "精简并增强戏剧冲突"),"selected_text":selected})}]})
                replacement = response["choices"][0]["message"]["content"]
                if not isinstance(replacement, str) or not replacement.strip():
                    raise ValueError("供应商返回了空白改写结果")
                output = {"replacement": replacement, "base_revision": chapter["revision"], "start":payload["start"], "end":payload["end"]}
                tokens = response.get("usage", {}).get("total_tokens", len(selected.encode())+1000)
                charge = (payload["_config"]["text_model"], tokens/1000*payload["_config"]["text_price"], {"tokens":tokens,"basis":"configured_blended_rate"})
            if charge:
                # Cost is durable even if a concurrent edit makes the resulting artifact obsolete.
                with self.store.connection(immediate=True) as conn:
                    conn.execute("INSERT OR IGNORE INTO ledger VALUES(?,?,?,?,?,?,?)", (job["id"]+":"+target, job["id"], payload["_config"]["provider_url"], charge[0], charge[1], time.time(), dumps(charge[2])))
                    conn.execute("UPDATE jobs SET result='{}' WHERE id=? AND token=?", (job["id"], job["token"]))
            with self.store.connection(immediate=True) as conn:
                active = self.active(conn, job)
                if not active:
                    return
                current = self.store.chapter(chapter["id"], conn)
                if current["revision"] != payload["revision"]:
                    raise Conflict("任务完成时剧本已变更，未覆盖当前内容；外部调用费用按已发生用量记录")
                if kind == "export":
                    now_shots=[s for s in self.store.shots(job["project_id"],conn) if s["id"] in payload["target_ids"]]
                    current_fingerprint=fingerprint([{k:s.get(k) for k in ("id","revision","image","audio","duration","stale","asset_changed")} for s in now_shots])
                    if current_fingerprint != payload["media_fingerprint"]:
                        raise Conflict("合成期间镜头或媒体已变更，未发布过期样片，请重新导出")
                    fields=('id','image','video','audio','duration','action','dialogue','speaker','style','size','camera','voice','voice_rate','prompt_override','asset_ids','stale','asset_changed')
                    by_id={s['id']:s for s in now_shots}
                    output['source']={'version':1,'chapter_id':current['id'],'chapter_revision':current['revision'],
                        'shots':[{key:by_id[identifier].get(key) for key in fields} for identifier in payload['target_ids']],
                        'visual_updated':json.loads(conn.execute('SELECT data FROM projects WHERE id=?',(job['project_id'],)).fetchone()[0]).get('visual_updated',0)}
                if kind == "extract":
                    existing = self.store.assets(job["project_id"], conn)
                    count = 0
                    for item in extract_assets(current["ast"]):
                        if any(a["type"] == item["type"] and (a["name"] == item["name"] or item["name"] in a["data"].get("aliases", [])) for a in existing):
                            continue
                        conn.execute("INSERT INTO assets VALUES(?,?,?,?,?,?,?)", (uid("as_"), job["project_id"], item["type"], item["name"], 0, 1, dumps(item["data"])))
                        count += 1
                    output = {"created":count,"mode":"local_rules"}
                elif kind == "compile":
                    dependent=conn.execute("SELECT COUNT(*) FROM jobs WHERE id<>? AND state IN ('PENDING','RUNNING','PAUSED') AND json_extract(payload,'$.chapter_id')=? AND kind IN ('images','voices','export','videos')",(job["id"],current["id"])).fetchone()[0]
                    if dependent:
                        raise Conflict("当前章节仍有媒体任务，请等待完成或取消后再编译")
                    project = json.loads(conn.execute("SELECT data FROM projects WHERE id=?", (job["project_id"],)).fetchone()[0])
                    rows = compile_shots(current["ast"], current["id"], current["revision"], self.store.assets(job["project_id"], conn), visual_style(project))
                    conn.execute("DELETE FROM shots WHERE chapter_id=?", (current["id"],))
                    for index, new in enumerate(rows):
                        conn.execute("INSERT INTO shots VALUES(?,?,?,?,?)", (new["id"], job["project_id"], current["id"], index, dumps(new)))
                    output = {"count":len(rows)}
                elif shot:
                    row = conn.execute("SELECT data FROM shots WHERE id=?", (shot["id"],)).fetchone()
                    if not row:
                        raise Conflict("镜头已被重编译，结果未覆盖新镜头")
                    current_shot = json.loads(row[0])
                    if current_shot.get("revision", 1) != payload["shot_revisions"][shot["id"]]:
                        raise Conflict("镜头已编辑，结果未覆盖新版本")
                    if kind=='videos':
                        if current_shot.get('image')!=payload['video_first_frames'][target]:raise Conflict('视频生成期间首帧已变化，未覆盖当前镜头；供应商费用已单独记录。')
                        current_shot.setdefault('video_versions',[]).append({'url':output['video'],'mode':'provider_video','created':time.time()})
                        current_shot['status']='待审'
                    if output.get("image"):
                        current_shot['video']=None
                        current_shot.setdefault("image_versions", []).append({"url":output["image"], "mode":output["mode"], "created":time.time()})
                        current_shot["status"] = "待审"
                        current_shot["asset_changed"] = False
                    current_shot.update(output)
                    conn.execute("UPDATE shots SET data=? WHERE id=?", (dumps(current_shot), shot["id"]))
                job["checkpoint"].append(target)
                progress = round(100*len(job["checkpoint"])/len(targets))
                conn.execute("UPDATE jobs SET checkpoint=?,progress=?,result=?,updated=? WHERE id=?", (dumps(job["checkpoint"]),progress,dumps(output),time.time(),job["id"]))
                self.store.event(conn, job["id"], f"已提交 {len(job['checkpoint'])}/{len(targets)} 个产物")
            if kind == "export":
                break
        with self.store.connection(immediate=True) as conn:
            if self.active(conn, job):
                conn.execute("UPDATE jobs SET state='SUCCEEDED',progress=100,lease_until=0,updated=? WHERE id=?", (time.time(),job["id"]))
                self.store.event(conn, job["id"], "执行完成，产物已保存")

    def render_cards(self, cards):
        request_path=self.store.root/(uid("render_")+".json")
        request_path.write_text(dumps({"cards":cards}),encoding="utf-8-sig")
        try:
            run_process(["powershell.exe","-NoProfile","-NonInteractive","-ExecutionPolicy","RemoteSigned","-File",str(APP_ROOT/"render-cards.ps1"),"-RequestPath",str(request_path)],timeout=180)
        except subprocess.CalledProcessError as exc:
            raise ValueError("本地画面渲染失败："+exc.stderr.decode("utf-8","replace")[-500:]) from None
        finally:
            request_path.unlink(missing_ok=True)

    def execute_episode(self, job):
        """A persisted parent plus idempotent children; no browser tab is needed to finish."""
        workflow=job['payload'].get('workflow_mode','local_preview');paid=workflow!='local_preview'
        stages=[('extract','提取角色与场景')]+([('asset_images','生成角色与场景定妆参考')] if paid else [])+[('compile','编译镜头表'),('images','生成AI画面' if paid else '生成本地画面'),('voices','配音并对齐时长')]+([('videos','生成动态镜头')] if workflow=='ai_video' else [])+[('export','合成、字幕与黑帧质检')]
        final={}
        for index,(kind,label) in enumerate(stages):
            if kind in job["checkpoint"]:
                continue
            with self.store.connection() as conn:
                if not self.active(conn,job) or pause_boundary(self.store,conn,job):return
            payload={"chapter_id":job["payload"]["chapter_id"],"revision":job["payload"]["revision"],"parent_job_id":job["id"],"mode":"remote" if paid and kind in {"images","asset_images","videos"} else "local"}
            shots=[s for s in self.store.shots(job["project_id"]) if s["chapter_id"]==payload["chapter_id"]]
            skip=False
            if kind in {"images","voices","export","videos"}:
                payload["target_ids"]=[s["id"] for s in shots if kind!="voices" or s.get("dialogue")]
                skip=not payload["target_ids"]
            if kind=='asset_images':
                assets=self.store.assets(job['project_id'])
                with self.store.connection() as conn:
                    payload['target_ids']=[a['id'] for a in assets if a['type'] in {'characters','scenes','props'} and not conn.execute("SELECT 1 FROM asset_media WHERE asset_id=? AND kind='image' AND mode<>'local' LIMIT 1",(a['id'],)).fetchone()]
                skip=not payload['target_ids']
            if kind=="images" and not paid:payload["native_images"]=True
            if kind=="export":payload["auto_frames"]=True
            if not skip:
                child_id=self.submit(job["project_id"],kind,payload,job["id"]+":"+kind)
                child=self.claim(child_id)
                if child:self.process_job(child)
                while True:
                    with self.store.connection() as conn:
                        if not self.active(conn,job):return
                        record=conn.execute("SELECT * FROM jobs WHERE id=?",(child_id,)).fetchone()
                    if record['state']=='PAUSED':
                        with self.store.connection(immediate=True) as conn:pause_boundary(self.store,conn,job)
                        return
                    if record["state"]=="SUCCEEDED":break
                    if record["state"] in {"FAILED","CANCELED"}:raise ValueError(label+"未完成："+(record["error"] or "子任务已取消"))
                    self.stop.wait(.2)
                final=json.loads(record["result"])
            if kind=="voices":
                aligned=0
                with self.store.connection(immediate=True) as conn:
                    for shot in self.store.shots(job["project_id"],conn):
                        if shot["chapter_id"]!=payload["chapter_id"]:continue
                        if shot.get("audio_duration",0)>shot["duration"]+.05:
                            duration=math.ceil((shot["audio_duration"]+.2)*10)/10
                            if duration>60:raise ValueError("单句配音超过 60 秒，请回故事台拆句")
                            shot["duration"]=duration;shot["revision"]=shot.get("revision",1)+1
                            conn.execute("UPDATE shots SET data=? WHERE id=?",(dumps(shot),shot["id"]));aligned+=1
                    if aligned:self.store.event(conn,job["id"],f"已自动延长 {aligned} 个镜头，保留完整语音")
            job["checkpoint"].append(kind)
            with self.store.connection(immediate=True) as conn:
                if not self.active(conn,job):return
                conn.execute("UPDATE jobs SET checkpoint=?,progress=?,result=?,updated=? WHERE id=?",(dumps(job["checkpoint"]),round((index+1)/len(stages)*100),dumps(final),time.time(),job["id"]))
                self.store.event(conn,job["id"],label+"已完成")
        with self.store.connection(immediate=True) as conn:
            if self.active(conn,job):
                conn.execute("UPDATE jobs SET state='SUCCEEDED',progress=100,lease_until=0,updated=? WHERE id=?",(time.time(),job["id"]))
                self.store.event(conn,job["id"],"本集样片生成完成，可下载 MP4、字幕和质检报告")

    def render(self, job):
        payload = job["payload"]
        all_shots = self.store.shots(job["project_id"])
        by_id = {s["id"]:s for s in all_shots}
        shots = [by_id[i] for i in payload["target_ids"]]
        media = self.store.root / "media"
        if any(s.get("video") for s in shots):payload["auto_frames"]=True
        project=None
        if payload.get("auto_frames"):
            project=None
            with self.store.connection() as conn:project=json.loads(conn.execute("SELECT data FROM projects WHERE id=?",(job["project_id"],)).fetchone()[0])
            width,height=dimensions(project["ratio"])
            cards=[];frames={}
            for index,shot in enumerate(shots):
                path=media/(uid("frame_")+".png");frames[shot["id"]]=path.name
                image=media/Path(shot.get("image") or "").name
                cards.append({"output":str(path),"image":str(image) if image.is_file() else None,"width":width,"height":height,"variant":index%6,
                              "compose":True,"transparent":bool(shot.get("video")),"title":project["name"],"mark":"本地分镜样片 / YAOBAO DIRECTOR", "caption":(shot["speaker"]+"："+shot["dialogue"]) if shot.get("dialogue") else shot["action"],"label":f"SHOT {index+1:02} / {shot['duration']}s"})
            self.render_cards(cards);payload["frames"]=frames
        stem = uid("film_")
        concat, audio_path, video_path = media/(stem+".txt"), media/(stem+".wav"), media/(stem+".mp4")
        with wave.open(str(audio_path), "wb") as out:
            out.setnchannels(1); out.setsampwidth(2); out.setframerate(24000)
            for shot in shots:
                count = round(shot["duration"] * 24000)
                raw = b""
                if shot.get("audio"):
                    path = media / Path(shot["audio"]).name
                    with wave.open(str(path), "rb") as source:
                        if (source.getframerate(), source.getnchannels(), source.getsampwidth()) != (24000, 1, 2):
                            raise ValueError("音轨格式不一致，请重新配音")
                        raw = source.readframes(source.getnframes())
                    if len(raw) > count * 2 + 2400:
                        raise ValueError("台词超长，已停止合成以避免截断")
                out.writeframes(raw + b"\0" * max(0, count*2-len(raw)))
        segments=[]
        if any(s.get('video') for s in shots):
            segments=motion_segments(self,shots,media,payload['frames'],stem,width,height)
            lines=["file '"+path.name+"'" for path in segments]
        else:
            lines = []
            for shot in shots:
                frame_name = payload["frames"][shot["id"]]
                if not re.fullmatch(r"frame_[a-f0-9]+\.png", frame_name):
                    raise ValueError("导出画面名称无效")
                lines += ["file '"+frame_name+"'", "duration "+str(shot["duration"])]
            lines.append("file '"+payload["frames"][shots[-1]["id"]]+"'")
        concat.write_text("\n".join(lines), encoding="utf-8")
        args = [ffmpeg_path(), "-hide_banner", "-loglevel", "warning", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
                "-i",str(audio_path), "-vf","fps=24,format=yuv420p", "-c:v","libx264","-preset","veryfast","-crf","22",
                "-c:a","aac","-b:a","128k","-t",str(sum(s["duration"] for s in shots)),"-movflags","+faststart",str(video_path)]
        try:
            run_process(args, timeout=300)
            scan = run_process([ffmpeg_path(),"-hide_banner","-i",str(video_path),"-vf","blackdetect=d=0.3:pix_th=0.05","-an","-f","null","-"],timeout=180)
            black = b"black_start:" in scan.stderr
            if black:
                video_path.unlink(missing_ok=True)
                raise ValueError("黑帧检测未通过，请重新选择画面")
            metadata=scan.stderr.decode("utf-8","replace")
            match=re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)",metadata)
            if not match:raise ValueError("无法核实输出视频时长，未发布样片")
            actual_duration=int(match[1])*3600+int(match[2])*60+float(match[3])
            expected_duration=sum(s["duration"] for s in shots)
            if abs(actual_duration-expected_duration)>.2:
                raise ValueError("输出时长与镜头时间线不符，未发布样片")
            volume=run_process([ffmpeg_path(),"-hide_banner","-i",str(video_path),"-af","volumedetect","-vn","-sn","-f","null","-"],timeout=120)
            volume_match=re.search(r"mean_volume:\s*(-?inf|-?\d+(?:\.\d+)?)\s*dB",volume.stderr.decode("utf-8","replace"))
            mean_db=float(volume_match[1]) if volume_match else None
            if any(s.get("dialogue") for s in shots) and (mean_db is None or mean_db < -70):
                raise ValueError("成片台词音轨近乎静音，未发布样片，请检查配音")
        except subprocess.CalledProcessError as exc:
            raise ValueError("合成失败：" + exc.stderr.decode("utf-8", "replace")[-600:]) from None
        finally:
            concat.unlink(missing_ok=True)
            audio_path.unlink(missing_ok=True)
            for path in segments:path.unlink(missing_ok=True)
        subtitle = media/(stem+".srt"); subtitle.write_text(srt_for(shots), encoding="utf-8-sig")
        report = {"width":width if payload.get("auto_frames") else None,"height":height if payload.get("auto_frames") else None,"ratio":project["ratio"] if project else None,"black_frames":"通过（FFmpeg 扫描）", "audio":"已检测输出音轨音量；动作镜头允许静音", "audio_mean_db":mean_db if mean_db is not None and math.isfinite(mean_db) else None,
                  "duration":round(actual_duration,3),"duration_expected":round(expected_duration,3),"duration_error":round(abs(actual_duration-expected_duration),3),
                  "subtitles":"按镜头边界生成，已烧录画面并附 SRT；未做语音级强制对齐", "mode":"本地分镜样片" if any(s.get("mode") == "local" for s in shots) else "静帧分镜成片"}
        if any(s.get("video") for s in shots):report.update(mode="视频与分镜混合成片",video_shots=sum(bool(s.get("video")) for s in shots),video_audio="导入视频原声未混入，使用角色配音；短素材按镜长循环或截取")
        report_path=media/(stem+".json");report_path.write_text(dumps(report),encoding="utf-8")
        return {"video":"/media/"+video_path.name,"subtitles":"/media/"+subtitle.name,"report":"/media/"+report_path.name,"qa":report}
