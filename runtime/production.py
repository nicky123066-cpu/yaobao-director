"""Asset curation, references and resumable production controls behind one local interface."""
import base64
import json
import math
from pathlib import Path
import re
import struct
import time

from domain import uid
from store import Conflict, dumps

ASSET_TYPES={'characters':'R','scenes':'C','props':'P','references':'F','frames':'V','groups':'G'}
VIEWS={'reference','face','front','side','back','board','voice','clip'}

def asset_prompt(asset,style='电影感国漫'):
    data=asset['data']
    labels={'gender':'性别','age':'年龄','identity':'身份','appearance':'外貌','hairStyle':'发型','hairColor':'发色',
        'eyeColor':'瞳色','skinTone':'肤色','bodyType':'体型','accessories':'配饰','performanceAnchors':'表演锚点','description':'描述'}
    details='；'.join(label+'：'+str(data[key]) for key,label in labels.items() if data.get(key) and data[key]!='待补充')
    costumes='；'.join(str(c.get('state','默认'))+'：'+str(c.get('desc','')) for c in data.get('costumes',[]) if isinstance(c,dict))
    layout='角色定妆联系表：同一角色的面部近景、正面全身、侧面全身、背面全身；四个区域身份、服装、比例一致。' if asset['type']=='characters' else '场景多视角设定联系表，统一空间结构、光线与材质。' if asset['type']=='scenes' else '物件设定联系表，展示整体、侧面与材质细节。'
    return f'风格：{style}\n资产：{asset["name"]}\n{layout}\n{details}\n服装/状态：{costumes}\n干净背景，无文字、无水印；生成结果需人工核验一致性。'

def decode_media(value,name):
    if not isinstance(value,str) or len(value)>34*1024*1024:raise ValueError('素材需在 24MB 内，请先压缩长视频。')
    try:raw=base64.b64decode(value.split(',')[-1],validate=True)
    except (ValueError,TypeError):raise ValueError('素材编码无效。') from None
    if not 12<=len(raw)<=24*1024*1024:raise ValueError('素材需在 24MB 内。')
    if raw.startswith(b'\x89PNG\r\n\x1a\n') and len(raw)>=24:
        width,height=struct.unpack('>II',raw[16:24])
        if not 1<=width<=12000 or not 1<=height<=12000 or width*height>60_000_000:raise ValueError('图片尺寸过大。')
        kind,suffix='image','.png'
    elif raw.startswith(b'\xff\xd8\xff'):kind,suffix='image','.jpg'
    elif raw[:4]==b'RIFF' and raw[8:12]==b'WEBP':kind,suffix='image','.webp'
    elif raw[:4]==b'RIFF' and raw[8:12]==b'WAVE':kind,suffix='audio','.wav'
    elif raw[:3]==b'ID3' or raw[:2] in (b'\xff\xfb',b'\xff\xf3',b'\xff\xf2'):kind,suffix='audio','.mp3'
    elif raw[4:8]==b'ftyp' and raw[8:12] in {b'isom',b'iso2',b'avc1',b'mp41',b'mp42',b'qt  ',b'M4V ',b'dash'}:kind,suffix='video','.mp4'
    else:raise ValueError('仅支持 PNG/JPEG/WebP、WAV/MP3 与 MP4 素材，不接收网页或脚本。')
    return raw,kind,suffix

def pause_boundary(store,conn,job):
    requested=conn.execute('SELECT paused FROM job_controls WHERE job_id=?',(job['id'],)).fetchone()
    if not requested or not requested[0]:return False
    conn.execute("UPDATE jobs SET state='PAUSED',lease_until=0,token=NULL,updated=? WHERE id=? AND token=? AND state='RUNNING'",(time.time(),job['id'],job['token']))
    store.event(conn,job['id'],'已在产物提交断点暂停；恢复后跳过已完成子项')
    return True

