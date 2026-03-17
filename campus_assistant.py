import hashlib
import json
import logging
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import dashscope
import gradio as gr
from dashscope.aigc.chat_completion import Completions
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter


# ===================== 日志 =====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [浙科大校园助手] - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


# ===================== 配置 =====================
DOCS_DIR = "campus_docs"
PERSIST_DIR = "chroma_campus_db"
MANIFEST_PATH = os.path.join(PERSIST_DIR, "manifest.json")
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}
MAX_PROMPT_HISTORY_TURNS = 6
MAX_SESSION_TURNS = 20
MAX_RETRIEVED_DOCS = 3
MIN_RELEVANCE_SCORE = 0.35
MAX_DISTANCE_SCORE = 0.8
MODEL_MAX_RETRIES = 3


# ===================== 环境变量 =====================
load_dotenv()
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
if not DASHSCOPE_API_KEY:
    logger.error("❌ DASHSCOPE_API_KEY未配置！请在.env文件中设置：DASHSCOPE_API_KEY=sk-xxxxxxxxx")
    raise SystemExit(1)

dashscope.api_key = DASHSCOPE_API_KEY

# 旧版 dashscope 没有 base_compatible_api_url，Completions.create 需要它
if not getattr(dashscope, "base_compatible_api_url", None):
    dashscope.base_compatible_api_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"


# ===================== 全局对象 =====================
vector_store: Optional[Chroma] = None
SESSION_HISTORY: Dict[str, List[Tuple[str, str]]] = {}
VECTOR_STORE_LOCK = Lock()
SESSION_LOCK = Lock()


