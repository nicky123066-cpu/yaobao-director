"""Manual-only production policy and authenticated loopback service."""
import json
import re
import secrets
import threading
import time
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs
from app import create_handler
from engine import Engine
from production import Production


class ManualEngine(Engine):
    def submit(self,project_id,kind,payload,idem):
        if kind=='episode' or payload.get('parent_job_id'):
            raise ValueError('独立桌面版按步骤手动制作，请分别操作资产、分镜、配音、视频与合成。')
        if payload.get('manual_action') is not True:
            raise ValueError('请在当前步骤点击生成，应用不会自动启动下一阶段。')
        if kind=='commerce':
            from commerce import Commerce
            return Commerce(self.store).submit(self,project_id,payload,idem)
        return super().submit(project_id,kind,payload,idem)

    def execute(self,job):
        if job['kind']=='commerce':
            from commerce import Commerce
            return Commerce(self.store).render(self,job)
        return super().execute(job)


def pause_unfinished(store):
    """Startup never resumes a paid call or queued stage without a user action."""
    Production(store)
    with store.connection(immediate=True) as db:
        rows=db.execute("SELECT id FROM jobs WHERE state IN ('PENDING','RUNNING','PAUSED')").fetchall()
        for row in rows:
            db.execute("UPDATE jobs SET state='PAUSED',token=NULL,lease_until=0,updated=? WHERE id=?",(time.time(),row['id']))
            db.execute('INSERT INTO job_controls(job_id,paused) VALUES(?,1) ON CONFLICT(job_id) DO UPDATE SET paused=1',(row['id'],))
            store.event(db,row['id'],'桌面应用打开后保持暂停，请手动核对并继续当前步骤；不自动运行下一阶段')
    return len(rows)


def handler_for(store,engine,port,ticket):
    Base=create_handler(store,engine,port)
    class Handler(Base):
        def security(self):
            super().security()
            if urlsplit(self.path).path=='/api/health':return
            try:
                cookie=SimpleCookie(self.headers.get('Cookie',''))
                value=cookie['director_session'].value if 'director_session' in cookie else ''
            except Exception:value=''
            if not secrets.compare_digest(value,ticket):raise PermissionError('请从幺爆导演台桌面应用打开。')

        def do_GET(self):
            parsed=urlsplit(self.path)
            if parsed.path=='/desktop/open':
                # One-time native window bootstrap; credentials never enter logs or disk.
                if self.headers.get('Host')!=f'127.0.0.1:{port}' or not secrets.compare_digest(parse_qs(parsed.query).get('ticket',[''])[0],ticket):
                    return self.reply({'error':'桌面会话无效'},403)
                return self.reply(b'',302,'text/plain',{'Location':'/?desktop=1#home','Set-Cookie':'director_session='+ticket+'; Path=/; HttpOnly; SameSite=Strict'})
            return super().do_GET()

        def route_mutation(self,method,path,body):
            match=re.fullmatch(r'/api/jobs/([a-z0-9_]+)/(resume|retry)',path)
            if match:
                with store.connection() as db:
                    row=db.execute('SELECT kind,payload FROM jobs WHERE id=?',(match[1],)).fetchone()
                if row and (row['kind']=='episode' or json.loads(row['payload']).get('parent_job_id')):
                    raise ValueError('历史自动流程仅作记录保留，请在对应制作步骤手动生成。')
                if row and row['kind']=='videos' and match[2]=='resume' and engine.video_tasks.recoverable(match[1]):
                    with store.connection(immediate=True) as db:
                        current=db.execute('SELECT state FROM jobs WHERE id=?',(match[1],)).fetchone()
                        if current['state']!='PAUSED':raise ValueError('当前视频任务无需恢复。')
                        db.execute("UPDATE jobs SET state='PENDING',token=NULL,lease_until=0,updated=? WHERE id=?",(time.time(),match[1]))
                        db.execute('UPDATE job_controls SET paused=0 WHERE job_id=?',(match[1],))
                        store.event(db,match[1],'用户手动恢复，只查询已有视频编号，不重复创建')
                    return self.reply({'id':match[1],'resumed_provider_task':True})
            return super().route_mutation(method,path,body)
    return Handler


def serve(store,workers=2):
    paused=pause_unfinished(store)
    engine=ManualEngine(store,workers=workers)
    server=ThreadingHTTPServer(('127.0.0.1',0),None)
    server.daemon_threads=True
    ticket=secrets.token_urlsafe(32)
    server.RequestHandlerClass=handler_for(store,engine,server.server_port,ticket)
    thread=threading.Thread(target=server.serve_forever,name='director-local-api',daemon=True)
    thread.start();engine.start()
    return server,engine,f'http://127.0.0.1:{server.server_port}/desktop/open?ticket='+ticket,paused


def shutdown(server,engine):
    engine.stop.set()
    pause_unfinished(engine.store)
    server.shutdown();server.server_close()
