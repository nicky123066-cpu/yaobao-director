"""Durable Seedance tasks. A known provider ID is polled, never recreated."""
import json
import math
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from domain import prompt_for,uid
from gateway import api_key
from model_workflow import data_image,require_capability
from store import dumps,Conflict

TASKS='/contents/generations/tasks'

class VideoTasks:
    def __init__(self,engine):
        self.engine=engine;self.store=engine.store
        with self.store.connection() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS provider_video_tasks(
                job_id TEXT NOT NULL,target_id TEXT NOT NULL,provider_id TEXT NOT NULL,
                state TEXT NOT NULL,duration INTEGER NOT NULL,local_video TEXT NOT NULL DEFAULT '',
                updated REAL NOT NULL,PRIMARY KEY(job_id,target_id))''')
    def recoverable(self,job_id):
        with self.store.connection() as conn:return bool(conn.execute("SELECT 1 FROM provider_video_tasks WHERE job_id=? AND state IN ('queued','running','succeeded') LIMIT 1",(job_id,)).fetchone())
    def request(self,config,method,path):
        secret=api_key(config,self.store.root)
        if not secret:raise ValueError('视频任务对应的火山密钥不可用，请恢复原连接后核对任务。')
        request=urllib.request.Request(config['provider_url'].rstrip('/')+path,method=method,headers={'Authorization':'Bearer '+secret,'Accept':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=25) as response:
                raw=response.read(4*1024*1024+1)
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            code=exc.code;exc.close()
            raise ValueError('视频任务查询HTTP '+str(code)+'，保留原任务ID；恢复连接后继续查询，不重新创建。') from None
        except (OSError,ValueError):raise ValueError('视频任务查询暂未确认，已保留原任务ID；稍后可继续查询。') from None
    def row(self,job_id,target):
        with self.store.connection() as conn:r=conn.execute('SELECT * FROM provider_video_tasks WHERE job_id=? AND target_id=?',(job_id,target)).fetchone()
        return dict(r) if r else None
    def _clear_marker(self,conn,job_id):
        row=conn.execute('SELECT result FROM jobs WHERE id=?',(job_id,)).fetchone()
        result=json.loads(row[0]);result.pop('inflight',None)
        conn.execute('UPDATE jobs SET result=? WHERE id=?',(dumps(result),job_id))
    def _record(self,job,row,response):
        state=response.get('status')
        if state not in {'queued','running','cancelled','succeeded','failed','expired'}:raise ValueError('供应商视频任务状态无法识别；保留原任务等待核对。')
        with self.store.connection(immediate=True) as conn:
            conn.execute('UPDATE provider_video_tasks SET state=?,updated=? WHERE job_id=? AND target_id=?',(state,time.time(),job['id'],row['target_id']))
            if state=='succeeded':
                config=job['payload']['_config'];usage=response.get('usage') or {}
                details=dict(units=row['duration'],unit='video_second',basis='configured_estimate_not_provider_bill',provider_task=row['provider_id'],usage={k:v for k,v in usage.items() if isinstance(v,(int,float)) and math.isfinite(v)})
                conn.execute('INSERT OR IGNORE INTO ledger VALUES(?,?,?,?,?,?,?)',(job['id']+':'+row['target_id'],job['id'],config['provider_url'],config['video_model'],row['duration']*float(config.get('video_price',1)),time.time(),dumps(details)))
            if state in {'cancelled','failed','expired'} and not conn.execute("SELECT 1 FROM provider_video_tasks WHERE job_id=? AND state IN ('queued','running','succeeded') LIMIT 1",(job['id'],)).fetchone():self._clear_marker(conn,job['id'])
        return state
    def download(self,url):
        p=urlsplit(url)
        if p.scheme!='https' or not p.hostname or p.username or p.password:raise ValueError('视频任务未返回有效HTTPS成片地址。')
        import ipaddress
        try:address=ipaddress.ip_address(p.hostname)
        except ValueError:address=None
        if p.hostname=='localhost' or address is not None and not address.is_global:raise ValueError('视频下载地址不能是本机或内网地址。')
        path=self.store.root/'media'/(uid('video_')+'.mp4');temporary=path.with_suffix('.part')
        try:
            with urllib.request.urlopen(url,timeout=120) as response,temporary.open('wb') as stream:
                total=0
                while chunk:=response.read(1024*1024):
                    total+=len(chunk)
                    if total>128*1024*1024:raise ValueError('视频超过128MB，请降低分辨率或缩短镜头。')
                    stream.write(chunk)
            with temporary.open('rb') as stream:header=stream.read(16)
            if len(header)<12 or header[4:8]!=b'ftyp':raise ValueError('供应商成片不是可识别的MP4，请核对任务结果。')
            temporary.replace(path)
            return '/media/'+path.name
        finally:temporary.unlink(missing_ok=True)
    def run(self,job,shot):
        config=job['payload']['_config'];model=require_capability(config,'video')
        row=self.row(job['id'],shot['id'])
        if not row:
            frame=shot.get('image','')
            if not re.fullmatch(r'/media/[A-Za-z0-9_.-]+\.(png|jpg|jpeg|webp)',frame):raise ValueError('动态镜头需先选择PNG、JPEG或WebP首帧，不能使用SVG示意图。')
            path=(self.store.root/'media'/Path(frame).name)
            if path.is_symlink() or not path.is_file():raise ValueError('动态镜头首帧文件不存在。')
            duration=max(4,math.ceil(shot['duration']))
            maximum=30 if '-2-5-' in model else 15
            if duration>maximum:raise ValueError('当前模型单镜最长'+str(maximum)+'秒，请先拆分镜头。')
            body=dict(model=model,content=[{'type':'text','text':prompt_for(shot,self.store.assets(job['project_id']))+'\n让人物与场景按动作自然运动，保持首帧人物、服装和场景一致。无新增台词。'},
                {'type':'image_url','image_url':{'url':data_image(path.name,path.read_bytes())},'role':'first_frame'}],duration=duration,resolution=config.get('video_resolution','720p'),ratio='adaptive',generate_audio=False,watermark=config.get('video_watermark',True))
            response=self.engine.remote(job,TASKS,body)
            provider_id=response.get('id','')
            if not isinstance(provider_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}',provider_id):raise ValueError('视频提交结果未返回任务ID，请先核对供应商记录，勿重复创建。')
            with self.store.connection(immediate=True) as conn:
                conn.execute('INSERT INTO provider_video_tasks(job_id,target_id,provider_id,state,duration,updated) VALUES(?,?,?,?,?,?)',(job['id'],shot['id'],provider_id,'queued',duration,time.time()))
                conn.execute('UPDATE jobs SET result=? WHERE id=?',(dumps({'inflight':TASKS+'/'+provider_id,'provider_task_id':provider_id}),job['id']))
                self.store.event(conn,job['id'],'视频任务已提交，接下来只查询此任务，不重复创建')
            row=self.row(job['id'],shot['id'])
        started=time.monotonic();previous=None
        while True:
            with self.store.connection() as conn:
                if not self.engine.active(conn,job):return None
            if self.engine.stop.is_set() or time.monotonic()-started>config.get('video_timeout',1200):raise ValueError('视频仍在处理；原任务ID已保存，可继续查询，不能再次创建付费任务。')
            result=self.request(config,'GET',TASKS+'/'+row['provider_id']);state=self._record(job,row,result)
            if state!=previous:
                with self.store.connection() as conn:self.store.event(conn,job['id'],'供应商视频状态：'+state)
                previous=state
            if state=='succeeded':
                local=row.get('local_video')
                if not local or not (self.store.root/'media'/Path(local).name).is_file():
                    local=self.download((result.get('content') or {}).get('video_url',''))
                    with self.store.connection() as conn:conn.execute('UPDATE provider_video_tasks SET local_video=?,updated=? WHERE job_id=? AND target_id=?',(local,time.time(),job['id'],shot['id']))
                return dict(video=local,mode='provider_video',provider_task_id=row['provider_id'],generated_video_seconds=row['duration'])
            if state in {'failed','expired','cancelled'}:raise ValueError('供应商视频任务'+state+'；未替换原镜头，请核对供应商记录后再决定重试。')
            self.engine.stop.wait(config.get('video_poll_seconds',4))
    def inspect(self,job_id,cancel=False):
        with self.store.connection() as conn:
            stored=conn.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
            rows=[dict(r) for r in conn.execute('SELECT * FROM provider_video_tasks WHERE job_id=?',(job_id,))]
        if not stored:raise ValueError('视频任务不存在。')
        job={**dict(stored),'payload':json.loads(stored['payload'])};config=job['payload']['_config'];result=[]
        for row in rows:
            response=self.request(config,'GET',TASKS+'/'+row['provider_id']);state=self._record(job,row,response)
            if cancel and state=='queued':
                try:self.request(config,'DELETE',TASKS+'/'+row['provider_id'])
                except ValueError:pass  # It may have become running; re-query instead of deleting terminal records.
                # DELETE is requested only for an observed queued task, never a terminal record.
                response=self.request(config,'GET',TASKS+'/'+row['provider_id']);state=self._record(job,row,response)
            result.append(dict(target_id=row['target_id'],provider_task_id=row['provider_id'],status=state,cancel_supported=state=='queued'))
        if not rows:raise ValueError('没有可核对的视频任务ID；若提交结果未知，请在供应商后台核对，勿重复生成。')
        if all(r['status'] in {'failed','expired','cancelled'} for r in result):
            with self.store.connection(immediate=True) as conn:self._clear_marker(conn,job_id)
        return dict(items=result,created_new_tasks=False)
