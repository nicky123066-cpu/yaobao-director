"""Shared creative presets, render sizes and revision-safe project direction."""
import json,time
from store import Conflict,dumps

RATIOS=[
 dict(id='9:16',name='竖屏短剧',width=720,height=1280,use='手机全屏短剧、竖屏信息流'),
 dict(id='16:9',name='横屏叙事',width=1280,height=720,use='横屏短剧、访谈、长视频'),
 dict(id='1:1',name='方形画面',width=960,height=960,use='方形展示、通用内容素材'),
 dict(id='4:5',name='信息流竖版',width=768,height=960,use='人物与商品展示、图文信息流'),
 dict(id='3:4',name='图文竖版',width=720,height=960,use='竖版封面、人物设定与图文'),
 dict(id='4:3',name='经典横版',width=960,height=720,use='复古影像、传统动画叙事'),
 dict(id='2:3',name='海报竖版',width=720,height=1080,use='海报式故事、竖版插画'),
 dict(id='3:2',name='摄影横版',width=1080,height=720,use='摄影质感与风景叙事'),
 dict(id='21:9',name='电影宽银幕',width=1680,height=720,use='电影感场景、横向空间与群像'),
]
STYLES=[dict(id=i,name=n,use=u,direction=d) for i,n,u,d in [
 ('cinema','电影写实','都市、情感、现实题材','自然皮肤与材质，可信空间光线，电影分镜构图，克制调色'),
 ('cn3d','国漫 3D','仙侠、玄幻、古装','统一三维角色比例与服装材质，精细毛发，电影级光影，连贯空间'),
 ('anime2d','清新二维动画','青春、校园、轻喜剧','清晰线稿，平涂与柔和阴影，统一角色比例，明快自然配色'),
 ('ink','水墨国风','武侠、仙侠、寓言','水墨层次与留白，东方山水构图，人物轮廓清晰，克制色彩'),
 ('gongbi','古风工笔','古装、历史、东方幻想','工笔线描，细致纹样，雅致矿物色，统一服饰朝代与结构'),
 ('noir','都市悬疑','推理、悬疑、夜景','冷暖光对比，电影黑色质感，清晰人物剪影，保留暗部细节'),
 ('cyber','赛博霓虹','科幻、都市幻想','霓虹反射与电子城市，统一科技设计语言，主体清晰，避免画面信息过载'),
 ('wasteland','末世废土','末世、生存、冒险','磨损材质与荒废空间，低饱和土色，可信环境尺度和装备连续性'),
 ('fairytale','治愈童话','亲子、治愈、轻奇幻','温暖柔光，圆润造型，舒适色彩，温和表情与自然空间层次'),
 ('retro','复古港风','都市、年代、悬疑','复古胶片配色，城市生活细节，柔和高光，统一年代服饰与道具'),
 ('stopmotion','定格手作','童话、创意、产品故事','手工材质与微缩布景，柔和棚拍光，稳定角色轮廓与手作纹理'),
 ('comic','黑白漫画','悬疑、动作、剧情预演','黑白墨线与网点，清晰轮廓和明暗分组，强叙事构图，无文字气泡'),
]]

def catalog():return {'ratios':RATIOS,'styles':STYLES}
def dimensions(ratio):
    row=next((r for r in RATIOS if r['id']==ratio),None)
    if not row:raise ValueError('请选择支持的画面比例')
    return row['width'],row['height']
def image_size(ratio):
    width,height=dimensions(ratio)
    return '1024x1024' if width==height else '1536x1024' if width>height else '1024x1536'
def normalize(ratio,style,style_id='',style_notes=''):
    dimensions(ratio)
    if not isinstance(style,str) or not 1<=len(style.strip())<=160:raise ValueError('视觉风格名称需为 1–160 字')
    if not isinstance(style_notes,str) or len(style_notes)>1200:raise ValueError('风格补充需在 1200 字以内')
    preset=next((s for s in STYLES if s['id']==style_id),None)
    if style_id and style_id!='custom' and not preset:raise ValueError('视觉风格预设不存在')
    return dict(ratio=ratio,style=preset['name'] if preset else style.strip(),style_id=preset['id'] if preset else 'custom',style_notes=style_notes.strip())
def visual_style(project):
    preset=next((s for s in STYLES if s['id']==project.get('style_id')),None)
    return '；'.join(v for v in [project['style'],preset['direction'] if preset else '',project.get('style_notes','')] if v)
def save_visual(store,identifier,body):
    with store.connection(immediate=True) as conn:
        row=conn.execute('SELECT data FROM projects WHERE id=?',(identifier,)).fetchone()
        if not row:raise ValueError('项目不存在')
        project=json.loads(row[0]);revision=project.get('visual_revision',1)
        if body.get('revision')!=revision:raise Conflict('画幅与风格已更新，请刷新后重试')
        values=normalize(body.get('ratio',project['ratio']),body.get('style',project['style']),body.get('style_id',project.get('style_id','custom')),body.get('style_notes',project.get('style_notes','')))
        if all(project.get(k,'custom' if k=='style_id' else '')==v for k,v in values.items()):return {'changed':False}
        if conn.execute("SELECT 1 FROM jobs WHERE project_id=? AND (state IN ('PENDING','RUNNING','PAUSED') OR json_extract(result,'$.inflight') IS NOT NULL)",(identifier,)).fetchone():raise Conflict('请先完成或处理本项目任务，再修改画幅与风格')
        style_changed=any(project.get(k,'custom' if k=='style_id' else '')!=values[k] for k in ('style','style_id','style_notes'))
        project.update(**values,visual_revision=revision+1,visual_updated=time.time())
        conn.execute('UPDATE projects SET data=?,updated=? WHERE id=?',(dumps(project),time.time(),identifier))
        if style_changed:
            for shot in store.shots(identifier,conn):
                shot.update(style=visual_style(project),asset_changed=True,revision=shot.get('revision',1)+1)
                conn.execute('UPDATE shots SET data=? WHERE id=?',(dumps(shot),shot['id']))
    return {'changed':True,'style_changed':style_changed,'revision':revision+1}
