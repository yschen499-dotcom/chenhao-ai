"""钉钉自定义机器人 Webhook（markdown）。"""

from __future__ import annotations

import logging
from typing import Optional

import requests

from .config import get_dingtalk_webhook_url

_MARKDOWN_FOOTER = "\n\n---\n\n💡 发送「帮助」获取更多功能"


def send_markdown_webhook(title: str, text: str, *, webhook_url: Optional[str] = None) -> bool:
    url = (webhook_url or "").strip() or get_dingtalk_webhook_url()
    if not url:
        logging.warning("未配置 AGENT_DINGTALK_WEBHOOK_URL，跳过钉钉推送。")
        return False
    t = (text or "").rstrip()
    if _MARKDOWN_FOOTER.strip() not in t:
        t = t + _MARKDOWN_FOOTER
    body = {"msgtype": "markdown", "markdown": {"title": title, "text": t}}
    try:
        r = requests.post(url, json=body, timeout=20)
        if r.status_code != 200:
            logging.error("钉钉 Webhook HTTP %s: %s", r.status_code, r.text[:300])
            return False
        data = r.json()
        if isinstance(data, dict) and data.get("errcode") not in (0, None):
            logging.error("钉钉 Webhook 业务错误: %s", data)
            return False
        return True
    except requests.RequestException:
        logging.exception("钉钉 Webhook 请求失败")
        return False
