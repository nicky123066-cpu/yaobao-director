"""Capability-specific model routing; no credentials are returned in this catalog."""
import base64
import copy
import math
from urllib.parse import urlsplit

ARK_BASE='https://ark.cn-beijing.volces.com/api/v3'
IMAGE_MODEL='doubao-seedream-5-0-flash-260915'
VIDEO_MODEL='doubao-seedance-2-5-260628'
ROLE_FIELDS=('image_provider','image_provider_url','image_key_env','image_protocol','image_size',
             'video_provider','video_provider_url','video_key_env','video_model','video_price','video_resolution',
             'video_poll_seconds','video_timeout','image_watermark','video_watermark','text_protocol')
DEFAULTS=dict(image_protocol='openai_images',image_size='2K',image_watermark=True,
    video_provider='ark',video_provider_url=ARK_BASE,video_key_env='ARK_API_KEY',video_model=VIDEO_MODEL,
    video_price=1.0,video_resolution='720p',video_poll_seconds=4,video_timeout=1200,video_watermark=True,
    text_protocol='chat_completions')

def role_config(config,role):
    result=copy.deepcopy(config)
    if role in {'image','video'}:
        independent=role=='video' or bool(config.get(role+'_provider_url'))
        if independent:
            for source,target in [('provider','provider'),('provider_url','provider_url'),('key_env','key_env')]:
                result[target]=config.get(role+'_'+source,DEFAULTS.get(role+'_'+source,''))
    return result

def validate(config):
    from gateway import KEY_NAMES
    for role in ['image','video']:
        base=config.get(role+'_provider_url','')
        if base:
            p=urlsplit(base)
            if not p.hostname or p.username or p.password or p.query or p.fragment or '\\' in base or p.scheme!='https' and not(p.scheme=='http' and p.hostname in {'127.0.0.1','localhost'}):raise ValueError('模型角色地址需为HTTPS或本机HTTP，不能含凭据或查询。')
        if config.get(role+'_key_env') and config[role+'_key_env'] not in KEY_NAMES:raise ValueError('模型角色密钥配置无效。')
    if config.get('image_protocol','openai_images') not in {'openai_images','ark_images'}:raise ValueError('生图协议无效。')
    if config.get('text_protocol','chat_completions') not in {'chat_completions','responses'}:raise ValueError('文本协议无效。')
    if config.get('video_resolution','720p') not in {'480p','720p','1080p','4k'}:raise ValueError('视频分辨率无效。')
    for key,low,high in [('video_price',0,1000),('video_poll_seconds',2,30),('video_timeout',30,3600)]:
        v=config.get(key,DEFAULTS[key])
        if type(v) not in (int,float) or not math.isfinite(v) or not low<=v<=high:raise ValueError('视频估价、轮询或超时参数无效。')
    for key in ['image_watermark','video_watermark']:
        if key in config and type(config[key]) is not bool:raise ValueError('模型水印开关无效。')
    return config

def require_capability(config,role):
    model=str(config.get('image_model' if role=='image' else 'video_model' if role=='video' else 'text_model','')).strip()
    lower=model.lower()
    if not model:raise ValueError('请先配置'+{'image':'生图','video':'动态视频','text':'文本'}[role]+'模型。')
    if role=='image' and lower in {'gpt-image-1','dall-e-2','dall-e-3'}:raise ValueError('该旧生图型号已停用或不再作为当前推荐，请从账户可用目录选择图片模型。')
    if role=='image' and any(s in lower for s in ['-vl','vision','deepseek','qwen-plus','qwen-max','qwen-turbo','seedance','wan2.','wan3.']):raise ValueError('这是看图理解、文本或视频模型，不能作为生图模型。请选择Seedream或实际开放的图片生成模型。')
    if role=='video':
        if config.get('provider')!='ark' or not ('seedance' in lower or lower.startswith('ep-')):raise ValueError('当前动态镜头通道支持火山Seedance，请配置对应模型与API地址。')
        if 'flash' in lower and config.get('video_resolution','720p') not in {'480p','720p'}:raise ValueError('Seedance Flash仅支持480p或720p，请降低分辨率。')
    if role=='image' and config.get('image_protocol')=='ark_images' and 'seedream' not in lower and not lower.startswith('ep-'):raise ValueError('火山生图通道请填写Seedream模型或对应生图接入点。')
    if role=='image' and any(v in lower for v in ['seedream-5-5','seedream-5-0-flash']) and config.get('image_size','2K')=='4K':raise ValueError('当前Seedream型号不支持4K，请使用1K、1.5K、2K或合规像素尺寸。')
    return model

def image_size(config):
    size=config.get('image_size','2K');ratio=config.get('_image_ratio')
    sizes={'1K':{'9:16':'768x1360','16:9':'1360x768','1:1':'1024x1024'},
           '1.5K':{'9:16':'1152x2048','16:9':'2048x1152','1:1':'1536x1536'},
           '2K':{'9:16':'1440x2560','16:9':'2560x1440','1:1':'2048x2048'}}
    return sizes.get(size,{}).get(ratio,size)

def image_request(config,prompt,references=None):
    model=require_capability(config,'image');references=references or []
    if config.get('image_protocol')=='ark_images' or 'seedream' in model.lower():
        body=dict(model=model,prompt=prompt,size=image_size(config),response_format='b64_json',stream=False,watermark=config.get('image_watermark',True))
        if references:
            if len(references)>8:raise ValueError('当前镜头参考图超过8张，请减少引用资产。')
            body['image']=[data_image(name,raw) for _,name,raw in references]
        return '/images/generations',body,None
    # GPT image models return base64 natively; response_format is deliberately omitted.
    body=dict(model=model,prompt=prompt,n=1,size={'16:9':'1536x1024','1:1':'1024x1024'}.get(config.get('_image_ratio'),'1024x1536'))
    return ('/images/edits' if references else '/images/generations'),body,references or None

