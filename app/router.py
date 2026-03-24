from typing import Callable, Optional

from .commands import parse_admin_command
from .storage import Storage


class CommandRouter:
    def __init__(self, storage: Storage, scan_callback: Optional[Callable[[], str]] = None):
        self.storage = storage
        self.scan_callback = scan_callback

    def handle_text(self, text: str) -> Optional[str]:
        return parse_admin_command(text, self.storage, self.scan_callback)