def _ensure_str(value: Any) -> str:
    """把 Gradio / 模型响应里可能出现的复杂 content 统一转成字符串。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")).strip())
            else:
                parts.append(str(item).strip())
        return " ".join(part for part in parts if part).strip()
    if isinstance(value, dict):
        return str(value.get("text", "")).strip()
    return str(value).strip()


def get_embeddings() -> DashScopeEmbeddings:
    return DashScopeEmbeddings(
        dashscope_api_key=DASHSCOPE_API_KEY,
        model="text-embedding-v1",
    )


def compute_file_sha256(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with file_path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def build_docs_manifest(docs_dir: str = DOCS_DIR) -> List[Dict[str, Any]]:
    if not os.path.isdir(docs_dir):
        return []

    manifest: List[Dict[str, Any]] = []
    for file_path in sorted(Path(docs_dir).iterdir()):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        manifest.append(
            {
                "name": file_path.name,
                "size": file_path.stat().st_size,
                "sha256": compute_file_sha256(file_path),
            }
        )
    return manifest


def load_saved_manifest() -> Optional[List[Dict[str, Any]]]:
    if not os.path.exists(MANIFEST_PATH):
        return None

    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as file_obj:
            return json.load(file_obj)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(f"⚠️ 读取知识库清单失败，将重新构建知识库：{exc}")
        return None


def save_manifest(manifest: List[Dict[str, Any]]) -> None:
    os.makedirs(PERSIST_DIR, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as file_obj:
        json.dump(manifest, file_obj, ensure_ascii=False, indent=2)


def has_persisted_vector_store() -> bool:
    persist_path = Path(PERSIST_DIR)
    if not persist_path.exists() or not persist_path.is_dir():
        return False
    return any(child.name != Path(MANIFEST_PATH).name for child in persist_path.iterdir())


def should_rebuild_vector_store(current_manifest: List[Dict[str, Any]]) -> bool:
    if not has_persisted_vector_store():
        return True
    saved_manifest = load_saved_manifest()
    return saved_manifest != current_manifest


def reset_persist_directory(persist_dir: str = PERSIST_DIR) -> None:
    if os.path.exists(persist_dir):
        shutil.rmtree(persist_dir)


def load_existing_vector_store(persist_dir: str = PERSIST_DIR) -> Chroma:
    logger.info("✅ 检测到文档未变化，直接加载已有知识库，跳过重复 embedding")
    return Chroma(
        embedding_function=get_embeddings(),
        persist_directory=persist_dir,
    )


# ===================== 文档加载 =====================
def load_campus_docs(docs_dir: str = DOCS_DIR):
    """加载校园文档（支持 PDF/TXT/MD）"""
    if not os.path.exists(docs_dir):
        os.makedirs(docs_dir, exist_ok=True)
        logger.warning(f"⚠️ 已自动创建【校园文档目录】，请把校园文档放入 {docs_dir} 文件夹")
        return []

    docs = []
    for file_name in sorted(os.listdir(docs_dir)):
        file_path = os.path.join(docs_dir, file_name)
        try:
            lower = file_name.lower()
            if lower.endswith(".pdf"):
                loader = PyPDFLoader(file_path)
                docs.extend(loader.load())
                logger.info(f"✅ 加载校园PDF文档：{file_name}")
            elif lower.endswith(".txt") or lower.endswith(".md"):
                loader = TextLoader(file_path, encoding="utf-8")
                docs.extend(loader.load())
                logger.info(f"✅ 加载校园文档：{file_name}")
            else:
                logger.info(f"⚠️ 不支持的文件格式：{file_name}")
        except Exception as exc:
            logger.exception(f"❌ 加载文档 {file_name} 失败：{exc}")

    return docs


def create_vector_store(
    docs,
    persist_dir: str = PERSIST_DIR,
    docs_manifest: Optional[List[Dict[str, Any]]] = None,
):
    """创建本地向量库（每次重建前清空旧库，避免重复写入）"""
    embeddings = get_embeddings()
    reset_persist_directory(persist_dir)

    if not docs:
        logger.warning("⚠️ 没有加载到校园文档，将创建空的知识库（可先上传文档后再更新）")
        vs = Chroma(
            embedding_function=embeddings,
            persist_directory=persist_dir,
        )
        save_manifest(docs_manifest or [])
        logger.info("✅ 空的校园知识库创建成功")
        return vs

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    split_docs = text_splitter.split_documents(docs)

    vs = Chroma.from_documents(
        documents=split_docs,
        embedding=embeddings,
        persist_directory=persist_dir,
    )
    save_manifest(docs_manifest or [])
    logger.info(f"✅ 校园知识库创建成功，共存储 {len(split_docs)} 个文档片段")
    return vs


def initialize_vector_store(force_rebuild: bool = False) -> Chroma:
    current_manifest = build_docs_manifest(DOCS_DIR)
    if not force_rebuild and not should_rebuild_vector_store(current_manifest):
        return load_existing_vector_store()

    docs = load_campus_docs(DOCS_DIR)
    refreshed_manifest = build_docs_manifest(DOCS_DIR)
    return create_vector_store(docs, docs_manifest=refreshed_manifest)


def format_history(history: List[Tuple[str, str]], max_turns: int = MAX_PROMPT_HISTORY_TURNS) -> str:
    """把历史对话拼成文本，给模型做上下文理解"""
    if not history:
        return "（无）"
    sliced = history[-max_turns:]
    lines = []
    for user_text, assistant_text in sliced:
        lines.append(f"用户：{user_text}")
        lines.append(f"助手：{assistant_text}")
    return "\n".join(lines)


def append_history(session_id: str, user_text: str, assistant_text: str) -> None:
    with SESSION_LOCK:
        history = SESSION_HISTORY.get(session_id, [])
        history.append((user_text, assistant_text))
        SESSION_HISTORY[session_id] = history[-MAX_SESSION_TURNS:]


def get_history(session_id: str) -> List[Tuple[str, str]]:
    with SESSION_LOCK:
        return list(SESSION_HISTORY.get(session_id, []))


def clear_session_history(session_id: Optional[str] = None) -> None:
    with SESSION_LOCK:
        if session_id is None:
            SESSION_HISTORY.clear()
        else:
            SESSION_HISTORY[session_id] = []


def format_docs_for_prompt(docs, max_chars: int = 6000) -> str:
    """把检索到的文档内容压缩进 prompt，避免太长"""
    if not docs:
        return "（未检索到相关内容）"

    parts = []
    used = 0
    for index, doc in enumerate(docs, start=1):
        src = doc.metadata.get("source", "unknown")
        text = (doc.page_content or "").strip()
        block = f"[片段{index} | 来源：{src}]\n{text}\n"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)

    return "\n".join(parts) if parts else "（检索内容过长，已被截断）"


def extract_model_content(response: Any) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    if message is None:
        return ""
    return _ensure_str(getattr(message, "content", ""))


def call_qwen(prompt: str, model_name: str = "qwen-turbo", temperature: float = 0.1) -> str:
    """使用 OpenAI 兼容接口调用通义千问，并补上重试与友好异常处理。"""
    text = _ensure_str(prompt)
    if not text:
        return "请输入有效问题。"

    messages = [
        {"role": "system", "content": "你是浙江科技大学校园智能助手，请根据提供的资料简洁回答。"},
        {"role": "user", "content": text},
    ]

    last_error: Optional[Exception] = None
    for attempt in range(1, MODEL_MAX_RETRIES + 1):
        try:
            response = Completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
            )
            status_code = getattr(response, "status_code", 200)
            if status_code != 200:
                message = getattr(response, "message", f"通义千问调用失败，状态码：{status_code}")
                raise RuntimeError(message)

            content = extract_model_content(response)
            if not content:
                raise RuntimeError("通义千问返回了空内容")
            return content
        except Exception as exc:
            last_error = exc
            logger.warning(f"⚠️ 第 {attempt}/{MODEL_MAX_RETRIES} 次模型调用失败：{exc}")
            if attempt < MODEL_MAX_RETRIES:
                time.sleep(attempt)

    logger.error(f"❌ 模型服务连续调用失败：{last_error}")
    raise RuntimeError("大模型服务暂时不可用，请稍后重试。") from last_error


def retrieve_relevant_docs(store: Chroma, question: str, k: int = MAX_RETRIEVED_DOCS):
    """兼容不同 LangChain 版本的检索 API，并加入分数阈值过滤。"""
    try:
        if hasattr(store, "similarity_search_with_relevance_scores"):
            docs_with_scores = store.similarity_search_with_relevance_scores(question, k=k)
            filtered = [(doc, float(score)) for doc, score in docs_with_scores if score is not None and float(score) >= MIN_RELEVANCE_SCORE]
            logger.info(f"🔍 relevance_score 检索命中 {len(filtered)} 个片段，阈值={MIN_RELEVANCE_SCORE}")
            return filtered
    except Exception as exc:
        logger.warning(f"⚠️ relevance_score 检索失败，回退到其他检索方式：{exc}")

    try:
        if hasattr(store, "similarity_search_with_score"):
            docs_with_scores = store.similarity_search_with_score(question, k=k)
            filtered = [(doc, float(score)) for doc, score in docs_with_scores if score is not None and float(score) <= MAX_DISTANCE_SCORE]
            logger.info(f"🔍 distance_score 检索命中 {len(filtered)} 个片段，阈值<={MAX_DISTANCE_SCORE}")
            return filtered
    except Exception as exc:
        logger.warning(f"⚠️ distance_score 检索失败，回退到普通检索：{exc}")

    retriever = store.as_retriever(search_kwargs={"k": k})
    if hasattr(retriever, "invoke"):
        docs = retriever.invoke(question)
    else:
        docs = retriever.get_relevant_documents(question)
    logger.warning("⚠️ 当前向量库版本不支持分数阈值，已回退为普通检索")
    return [(doc, None) for doc in docs]


def unique_sources_from_docs(docs) -> List[str]:
    seen = set()
    sources = []
    for doc in docs:
        source = os.path.basename(str(doc.metadata.get("source", "unknown")))
        if source not in seen:
            seen.add(source)
            sources.append(source)
    return sources


def append_sources_to_answer(answer: str, sources: List[str]) -> str:
    if not sources:
        return answer
    source_lines = [f"{index}. {source}" for index, source in enumerate(sources, start=1)]
    return f"{answer}\n\n参考来源：\n" + "\n".join(source_lines)


def rag_answer(question, session_id: str = "default") -> Tuple[str, List[str]]:
    question = _ensure_str(question)
    if not question:
        return "请输入有效问题。", []

    with VECTOR_STORE_LOCK:
        store = vector_store

    if store is None:
        return "😅 助手还没初始化哦，请先上传校园文档或检查启动日志。", []

    history = get_history(session_id)
    chat_history_text = format_history(history)
    docs_with_scores = retrieve_relevant_docs(store, question)
    docs = [doc for doc, _ in docs_with_scores]

    if not docs:
        answer = "抱歉，我暂时没有找到相关信息。"
        append_history(session_id, question, answer)
        return answer, []

    context_text = format_docs_for_prompt(docs)
    prompt = f"""