def data_image(name,raw):
    if not raw or len(raw)>20*1024*1024:raise ValueError('参考图需为20MB以内的PNG、JPEG或WebP。')
    mime='image/png' if raw.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if raw.startswith(b'\xff\xd8\xff') else 'image/webp' if raw[:4]==b'RIFF' and raw[8:12]==b'WEBP' else ''
    if not mime:raise ValueError('动态镜头首帧必须使用真实PNG、JPEG或WebP，不能使用本地SVG示意图。')
    return 'data:'+mime+';base64,'+base64.b64encode(raw).decode()

def catalog(config=None,root=None):
    from gateway import api_key
    c={**DEFAULTS,**(config or {})}
    roles={r:dict(model=role_config(c,r).get('text_model' if r=='text' else r+'_model',''),key_ready=bool(api_key(role_config(c,r),root))) for r in ['text','image','video']}
    return dict(checked_at='2026-11-22',remote_enabled=bool(c.get('remote_enabled')),roles=roles,
        recommendations=[
            dict(role='text',name='DeepSeek Flash',model='deepseek-flash',provider='deepseek',base_url='https://api.deepseek.com',description='日常接待、剧本改写与分镜文字；沿用现有DeepSeek连接。',source='https://api-docs.deepseek.com/'),
            dict(role='vision',name='千问视觉理解',model='qwen3-vl-plus',provider='dashscope',description='用于看图、读字与聊天截图理解，不用于生成画面。',source='https://help.aliyun.com/zh/model-studio/vision'),
            dict(role='image',name='Seedream 5.0 Flash',model=IMAGE_MODEL,provider='ark',base_url=ARK_BASE,description='角色定妆、场景和分镜画面；支持参考图。需账号实际开放模型权限。',source='https://docs.volcengine.com/docs/zh/ark/image-generation-api.md'),
            dict(role='image',name='Seedream 5.5',model='doubao-seedream-5-5-261028',provider='ark',base_url=ARK_BASE,description='精修画面备选；按实际输入图片与输出像素计费。',source='https://docs.volcengine.com/docs/zh/ark/model-list.md'),
            dict(role='video',name='即梦 Seedance 2.5（默认）',model=VIDEO_MODEL,provider='ark',base_url=ARK_BASE,description='默认动态镜头接口：火山方舟Seedance 2.5标准版，首帧生成，手动点击后提交任务。',source='https://docs.volcengine.com/docs/zh/ark/create-video-generation-task-api.md'),
            dict(role='video',name='Seedance 2.5 Flash（可选）',model='doubao-seedance-2-5-flash-261115',provider='ark',base_url=ARK_BASE,description='可选Flash版本，支持480p/720p；需账号实际开放权限。',source='https://docs.volcengine.com/docs/zh/ark/model-list.md')],
        workflows=[dict(id='local_preview',name='本地预演',paid=False),dict(id='ai_images',name='AI画面＋本地配音样片',paid=True),dict(id='ai_video',name='AI画面＋动态镜头＋配音成片',paid=True)],
        notice='推荐不等于已开通或效果保证。先保存各用途连接与密钥，再手动启用真实生成；保存和目录检测不生成付费内容。')

def preflight(store,project_id,chapter_id):
    from gateway import api_key
    from domain import compile_shots,extract_assets
    from engine import ffmpeg_path
    import os
    config={**DEFAULTS,**store.settings()};chapter=store.chapter(chapter_id)
    if chapter['project_id']!=project_id:raise ValueError('章节与项目不一致。')
    with store.connection() as conn:
        row=conn.execute('SELECT data FROM projects WHERE id=?',(project_id,)).fetchone()
        if not row:raise ValueError('项目不存在。')
        project=__import__('json').loads(row[0])
    shots=compile_shots(chapter['ast'],chapter_id,chapter['revision'],store.assets(project_id),project['style'])
    assets=[a for a in extract_assets(chapter['ast']) if a['type'] in {'characters','scenes','props'}]
    common=[]
    if not shots or len(shots)>60:common.append('一集需包含1–60个动作或台词镜头')
    if not ffmpeg_path():common.append('FFmpeg尚未就绪')
    if os.name!='nt':common.append('当前中文配音流程需要Windows语音引擎')
    modes=[]
    for mode in ['local_preview','ai_images','ai_video']:
        reasons=list(common);cost=0
        if mode!='local_preview':
            if not config.get('remote_enabled'):reasons.append('请先手动启用真实模型生成')
            for role in (['image','video'] if mode=='ai_video' else ['image']):
                effective=role_config(config,role)
                try:require_capability(effective,role)
                except ValueError as exc:reasons.append(str(exc))
                if not api_key(effective,store.root):reasons.append(role+'用途供应商密钥未保存')
            cost=(len(shots)+len(assets))*float(config.get('image_price',.15))
            if mode=='ai_video':cost+=sum(max(4,math.ceil(s['duration']))*float(config.get('video_price',1)) for s in shots)
        modes.append(dict(id=mode,ready=not reasons,blockers=reasons,estimated_cost=round(cost,2)))
    return dict(chapter_revision=chapter['revision'],shot_count=len(shots),asset_estimate=len(assets),modes=modes,budget=config.get('budget',0),
        note='费用为本地参考估算，可能包含角色定妆；已有参考图会复用。供应商账单、角色一致性和实际成片效果需另行核验。')
