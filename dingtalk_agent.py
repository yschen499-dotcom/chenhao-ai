import asyncio
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import dingtalk_stream
import requests
from dingtalk_stream import AckMessage


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = os.getenv("DINGTALK_AGENT_ENV_FILE", ".env.dingtalk_agent")
ENV_PATH = BASE_DIR / ENV_FILE
MAX_REPLY_CHARS = int(os.getenv("AGENT_MAX_REPLY_CHARS", "3000"))
ALLOWED_PREFIXES = tuple(
    p.strip()
    for p in os.getenv("AGENT_ALLOWED_CMD_PREFIXES", "python,python3,pytest,dir,echo").split(",")
    if p.strip()
)


def _load_env():
    """
    Minimal .env loader:
    - supports KEY=VALUE lines
    - ignores comments and blank lines
    - does not override process environment variables
    """
    try:
        if not ENV_PATH.exists():
            return
        with ENV_PATH.open("r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


def _truncate(s: str) -> str:
    if len(s) <= MAX_REPLY_CHARS:
        return s
    return s[: MAX_REPLY_CHARS - 20] + "\n...(truncated)..."


def _run_command(cmd: str) -> str:
    cmd = cmd.strip()
    if not cmd:
        return "Empty command."

    first = cmd.split()[0].lower()
    if first not in {p.lower() for p in ALLOWED_PREFIXES}:
        return f"Blocked. Allowed command prefixes: {', '.join(ALLOWED_PREFIXES)}"

    try:
        cp = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        out = (cp.stdout or "") + (("\n" + cp.stderr) if cp.stderr else "")
        out = out.strip() or "(no output)"
        return f"exit_code={cp.returncode}\n{out}"
    except subprocess.TimeoutExpired:
        return "Command timed out (120s)."
    except Exception as e:
        return f"Command failed: {e!r}"


def _parse_instruction(text: str) -> Optional[str]:
    t = (text or "").strip()
    if not t:
        return None

    lower = t.lower()
    if "ping" in lower:
        return "pong"
    if "run:" in lower:
        idx = lower.index("run:")
        cmd = t[idx + 4 :].strip()
        return _run_command(cmd)
    return None


class LocalCommandBotHandler(dingtalk_stream.ChatbotHandler):
    async def process(self, callback: dingtalk_stream.CallbackMessage):
        try:
            incoming = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
            text = ""
            if getattr(incoming, "text", None) and getattr(incoming.text, "content", None):
                text = incoming.text.content

            logging.info("Incoming chatbot text: %r", text)

            reply = _parse_instruction(text)
            if reply is not None:
                self.reply_text(_truncate(reply), incoming)
        except Exception:
            logging.exception("Failed to process callback")

        return AckMessage.STATUS_OK, "OK"


def _validate_stream_credentials(client_id: str, client_secret: str):
    """
    Validate AppKey/AppSecret once before connecting stream.
    Raises RuntimeError with clear message when credentials are invalid.
    """
    try:
        resp = requests.post(
            "https://api.dingtalk.com/v1.0/oauth2/accessToken",
            json={"appKey": client_id, "appSecret": client_secret},
            timeout=10,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"钉钉凭证校验失败：无法连接鉴权接口（{e}）") from e

    if resp.status_code != 200:
        raise RuntimeError(f"钉钉凭证校验失败：HTTP {resp.status_code}，请检查网络或企业策略。")

    try:
        data = resp.json()
    except ValueError as e:
        raise RuntimeError(f"钉钉凭证校验失败：鉴权响应不是JSON：{resp.text[:200]}") from e

    access_token = data.get("accessToken")
    if access_token:
        logging.info("Credential check OK (accessToken acquired).")
        return

    code = data.get("code")
    message = data.get("message")
    raise RuntimeError(
        f"钉钉凭证校验失败：{code or 'unknown_error'}，"
        f"{message or '请检查 AppKey/AppSecret 是否来自同一应用且为最新值。'}"
    )


def _loop_exception_handler(loop: asyncio.AbstractEventLoop, context: dict):
    """
    Suppress known noisy websocket EOF callback errors on Windows/Python 3.12.
    Connection loss is expected; outer loop already reconnects.
    """
    exc = context.get("exception")
    if isinstance(exc, EOFError) and "stream ended" in str(exc).lower():
        logging.warning("Stream closed (EOF), waiting for reconnect...")
        return
    loop.default_exception_handler(context)


def main():
    _load_env()

    client_id = os.getenv("DINGTALK_STREAM_CLIENT_ID", "").strip() or os.getenv("DINGTALK_APP_KEY", "").strip()
    client_secret = os.getenv("DINGTALK_STREAM_CLIENT_SECRET", "").strip() or os.getenv(
        "DINGTALK_APP_SECRET", ""
    ).strip()

    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing stream credentials. Please set DINGTALK_STREAM_CLIENT_ID/DINGTALK_STREAM_CLIENT_SECRET "
            "or DINGTALK_APP_KEY/DINGTALK_APP_SECRET in .env.dingtalk_agent."
        )

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    # Suppress noisy logging formatting errors from third-party SDK internals.
    logging.raiseExceptions = False
    logging.getLogger("dingtalk_stream").setLevel(logging.INFO)
    logging.info("Starting DingTalk Stream bot...")
    logging.info("ENV file: %s", ENV_PATH)
    _validate_stream_credentials(client_id, client_secret)

    # Windows fix: avoid ProactorEventLoop + websockets instability (InvalidStateError/EOFError).
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    while True:
        try:
            loop = asyncio.new_event_loop()
            loop.set_exception_handler(_loop_exception_handler)
            asyncio.set_event_loop(loop)

            credential = dingtalk_stream.Credential(client_id, client_secret)
            client = dingtalk_stream.DingTalkStreamClient(credential)
            handler = LocalCommandBotHandler()
            client.register_callback_handler(dingtalk_stream.chatbot.ChatbotMessage.TOPIC, handler)
            # Some bot scenarios deliver callbacks via delegate topic.
            client.register_callback_handler(dingtalk_stream.chatbot.ChatbotMessage.DELEGATE_TOPIC, handler)
            client.start_forever()
        except KeyboardInterrupt:
            logging.info("Stream bot stopped by user.")
            break
        except Exception:
            logging.exception("Stream connection crashed, reconnect in 3s...")
            time.sleep(3)


if __name__ == "__main__":
    main()
