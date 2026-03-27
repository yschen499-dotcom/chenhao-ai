import asyncio
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional, Tuple

import dingtalk_stream
import requests
from dingtalk_stream import AckMessage

from app.alerts import record_triggered_alert
from app.config import (
    get_log_level,
    get_max_reply_chars,
    get_scan_interval_seconds,
    is_background_scan_enabled,
)
from app.market_overview import run_market_overview
from app.monitor import MonitorService
from app.deep_analysis import run_deep_analysis
from app.router import CommandRouter
from app.llm import warm_llm_connection
from app.scheduler import start_scheduler
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


_REPLY_FOOTER = "\n\n💡 发送「帮助」获取更多功能"


def _finalize_reply(body: str) -> str:
    """
    所有会话回复统一追加尾注，避免用户不知道可发「帮助」。
    总长度受 AGENT_MAX_REPLY_CHARS 限制，尾注不被截断。
    """
    max_total = get_max_reply_chars()
    text = (body or "").rstrip()
    if not text:
        return _REPLY_FOOTER.strip()
    if len(text) + len(_REPLY_FOOTER) <= max_total:
        return text + _REPLY_FOOTER
    suffix = "\n...(truncated)..."
    room = max_total - len(_REPLY_FOOTER) - len(suffix)
    if room < 1:
        return _REPLY_FOOTER.strip()[:max_total]
    head = text[:room]
    return head + suffix + _REPLY_FOOTER

def _preview_json(data, limit: int = 800) -> str:
    try:
        text = json.dumps(data, ensure_ascii=False, sort_keys=True)
    except TypeError:
        text = repr(data)
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "...(truncated)..."


# Stream 每次重连会 new 新的 ChatbotHandler，后台扫描线程不能长期捕获「第一个」 handler，
# 否则 reply_text 仍指向旧实例，会话 Webhook 失效，钉钉收不到主动预警。
_bot_session_lock = threading.Lock()
_bot_session_handler: Optional[Any] = None
_bot_session_incoming = None


def _set_bot_session(handler: Any, incoming: Any) -> None:
    global _bot_session_handler, _bot_session_incoming
    with _bot_session_lock:
        _bot_session_handler = handler
        _bot_session_incoming = incoming


def _get_bot_session() -> Tuple[Optional[Any], Any]:
    with _bot_session_lock:
        return _bot_session_handler, _bot_session_incoming


class InternalTestBotHandler(dingtalk_stream.ChatbotHandler):
    def __init__(self, router: CommandRouter, storage: Storage):
        super().__init__()
        self.router = router
        self.storage = storage
        self._latest_incoming = None

    def latest_incoming(self):
        return self._latest_incoming

    async def process(self, callback: dingtalk_stream.CallbackMessage):
        try:
            logging.info(
                "Raw callback received: topic=%r headers=%s data=%s",
                getattr(callback, "topic", None),
                _preview_json(getattr(callback, "headers", None)),
                _preview_json(getattr(callback, "data", None)),
            )
            incoming = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
            self._latest_incoming = incoming
            _set_bot_session(self, incoming)
            sender_staff_id = getattr(incoming, "sender_staff_id", "") or ""
            if sender_staff_id:
                self.storage.write_state("admin_sender_staff_id", sender_staff_id)
            text = ""
            if getattr(incoming, "text", None) and getattr(incoming.text, "content", None):
                text = (incoming.text.content or "").strip()

            if not text:
                logging.info(
                    "Incoming message has empty text (e.g. image/card); conversation_type=%r sender=%r",
                    getattr(incoming, "conversation_type", None),
                    getattr(incoming, "sender_staff_id", None),
                )
            else:
                logging.info(
                    "Incoming chatbot text=%r conversation_type=%r sender=%r",
                    text,
                    getattr(incoming, "conversation_type", None),
                    getattr(incoming, "sender_staff_id", None),
                )

            try:
                reply = self.router.handle_text(text)
            except Exception as e:
                logging.exception("router.handle_text 失败")
                reply = f"命令处理异常：{e}"

            if reply is not None:
                out = _finalize_reply(reply)
                logging.info("Replying with %d chars (incl. footer)", len(out))
                send_result = self.reply_text(out, incoming)
                if send_result is None:
                    logging.error(
                        "reply_text failed (session webhook). See dingtalk_stream ERROR above; "
                        "check robot permissions and corporate network to oapi.dingtalk.com."
                    )
                else:
                    logging.info("reply_text sent OK.")
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