你是【浙江科技大学专属校园智能问答助手】，回答必须符合浙科大校园场景。

请优先参考以下校园资料内容（不允许提及“检索/文档/RAG”等技术词）：
{context_text}

历史对话：
{chat_history_text}

用户问题：{question}

回答要求：
- 简洁准确，符合浙科大校园实际情况
- 优先使用提供的校园资料，不要脱离资料随意发挥
- 不知道的内容不要编造，直接说“抱歉，我暂时没有找到相关信息”
""".strip()

    answer = call_qwen(prompt, model_name="qwen-turbo", temperature=0.1)
    sources = unique_sources_from_docs(docs)
    append_history(session_id, question, answer)
    return append_sources_to_answer(answer, sources), sources


def build_safe_upload_filename(filename: str) -> str:
    original_name = os.path.basename(filename or "uploaded_file")
    suffix = Path(original_name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"不支持的文件类型：{suffix or '无扩展名'}")

    stem = Path(original_name).stem
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    if not safe_stem:
        safe_stem = "campus_doc"
    return f"{safe_stem[:40]}_{uuid.uuid4().hex[:8]}{suffix}"


# ===================== Gradio UI =====================
def create_gradio_ui():
    with gr.Blocks(title="浙科大校园智能问答助手") as demo:
        gr.Markdown(
            """
