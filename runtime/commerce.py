"""Manual commerce-video drafts and local exports using user supplied media."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import textwrap
import wave
from domain import uid, fingerprint
from store import Conflict, dumps
from engine import ffmpeg_path, APP_ROOT
from production import pause_boundary


def command(args, cwd=None, timeout=300):
    try:
        return subprocess.run(args,cwd=cwd,capture_output=True,timeout=timeout,check=True,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except subprocess.CalledProcessError as exc:
        raise ValueError('素材处理失败：'+exc.stderr.decode('utf-8','replace')[-450:]) from None


def probe(path):
    run=subprocess.run([ffmpeg_path(),'-hide_banner','-protocol_whitelist','file,pipe','-i',str(path)],
                       capture_output=True,timeout=25,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    text=run.stderr.decode('utf-8','replace')
    match=re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)',text)
    return dict(duration=int(match[1])*3600+int(match[2])*60+float(match[3]) if match else 0,
                video=bool(re.search(r'Stream #.*Video:',text)),audio=bool(re.search(r'Stream #.*Audio:',text)))


def stamp(seconds):
    ms=round(seconds*1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'


def captions(text,duration):
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    return '\n\n'.join(f'{i+1}\n{stamp(i*duration/len(lines))} --> {stamp((i+1)*duration/len(lines))}\n{line}' for i,line in enumerate(lines))+'\n' if lines else ''


class Commerce:
    def __init__(self,store):
        self.store=store
        with store.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS commerce_drafts(id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS commerce_media(id TEXT PRIMARY KEY,data TEXT NOT NULL);
            ''')

    def summary(self):
        with self.store.connection() as db:
            drafts=[json.loads(r[0]) for r in db.execute('SELECT data FROM commerce_drafts ORDER BY rowid DESC')]
            media=[json.loads(r[0]) for r in db.execute('SELECT data FROM commerce_media ORDER BY rowid DESC')]
        return dict(drafts=drafts,media=media,ffmpeg=bool(ffmpeg_path()),avatar_connected=False,
                    modes=['real','product'],notice='真人实拍保留原声；商品图可用本地配音。照片数字人口播和精确口型尚未接入。')

    def get(self,identifier,db=None):
        if db is None:
            with self.store.connection() as conn:return self.get(identifier,conn)
        row=db.execute('SELECT data FROM commerce_drafts WHERE id=?',(identifier,)).fetchone()
        if not row:raise ValueError('带货项目不存在。')
        return json.loads(row[0])

    def media(self,identifier,kind=None):
        with self.store.connection() as db:row=db.execute('SELECT data FROM commerce_media WHERE id=?',(identifier,)).fetchone()
        if not row:raise ValueError('请选择已上传的本机素材。')
        item=json.loads(row[0]);path=self.store.root/'media'/Path(item['url']).name
        if not path.is_file() or path.is_symlink() or path.resolve().parent!=(self.store.root/'media').resolve():raise ValueError('素材已移动或不可用。')
        if kind and item['kind']!=kind:raise ValueError('素材类型不符合当前制作方式。')
        return item,path

    def upload(self,stream,size,name):
        if not ffmpeg_path():raise ValueError('未找到FFmpeg。')
        if type(size) is not int or not 12<=size<=250*1024*1024:raise ValueError('素材需在250MB以内。')
        suffix=Path(name).suffix.lower()
        if suffix not in {'.mp4','.mov','.png','.jpg','.jpeg','.webp'}:raise ValueError('支持MP4/MOV视频和PNG/JPEG/WebP图片。')
        identifier=uid('cm_');path=self.store.root/'media'/(identifier+suffix);temporary=path.with_suffix('.upload')
        digest=hashlib.sha256()
        try:
            with temporary.open('xb') as output:
                left=size
                while left:
                    chunk=stream.read(min(left,1024*1024))
                    if not chunk:raise ValueError('上传未完成，请重新选择素材。')
                    output.write(chunk);digest.update(chunk);left-=len(chunk)
            header=temporary.read_bytes()[:32] if size<32 else None
            if header is None:
                with temporary.open('rb') as source:header=source.read(32)
            is_video=suffix in {'.mp4','.mov'}
            valid=header[4:8]==b'ftyp' if is_video else header.startswith((b'\x89PNG\r\n\x1a\n',b'\xff\xd8\xff')) or header[:4]==b'RIFF' and header[8:12]==b'WEBP'
            if not valid:raise ValueError('文件内容与支持的媒体格式不符。')
            temporary.replace(path);metadata=probe(path)
            if not metadata['video'] or is_video and not 0<metadata['duration']<=3600:raise ValueError('媒体不可解码，或视频时长超过60分钟。')
            item=dict(id=identifier,name=Path(name).name[:120],url='/media/'+path.name,kind='video' if is_video else 'image',sha256=digest.hexdigest(),**metadata)
            with self.store.connection() as db:db.execute('INSERT INTO commerce_media VALUES(?,?)',(identifier,dumps(item)))
            return item
        except Exception:
            path.unlink(missing_ok=True)
            raise
        finally:temporary.unlink(missing_ok=True)

    def save(self,data):
        old=self.get(data['id']) if data.get('id') else None
        fields={}
        for key,limit in [('name',80),('price',100),('selling_points',2000),('audience',300),('cta',300),('script',6000),('subtitles',2000)]:
            value=data.get(key,'')
            if not isinstance(value,str) or len(value)>limit or '\x00' in value:raise ValueError('商品资料格式或长度无效。')
            fields[key]=value.strip()
        if not fields['name'] or not fields['selling_points']:raise ValueError('请填写商品名称和已确认的卖点。')
        mode=data.get('mode','real');ratio=data.get('ratio','9:16');duration=data.get('duration',30);start=data.get('start',0)
        if mode not in {'real','product','avatar'} or ratio not in {'9:16','16:9','1:1'} or type(duration) not in (int,float) or not math.isfinite(duration) or not 3<=duration<=120 or type(start) not in (int,float) or not math.isfinite(start) or not 0<=start<=3600:raise ValueError('制作方式、比例或时长无效。')
        media_ids=data.get('media_ids',[])
        if not isinstance(media_ids,list) or len(media_ids)>8 or any(not isinstance(i,str) for i in media_ids) or len(set(media_ids))!=len(media_ids):raise ValueError('最多选择8项不同素材。')
        for identifier in media_ids:self.media(identifier)
        if old and data.get('revision')!=old['revision']:raise Conflict('商品资料已更新，请刷新后保存。')
        identifier=old['id'] if old else self.store.new_project(fields['name']+' · 带货',ratio=ratio,style='真人商品展示',premise=fields['selling_points'],episodes=1)
        value=dict(id=identifier,revision=old['revision']+1 if old else 1,mode=mode,ratio=ratio,duration=duration,start=start,media_ids=media_ids,**fields)
        with self.store.connection(immediate=True) as db:
            if old and self.get(identifier,db)['revision']!=old['revision']:raise Conflict('商品资料已更新。')
            db.execute('INSERT OR REPLACE INTO commerce_drafts VALUES(?,?)',(identifier,dumps(value)))
        return value

    def script(self,data):
        name=data.get('name','').strip();points=data.get('selling_points','').strip()
        if not name or not points:raise ValueError('请先填写商品名称与真实卖点。')
        audience=data.get('audience','').strip();price=data.get('price','').strip();cta=data.get('cta','').strip()
        text='\n'.join(filter(None,[f'正在挑选{name}的朋友，可以看看这款。',f'如果你关注{audience}，先了解这几个特点。' if audience else '',points,f'当前商品信息：{price}。' if price else '',cta or '具体规格与实时价格，请查看商品页面。']))
        return dict(script=text,outline=['开场介绍商品','展示真实卖点与使用细节','核对规格价格','引导查看商品'],mode='本地资料整理，未调用模型')

    def submit(self,engine,identifier,payload,idem):
        draft=self.get(identifier)
        if payload.get('manual_action') is not True:raise ValueError('请手动点击导出带货视频。')
        if payload.get('revision')!=draft['revision']:raise Conflict('商品资料已更新，请先保存再导出。')
        if draft['mode']=='avatar':raise ValueError('照片数字人口播尚未接入，不能用静态照片冒充真人口播。')
        if not ffmpeg_path():raise ValueError('未找到FFmpeg。')
        if not isinstance(idem,str) or not 1<=len(idem)<=160:raise ValueError('导出请求标识无效。')
        kind='video' if draft['mode']=='real' else 'image'
        sources=[self.media(i) for i in draft['media_ids']]
        sources=[(item,path) for item,path in sources if item['kind']==kind]
        if not sources:raise ValueError('请先上传并选择真人视频。' if kind=='video' else '请先选择商品图片。')
        if kind=='video':
            info=sources[0][0]
            if not info['audio']:raise ValueError('真人素材没有音轨，请上传带原声的视频，或选择商品图配音。')
            if draft['start']+draft['duration']>info['duration']+.15:raise ValueError('素材剩余时长不足，请缩短成片时长或调整起点。')
        elif not draft['script']:raise ValueError('商品图配音需要先填写并保存口播文案。')
        content={**draft,'manual_action':True,'sources':[item for item,_ in sources]};digest=fingerprint(content)
        with self.store.connection(immediate=True) as db:
            old=db.execute('SELECT id,digest FROM jobs WHERE idem=?',(idem,)).fetchone()
            if old:
                if old['digest']!=digest:raise Conflict('同一导出请求不能使用不同资料。')
                return old['id']
            if db.execute("SELECT 1 FROM jobs WHERE project_id=? AND kind='commerce' AND state IN ('PENDING','RUNNING','PAUSED')",(identifier,)).fetchone():raise Conflict('已有带货导出任务，请先完成或取消。')
            job_id=uid('job_');stamp_now=time.time()
            db.execute("INSERT INTO jobs(id,project_id,kind,state,payload,idem,digest,estimate,created,updated) VALUES(?,?,'commerce','PENDING',?,?,?,0,?,?)",(job_id,identifier,dumps(content),idem,digest,stamp_now,stamp_now))
            self.store.event(db,job_id,'带货合成已入队；使用本机素材，不调用数字人或视频模型')
        return job_id

    def render(self,engine,job):
        draft=job['payload'];media=self.store.root/'media';stem=uid('commerce_');video=media/(stem+'.mp4')
        duration=draft['duration'];sources=[self.media(item['id']) for item in draft['sources']]
        files=[];result_files=[]
        def alive():
            with self.store.connection() as db:
                if engine.stop.is_set() or not engine.active(db,job) or pause_boundary(self.store,db,job):return False
            if self.get(job['project_id'])['revision']!=draft['revision']:raise Conflict('合成期间商品资料已更新，请重新导出。')
            return True
        if not alive():return
        try:
            audio=None
            if draft['mode']=='product':
                audio=media/(stem+'.wav');request=media/(stem+'-speech.json');files.extend([audio,request])
                request.write_text(dumps(dict(text=draft['script'],output=str(audio),voice='',rate=0)),'utf-8')
                command(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(APP_ROOT/'speech.ps1'),'-RequestPath',str(request)],timeout=180)
                with wave.open(str(audio)) as wav:spoken=wav.getnframes()/wav.getframerate()
                if spoken>duration:raise ValueError(f'口播约{spoken:.1f}秒，超过成片时长；请缩短文案或延长时长。')
            title=media/(stem+'-title.txt');files.append(title);title.write_text('\n'.join(textwrap.wrap(draft['name']+(' · '+draft['price'] if draft['price'] else ''),width=28)),'utf-8')
            srt=media/(stem+'.srt');srt.write_text(captions(draft['subtitles'],duration),'utf-8-sig');result_files.append(srt)
            width,height={'9:16':(1080,1920),'16:9':(1920,1080),'1:1':(1080,1080)}[draft['ratio']]
            font=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/msyh.ttc'
            font_filter="fontfile='"+font.as_posix().replace(':','\\:')+"':" if font.is_file() else ''
            vf=f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=24'
            vf+=f",drawtext={font_filter}textfile={title.name}:expansion=none:fontcolor=white:fontsize=34:box=1:boxcolor=black@0.65:boxborderw=14:x=(w-tw)/2:y=55"
            if draft['subtitles'].strip():vf+=f",subtitles={srt.name}:force_style='FontName=Microsoft YaHei,FontSize=20,Outline=2,MarginV=35'"
            if not alive():return
            if draft['mode']=='real':
                args=[ffmpeg_path(),'-hide_banner','-loglevel','error','-y','-ss',str(draft['start']),'-protocol_whitelist','file,pipe','-i',str(sources[0][1]),'-map','0:v:0','-map','0:a:0','-vf',vf,'-af',f'afade=t=in:d=0.03,afade=t=out:st={max(0,duration-.03)}:d=0.03']
            else:
                concat=media/(stem+'-images.txt');files.append(concat);lines=[]
                for _,path in sources:lines.extend(["file '"+path.name+"'",'duration '+str(duration/len(sources))])
                lines.append("file '"+sources[-1][1].name+"'");concat.write_text('\n'.join(lines),'utf-8')
                args=[ffmpeg_path(),'-hide_banner','-loglevel','error','-y','-f','concat','-safe','1','-i',str(concat),'-i',str(audio),'-map','0:v:0','-map','1:a:0','-vf',vf,'-af','apad,afade=t=in:d=0.03']
            args+=['-t',str(duration),'-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart',str(video)]
            command(args,cwd=media,timeout=360)
            metadata=probe(video)
            if not metadata['video'] or not metadata['audio'] or abs(metadata['duration']-duration)>.25:raise ValueError('成片时长或音轨核验未通过。')
            if not alive():return
            report=media/(stem+'.json');result_files.append(report)
            qa=dict(duration=metadata['duration'],width=width,height=height,audio='保留真人原声' if draft['mode']=='real' else 'Windows本地配音',subtitles='按输入行数均分时长，非语音识别对齐' if draft['subtitles'] else '未添加对白字幕',avatar_generated=False,source_revision=draft['revision'])
            report.write_text(dumps(qa),'utf-8')
            output=dict(video='/media/'+video.name,subtitles='/media/'+srt.name,report='/media/'+report.name,qa=qa,commerce_revision=draft['revision'])
            with self.store.connection(immediate=True) as db:
                if not engine.active(db,job) or self.get(job['project_id'],db)['revision']!=draft['revision']:raise Conflict('任务已取消或商品资料已变更，未发布成片。')
                db.execute("UPDATE jobs SET state='SUCCEEDED',progress=100,result=?,lease_until=0,updated=? WHERE id=?",(dumps(output),time.time(),job['id']))
                self.store.event(db,job['id'],'带货成片已核验，可播放和下载MP4')
            result_files=[];video=None
        finally:
            for path in files+result_files+([video] if video else []):path.unlink(missing_ok=True)
