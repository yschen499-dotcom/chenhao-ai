import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_title: str = "浙科大校园智能问答助手 v3.0-A"
    docs_dir: str = "campus_docs"
    persist_dir: str = "chroma_campus_db"
    manifest_path: str = os.path.join("chroma_campus_db", "manifest.json")
    supported_extensions: set = field(default_factory=lambda: {".pdf", ".txt", ".md"})
    max_prompt_history_turns: int = 6
    max_session_turns: int = 20
    model_max_retries: int = 3
    rewrite_context_turns: int = 2
    retrieve_k: int = 3
    max_combined_docs: int = 5
    query_rewrite_enabled: bool = True
    answer_template_enabled: bool = True
    natural_style_enabled: bool = True
    default_chat_model: str = "qwen-turbo"
    rewrite_model: str = "qwen-turbo"
    embedding_model: str = "text-embedding-v1"
    server_name: str = "127.0.0.1"
    server_port: int = 7860
    debug: bool = True
    fact_question_keywords: List[str] = field(
        default_factory=lambda: [
            "几点",
            "时间",
            "电话",
            "地点",
            "地址",
            "在哪",
            "哪里",
            "开放",
            "开门",
            "什么时候",
        ]
    )
    process_question_keywords: List[str] = field(
        default_factory=lambda: [
            "怎么",
            "如何",
            "申请",
            "办理",
            "流程",
            "步骤",
            "材料",
            "需要什么",
        ]
    )
    policy_question_keywords: List[str] = field(
        default_factory=lambda: [
            "规定",
            "要求",
            "条件",
            "补考",
            "重修",
            "违纪",
            "处分",
            "学籍",
            "奖学金",
            "能不能",
            "可以吗",
            "是否",
        ]
    )

    @property
    def dashscope_api_key(self) -> str:
        return os.getenv("DASHSCOPE_API_KEY", "")


settings = Settings()