# 🎓 浙科大校园智能问答助手
**基于通义千问大模型 + 本地知识库（Chroma） 的校园助手**
""".strip()
        )

        chatbot = gr.Chatbot(height=500)
        msg = gr.Textbox(label="你的问题", placeholder="比如：图书馆开放时间是什么时候？")
        clear_btn = gr.Button("清除对话")

        with gr.Tab("📚 上传校园文档"):
            gr.Markdown("上传浙科大校园相关文档（PDF/TXT/MD），助手会自动学习")
            file_upload = gr.File(file_count="multiple", label="选择校园文档")
            upload_btn = gr.Button("上传并更新知识库")
            upload_status = gr.Textbox(label="上传状态", interactive=False)

        def user_input_handler(question, chat_history):
            chat_history = chat_history or []
            user_text = _ensure_str(question)
            if not user_text:
                return "", chat_history
            return "", chat_history + [{"role": "user", "content": user_text}]

        def bot_response_handler(chat_history):
            chat_history = chat_history or []
            if not chat_history:
                return chat_history

            question = ""
            for message in reversed(chat_history):
                if isinstance(message, dict) and message.get("role") == "user":
                    question = _ensure_str(message.get("content", ""))
                    break
            if not question:
                return chat_history

            try:
                answer, sources = rag_answer(question, session_id="default")
                chat_history = chat_history + [{"role": "assistant", "content": answer}]
                logger.info(f"🔍 回答来源文档：{sources}")
                return chat_history
            except Exception as exc:
                logger.exception("❌ 回答失败（这里会打印完整堆栈）")
                chat_history = chat_history + [{"role": "assistant", "content": f"😔 回答失败：{str(exc)}"}]
                return chat_history

        def upload_docs_handler(files):
            global vector_store
            if not files:
                return "请先选择要上传的校园文档"

            os.makedirs(DOCS_DIR, exist_ok=True)
            saved = 0
            rejected = []

            for file_obj in files:
                src_path = getattr(file_obj, "path", None) or getattr(file_obj, "name", None)
                orig_name = getattr(file_obj, "orig_name", None) or os.path.basename(str(src_path or "uploaded_file"))
                if not src_path or not os.path.exists(src_path):
                    logger.warning(f"⚠️ 上传文件不存在，已跳过：{orig_name}")
                    continue

                try:
                    safe_name = build_safe_upload_filename(orig_name)
                    dst_path = os.path.join(DOCS_DIR, safe_name)
                    with open(src_path, "rb") as read_file, open(dst_path, "wb") as write_file:
                        shutil.copyfileobj(read_file, write_file)
                    logger.info(f"📤 上传文档：原始名={orig_name}，保存为={safe_name}")
                    saved += 1
                except ValueError:
                    rejected.append(orig_name)
                except Exception as exc:
                    logger.exception(f"❌ 保存上传文件失败：{orig_name}，错误：{exc}")

            if saved == 0:
                if rejected:
                    return f"未保存任何文件，仅支持：{', '.join(sorted(SUPPORTED_EXTENSIONS))}"
                return "未保存任何文件，请检查上传文件后重试"

            with VECTOR_STORE_LOCK:
                vector_store = initialize_vector_store(force_rebuild=True)

            clear_session_history()

            messages = [f"✅ 成功上传并保存 {saved} 个文档，校园知识库已更新！"]
            if rejected:
                messages.append(f"⚠️ 已跳过不支持的文件：{', '.join(rejected)}")
            return "\n".join(messages)

        msg.submit(
            user_input_handler,
            inputs=[msg, chatbot],
            outputs=[msg, chatbot],
            queue=False,
        ).then(
            bot_response_handler,
            inputs=[chatbot],
            outputs=[chatbot],
        )

        def clear_all():
            clear_session_history("default")
            return []

        clear_btn.click(clear_all, None, chatbot, queue=False)

        upload_btn.click(
            upload_docs_handler,
            inputs=[file_upload],
            outputs=[upload_status],
        )

    return demo


# ===================== 程序入口 =====================
if __name__ == "__main__":
    logger.info("🚀 启动浙科大校园智能问答助手...")

    with VECTOR_STORE_LOCK:
        vector_store = initialize_vector_store()

    demo = create_gradio_ui()
    demo.launch(
        theme=gr.themes.Soft(),
        share=False,
        server_name="127.0.0.1",
        server_port=7860,
        debug=True,
    )
