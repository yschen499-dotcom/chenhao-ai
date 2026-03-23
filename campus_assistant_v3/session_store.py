from typing import Dict, List, Tuple

from campus_assistant_v3.config import settings


SESSION_HISTORY: Dict[str, List[Tuple[str, str]]] = {}


def get_history(session_id: str = "default") -> List[Tuple[str, str]]:
    return list(SESSION_HISTORY.get(session_id, []))


def append_history(session_id: str, user_text: str, assistant_text: str) -> None:
    history = SESSION_HISTORY.get(session_id, [])
    history.append((user_text, assistant_text))
    SESSION_HISTORY[session_id] = history[-settings.max_session_turns :]


def clear_history(session_id: str = "default") -> None:
    SESSION_HISTORY[session_id] = []


def clear_all_history() -> None:
    SESSION_HISTORY.clear()