_background_scan_thread_started = False


def _start_background_scan_loop(
    monitor: MonitorService,
    storage: Storage,
) -> None:
    """只应启动一次；会话上下文见 _get_bot_session（随每条消息更新）。"""
    global _background_scan_thread_started
    if not is_background_scan_enabled():
        logging.info("自动扫描未开启（AGENT_ENABLE_BACKGROUND_SCAN=false），无后台轮询与预警推送。")
        return
    if _background_scan_thread_started:
        return
    _background_scan_thread_started = True

    interval = get_scan_interval_seconds()

    def _worker():
        logging.info("后台自动扫描已启动，间隔 %ss。", interval)
        while True:
            try:
                result = monitor.run_scan(scan_channel="background")
                for alert in result.triggered_alerts:
                    inserted = record_triggered_alert(
                        storage=storage,
                        alert_type=alert.alert_type,
                        alert_key=alert.alert_key,
                        message=alert.message,
                        item_name=alert.item_name,
                    )
                    if not inserted:
                        continue
                    reply_handler, latest_incoming = _get_bot_session()
                    if latest_incoming is None or reply_handler is None:
                        logging.info("命中提醒但尚无会话上下文（请先在单聊或群里 @ 机器人发一条消息），跳过主动推送。")
                        continue
                    send_result = reply_handler.reply_text(
                        _finalize_reply(alert.message), latest_incoming
                    )
                    if send_result is None:
                        logging.error(
                            "主动推送 reply_text 失败：%s（检查会话 Webhook、机器人权限与网络）",
                            alert.alert_key,
                        )
                    else:
                        logging.info("主动推送异动提醒已送达：%s", alert.alert_key)
            except Exception:
                logging.exception("后台自动扫描失败。")
            time.sleep(interval)

    thread = threading.Thread(target=_worker, daemon=True, name="price-alert-loop")
    thread.start()


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
    logging.info("Agent root: %s (cwd=%s)", BASE_DIR, os.getcwd())
    logging.info("ENV file: %s", ENV_PATH)
    logging.info("Log level: %s", log_level)
    _validate_stream_credentials(client_id, client_secret)

    # Windows fix: avoid ProactorEventLoop + websockets instability (InvalidStateError/EOFError).
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    storage = Storage()
    monitor = MonitorService(storage)
    router = CommandRouter(
        storage=storage,
        market_overview_callback=lambda: run_market_overview(storage, monitor.collector),
        collector=monitor.collector,
        deep_analysis_callback=lambda name: run_deep_analysis(name, storage, monitor.collector),
    )
    try:
        start_scheduler(storage, monitor)
    except Exception:
        logging.exception("定时任务启动失败（可检查 APScheduler / tzdata 是否已安装）。")
    warm_llm_connection()
    logging.info(
        "命令已就绪：帮助/状态/监控列表/添加监控/删除监控/深度解析/大盘/测试早报周报月报/测试提醒"
    )

    while True:
        try:
            loop = asyncio.new_event_loop()
            loop.set_exception_handler(_loop_exception_handler)
            asyncio.set_event_loop(loop)

            credential = dingtalk_stream.Credential(client_id, client_secret)
            client = dingtalk_stream.DingTalkStreamClient(credential)
            handler = InternalTestBotHandler(router, storage)
            chatbot_topic = dingtalk_stream.ChatbotMessage.TOPIC
            delegate_topic = dingtalk_stream.ChatbotMessage.DELEGATE_TOPIC
            client.register_callback_handler(chatbot_topic, handler)
            # Some bot scenarios deliver callbacks via delegate topic.
            client.register_callback_handler(delegate_topic, handler)
            logging.info("Registered callback handlers: %s, %s", chatbot_topic, delegate_topic)
            logging.info("Waiting for direct-chat messages or @mentions in group chats.")
            _start_background_scan_loop(monitor, storage)
            client.start_forever()
        except KeyboardInterrupt:
            logging.info("Stream bot stopped by user.")
            break
        except Exception:
            logging.exception("Stream connection crashed, reconnect in 3s...")
            time.sleep(3)


if __name__ == "__main__":
    main()
