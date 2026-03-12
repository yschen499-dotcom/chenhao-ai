# test_dingding

Simple DingTalk Stream bot that:

- replies `pong` when a message contains `ping`
- runs a shell command when a message contains `run: ...`
- validates DingTalk credentials before connecting
- automatically reconnects if the stream connection drops

## Files

- `dingtalk_agent.py`: main bot entrypoint
- `requirements.txt`: Python dependencies
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
# AGENT_MAX_REPLY_CHARS=3000
# AGENT_ALLOWED_CMD_PREFIXES=python,python3,pytest,dir,echo
```

You can also use `DINGTALK_APP_KEY` and `DINGTALK_APP_SECRET` instead of the
stream-specific variable names.

## Run

```bash
python3 dingtalk_agent.py
```

## Supported message patterns

- `ping` -> `pong`
- `run: echo hello`
- `run: python3 --version`

Only commands whose first token matches an allowed prefix are executed.