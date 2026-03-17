from typing import List

from campus_assistant_v3.config import settings
from campus_assistant_v3.schemas import QueryPlan, RetrievalResult


def retrieve_docs_for_query(vector_store, query: str, k: int = settings.retrieve_k):
    retriever = vector_store.as_retriever(search_kwargs={"k": k})
    if hasattr(retriever, "invoke"):
        return retriever.invoke(query)
    return retriever.get_relevant_documents(query)


def merge_docs(original_docs, rewritten_docs, max_docs: int = settings.max_combined_docs):
    merged = []
    seen = set()

    for doc in list(original_docs) + list(rewritten_docs):
        source = str(doc.metadata.get("source", "unknown"))
        page = str(doc.metadata.get("page", ""))
        content_key = (doc.page_content or "").strip()[:120]
        doc_key = (source, page, content_key)
        if doc_key in seen:
            continue
        seen.add(doc_key)
        merged.append(doc)
        if len(merged) >= max_docs:
            break
    return merged


def extract_sources(docs: List) -> List[str]:
    return [doc.metadata.get("source", "unknown") for doc in docs]


def build_retrieval_result(vector_store, query_plan: QueryPlan) -> RetrievalResult:
    original_docs = retrieve_docs_for_query(vector_store, query_plan.original_question)
    rewritten_docs = []
    retrieval_queries = [query_plan.original_question]

    if query_plan.use_rewrite:
        rewritten_docs = retrieve_docs_for_query(vector_store, query_plan.rewritten_question)
        retrieval_queries.append(query_plan.rewritten_question)

    docs = merge_docs(original_docs, rewritten_docs)
    return RetrievalResult(
        query_plan=query_plan,
        docs=docs,
        sources=extract_sources(docs),
        retrieval_queries=retrieval_queries,
    )