class Production:
    def __init__(self,store):self.store=store

    @staticmethod
    def schema(conn):
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS asset_media(id TEXT PRIMARY KEY,asset_id TEXT NOT NULL REFERENCES assets(id),
                kind TEXT NOT NULL,url TEXT NOT NULL,name TEXT NOT NULL,view TEXT NOT NULL,mode TEXT NOT NULL,
                selected INTEGER NOT NULL DEFAULT 0,created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS job_controls(job_id TEXT PRIMARY KEY REFERENCES jobs(id),paused INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS prompt_templates(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),
                name TEXT NOT NULL,body TEXT NOT NULL,revision INTEGER NOT NULL,updated REAL NOT NULL);
        ''')

    def enrich(self,snapshot):
        with self.store.connection() as conn:
            for project in snapshot['projects']:
                from creative import dimensions
                project['output_width'],project['output_height']=dimensions(project['ratio'])
                project['prompt_templates']=[dict(r) for r in conn.execute('SELECT * FROM prompt_templates WHERE project_id=? ORDER BY updated DESC',(project['id'],))]
                counters={k:0 for k in ASSET_TYPES}
                for asset in project['assets']:
                    counters[asset['type']]+=1
                    asset['code']=ASSET_TYPES[asset['type']]+str(counters[asset['type']]).zfill(4)
                    asset['media']=[dict(r) for r in conn.execute('SELECT * FROM asset_media WHERE asset_id=? ORDER BY created DESC',(asset['id'],))]
                    primary=next((m for m in asset['media'] if m['selected'] and m['kind']=='image'),None)
                    asset['cover']=primary['url'] if primary else next((m['url'] for m in asset['media'] if m['kind']=='image'),None)
                    from creative import visual_style
                    asset['generation_prompt']=asset_prompt(asset,visual_style(project))
            paused={r['job_id']:bool(r['paused']) for r in conn.execute('SELECT * FROM job_controls')}
            for job in snapshot['jobs']:job['pause_requested']=paused.get(job['id'],False)
        return snapshot

    def template(self,body):
        identifier=body.get('id') or uid('pt_');project=body.get('project_id')
        with self.store.connection(immediate=True) as conn:
            if not conn.execute('SELECT 1 FROM projects WHERE id=?',(project,)).fetchone():raise ValueError('项目不存在')
            old=conn.execute('SELECT * FROM prompt_templates WHERE id=?',(identifier,)).fetchone()
            if old and (old['project_id']!=project or old['revision']!=body.get('revision')):raise Conflict('提示词模板已更新，请刷新')
            if body.get('delete'):
                if not old:raise ValueError('模板不存在')
                conn.execute('DELETE FROM prompt_templates WHERE id=?',(identifier,));return {'ok':True}
            name=body.get('name','');text=body.get('body','')
            if not isinstance(name,str) or not 1<=len(name.strip())<=80 or not isinstance(text,str) or not 1<=len(text.strip())<=6000:raise ValueError('模板需有名称（1–80字）和内容（1–6000字）')
            if conn.execute('SELECT 1 FROM prompt_templates WHERE project_id=? AND name=? AND id<>?',(project,name.strip(),identifier)).fetchone():raise Conflict('模板名称已存在')
            if not old and conn.execute('SELECT COUNT(*) FROM prompt_templates WHERE project_id=?',(project,)).fetchone()[0]>=100:raise ValueError('每项目最多 100 个模板')
            conn.execute('INSERT INTO prompt_templates VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,body=excluded.body,revision=excluded.revision,updated=excluded.updated',
                (identifier,project,name.strip(),text.strip(),old['revision']+1 if old else 1,time.time()))
        return {'id':identifier}

    @staticmethod
    def edit_shot(shot,values):
        original=dict(shot)
        allowed={'duration','size','camera','voice','voice_rate','status','image','prompt_override'}
        shot.update({k:v for k,v in values.items() if k in allowed})
        if isinstance(shot['duration'],bool) or not isinstance(shot['duration'],(int,float)) or not math.isfinite(shot['duration']) or not .5<=shot['duration']<=60:raise ValueError('镜长需在 0.5–60 秒之间')
        if shot['size'] not in {'大特写','特写','近景','中景','全景'}:raise ValueError('景别无效')
        if not isinstance(shot['camera'],str) or not 1<=len(shot['camera'].strip())<=80:raise ValueError('运镜需在 1–80 字之间')
        if shot.get('image') and shot['image'] not in [v['url'] for v in shot.get('image_versions',[])]:raise ValueError('只能选择已有画面版本')
        if shot['status'] not in {'待生成','待审','已定稿'}:raise ValueError('状态无效')
        if shot['status']=='已定稿' and (not (shot.get('image') or shot.get('video')) or shot.get('stale') or shot.get('asset_changed')):raise ValueError('请先更新或生成有效镜头素材再定稿')
        if shot.get('voice_rate') not in range(-5,6):raise ValueError('语速需在 -5 到 5 之间')
        prompt=shot.get('prompt_override','')
        if not isinstance(prompt,str) or len(prompt)>6000:raise ValueError('镜头补充提示词需在 6000 字以内')
        if any(shot.get(k)!=original.get(k) for k in ('voice','voice_rate')):shot.update(audio=None,audio_duration=0)
        if any(shot.get(k)!=original.get(k) for k in ('size','camera','prompt_override')):
            shot['asset_changed']=True;shot['status']='待审' if shot.get('image') or shot.get('video') else '待生成'
        if 'image' in values and values['image']!=original.get('image'):
            shot['video']=None
            version=next((v for v in shot.get('image_versions',[]) if v['url']==values['image']),{})
            shot['mode']=version.get('mode',shot.get('mode','local'))
        shot['revision']=shot.get('revision',1)+1
        return shot

    def batch_shots(self,body):
        ids=body.get('shot_ids');values=body.get('values',{})
        if not isinstance(ids,list) or not 1<=len(ids)<=100 or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):raise ValueError('一次编辑 1–100 个不同镜头')
        if not isinstance(values,dict) or not values or set(values)-{'duration','size','camera','status','prompt_override'}:raise ValueError('批量镜头字段无效')
        if not isinstance(body.get('revisions'),dict):raise ValueError('缺少镜头版本信息')
        with self.store.connection(immediate=True) as conn:
            for identifier in ids:
                row=conn.execute('SELECT project_id,chapter_id,data FROM shots WHERE id=?',(identifier,)).fetchone()
                if not row or row['project_id']!=body.get('project_id') or row['chapter_id']!=body.get('chapter_id'):raise ValueError('只能批量编辑当前项目和章节的镜头')
                shot=json.loads(row['data'])
                if shot.get('revision',1)!=body['revisions'].get(identifier):raise Conflict('所选镜头已更新，整批未保存，请刷新')
                conn.execute('UPDATE shots SET data=? WHERE id=?',(dumps(self.edit_shot(shot,values)),identifier))
        return {'updated':len(ids)}

    def shot_references(self,shot,config):
        with self.store.connection() as conn:
            refs=[]
            for identifier in shot.get('asset_ids',[]):
                ref=conn.execute("SELECT * FROM asset_media WHERE asset_id=? AND kind='image' AND mode<>'local' ORDER BY selected DESC,created DESC LIMIT 1",(identifier,)).fetchone()
                if ref:refs.append(dict(ref))
        if not refs:return []
        if config.get('image_reference_mode') not in {'openai_edits','ark_images'} and config.get('image_protocol')!='ark_images':raise ValueError('镜头资产已有参考图。请在创作模型中启用兼容 images/edits 的参考图接口后生成。')
        if len(refs)>8:raise ValueError('单镜头参考图最多 8 项，请精简镜头资产')
        files=[]
        for ref in refs:
            path=self.store.root/'media'/Path(ref['url']).name
            if not path.is_file() or path.is_symlink() or path.stat().st_size>24*1024*1024:raise ValueError('参考图片不可用')
            files.append(('image[]',path.name,path.read_bytes()))
        return files

    def save_asset(self,identifier,body,conn=None):
        if conn is None:
            with self.store.connection(immediate=True) as connection:return self.save_asset(identifier,body,connection)
        asset=conn.execute('SELECT * FROM assets WHERE id=?',(identifier,)).fetchone()
        if not asset:raise ValueError('资产不存在')
        if asset['revision']!=body['revision']:raise Conflict('资产已有新版本，请刷新')
        old=json.loads(asset['data']);data=body.get('data',old);locked=body.get('locked',bool(asset['locked']))
        if not isinstance(data,dict) or len(dumps(data))>40000:raise ValueError('资产字段格式或长度无效')
        if asset['locked'] and data!=old:raise Conflict('资产已锁定，请先解锁再编辑')
        name=str(data.get('name',asset['name'])).strip()[:80]
        if not name:raise ValueError('资产名称不能为空')
        aliases=data.get('aliases',[])
        if not isinstance(aliases,list) or len(aliases)>30 or any(not isinstance(a,str) or not a.strip() or len(a)>80 for a in aliases):raise ValueError('别名需为最多 30 个有效名称')
        for other in self.store.assets(asset['project_id'],conn):
            if other['id']!=identifier and other['type']==asset['type'] and set([name]+aliases)&set([other['name']]+other['data'].get('aliases',[])):
                raise Conflict('名称或别名与另一资产冲突，请先确认是否为同一角色')
        conn.execute('UPDATE assets SET name=?,data=?,locked=?,revision=revision+1 WHERE id=?',(name,dumps(data),int(bool(locked)),identifier))
        if data!=old:self._invalidate(conn,asset['project_id'],identifier)
        return {'ok':True}

    def _invalidate(self,conn,project_id,asset_id):
        for shot in self.store.shots(project_id,conn):
            if asset_id in shot.get('asset_ids',[]):
                shot['asset_changed']=True;shot['revision']=shot.get('revision',1)+1
                conn.execute('UPDATE shots SET data=? WHERE id=?',(dumps(shot),shot['id']))

    def import_assets(self,body):
        entries=body.get('assets')
        if not isinstance(entries,list) or not 1<=len(entries)<=300:raise ValueError('一次导入 1–300 项资产')
        prepared=[];names={kind:set() for kind in ASSET_TYPES}
        for entry in entries:
            if not isinstance(entry,dict) or entry.get('type') not in ASSET_TYPES:raise ValueError('资产类型无效')
            name=str(entry.get('name','')).strip()
            data=entry.get('data',{})
            if not name or len(name)>80 or not isinstance(data,dict) or len(dumps(data))>40000:raise ValueError('资产名称或设定无效')
            aliases=data.get('aliases',[])
            if not isinstance(aliases,list) or len(aliases)>30 or any(not isinstance(a,str) or not a.strip() or len(a)>80 for a in aliases):raise ValueError('资产别名格式无效')
            keys={name,*aliases}
            if keys&names[entry['type']]:raise Conflict('导入文件内存在重复名称或别名')
            names[entry['type']].update(keys)
            prepared.append((entry['type'],name,{**data,'name':name,'aliases':aliases}))
        created=skipped=updated=0
        with self.store.connection(immediate=True) as conn:
            if not conn.execute('SELECT 1 FROM projects WHERE id=?',(body.get('project_id'),)).fetchone():raise ValueError('项目不存在')
            existing=self.store.assets(body['project_id'],conn)
            for kind,name,data in prepared:
                matching=[a for a in existing if a['type']==kind and {name,*data['aliases']}&{a['name'],*a['data'].get('aliases',[])}]
                if len(matching)>1:raise Conflict('导入别名同时匹配多项资产，请先整理名称')
                if matching:
                    current=matching[0]
                    if body.get('strategy')!='merge' or current['locked']:skipped+=1;continue
                    revision=body.get('revisions',{}).get(current['id'])
                    if revision!=current['revision']:raise Conflict('合并目标已有新版本，请刷新')
                    self.save_asset(current['id'],{'revision':revision,'data':{**current['data'],**data}},conn);updated+=1
                else:
                    identifier=uid('as_');conn.execute('INSERT INTO assets VALUES(?,?,?,?,?,?,?)',(identifier,body['project_id'],kind,name,0,1,dumps(data)));created+=1
        return dict(created=created,updated=updated,skipped=skipped)

    def add_reference(self,identifier,body):
        raw,kind,suffix=decode_media(body.get('content'),body.get('name',''))
        view=body.get('view','reference')
        if view not in VIEWS:raise ValueError('素材视角无效')
        if kind!='image' and view in {'face','front','side','back','board'}:raise ValueError('该视角需要图片素材')
        filename=uid('reference_')+suffix;path=self.store.root/'media'/filename
        with self.store.connection(immediate=True) as conn:
            row=conn.execute('SELECT * FROM assets WHERE id=?',(identifier,)).fetchone()
            if not row:raise ValueError('资产不存在')
            if row['revision']!=body.get('revision'):raise Conflict('资产已有新版本，请刷新后上传')
            count=conn.execute('SELECT COUNT(*) FROM asset_media WHERE asset_id=?',(identifier,)).fetchone()[0]
            if count>=40:raise ValueError('每项资产最多保留 40 个素材版本')
            selected=kind=='image' and bool(body.get('make_primary',False))
            path.write_bytes(raw)
            if selected:conn.execute('UPDATE asset_media SET selected=0 WHERE asset_id=?',(identifier,))
            media_id=uid('am_')
            conn.execute('INSERT INTO asset_media VALUES(?,?,?,?,?,?,?,?,?)',(media_id,identifier,kind,'/media/'+filename,str(body.get('name','素材'))[:160],view,'imported',int(selected),time.time()))
            conn.execute('UPDATE assets SET revision=revision+1 WHERE id=?',(identifier,))
            if selected:self._invalidate(conn,row['project_id'],identifier)
        return {'id':media_id,'kind':kind,'url':'/media/'+filename}

    def select_reference(self,identifier,body):
        with self.store.connection(immediate=True) as conn:
            asset=conn.execute('SELECT * FROM assets WHERE id=?',(identifier,)).fetchone()
            if not asset or asset['revision']!=body.get('revision'):raise Conflict('资产已更新，请刷新')
            selected=conn.execute("SELECT * FROM asset_media WHERE id=? AND asset_id=? AND kind='image'",(body.get('media_id'),identifier)).fetchone()
            if not selected:raise ValueError('请选择此资产的图片版本')
            conn.execute('UPDATE asset_media SET selected=(id=?) WHERE asset_id=?',(selected['id'],identifier))
            conn.execute('UPDATE assets SET revision=revision+1 WHERE id=?',(identifier,));self._invalidate(conn,asset['project_id'],identifier)
        return {'ok':True}

    def shot_media(self,identifier,body):
        raw,kind,suffix=decode_media(body.get('content'),body.get('name',''))
        if kind not in {'video','image'}:raise ValueError('镜头素材仅支持图片或 MP4')
        filename=uid('shot_')+suffix;path=self.store.root/'media'/filename
        with self.store.connection(immediate=True) as conn:
            row=conn.execute('SELECT data FROM shots WHERE id=?',(identifier,)).fetchone()
            if not row:raise ValueError('镜头不存在')
            shot=json.loads(row[0])
            if shot.get('revision',1)!=body.get('revision'):raise Conflict('镜头已更新，请刷新后上传')
            field='video' if kind=='video' else 'image';versions=shot.setdefault(field+'_versions',[])
            if len(versions)>=40:raise ValueError('每镜最多 40 个素材版本')
            path.write_bytes(raw);url='/media/'+filename
            versions.append({'url':url,'mode':'imported','created':time.time(),'name':str(body.get('name','镜头素材'))[:160]})
            shot[field]=url;shot['revision']=shot.get('revision',1)+1;shot['status']='待审'
            shot['asset_changed']=False;shot['mode']='imported'
            if kind=='image':shot['video']=None
            conn.execute('UPDATE shots SET data=? WHERE id=?',(dumps(shot),identifier))
        return {'url':url,'kind':kind}

    def shot_assets(self,identifier,body):
        with self.store.connection(immediate=True) as conn:
            row=conn.execute('SELECT project_id,data FROM shots WHERE id=?',(identifier,)).fetchone()
            if not row:raise ValueError('镜头不存在')
            shot=json.loads(row['data'])
            if shot.get('revision',1)!=body.get('revision'):raise Conflict('镜头已更新，请刷新')
            ids=body.get('asset_ids',[])
            if not isinstance(ids,list) or len(ids)>40 or len(set(ids))!=len(ids) or not set(ids)<={a['id'] for a in self.store.assets(row['project_id'],conn)}:raise ValueError('仅可关联本项目中的最多 40 项资产')
            if ids==shot.get('asset_ids',[]):return {'ok':True,'changed':False}
            shot.update(asset_ids=ids,asset_changed=True,revision=shot.get('revision',1)+1)
            conn.execute('UPDATE shots SET data=? WHERE id=?',(dumps(shot),identifier))
        return {'ok':True}

    def select_video(self,identifier,body):
        with self.store.connection(immediate=True) as conn:
            row=conn.execute('SELECT data FROM shots WHERE id=?',(identifier,)).fetchone()
            if not row:raise ValueError('镜头不存在')
            shot=json.loads(row[0])
            if shot.get('revision',1)!=body.get('revision'):raise Conflict('镜头已更新，请刷新')
            url=body.get('video')
            if url is not None and url not in {v['url'] for v in shot.get('video_versions',[])}:raise ValueError('只能选择本镜头已有的视频版本')
            if url is None and not shot.get('image'):raise ValueError('此镜头尚无静帧画面')
            shot.update(video=url,revision=shot.get('revision',1)+1)
            conn.execute('UPDATE shots SET data=? WHERE id=?',(dumps(shot),identifier))
        return {'ok':True}

    def control(self,identifier,action):
        if action not in {'pause','resume'}:raise ValueError('未知任务控制动作')
        with self.store.connection(immediate=True) as conn:
            job=conn.execute('SELECT * FROM jobs WHERE id=?',(identifier,)).fetchone()
            if not job:raise ValueError('任务不存在')
            if job['state'] not in {'PENDING','RUNNING','PAUSED'}:raise Conflict('仅能控制排队、运行或暂停的任务')
            parent=json.loads(job['payload']).get('parent_job_id')
            if parent:identifier=parent;job=conn.execute('SELECT * FROM jobs WHERE id=?',(parent,)).fetchone()
            rows=conn.execute("SELECT * FROM jobs WHERE id=? OR json_extract(payload,'$.parent_job_id')=?",(identifier,identifier)).fetchall()
            for row in rows:
                if row['state'] not in {'PENDING','RUNNING','PAUSED'}:continue
                if action=='resume' and json.loads(row['result']).get('inflight') and row['state']!='RUNNING':raise Conflict('外部请求结果未确认，不能自动恢复')
                conn.execute('INSERT INTO job_controls VALUES(?,?) ON CONFLICT(job_id) DO UPDATE SET paused=excluded.paused',(row['id'],int(action=='pause')))
                if action=='pause' and row['state']=='PENDING':conn.execute("UPDATE jobs SET state='PAUSED',updated=? WHERE id=?",(time.time(),row['id']))
                if action=='resume' and row['state']=='PAUSED':conn.execute("UPDATE jobs SET state='PENDING',token=NULL,lease_until=0,updated=? WHERE id=?",(time.time(),row['id']))
                self.store.event(conn,row['id'],'已请求暂停，将在当前产物保存后停止派发' if action=='pause' else '已恢复，将跳过已完成产物')
        return {'id':identifier,'action':action}

    def generate_assets(self,engine,job):
        from artwork import artwork
        config=job['payload']['_config'];targets=job['payload']['target_ids']
        for target in targets:
            if target in job['checkpoint']:continue
            with self.store.connection(immediate=True) as conn:
                if not engine.active(conn,job) or pause_boundary(self.store,conn,job):return
                asset=next((a for a in self.store.assets(job['project_id'],conn) if a['id']==target),None)
                if not asset or asset['revision']!=job['payload']['asset_revisions'][target]:raise Conflict('资产设定已变更，请重新确认生成任务')
                project=json.loads(conn.execute('SELECT data FROM projects WHERE id=?',(job['project_id'],)).fetchone()[0])
                references=[dict(r) for r in conn.execute("SELECT * FROM asset_media WHERE asset_id=? AND kind='image' AND mode<>'local' ORDER BY selected DESC,created DESC LIMIT 4",(target,))]
            from creative import visual_style
            prompt=asset_prompt(asset,visual_style(project));charge=None
            if config['remote_enabled']:
                files=[]
                if references:
                    if config.get('image_reference_mode') not in {'openai_edits','ark_images'} and config.get('image_protocol')!='ark_images':raise ValueError('该资产已有参考图，请在模型中心选择火山参考图或兼容 images/edits 的参考图通道。')
                    for reference in references:
                        path=self.store.root/'media'/Path(reference['url']).name
                        if not path.is_file() or path.is_symlink() or path.stat().st_size>24*1024*1024:raise ValueError('参考图片不可用')
                        files.append(('image[]',path.name,path.read_bytes()))
                from model_workflow import image_request
                endpoint,body,uploads=image_request(config,prompt,files)
                response=engine.remote(job,endpoint,body,**({'files':uploads} if uploads else {}))
                result=response['data'][0]
                if result.get('b64_json'):raw=base64.b64decode(result['b64_json'],validate=True)
                else:
                    import urllib.request
                    url=result.get('url','')
                    if not url.startswith('https://'):raise ValueError('供应商未返回有效 HTTPS 图片地址')
                    with urllib.request.urlopen(url,timeout=60) as response:raw=response.read(24*1024*1024+1)
                checked,kind,suffix=decode_media(base64.b64encode(raw).decode(),'generated')
                if kind!='image':raise ValueError('供应商没有返回图片')
                mode='provider_reference' if files else 'provider';filename=uid('asset_')+suffix
                (self.store.root/'media'/filename).write_bytes(checked)
                charge=config['image_price']
            else:
                mode='local';filename=uid('asset_concept_')+'.svg'
                (self.store.root/'media'/filename).write_text(artwork(sum(map(ord,target))%6),encoding='utf-8')
            output={'asset_id':target,'image':'/media/'+filename,'mode':mode}
            with self.store.connection(immediate=True) as conn:
                if charge is not None:
                    conn.execute('INSERT OR IGNORE INTO ledger VALUES(?,?,?,?,?,?,?)',(job['id']+':'+target,job['id'],config['provider_url'],config['image_model'],charge,time.time(),dumps({'units':1,'unit':'asset_sheet'})))
                    conn.execute("UPDATE jobs SET result='{}' WHERE id=? AND token=?",(job['id'],job['token']))
                if not engine.active(conn,job):return
                current=conn.execute('SELECT revision FROM assets WHERE id=?',(target,)).fetchone()
                if not current or current[0]!=job['payload']['asset_revisions'][target]:raise Conflict('生成期间资产已修改，未替换当前参考素材；已发生费用单独记录')
                primary=not conn.execute("SELECT 1 FROM asset_media WHERE asset_id=? AND selected=1",(target,)).fetchone()
                conn.execute('INSERT INTO asset_media VALUES(?,?,?,?,?,?,?,?,?)',(uid('am_'),target,'image',output['image'],'本地概念占位（非定妆图）' if mode=='local' else 'AI 多视图设定（待核验）','board',mode,int(primary),time.time()))
                if primary:self._invalidate(conn,job['project_id'],target)
                job['checkpoint'].append(target)
                progress=round(len(job['checkpoint'])/len(targets)*100)
                conn.execute('UPDATE jobs SET checkpoint=?,progress=?,result=?,updated=? WHERE id=?',(dumps(job['checkpoint']),progress,dumps(output),time.time(),job['id']))
                self.store.event(conn,job['id'],f'已保存资产设定图 {len(job["checkpoint"])}/{len(targets)}')
        with self.store.connection(immediate=True) as conn:
            if engine.active(conn,job):conn.execute("UPDATE jobs SET state='SUCCEEDED',progress=100,lease_until=0,updated=? WHERE id=?",(time.time(),job['id']));self.store.event(conn,job['id'],'资产画面任务完成，原版本已保留')

def encode_multipart(fields,files):
    boundary=uid('heli_');parts=[]
    for key,value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    for field,name,raw in files:
        if field!='image[]' or not re.fullmatch(r'[a-zA-Z0-9_.-]+',name):raise ValueError('参考图片参数无效')
        mime='image/png' if name.endswith('.png') else 'image/jpeg' if name.endswith('.jpg') else 'image/webp'
        parts.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{name}"\r\nContent-Type: {mime}\r\n\r\n'.encode(),raw,b'\r\n'])
    parts.append(f'--{boundary}--\r\n'.encode())
    return b''.join(parts),'multipart/form-data; boundary='+boundary

def motion_segments(engine,shots,media,frames,stem,width,height):
    """Normalize each clip to one frame clock; original audio never silently replaces dialogue."""
    from engine import ffmpeg_path,run_process
    segments=[];cursor=0
    try:
        for index,shot in enumerate(shots):
            start=round(cursor*24);cursor+=shot['duration'];count=max(1,round(cursor*24)-start)
            target=media/(stem+'_'+str(index)+'.mp4');segments.append(target)
            frame=media/frames[shot['id']]
            args=[ffmpeg_path(),'-hide_banner','-loglevel','error','-y']
            if shot.get('video'):
                if not re.fullmatch(r'/media/[a-zA-Z0-9_.-]+\.mp4',shot['video']):raise ValueError('镜头视频路径无效')
                video=media/Path(shot['video']).name
                if not video.is_file() or video.is_symlink():raise ValueError('镜头视频不存在')
                args+=['-stream_loop','-1','-i',str(video),'-loop','1','-i',str(frame),'-filter_complex',f'[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps=24[base];[base][1:v]overlay=0:0:shortest=1,format=yuv420p[v]','-map','[v]']
            else:args+=['-loop','1','-i',str(frame),'-vf','fps=24,format=yuv420p']
            args+=['-an','-frames:v',str(count),'-c:v','libx264','-preset','veryfast','-crf','22','-video_track_timescale','24000',str(target)]
            run_process(args,timeout=180)
        return segments
    except Exception:
        for path in segments:path.unlink(missing_ok=True)
        raise
