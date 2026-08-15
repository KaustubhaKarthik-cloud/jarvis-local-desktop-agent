import sqlite3
import datetime
import os

from config import MEMORY_DB_PATH, DATA_DIR


class Memory:
    """SQLite-backed facts and bounded conversation history."""

    def __init__(self, db_path=MEMORY_DB_PATH):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.conn = sqlite3.connect(db_path, timeout=5)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._init_tables()

    def _init_tables(self):
        cur = self.conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS facts (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, value TEXT, created_at TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, created_at TEXT)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(key)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_history_id ON history(id)")
        self.conn.commit()

    @staticmethod
    def _clean(value):
        return " ".join(str(value).strip().lower().split())

    def remember_fact(self, key: str, value: str):
        key = self._clean(key)
        value = str(value).strip()
        if not key or not value:
            return
        now = datetime.datetime.now().isoformat(timespec="seconds")
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM facts WHERE key = ? ORDER BY id DESC LIMIT 1", (key,))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE facts SET value = ?, created_at = ? WHERE id = ?", (value, now, row[0]))
        else:
            cur.execute("INSERT INTO facts (key, value, created_at) VALUES (?, ?, ?)", (key, value, now))
        self.conn.commit()

    def recall_fact(self, key: str):
        key = self._clean(key)
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM facts WHERE key = ? ORDER BY id DESC LIMIT 1", (key,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute("SELECT value FROM facts WHERE key LIKE ? ORDER BY id DESC LIMIT 1", (f"%{key}%",))
        row = cur.fetchone()
        return row[0] if row else None

    def all_facts(self):
        cur = self.conn.cursor()
        cur.execute("SELECT key, value FROM facts ORDER BY id DESC")
        return cur.fetchall()

    def add_turn(self, role: str, content: str):
        self.conn.execute("INSERT INTO history (role, content, created_at) VALUES (?, ?, ?)", (role, str(content), datetime.datetime.now().isoformat(timespec="seconds")))
        self.conn.commit()

    def recent_history(self, limit=6):
        limit = max(1, min(int(limit), 12))
        cur = self.conn.cursor()
        cur.execute("SELECT role, content FROM history ORDER BY id DESC LIMIT ?", (limit,))
        return list(reversed(cur.fetchall()))

    def close(self):
        self.conn.close()
