"""Local durable checkpoints. Each process uses its own SQLite database."""
import sqlite3
import json
import config as c
class State:
    def __init__(self, name):
        c.STATE.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(c.STATE / (name+'.sqlite3'))
        self.db.execute('CREATE TABLE IF NOT EXISTS done (key TEXT PRIMARY KEY)')
        self.db.execute('CREATE TABLE IF NOT EXISTS pending (key TEXT PRIMARY KEY, payload TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS cursor (key TEXT PRIMARY KEY, value INTEGER)')
    def has(self, key):
        return self.db.execute('SELECT 1 FROM done WHERE key=?', (key,)).fetchone() is not None
    def mark(self, key):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO done VALUES (?)', (key,))
    def position(self, key):
        row = self.db.execute('SELECT value FROM cursor WHERE key=?', (key,)).fetchone()
        return row[0] if row else 0
    def advance(self, key, value):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO cursor VALUES (?,?)', (key, value))
    def pending_sample(self, key):
        row = self.db.execute('SELECT payload FROM pending WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else None
    def save_pending(self, key, sample):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO pending VALUES (?,?)', (key, json.dumps(sample)))
    def complete(self, key, next_index):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO cursor VALUES (?,?)', (key, next_index))
            self.db.execute('DELETE FROM pending WHERE key=?', (key,))
