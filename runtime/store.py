"""SQLite persistence. Each operation uses its own connection and explicit transactions."""
import contextlib
import json
import sqlite3
import time
from pathlib import Path

from domain import SEED_SCRIPT, compile_shots, extract_assets, parse_script, uid
from model_workflow import DEFAULTS as MODEL_DEFAULTS


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


DEFAULT_SETTINGS = {"provider_url": "https://api.openai.com/v1", "text_model": "gpt-4.1-mini",
    "image_model": "gpt-image-2.5-sunburst", "image_price": 0.15, "budget": 100.0, "remote_enabled": False,
    "voice": "Microsoft Huihui Desktop", "voice_rate": 0, **MODEL_DEFAULTS}


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, root, seed=True):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "media").mkdir(exist_ok=True)
        self.path = self.root / "workbench.sqlite3"
        with self.connection() as conn:
            conn.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,data TEXT NOT NULL,updated REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS chapters(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,body TEXT NOT NULL,revision INTEGER NOT NULL,position INTEGER NOT NULL,ast TEXT NOT NULL,source_key TEXT);
                CREATE UNIQUE INDEX IF NOT EXISTS chapter_source ON chapters(project_id,source_key) WHERE source_key IS NOT NULL;
                CREATE TABLE IF NOT EXISTS versions(id TEXT PRIMARY KEY,chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
                    body TEXT NOT NULL,revision INTEGER NOT NULL,created REAL NOT NULL,label TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    type TEXT NOT NULL,name TEXT NOT NULL,locked INTEGER NOT NULL DEFAULT 0,revision INTEGER NOT NULL DEFAULT 1,data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS shots(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,position INTEGER NOT NULL,data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,state TEXT NOT NULL,payload TEXT NOT NULL,idem TEXT UNIQUE NOT NULL,digest TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,checkpoint TEXT NOT NULL DEFAULT '[]',attempts INTEGER NOT NULL DEFAULT 0,
                    lease_until REAL NOT NULL DEFAULT 0,token TEXT,estimate REAL NOT NULL DEFAULT 0,error TEXT,
                    created REAL NOT NULL,updated REAL NOT NULL,result TEXT NOT NULL DEFAULT '{}');
                CREATE TABLE IF NOT EXISTS job_events(id INTEGER PRIMARY KEY AUTOINCREMENT,job_id TEXT NOT NULL REFERENCES jobs(id),
                    created REAL NOT NULL,message TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS ledger(call_id TEXT PRIMARY KEY,job_id TEXT NOT NULL REFERENCES jobs(id),
                    provider TEXT NOT NULL,model TEXT NOT NULL,amount REAL NOT NULL,created REAL NOT NULL,details TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1),data TEXT NOT NULL);
            """)
            conn.execute("INSERT OR IGNORE INTO settings VALUES(1,?)", (dumps(DEFAULT_SETTINGS),))
        from production import Production
        with self.connection() as conn:Production.schema(conn)
        if seed:
            self.seed()

    @contextlib.contextmanager
    def connection(self, immediate=False):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=15000")
        try:
            if immediate:
                conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def settings(self):
        with self.connection() as conn:
            return json.loads(conn.execute("SELECT data FROM settings WHERE id=1").fetchone()[0])

    def assets(self, project_id, conn=None):
        if conn is None:
            with self.connection() as connection:
                return self.assets(project_id, connection)
        return [{**dict(row), "data": json.loads(row["data"]), "locked": bool(row["locked"])}
                for row in conn.execute("SELECT * FROM assets WHERE project_id=? ORDER BY rowid", (project_id,))]

    def shots(self, project_id, conn=None):
        if conn is None:
            with self.connection() as connection:
                return self.shots(project_id, connection)
        return [json.loads(row["data"]) for row in conn.execute("SELECT data FROM shots WHERE project_id=? ORDER BY chapter_id,position", (project_id,))]

    def chapter(self, chapter_id, conn=None):
        if conn is None:
            with self.connection() as connection:
                return self.chapter(chapter_id, connection)
        row = conn.execute("SELECT * FROM chapters WHERE id=?", (chapter_id,)).fetchone()
        if row is None:
            raise ValueError("章节不存在")
        return {**dict(row), "ast": json.loads(row["ast"])}

    def update_chapter(self, chapter_id, body, revision, title=None, label="手动保存"):
        if not isinstance(body, str) or len(body) > 500000:
            raise ValueError("剧本长度需在 50 万字以内")
        with self.connection(immediate=True) as conn:
            chapter = self.chapter(chapter_id, conn)
            if chapter["revision"] != revision:
                raise Conflict("该章节已有新版本，请刷新后合并你的修改")
            if body != chapter["body"]:
                ast = parse_script(body, chapter["ast"]["nodes"])
                new_revision = revision + 1
                conn.execute("INSERT INTO versions VALUES(?,?,?,?,?,?)", (uid("ver_"), chapter_id, body, new_revision, time.time(), label))
                conn.execute("UPDATE chapters SET body=?,revision=?,ast=? WHERE id=?", (body, new_revision, dumps(ast), chapter_id))
                for row in conn.execute("SELECT id,data FROM shots WHERE chapter_id=?", (chapter_id,)).fetchall():
                    shot = json.loads(row["data"])
                    shot["stale"] = True
                    conn.execute("UPDATE shots SET data=? WHERE id=?", (dumps(shot), row["id"]))
            if title is not None:
                conn.execute("UPDATE chapters SET title=? WHERE id=?", (str(title).strip()[:100] or "未命名章节", chapter_id))
            conn.execute("UPDATE projects SET updated=? WHERE id=?", (time.time(), chapter["project_id"]))
        return self.chapter(chapter_id)

    def add_chapter(self, project_id, title="新章节", body="", source_key=None, conn=None):
        if conn is None:
            with self.connection(immediate=True) as connection:
                return self.add_chapter(project_id, title, body, source_key, connection)
        if not conn.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone():
            raise ValueError("项目不存在")
        chapter_id = uid("ch_")
        position = conn.execute("SELECT COALESCE(MAX(position),-1)+1 FROM chapters WHERE project_id=?", (project_id,)).fetchone()[0]
        ast = parse_script(body)
        conn.execute("INSERT INTO chapters VALUES(?,?,?,?,?,?,?,?)", (chapter_id, project_id, title, body, 1, position, dumps(ast), source_key))
        conn.execute("INSERT INTO versions VALUES(?,?,?,?,?,?)", (uid("ver_"), chapter_id, body, 1, time.time(), "初始版本"))
        conn.execute("UPDATE projects SET updated=? WHERE id=?", (time.time(), project_id))
        return chapter_id

    def new_project(self, name, ratio="9:16", style="东方悬疑 · 电影国漫", premise="", episodes=12, style_id="", style_notes=""):
        project_id = uid("pr_")
        data = {"name": name.strip()[:80] or "未命名漫剧", "ratio": ratio, "style": style, "premise": premise[:2000],
                "episodes": episodes, "cover": int(time.time()) % 6, "created": time.time()}
        from creative import normalize
        data.update(**normalize(ratio,style,style_id,style_notes),visual_revision=1)
        with self.connection(immediate=True) as conn:
            conn.execute("INSERT INTO projects VALUES(?,?,?)", (project_id, dumps(data), time.time()))
            self.add_chapter(project_id, "第 1 集 · 故事的开始", f"第1集\n\n1-1 日 外 待定场景\n人物：\n△ {premise or '在这里写下故事的第一个画面。'}\n", conn=conn)
        return project_id

    def seed(self):
        with self.connection() as conn:
            if conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]:
                return
        first = self.new_project("长安夜未央", style="东方悬疑 · 电影国漫", premise="一封来自三年前的信，将她带回那场未曾结束的长安旧梦。", episodes=12)
        ch = None
        with self.connection(immediate=True) as conn:
            ch = self.chapter(conn.execute("SELECT id FROM chapters WHERE project_id=?", (first,)).fetchone()[0], conn)
            ast = parse_script(SEED_SCRIPT, ch["ast"]["nodes"])
            conn.execute("UPDATE chapters SET title=?,body=?,ast=? WHERE id=?", ("第 1 集 · 雨夜来客", SEED_SCRIPT, dumps(ast), ch["id"]))
            conn.execute("UPDATE versions SET body=? WHERE chapter_id=?", (SEED_SCRIPT, ch["id"]))
            data = json.loads(conn.execute("SELECT data FROM projects WHERE id=?", (first,)).fetchone()[0])
            data["cover"] = 0
            conn.execute("UPDATE projects SET data=? WHERE id=?", (dumps(data), first))
            for item in extract_assets(ast):
                if item["name"] == "沈知夏":
                    item["data"].update(gender="女", age="22", identity="没落书香世家的独女", appearance="清冷眉眼，左眼角一颗小痣",
                        hairStyle="长发半束，发尾微卷", hairColor="墨黑", eyeColor="深棕", skinTone="冷白", bodyType="纤细挺拔",
                        accessories="银色素簪", performanceAnchors="说话时微微抬头，紧张时收紧指尖", costumes=[{"state":"默认","desc":"青灰色交领长裙，暗纹云肩"}])
                elif item["name"] == "陆沉":
                    item["data"].update(gender="男", age="27", identity="听雨书铺掌柜", appearance="眉骨分明，神情沉静",
                        hairStyle="高束长发", hairColor="墨黑", eyeColor="黑棕", skinTone="冷白", bodyType="高挑修长",
                        accessories="青玉束冠", performanceAnchors="垂眸后再开口，语气平缓", costumes=[{"state":"默认","desc":"玄色窄袖长袍"}])
                conn.execute("INSERT INTO assets VALUES(?,?,?,?,?,?,?)", (uid("as_"), first, item["type"], item["name"], int(item["name"] == "沈知夏"), 1, dumps(item["data"])))
            shots = compile_shots(ast, ch["id"], 1, self.assets(first, conn), data["style"])
            for i, shot in enumerate(shots):
                if i < 4:
                    shot.update(image=f"/api/art/{i}.svg", image_versions=[{"url":f"/api/art/{i}.svg","mode":"local","created":time.time()}], status="待审")
                conn.execute("INSERT INTO shots VALUES(?,?,?,?,?)", (shot["id"], first, ch["id"], i, dumps(shot)))
            self.add_chapter(first, "第 2 集 · 旧梦回声", "第2集 旧梦回声\n\n2-1 清晨 内 听雨书铺\n人物：沈知夏、陆沉\n△ 晨光穿过窗棂，落在摊开的旧信上。\n[00:03] 沈知夏（平静）：从头告诉我吧。\n", conn=conn)
            self.add_chapter(first, "第 3 集 · 朱雀疑云", "第3集 朱雀疑云\n\n3-1 黄昏 外 朱雀城门\n人物：沈知夏\n△ 城门缓缓关闭，一场更大的风暴即将来临。\n", conn=conn)
        second = self.new_project("末日便利店", style="赛博都市 · 日系动画", premise="世界末日后，这间便利店依旧二十四小时营业。", episodes=24)
        third = self.new_project("风起青云", style="水墨仙侠 · 东方幻想", premise="少年拾得一把断剑，从此踏上重返青云的旅程。", episodes=16)
        with self.connection() as conn:
            for pid, cover, delay in [(first, 0, 0), (second, 1, 3600), (third, 2, 7200)]:
                row = conn.execute("SELECT data FROM projects WHERE id=?", (pid,)).fetchone()
                data = json.loads(row[0]); data["cover"] = cover
                conn.execute("UPDATE projects SET data=?,updated=? WHERE id=?", (dumps(data), time.time() - delay, pid))

    def snapshot(self):
        with self.connection() as conn:
            projects = []
            for row in conn.execute("SELECT * FROM projects ORDER BY updated DESC"):
                project = {"id": row["id"], **json.loads(row["data"]), "updated": row["updated"]}
                project["chapters"] = [{**dict(ch), "ast": json.loads(ch["ast"])} for ch in conn.execute("SELECT * FROM chapters WHERE project_id=? ORDER BY position", (row["id"],))]
                project["assets"] = self.assets(row["id"], conn)
                project["shots"] = self.shots(row["id"], conn)
                projects.append(project)
            jobs = [{**dict(row), "payload": json.loads(row["payload"]), "checkpoint": json.loads(row["checkpoint"]), "result": json.loads(row["result"])}
                    for row in conn.execute("SELECT * FROM jobs ORDER BY created DESC LIMIT 100")]
            ledger = [dict(row) for row in conn.execute("SELECT * FROM ledger ORDER BY created DESC LIMIT 200")]
            spent = conn.execute("SELECT COALESCE(SUM(amount),0) FROM ledger").fetchone()[0]
            reserved = conn.execute("SELECT COALESCE(SUM(MAX(0,estimate-(SELECT COALESCE(SUM(amount),0) FROM ledger WHERE ledger.job_id=jobs.id))),0) FROM jobs WHERE (state IN ('PENDING','RUNNING','PAUSED') OR (state IN ('FAILED','CANCELED') AND json_extract(result,'$.inflight') IS NOT NULL))").fetchone()[0]
        return {"projects": projects, "jobs": jobs, "ledger": ledger, "spent": round(spent, 4), "reserved": round(reserved, 4), "settings": self.settings()}

    @staticmethod
    def event(conn, job_id, message):
        conn.execute("INSERT INTO job_events(job_id,created,message) VALUES(?,?,?)", (job_id, time.time(), message))
