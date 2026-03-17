import hashlib
import json
import logging
import os
import re
import shutil
import time
import uuid
from pathlib import Path
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
MODEL_MAX_RETRIES = 3
REWRITE_CONTEXT_TURNS = 2
RETRIEVE_K = 3
MAX_COMBINED_DOCS = 5

FACT_QUESTION_KEYWORDS = [
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
PROCESS_QUESTION_KEYWORDS = [
    "怎么",
    "如何",
    "申请",
    "办理",
    "流程",
    "步骤",
    "材料",
    "需要什么",
]
POLICY_QUESTION_KEYWORDS = [
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
# session_id -> [(user, assistant), ...]
SESSION_HISTORY: Dict[str, List[Tuple[str, str]]] = {}


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
    for file_name in os.listdir(docs_dir):
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
    """创建/更新本地向量库（重建前清空旧库，避免重复写入）"""
    embeddings = get_embeddings()
    reset_persist_directory(persist_dir)

    # 没文档也允许启动：创建空库
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


def format_recent_history_for_rewrite(history: List[Tuple[str, str]], max_turns: int = REWRITE_CONTEXT_TURNS) -> str:
    if not history:
        return "（无）"
    sliced = history[-max_turns:]
    lines = []
    for user_text, assistant_text in sliced:
        lines.append(f"用户：{user_text}")
        lines.append(f"助手：{assistant_text}")
    return "\n".join(lines)


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


def call_qwen(prompt: str, model_name: str = "qwen-Plus", temperature: float = 0.1) -> str:
    """使用 OpenAI 兼容接口调用通义千问，并加入重试与友好错误提示。"""
    text = str(prompt).strip() if prompt else ""
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
                raise RuntimeError(getattr(response, "message", "通义千问调用失败"))

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


def _ensure_str(x) -> str:
    """把 Gradio 可能传来的 list content 转成字符串。"""
    if x is None:
        return ""
    if isinstance(x, str):
        return x.strip()
    if isinstance(x, list):
        return " ".join(
            str(item) if not isinstance(item, dict) else item.get("text", str(item)) for item in x
        ).strip()
    return str(x).strip()


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


def should_rewrite_question(question: str, history: List[Tuple[str, str]]) -> bool:
    question = _ensure_str(question)
    if not question:
        return False
    if len(question) >= 28:
        return False

    ambiguous_patterns = [
        r"^(这个|那个|这个呢|那个呢|周末呢|然后呢|怎么办|怎么弄|怎么申请|什么时候|在哪|在哪里|怎么评)$",
        r"(这个|那个|周末呢|怎么办|怎么申请|什么时候|在哪里|能不能|可以吗)$",
    ]
    if any(re.search(pattern, question) for pattern in ambiguous_patterns):
        return True

    if len(question) <= 12:
        return True

    if history and len(question) <= 18:
        return True

    return False


def build_query_rewrite_prompt(question: str, history: List[Tuple[str, str]]) -> str:
    history_text = format_recent_history_for_rewrite(history)
    return f"""
你是一个“校园知识库检索问题改写器”，不是问答助手。

你的任务：把用户当前问题改写成“更适合在浙江科技大学校园知识库中检索”的一句短问题。

要求：
- 只输出一行改写后的检索问题
- 不要回答问题
- 不要解释原因
- 不要输出“好的/根据资料/答案是”等多余内容
- 尽量保留用户原意，只做必要的补全
- 如果原问题已经足够清晰，就原样返回
- 如当前问题依赖上下文，可结合最近对话补全主语
- 不要编造用户没有明确提到的具体条件

最近对话：
{history_text}

当前问题：
{question}
""".strip()


def sanitize_rewritten_query(original_question: str, rewritten_query: str) -> str:
    original_question = _ensure_str(original_question)
    rewritten_query = _ensure_str(rewritten_query)

    if not rewritten_query:
        return original_question

    rewritten_query = rewritten_query.splitlines()[0].strip()
    rewritten_query = rewritten_query.strip("`\"' ")

    if not rewritten_query:
        return original_question

    answer_like_prefixes = ("答：", "回答：", "答案：", "根据", "一般来说", "可以", "不能")
    if rewritten_query.startswith(answer_like_prefixes):
        return original_question

    if len(rewritten_query) > 60:
        return original_question

    return rewritten_query


def rewrite_query(question: str, history: List[Tuple[str, str]]) -> str:
    if not should_rewrite_question(question, history):
        return question

    rewrite_prompt = build_query_rewrite_prompt(question, history)
    try:
        rewritten_query = call_qwen(rewrite_prompt, model_name="qwen-turbo", temperature=0.0)
        safe_query = sanitize_rewritten_query(question, rewritten_query)
        logger.info(f"🔁 查询改写：原问题={question} | 改写后={safe_query}")
        return safe_query
    except Exception as exc:
        logger.warning(f"⚠️ 查询改写失败，回退原问题：{exc}")
        return question


def retrieve_docs_for_query(query: str, k: int = RETRIEVE_K):
    retriever = vector_store.as_retriever(search_kwargs={"k": k})
    if hasattr(retriever, "invoke"):
        return retriever.invoke(query)
    return retriever.get_relevant_documents(query)


def merge_docs(original_docs, rewritten_docs, max_docs: int = MAX_COMBINED_DOCS):
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


def classify_question_type(question: str) -> str:
    question = _ensure_str(question)

    if any(keyword in question for keyword in PROCESS_QUESTION_KEYWORDS):
        return "process"
    if any(keyword in question for keyword in POLICY_QUESTION_KEYWORDS):
        return "policy"
    if any(keyword in question for keyword in FACT_QUESTION_KEYWORDS):
        return "fact"
    return "general"


def build_answer_template(question_type: str) -> str:
    if question_type == "process":
        return """
请优先按以下结构组织回答（如果资料不支持某一项，可以省略，不要硬编）：
1. 办理结论：先用1-2句话直接回答用户最关心的结果
2. 基本流程：用简短条目说明主要步骤
3. 条件或材料：只写资料里明确提到的条件、材料或要求
4. 温馨提醒：如有时间节点、负责部门或“以最新通知为准”等提醒，可简短补充
""".strip()

    if question_type == "policy":
        return """
请优先按以下结构组织回答（如果资料不支持某一项，可以省略，不要硬编）：
1. 结论：先直接说明可以/不可以、要求是什么或规则核心是什么
2. 适用情况：说明适用于哪些学生、课程或场景
3. 关键规则：用简短条目列出最重要的制度内容
4. 注意事项：补充限制条件、例外情况或建议咨询部门
""".strip()

    if question_type == "fact":
        return """
请优先按以下结构组织回答（如果资料不支持某一项，可以省略，不要硬编）：
1. 直接答案：先直接回答时间、地点、电话或事实信息
2. 补充说明：补充必要的细节或特殊情况
3. 温馨提醒：如遇节假日、临时安排或最新通知要求，可简短提醒
""".strip()

    return """
请优先按以下结构组织回答（如果资料不支持某一项，可以省略，不要硬编）：
1. 结论：先用1-2句话回答核心问题
2. 关键信息：用简短条目列出用户最需要知道的内容
3. 补充提醒：如有适用范围、时间节点或咨询建议，可简短补充
""".strip()


def build_answer_prompt(question: str, chat_history_text: str, context_text: str) -> str:
    question_type = classify_question_type(question)
    logger.info(f"🧭 问题类型识别：{question_type}")
    answer_template = build_answer_template(question_type)

    return f"""
你是【浙江科技大学专属校园智能问答助手】，回答必须符合浙科大校园场景。

请优先参考以下校园资料内容（不允许提及“检索/文档/RAG”等技术词）：
{context_text}

历史对话：
{chat_history_text}

用户问题：{question}

当前问题类型：{question_type}

回答模板：
{answer_template}

通用回答要求：
- 保持结构清晰，但语言自然，不要像公文
- 优先依据资料回答，不要脱离资料随意发挥
- 如果资料不支持某一项内容，可以省略该项，不要为了凑模板硬写
- 不知道的内容不要编造，直接说“抱歉，我暂时没有找到相关信息”
- 不要提及“检索/文档/RAG”等技术词
""".strip()


def rag_answer(question, session_id: str = "default") -> Tuple[str, List[str]]:
    question = _ensure_str(question)
    if vector_store is None:
        return "😅 助手还没初始化哦，请先上传校园文档或检查启动日志。", []

    history = SESSION_HISTORY.get(session_id, [])
    chat_history_text = format_history(history)

    rewritten_query = rewrite_query(question, history)
    original_docs = retrieve_docs_for_query(question)
    rewritten_docs = []
    if rewritten_query and rewritten_query != question:
        rewritten_docs = retrieve_docs_for_query(rewritten_query)

    docs = merge_docs(original_docs, rewritten_docs)
    context_text = format_docs_for_prompt(docs)
    prompt = build_answer_prompt(question, chat_history_text, context_text)

    answer = call_qwen(prompt, model_name="qwen-turbo", temperature=0.1)

    sources = []
    for doc in docs:
        sources.append(doc.metadata.get("source", "unknown"))

    history.append((question, answer))
    SESSION_HISTORY[session_id] = history[-MAX_SESSION_TURNS:]

    return answer, sources


# ===================== Gradio UI =====================
def create_gradio_ui():
    with gr.Blocks(title="浙科大校园智能问答助手 v2.2") as demo:
        gr.Markdown(
            """
# 🎓 浙科大校园智能问答助手 v2.2
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
            # 保持与 v1.0 / v2.0 / v2.1 一致的聊天数据结构
            chat_history = chat_history or []
            return "", chat_history + [{"role": "user", "content": question}]

        def bot_response_handler(chat_history):
            chat_history = chat_history or []
            if not chat_history:
                return chat_history

            # Find latest user message（content 可能是 str 或 list，统一转成 str）
            question = None
            for message in reversed(chat_history):
                if isinstance(message, dict) and message.get("role") == "user":
                    raw = message.get("content", "")
                    if isinstance(raw, list):
                        question = " ".join(
                            str(item) if not isinstance(item, dict) else item.get("text", str(item))
                            for item in raw
                        )
                    else:
                        question = str(raw).strip() if raw else ""
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

            vector_store = initialize_vector_store(force_rebuild=True)
            SESSION_HISTORY["default"] = []

            message_lines = [f"✅ 成功上传并保存 {saved} 个文档，校园知识库已更新！"]
            if rejected:
                message_lines.append(f"⚠️ 已跳过不支持的文件：{', '.join(rejected)}")
            return "\n".join(message_lines)

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
            SESSION_HISTORY["default"] = []
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
    logger.info("🚀 启动浙科大校园智能问答助手 v2.2 ...")

    vector_store = initialize_vector_store()

    demo = create_gradio_ui()
    demo.launch(
        theme=gr.themes.Soft(),
        share=False,
        server_name="127.0.0.1",
        server_port=7860,
        debug=True,
    )
