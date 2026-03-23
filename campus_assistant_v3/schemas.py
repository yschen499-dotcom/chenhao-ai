from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class QueryPlan:
    original_question: str
    rewritten_question: str
    use_rewrite: bool
    question_type: str


@dataclass
class RetrievalResult:
    query_plan: QueryPlan
    docs: List
    sources: List[str] = field(default_factory=list)
    retrieval_queries: List[str] = field(default_factory=list)


@dataclass
class AnswerResult:
    answer: str
    sources: List[str]
    question_type: str
    rewritten_question: Optional[str] = None
