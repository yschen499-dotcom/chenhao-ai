import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

import dingtalk_stream
import requests
from dingtalk_stream import AckMessage

from app.config import get_log_level, get_max_reply_chars
from app.monitor import MonitorService
from app.router import CommandRouter
from app.storage import Storage


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = os.getenv("DINGTALK_AGENT_ENV_FILE", ".env.dingtalk_agent")
ENV_PATH = BASE_DIR / ENV_FILE


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
    max_reply_chars = get_max_reply_chars()
    if len(s) <= max_reply_chars:
        return s
    return s[: max_reply_chars - 20] + "\n...(truncated)..."

def _preview_json(data, limit: int = 800) -> str:
    try:
        text = json.dumps(data, ensure_ascii=False, sort_keys=True)
    except TypeError:
        text = repr(data)
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "...(truncated)..."


class InternalTestBotHandler(dingtalk_stream.ChatbotHandler):
    def __init__(self, router: CommandRouter):
        super().__init__()
        self.router = router

    async def process(self, callback: dingtalk_stream.CallbackMessage):
        try:
            logging.info(
                "Raw callback received: topic=%r headers=%s data=%s",
                getattr(callback, "topic", None),
                _preview_json(getattr(callback, "headers", None)),
                _preview_json(getattr(callback, "data", None)),
            )
            incoming = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
            text = ""
            if getattr(incoming, "text", None) and getattr(incoming.text, "content", None):
                text = incoming.text.content

            logging.info(
                "Incoming chatbot text=%r conversation_type=%r sender=%r",
                text,
                getattr(incoming, "conversation_type", None),
                getattr(incoming, "sender_staff_id", None),
            )

            reply = self.router.handle_text(text)
            if reply is not None:
                logging.info("Replying with %d chars", len(reply))
                self.reply_text(_truncate(reply), incoming)
            else:
                logging.info("No reply generated for incoming text.")
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
    log_level = get_log_level()

    client_id = os.getenv("DINGTALK_STREAM_CLIENT_ID", "").strip() or os.getenv("DINGTALK_APP_KEY", "").strip()
    client_secret = os.getenv("DINGTALK_STREAM_CLIENT_SECRET", "").strip() or os.getenv(
        "DINGTALK_APP_SECRET", ""
    ).strip()

    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing stream credentials. Please set DINGTALK_STREAM_CLIENT_ID/DINGTALK_STREAM_CLIENT_SECRET "
            "or DINGTALK_APP_KEY/DINGTALK_APP_SECRET in .env.dingtalk_agent."
        )

    logging.basicConfig(level=getattr(logging, log_level, logging.INFO), format="%(asctime)s [%(levelname)s] %(message)s")
    # Suppress noisy logging formatting errors from third-party SDK internals.
    logging.raiseExceptions = False
    logging.getLogger("dingtalk_stream").setLevel(getattr(logging, log_level, logging.INFO))
    logging.info("Starting DingTalk Stream bot...")
    logging.info("ENV file: %s", ENV_PATH)
    logging.info("Log level: %s", log_level)
    _validate_stream_credentials(client_id, client_secret)

    # Windows fix: avoid ProactorEventLoop + websockets instability (InvalidStateError/EOFError).
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    storage = Storage()
    monitor = MonitorService(storage)
    router = CommandRouter(storage=storage, scan_callback=monitor.scan_once)
    logging.info("内部测试命令已就绪：帮助/状态/监控列表/添加监控/删除监控/立即扫描/测试提醒")

    while True:
        try:
            loop = asyncio.new_event_loop()
            loop.set_exception_handler(_loop_exception_handler)
            asyncio.set_event_loop(loop)

            credential = dingtalk_stream.Credential(client_id, client_secret)
            client = dingtalk_stream.DingTalkStreamClient(credential)
            handler = InternalTestBotHandler(router)
            chatbot_topic = dingtalk_stream.ChatbotMessage.TOPIC
            delegate_topic = dingtalk_stream.ChatbotMessage.DELEGATE_TOPIC
            client.register_callback_handler(chatbot_topic, handler)
            # Some bot scenarios deliver callbacks via delegate topic.
            client.register_callback_handler(delegate_topic, handler)
            logging.info("Registered callback handlers: %s, %s", chatbot_topic, delegate_topic)
            logging.info("Waiting for direct-chat messages or @mentions in group chats.")
            client.start_forever()
        except KeyboardInterrupt:
            logging.info("Stream bot stopped by user.")
            break
        except Exception:
            logging.exception("Stream connection crashed, reconnect in 3s...")
            time.sleep(3)


if __name__ == "__main__":
    main()
