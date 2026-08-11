"""持久化记忆存储（SQLite）。

设计要点（用户要求）：
- 对话历史分两层：
  * history      —— 全量存档，永不被物理删除，供维护查阅。
  * history_active —— 活跃窗口，只保留最近 N 轮用于生成上下文；
                     超出的从 active 移出（仍在 history 全量里）。
- /forget 只清 history_active（前端"看不见、像忘了"），history 全量保留。
- 教导/反馈：写入 teachings 表，每次生成时注入 user_prompt（不污染 persona 文件）。

库位置：<BASE>/data/memory.db
"""
import sqlite3
import time
from pathlib import Path

import config as C

DB_PATH = C.DATA_DIR / "memory.db"
_ACTIVE_TURNS = 24  # 活跃窗口轮数（1轮=user+assistant），仅用于生成上下文

_schema = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_chat ON history(chat_id, id);
CREATE TABLE IF NOT EXISTS history_active (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_active_chat ON history_active(chat_id, id);
CREATE TABLE IF NOT EXISTS teachings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    ts REAL NOT NULL
);
"""


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_schema)
    return conn


def append_turn(chat_id: str, role: str, content: str):
    """追加一条对话：同时写入全量 history 与活跃 history_active。
    活跃表超出窗口的旧记录被移出（物理删除 active 行，但全量仍留 history）。"""
    chat_id = str(chat_id)
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO history(chat_id, role, content, ts) VALUES (?,?,?,?)",
            (chat_id, role, content, time.time()),
        )
        conn.execute(
            "INSERT INTO history_active(chat_id, role, content, ts) VALUES (?,?,?,?)",
            (chat_id, role, content, time.time()),
        )
        conn.commit()
    finally:
        conn.close()
    _trim_active(chat_id)


def _trim_active(chat_id: str):
    """活跃表只留最近 _ACTIVE_TURNS*2 条；多出的删除（全量 history 不受影响）。"""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT id FROM history_active WHERE chat_id=? ORDER BY id DESC LIMIT -1 OFFSET ?",
            (chat_id, _ACTIVE_TURNS * 2),
        ).fetchall()
        if rows:
            ids = [r[0] for r in rows]
            conn.execute(
                "DELETE FROM history_active WHERE id IN (%s)" % ",".join("?" * len(ids)),
                ids,
            )
            conn.commit()
    finally:
        conn.close()


def load_history(chat_id: str, limit: int = _ACTIVE_TURNS) -> list:
    """返回最近 limit 轮的活跃历史 [{'role':..,'content':..}]（正序）。"""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT role, content FROM history_active WHERE chat_id=? ORDER BY id DESC LIMIT ?",
            (str(chat_id), limit * 2),
        ).fetchall()
    finally:
        conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


def count_history(chat_id: str) -> int:
    """全量存档条数（维护查阅用）。"""
    conn = _conn()
    try:
        n = conn.execute("SELECT COUNT(*) FROM history WHERE chat_id=?", (str(chat_id),)).fetchone()[0]
    finally:
        conn.close()
    return n


def add_teaching(text: str) -> int:
    """添加一条教导/反馈，返回其 id。"""
    conn = _conn()
    try:
        cur = conn.execute("INSERT INTO teachings(text, ts) VALUES (?,?)", (text, time.time()))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def load_teachings() -> str:
    """返回所有教导文本，按条目拼接（供注入生成）。空则返回空串。"""
    conn = _conn()
    try:
        rows = conn.execute("SELECT text FROM teachings ORDER BY id").fetchall()
    finally:
        conn.close()
    if not rows:
        return ""
    return "\n".join(f"- {r[0]}" for r in rows)


def forget_active(chat_id: str):
    """只清活跃窗口（前端"像忘了"），全量 history 保留供维护查阅。"""
    conn = _conn()
    try:
        conn.execute("DELETE FROM history_active WHERE chat_id=?", (str(chat_id),))
        conn.commit()
    finally:
        conn.close()


def clear_all(chat_id: str):
    """彻底删除该聊天的全量历史 + 活跃历史（慎用，仅维护命令调用）。"""
    conn = _conn()
    try:
        conn.execute("DELETE FROM history WHERE chat_id=?", (str(chat_id),))
        conn.execute("DELETE FROM history_active WHERE chat_id=?", (str(chat_id),))
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    cid = "unittest"
    forget_active(cid)  # 先清 active 保证干净
    append_turn(cid, "user", "第一条")
    append_turn(cid, "assistant", "你好")
    print("active:", load_history(cid))
    print("full count:", count_history(cid))
    forget_active(cid)
    print("after /forget active:", load_history(cid), "| full count still:", count_history(cid))
