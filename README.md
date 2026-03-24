# test_dingding

Internal-test DingTalk Stream bot for building a CS2 monitoring assistant.

This repository currently focuses on the first-stage internal test architecture:

- keep DingTalk as the management and testing entrypoint
- use SQLite for local internal state
- support admin/test commands through chat
- prepare the project structure for collector, strategy, monitor, and alert modules

## Files

- `dingtalk_agent.py`: DingTalk Stream entrypoint
- `app/`: internal test business modules
- `scripts/init_db.py`: initialize the SQLite database
- `CS2_MVP_Checklist.md`: product MVP planning doc
- `Internal_Test_Architecture.md`: internal architecture draft
- `.env.dingtalk_agent`: local credentials/config file (not committed)

## Setup

1. Create and activate a Python environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create `.env.dingtalk_agent` in the project root:

```env
DINGTALK_STREAM_CLIENT_ID=your_app_key
DINGTALK_STREAM_CLIENT_SECRET=your_app_secret

# Optional
# DINGTALK_AGENT_LOG_LEVEL=DEBUG
# AGENT_DB_PATH=data/app.db
# AGENT_SCAN_INTERVAL_SECONDS=60
# AGENT_MAX_REPLY_CHARS=3000
```

You can also use `DINGTALK_APP_KEY` and `DINGTALK_APP_SECRET` instead of the
stream-specific variable names.

## Initialize local storage

```bash
python3 scripts/init_db.py
```

## Run

```bash
python3 dingtalk_agent.py
```

## Internal test commands

- `ping`
- `help`
- `status`
- `watchlist`
- `add 名称`
- `remove 名称`
- `scan`
- `test alert`

## Notes

- The current version is an internal testing skeleton.
- Real CS2 market collection and strategy logic have not been connected yet.
- `scan` currently validates the command, state, and storage flow only.