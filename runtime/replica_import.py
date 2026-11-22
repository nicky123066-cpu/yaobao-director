"""Atomic, repeatable import of Yabo's independently edited storyboard package."""
import hashlib
import json
import math
import time

from domain import parse_script
from store import dumps


def import_replica(store, body):
    source = body.get('source_id')
    revision = body.get('source_revision')
    if not isinstance(source, str) or not source or len(source) > 100 or type(revision) is not int or revision < 1:
        raise ValueError('缺少有效来源版本。')
    pack = body.get('pack')
    if not isinstance(pack, dict) or not isinstance(pack.get('script'), str) or not 1 <= len(pack['script']) <= 30000:
        raise ValueError('缺少新剧本。')
    shots = pack.get('shots')
    if not isinstance(shots, list) or not 1 <= len(shots) <= 40:
        raise ValueError('需要1–40个分镜。')
    if body.get('ratio') not in {'9:16', '16:9', '1:1'}:
        raise ValueError('画幅无效。')
    ast = parse_script(pack['script'])
    if not ast['stats']['scenes']:
        raise ValueError('新剧本需要可识别的场次，例如：1-1 夜 外 车站。')
    identity = hashlib.sha256((source+':'+str(revision)).encode()).hexdigest()[:24]
    project_id, chapter_id = 'rep_'+identity, 'rch_'+identity
    fingerprint = hashlib.sha256(dumps(body).encode()).hexdigest()
    shot_ids = ['rsh_'+identity+'_'+str(i) for i in range(len(shots))]
    with store.connection(immediate=True) as conn:
        existing = conn.execute('SELECT data FROM projects WHERE id=?', (project_id,)).fetchone()
        if existing:
            if json.loads(existing[0]).get('replica_fingerprint') != fingerprint:
                raise ValueError('同一来源版本的内容不一致，请保存新版本后再送入。')
            return dict(id=project_id, shot_ids=shot_ids, reused=True)
        asset_rows, asset_ids = [], {}
        for kind in ('characters', 'scenes'):
            values = pack.get(kind)
            if not isinstance(values, list) or not 1 <= len(values) <= 30:
                raise ValueError('角色/场景列表无效。')
            for i, item in enumerate(values):
                name, desc = item.get('name'), item.get('description')
                if not isinstance(name, str) or not 1 <= len(name) <= 80 or not isinstance(desc, str) or len(desc) > 2000:
                    raise ValueError('角色/场景设定无效。')
                key = (kind, name)
                if key in asset_ids:
                    raise ValueError('角色或场景名称重复。')
                identifier = 'ras_'+identity+'_'+kind+'_'+str(i)
                asset_ids[key] = identifier
                asset_rows.append((identifier, project_id, kind, name, 0, 1, dumps(dict(name=name, description=desc, aliases=[]))))
        shot_rows = []
        for i, shot in enumerate(shots):
            d = shot.get('duration')
            if type(d) not in (int,float) or not math.isfinite(d) or not 2 <= d <= 15:
                raise ValueError('镜长应为2–15秒。')
            scene, people = shot.get('scene'), shot.get('characters')
            if not isinstance(people, list) or ('scenes', scene) not in asset_ids or any(('characters', p) not in asset_ids for p in people):
                raise ValueError('分镜引用了不存在的角色/场景。')
            for key in ('action', 'camera', 'image_prompt', 'video_prompt', 'dialogue'):
                if not isinstance(shot.get(key), str) or len(shot[key]) > 6000:
                    raise ValueError('分镜文字格式无效。')
            row = dict(id=shot_ids[i], chapter_id=chapter_id, source_revision=1, number='1-'+str(i+1).zfill(2),
                       source_line_ids=[], location=scene, characters=people, asset_ids=[asset_ids[('scenes',scene)]]+[asset_ids[('characters',p)] for p in people],
                       action=shot['action'], dialogue=shot['dialogue'], speaker=people[0] if people else '旁白', emotion='',
                       duration=d, size='中景', camera=shot['camera'][:80], style=body.get('style', '国风漫剧'),
                       prompt_override=shot['image_prompt'], video_prompt=shot['video_prompt'], image=None, image_versions=[],
                       video=None, video_versions=[], audio=None, audio_duration=0, voice='Microsoft Huihui Desktop', voice_rate=0,
                       stale=False, status='待生成', mode='local', revision=1)
            shot_rows.append((row['id'], project_id, chapter_id, i, dumps(row)))
        project = dict(name=str(body.get('name', '漫剧参考制作'))[:80], ratio=body['ratio'], style=str(body.get('style', '国风漫剧'))[:200],
                       premise=str(body.get('premise', ''))[:4000], episodes=1, cover=0, replica_fingerprint=fingerprint)
        conn.execute('INSERT INTO projects VALUES(?,?,?)', (project_id,dumps(project),time.time()))
        conn.execute('INSERT INTO chapters VALUES(?,?,?,?,?,?,?,?)', (chapter_id,project_id,'第1集',pack['script'],1,0,dumps(ast),source))
        conn.executemany('INSERT INTO assets VALUES(?,?,?,?,?,?,?)',asset_rows)
        conn.executemany('INSERT INTO shots VALUES(?,?,?,?,?)',shot_rows)
    return dict(id=project_id, shot_ids=shot_ids, reused=False)
