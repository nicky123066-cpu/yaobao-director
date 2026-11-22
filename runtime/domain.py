"""Lossless script syntax, rule extraction and storyboard compilation. No I/O."""
import difflib
import hashlib
import json
import re
import uuid


def uid(prefix=""):
    return prefix + uuid.uuid4().hex[:16]


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def parse_script(text, previous=None):
    nodes = []
    offset = 0
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip("\r\n").lstrip("\ufeff")
        node = {"id": uid("ln_"), "type": "unknown", "raw": raw, "start": offset, "end": offset + len(raw)}
        clean = line.strip()
        if not clean:
            node["type"] = "blank"
        elif match := re.match(r"^第\s*(\d+)\s*集(.*)$", clean):
            node.update(type="episode", number=int(match[1]), title=match[2].strip())
        elif match := re.match(r"^(\d+)-(\d+)\s+(日|夜|黄昏|清晨|傍晚|黎明)\s+(内|外)\s+(.+)$", clean):
            node.update(type="scene", number=match[1] + "-" + match[2], time=match[3], inout=match[4], location=match[5])
        elif match := re.match(r"^【场\s*(\d+)\s+(.+)】$", clean):
            node.update(type="scene", number=match[1], time="未标注", inout="未标注", location=match[2])
        elif match := re.match(r"^人物\s*[:：]\s*(.+)$", clean):
            node.update(type="characters", characters=[x.strip() for x in re.split(r"[、,，;；]", match[1]) if x.strip()])
        elif clean.startswith("△"):
            node.update(type="action", text=clean[1:].strip())
        elif match := re.match(r"^(?:\[(\d{1,3}):(\d{2})\]\s*)?([^:：\[\]（）()]+?)(?:[（(]([^）)]+)[）)])?\s*[:：]\s*(.+)$", clean):
            seconds = int(match[1]) * 60 + int(match[2]) if match[1] is not None else None
            if match[1] is None and match[4] is None:
                pass  # An arbitrary heading such as “备注：...” is not a spoken line.
            elif match[2] is not None and int(match[2]) >= 60:
                node.update(type="invalid", issue="时间码的秒必须在 00–59 之间")
            else:
                speaker=match[3].strip()
                if speaker.casefold() in {"旁白","解说","narrator"}:
                    speaker="旁白"
                node.update(type="dialogue", seconds=seconds, speaker=speaker, emotion=match[4] or "", text=match[5])
        nodes.append(node)
        offset += len(raw)
    if previous:
        matcher = difflib.SequenceMatcher(a=[n["raw"] for n in previous], b=[n["raw"] for n in nodes], autojunk=False)
        for op, a0, a1, b0, b1 in matcher.get_opcodes():
            if op == "equal":
                for a, b in zip(previous[a0:a1], nodes[b0:b1]):
                    b["id"] = a["id"]
            elif op == "replace" and a1 - a0 == b1 - b0:
                for a, b in zip(previous[a0:a1], nodes[b0:b1]):
                    if a["type"] == b["type"]:
                        b["id"] = a["id"]
    return {"nodes": nodes, "raw": text, "stats": script_stats(nodes, text)}


def serialize_script(ast):
    return "".join(n["raw"] for n in ast["nodes"])


def script_stats(nodes, text=""):
    speakers = list(dict.fromkeys(n["speaker"] for n in nodes if n["type"] == "dialogue"))
    dialogues = [n for n in nodes if n["type"] == "dialogue"]
    timed = [n for n in dialogues if n["seconds"] is not None]
    issues = []
    seen = set()
    last_time = -1
    for i, n in enumerate(nodes):
        if n["type"] == "scene":
            if n["number"] in seen:
                issues.append({"line": i + 1, "message": "场次编号重复：" + n["number"]})
            seen.add(n["number"])
        if n["type"] == "invalid":
            issues.append({"line": i + 1, "message": n["issue"]})
        if n["type"] == "dialogue" and n["seconds"] is not None:
            if n["seconds"] < last_time:
                issues.append({"line": i + 1, "message": "时间码早于上一句台词"})
            last_time = n["seconds"]
    if dialogues and len(timed) < len(dialogues):
        issues.append({"line": 0, "message": f"{len(dialogues)-len(timed)} 句台词缺少时间码"})
    if text.strip() and not any(n["type"] == "scene" for n in nodes):
        issues.append({"line": 0, "message": "未识别到场次，请使用“1-1 日 外 地点”格式"})
    return {"characters": len(re.sub(r"\s", "", text)), "scenes": sum(n["type"] == "scene" for n in nodes),
            "dialogues": len(dialogues), "timed": len(timed), "speakers": speakers, "issues": issues}


CHARACTER_FIELDS = ["name", "gender", "age", "identity", "appearance", "hairStyle", "hairColor",
                    "eyeColor", "skinTone", "bodyType", "accessories", "performanceAnchors"]


def extract_assets(ast):
    names = list(ast["stats"]["speakers"])
    for node in ast["nodes"]:
        if node["type"] == "characters":
            for name in node["characters"]:
                if name not in names:
                    names.append(name)
    assets = []
    for name in names:
        data = {k: "" for k in CHARACTER_FIELDS}
        data.update(name=name, identity="旁白 / 画外音" if name in ("旁白", "解说", "narrator") else "待补充",
                    aliases=[], costumes=[{"state": "默认", "desc": "待补充"}])
        assets.append({"type": "characters", "name": name, "data": data})
    for location in dict.fromkeys(n["location"] for n in ast["nodes"] if n["type"] == "scene"):
        assets.append({"type": "scenes", "name": location, "data": {"name": location, "description": "来自剧本场次，待补充美术设定"}})
    return assets


