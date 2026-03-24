import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests

from .config import (
    STEAMDT_API_BASE,
    STEAMDT_API_KEY,
    STEAMDT_BASE_CACHE_PATH,
    STEAMDT_PRICE_PLATFORM,
    STEAMDT_REQUEST_TIMEOUT_SECONDS,
    ensure_data_dir,
)


@dataclass
class CollectedPrice:
    item_name: str
    market_hash_name: str
    platform: str
    sell_price: float
    sell_count: int
    bidding_price: float
    bidding_count: int
    update_time: int


class SteamDTCollector:
    def __init__(self):
        ensure_data_dir()
        self.base_cache_path: Path = STEAMDT_BASE_CACHE_PATH
        self.session = requests.Session()
        if STEAMDT_API_KEY:
            self.session.headers.update({"Authorization": f"Bearer {STEAMDT_API_KEY}"})

    def _ensure_api_key(self) -> None:
        if not STEAMDT_API_KEY:
            raise RuntimeError(
                "未配置 SteamDT API Key。请在 .env.dingtalk_agent 中设置 "
                "AGENT_STEAMDT_API_KEY=你的SteamDT开放平台Key"
            )

    def _load_base_cache(self) -> Dict[str, str]:
        if not self.base_cache_path.exists():
            return {}
        try:
            with self.base_cache_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            logging.exception("Failed to load SteamDT base cache")
            return {}
        return data if isinstance(data, dict) else {}

    def _save_base_cache(self, mapping: Dict[str, str]) -> None:
        with self.base_cache_path.open("w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2, sort_keys=True)

    def refresh_base_cache(self) -> Dict[str, str]:
        """
        Fetch Chinese item names -> marketHashName mapping.
        SteamDT documents that this endpoint should be called sparingly.
        """
        self._ensure_api_key()
        url = f"{STEAMDT_API_BASE}/open/cs2/v1/base"
        resp = self.session.get(url, timeout=STEAMDT_REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("success"):
            raise RuntimeError(payload.get("errorMsg") or "SteamDT 基础信息接口返回失败。")

        mapping: Dict[str, str] = {}
        for item in payload.get("data") or []:
            name = (item.get("name") or "").strip()
            market_hash_name = (item.get("marketHashName") or "").strip()
            if name and market_hash_name:
                mapping[name] = market_hash_name

        if not mapping:
            raise RuntimeError("SteamDT 基础信息接口没有返回可用的饰品名称映射。")

        self._save_base_cache(mapping)
        return mapping

    def resolve_market_hash_name(self, item_name: str) -> str:
        item_name = item_name.strip()
        if not item_name:
            raise ValueError("饰品名称不能为空。")

        mapping = self._load_base_cache()
        market_hash_name = mapping.get(item_name)
        if market_hash_name:
            return market_hash_name

        logging.info("SteamDT base cache miss for item=%r, refreshing cache", item_name)
        mapping = self.refresh_base_cache()
        market_hash_name = mapping.get(item_name)
        if not market_hash_name:
            raise RuntimeError(f"未在 SteamDT 基础信息中找到饰品：{item_name}")
        return market_hash_name

    def fetch_single_price(self, item_name: str) -> CollectedPrice:
        self._ensure_api_key()
        market_hash_name = self.resolve_market_hash_name(item_name)
        url = f"{STEAMDT_API_BASE}/open/cs2/v1/price/single"
        params = {"marketHashName": market_hash_name}
        resp = self.session.get(url, params=params, timeout=STEAMDT_REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("success"):
            raise RuntimeError(payload.get("errorMsg") or f"SteamDT 价格接口返回失败：{item_name}")

        rows = payload.get("data") or []
        if not rows:
            raise RuntimeError(f"SteamDT 没有返回饰品价格：{item_name}")

        preferred_platform = STEAMDT_PRICE_PLATFORM
        selected = None
        for row in rows:
            if (row.get("platform") or "").upper() == preferred_platform:
                selected = row
                break
        if selected is None:
            selected = rows[0]

        return CollectedPrice(
            item_name=item_name,
            market_hash_name=market_hash_name,
            platform=(selected.get("platform") or "").upper() or preferred_platform,
            sell_price=float(selected.get("sellPrice") or 0),
            sell_count=int(selected.get("sellCount") or 0),
            bidding_price=float(selected.get("biddingPrice") or 0),
            bidding_count=int(selected.get("biddingCount") or 0),
            update_time=int(selected.get("updateTime") or 0),
        )

    def fetch_prices(self, item_names: List[str]) -> List[CollectedPrice]:
        collected: List[CollectedPrice] = []
        for item_name in item_names:
            collected.append(self.fetch_single_price(item_name))
        return collected
