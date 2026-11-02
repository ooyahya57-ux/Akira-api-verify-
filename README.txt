CTX Madara API + Telegram Bot

Files:
- main.py: API + Telegram bot in one persistent Python process.
- requirements.txt: required Python packages.
- .env.example: environment-variable template.
- keys.txt: 100 generated keys.
- import_keys.py: adds those keys to database.db.
- Procfile: worker start command for supported hosts.

SECURITY:
A bot token was exposed in an earlier message. Revoke it with @BotFather and create a NEW token.
Set BOT_TOKEN and ADMIN_ID in the hosting Environment Variables. Never upload .env or database.db
to GitHub. Do not paste the new token into chats.

LOCAL RUN:
1) pip install -r requirements.txt
2) Copy .env.example to .env and put your new BOT_TOKEN there.
3) python import_keys.py
4) python main.py
API: http://127.0.0.1:5000/api/verify

HOSTING:
Choose a host that supports a persistent Python worker/background process and durable disk.
Start command: python main.py
Set BOT_TOKEN and ADMIN_ID=8404634986 in Environment Variables.
Do not run this polling bot as a Vercel serverless function. SQLite requires a single persistent
instance and durable disk. For multiple instances/serverless, use a shared managed database.

API request:
POST /api/verify
JSON: {"key":"KEY_HERE","device":"ANDROID_ID"}
Success: {"ok":true,"msg":"Key verified successfully"}

Telegram admin commands:
/start
/Key KEY_NAME MAX_DEVICES DAYS
/DelKey KEY_NAME
/Keys
/Check KEY_NAME
/Disable KEY_NAME
/Enable KEY_NAME

The 100 supplied keys are configured for one device each and a far-future expiry.
Deleting a key line from keys.txt does not revoke it after import; use /DelKey KEY.