def compile_shots(ast, chapter_id, revision, assets, style):
    result, scene, scene_id, location, people = [], "1-1", None, "未标注", []
    for node in ast["nodes"]:
        if node["type"] == "scene":
            scene, scene_id, location = node["number"], node["id"], node["location"]
        elif node["type"] == "characters":
            people = node["characters"]
        elif node["type"] in ("dialogue", "action"):
            index = len(result) + 1
            spoken = node["text"] if node["type"] == "dialogue" else ""
            characters = [node["speaker"]] if spoken else list(people)
            refs = [a["id"] for a in assets if a["name"] in characters or a["name"] == location]
            result.append({"id": uid("sh_"), "chapter_id": chapter_id, "source_revision": revision,
                "number": f"{scene}-{index:02d}", "source_line_ids": [x for x in (scene_id, node["id"]) if x],
                "location": location, "characters": characters, "asset_ids": refs,
                "action": node["text"], "dialogue": spoken, "speaker": node.get("speaker", "旁白"),
                "emotion": node.get("emotion", ""), "duration": min(8, max(3, round(len(spoken) / 3.8 + 1, 1))) if spoken else 4,
                "size": "近景" if spoken else "全景", "camera": "固定" if spoken else "缓慢推进",
                "style": style, "image": None, "image_versions": [], "audio": None,
                "audio_duration": 0, "voice": "Microsoft Huihui Desktop", "voice_rate": 0, "stale": False,
                "status": "待生成", "mode": "local", "revision": 1})
    return result


def prompt_for(shot, assets):
    descriptions = []
    for asset in assets:
        if asset["id"] not in shot.get("asset_ids", []):
            continue
        data = asset["data"]
        desc = "；".join(str(data[k]) for k in ("identity", "appearance", "hairStyle", "hairColor", "description") if data.get(k) and data[k] != "待补充")
        costumes = data.get("costumes", [])
        desc += "；" + "；".join(c.get("desc", "") for c in costumes if c.get("state") == "默认")
        descriptions.append(asset["name"] + "：" + desc.strip("；"))
    extra=shot.get('prompt_override','').strip()
    return f"风格：{shot.get('style', '电影感国漫')}\n资产：{' / '.join(descriptions) or shot.get('location', '')}\n画面：{shot.get('action', '')}；{shot.get('emotion', '')}\n镜头：{shot.get('size', '中景')}，{shot.get('camera', '固定')}\n负向：低清晰度、文字水印、畸形肢体"+(f'\n导演补充：{extra}' if extra else '')


def utf16_index(text, offset):
    if not isinstance(offset, int) or offset < 0:
        raise ValueError("选区坐标无效")
    raw = text.encode("utf-16-le")
    if offset * 2 > len(raw):
        raise ValueError("选区超出正文")
    try:
        return len(raw[:offset * 2].decode("utf-16-le"))
    except UnicodeDecodeError as exc:
        raise ValueError("选区不能切开一个 Unicode 字符") from exc


def natural_key(filename):
    match = re.search(r"第\s*(\d+)\s*[集章]|(?:ep|episode|e)[\s._-]*(\d+)", filename, re.I)
    if match:
        return int(match[1] or match[2]), filename.casefold()
    numbers = re.findall(r"\d+", filename)
    return (int(numbers[-1]) if numbers else 10**9), filename.casefold()


def srt_for(shots):
    def stamp(seconds):
        ms = round(seconds * 1000)
        return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"
    entries, cursor = [], 0.0
    for shot in shots:
        if shot.get("dialogue"):
            entries.append(f"{len(entries)+1}\n{stamp(cursor)} --> {stamp(cursor + shot['duration'])}\n{shot['speaker']}：{shot['dialogue']}\n")
        cursor += shot["duration"]
    return "\n".join(entries)


SEED_SCRIPT = """第1集 雨夜来客

1-1 夜 外 长安城·朱雀街
人物：沈知夏、陆沉
△ 暴雨将至，朱雀街的灯笼在风中摇曳。沈知夏撑着一柄旧伞，停在封闭的书铺门前。
[00:04] 沈知夏（迟疑）：这封信，真的是你写的？
[00:09] 陆沉（低声）：你终于来了。我等了你整整三年。

1-2 夜 内 听雨书铺
人物：沈知夏、陆沉
△ 门轴轻响。陆沉点亮桌上的孤灯，一枚裂成两半的玉佩映出微光。
[00:18] 沈知夏（震惊）：这枚玉佩……怎么会在你手里？
[00:24] 陆沉（克制）：有些真相，你的父亲没有告诉你。

1-3 夜 外 书铺后巷
人物：沈知夏、陆沉、黑衣人
△ 窗外掠过一道黑影，灯火骤然熄灭。
[00:32] 黑衣人（冷峻）：交出玉佩，我可以让她离开。
[00:37] 沈知夏（坚定）：我的命，由我自己决定。
"""
