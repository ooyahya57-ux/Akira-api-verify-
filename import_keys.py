import os, sqlite3
from pathlib import Path
base = Path(__file__).resolve().parent
db = os.getenv("DB_PATH", str(base / "database.db"))
keyfile = base / "keys.txt"
never_expires = "9999-12-31T23:59:59+00:00"
keys = [s.strip() for s in keyfile.read_text(encoding="utf-8").splitlines()
        if s.strip() and not s.lstrip().startswith("#")]
c = sqlite3.connect(db)
try:
    c.execute("""CREATE TABLE IF NOT EXISTS keys (
      key TEXT PRIMARY KEY, max_devices INTEGER NOT NULL, expires_at TEXT NOT NULL,
      active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS devices (
      key TEXT NOT NULL, device TEXT NOT NULL, first_seen TEXT NOT NULL,
      PRIMARY KEY(key,device), FOREIGN KEY(key) REFERENCES keys(key) ON DELETE CASCADE)""")
    c.executemany("""INSERT OR IGNORE INTO keys
      (key,max_devices,expires_at,active,created_at)
      VALUES (?,1,?,1,datetime('now'))""", [(k, never_expires) for k in keys])
    c.commit()
    print(f"Imported/checked {len(keys)} keys. Existing entries unchanged.")
finally:
    c.close()
