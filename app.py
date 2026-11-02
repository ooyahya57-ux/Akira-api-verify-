import os, re, sqlite3, threading
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

load_dotenv()
BASE = Path(__file__).resolve().parent
DB_PATH = os.getenv("DB_PATH", str(BASE / "database.db"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "8404634986"))
BOT_TOKEN = os.getenv("BOT_TOKEN", "9092862857:AAF1bFjXdAx1_Dvw43YePSIdx3A_NWC_yBg").strip()
PORT = int(os.getenv("PORT", "5000"))
app = Flask(__name__)
db_lock = threading.RLock()

def now():
    return datetime.now(timezone.utc)

def connect():
    c = sqlite3.connect(DB_PATH, timeout=20)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    with db_lock, connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS keys (
            key TEXT PRIMARY KEY, max_devices INTEGER NOT NULL,
            expires_at TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS devices (
            key TEXT NOT NULL, device TEXT NOT NULL, first_seen TEXT NOT NULL,
            PRIMARY KEY(key, device),
            FOREIGN KEY(key) REFERENCES keys(key) ON DELETE CASCADE)""")

def status(row):
    if not row["active"]: return "موقوف"
    if datetime.fromisoformat(row["expires_at"]) <= now(): return "منتهي"
    return "فعال"

async def telegram_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m, u = update.effective_message, update.effective_user
    if not m or not u or not (m.text or "").startswith("/"): return
    parts = m.text.strip().split()
    cmd, args = parts[0].split("@", 1)[0].lower(), parts[1:]
    if u.id != ADMIN_ID:
        await m.reply_text("⛔ ما عندكش صلاحية الأدمن.")
        return

    if cmd == "/start":
        await m.reply_text("مرحبا بالأدمن.\n/Key KEY MAX_DEVICES DAYS\n/DelKey KEY\n/Keys\n/Check KEY\n/Disable KEY\n/Enable KEY")

    elif cmd == "/key":
        if len(args) != 3:
            await m.reply_text("الاستعمال: /Key KEY_NAME MAX_DEVICES DAYS"); return
        key = args[0].strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{4,80}", key):
            await m.reply_text("❌ صيغة KEY غير صالحة."); return
        try:
            devices, days = int(args[1]), int(args[2])
            if not (1 <= devices <= 10000 and 1 <= days <= 3650): raise ValueError
        except ValueError:
            await m.reply_text("❌ الأجهزة: 1-10000، الأيام: 1-3650."); return
        t = now()
        with db_lock, connect() as c:
            try:
                c.execute("INSERT INTO keys VALUES(?,?,?,?,?)",
                          (key, devices, (t+timedelta(days=days)).isoformat(), 1, t.isoformat()))
            except sqlite3.IntegrityError:
                await m.reply_text("⚠️ هاد KEY موجود من قبل."); return
        await m.reply_text(f"✅ تم إنشاء KEY\n🔑 {key}\n👥 الأجهزة: {devices}\n📅 الصلاحية: {days} يوم")

    elif cmd == "/delkey":
        if len(args) != 1:
            await m.reply_text("الاستعمال: /DelKey KEY"); return
        with db_lock, connect() as c:
            cur = c.execute("DELETE FROM keys WHERE key=?", (args[0],))
            c.execute("DELETE FROM devices WHERE key=?", (args[0],))
        await m.reply_text("🗑️ تم حذف KEY." if cur.rowcount else "❌ KEY ما لقيتوش.")

    elif cmd == "/keys":
        with db_lock, connect() as c:
            rows = c.execute("SELECT * FROM keys ORDER BY created_at DESC LIMIT 50").fetchall()
            counts = {r["key"]: c.execute("SELECT COUNT(*) FROM devices WHERE key=?", (r["key"],)).fetchone()[0] for r in rows}
        if not rows:
            await m.reply_text("ما كاين حتى KEY مسجل."); return
        lines = ["📋 آخر 50 KEY:"]
        for r in rows:
            lines.append(f"\n🔑 {r['key']}\nالحالة: {status(r)} | الأجهزة: {counts[r['key']]}/{r['max_devices']}\nينتهي: {r['expires_at'][:10]}")
        await m.reply_text("\n".join(lines))

    elif cmd in ("/disable", "/enable"):
        if len(args) != 1:
            await m.reply_text("الاستعمال: /Disable KEY أو /Enable KEY"); return
        active = 0 if cmd == "/disable" else 1
        with db_lock, connect() as c:
            cur = c.execute("UPDATE keys SET active=? WHERE key=?", (active, args[0]))
        if cur.rowcount: await m.reply_text("⏸️ تم توقيف KEY." if not active else "▶️ تم تفعيل KEY.")
        else: await m.reply_text("❌ KEY ما لقيتوش.")

    elif cmd == "/check":
        if len(args) != 1:
            await m.reply_text("الاستعمال: /Check KEY"); return
        with db_lock, connect() as c:
            r = c.execute("SELECT * FROM keys WHERE key=?", (args[0],)).fetchone()
            count = c.execute("SELECT COUNT(*) FROM devices WHERE key=?", (args[0],)).fetchone()[0]
        if not r: await m.reply_text("❌ KEY غير موجود.")
        else: await m.reply_text(f"🔑 {r['key']}\nالحالة: {status(r)}\nالأجهزة: {count}/{r['max_devices']}\nينتهي: {r['expires_at']}")

@app.post("/api/verify")
def verify_key():
    data = request.get_json(silent=True) or {}
    key, device = data.get("key"), data.get("device")
    if not isinstance(key, str) or not isinstance(device, str):
        return jsonify(ok=False, msg="Missing key or device"), 400
    key, device = key.strip(), device.strip()
    if not key or not device or len(key)>80 or len(device)>256:
        return jsonify(ok=False, msg="Invalid key or device"), 400
    with db_lock:
        c = connect()
        try:
            c.execute("BEGIN IMMEDIATE")
            r = c.execute("SELECT * FROM keys WHERE key=?", (key,)).fetchone()
            if not r: c.rollback(); return jsonify(ok=False, msg="Invalid key"), 401
            if not r["active"]: c.rollback(); return jsonify(ok=False, msg="Key disabled"), 403
            if datetime.fromisoformat(r["expires_at"]) <= now():
                c.rollback(); return jsonify(ok=False, msg="Key expired"), 403
            exists = c.execute("SELECT 1 FROM devices WHERE key=? AND device=?", (key, device)).fetchone()
            if not exists:
                count = c.execute("SELECT COUNT(*) FROM devices WHERE key=?", (key,)).fetchone()[0]
                if count >= r["max_devices"]:
                    c.rollback(); return jsonify(ok=False, msg="Device limit reached"), 403
                c.execute("INSERT INTO devices VALUES(?,?,?)", (key, device, now().isoformat()))
            c.commit()
            return jsonify(ok=True, msg="Key verified successfully"), 200
        except Exception:
            c.rollback()
            app.logger.exception("Verification error")
            return jsonify(ok=False, msg="Server error"), 500
        finally: c.close()

@app.get("/")
def health():
    return jsonify(status="online", service="Madara Key Verification API")

def run_api():
    app.run(host="0.0.0.0", port=PORT, threaded=True, use_reloader=False)

def run_bot():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN missing: set it in hosting Environment Variables.")
    bot = Application.builder().token(BOT_TOKEN).build()
    bot.add_handler(MessageHandler(filters.COMMAND, telegram_command))
    bot.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_api, daemon=True).start()
    run_bot()
