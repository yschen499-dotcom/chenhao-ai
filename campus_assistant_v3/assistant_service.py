import logging

from campus_assistant_v3.answering import generate_answer
from campus_assistant_v3.knowledge_base import initialize_vector_store
from campus_assistant_v3.query_understanding import build_query_plan
from campus_assistant_v3.retrieval import build_retrieval_result
from campus_assistant_v3.session_store import append_history, clear_history, get_history
from campus_assistant_v3.upload_manager import handle_upload


logger = logging.getLogger(__name__)


class CampusAssistantService:
    def __init__(self):
        self.vector_store = None

    def initialize(self) -> None:
        self.vector_store = initialize_vector_store()

    def answer_question(self, question: str, session_id: str = "default"):
        if self.vector_store is None:
            return "😅 助手还没初始化哦，请先上传校园文档或检查启动日志。", []

        history = get_history(session_id)
        query_plan = build_query_plan(question, history)
        retrieval_result = build_retrieval_result(self.vector_store, query_plan)
        answer_result = generate_answer(query_plan.original_question, history, retrieval_result)

        append_history(session_id, query_plan.original_question, answer_result.answer)
        return answer_result.answer, answer_result.sources

    def refresh_knowledge_base(self, files):
        message, vector_store = handle_upload(files)
        if vector_store is not None:
            self.vector_store = vector_store
            clear_history("default")
        return message

    def clear_session(self, session_id: str = "default"):
        clear_history(session_id)
