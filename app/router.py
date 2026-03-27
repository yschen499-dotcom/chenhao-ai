from typing import TYPE_CHECKING, Callable, Optional

from .commands import parse_admin_command
from .storage import Storage

if TYPE_CHECKING:
    from .collector import SteamDTCollector


class CommandRouter:
    def __init__(
        self,
        storage: Storage,
        market_overview_callback: Optional[Callable[[], str]] = None,
        collector: Optional["SteamDTCollector"] = None,
        deep_analysis_callback: Optional[Callable[[str], str]] = None,
    ):
        self.storage = storage
        self.market_overview_callback = market_overview_callback
        self.collector = collector
        self.deep_analysis_callback = deep_analysis_callback

    def handle_text(self, text: str) -> Optional[str]:
        return parse_admin_command(
            text,
            self.storage,
            self.market_overview_callback,
            self.collector,
            self.deep_analysis_callback,
        )
