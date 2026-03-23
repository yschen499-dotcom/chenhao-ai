import hashlib
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from campus_assistant_v3.config import settings


logger = logging.getLogger(__name__)


def get_embeddings() -> DashScopeEmbeddings:
    return DashScopeEmbeddings(
        dashscope_api_key=settings.dashscope_api_key,
        model=settings.embedding_model,
    )


def compute_file_sha256(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with file_path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def build_docs_manifest(docs_dir: str = settings.docs_dir) -> List[Dict[str, Any]]:
    if not os.path.isdir(docs_dir):
        return []

    manifest: List[Dict[str, Any]] = []
    for file_path in sorted(Path(docs_dir).iterdir()):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in settings.supported_extensions:
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
    if not os.path.exists(settings.manifest_path):
        return None
    try:
        with open(settings.manifest_path, "r", encoding="utf-8") as file_obj:
            return json.load(file_obj)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(f"⚠️ 读取知识库清单失败，将重新构建知识库：{exc}")
        return None


def save_manifest(manifest: List[Dict[str, Any]]) -> None:
    os.makedirs(settings.persist_dir, exist_ok=True)
    with open(settings.manifest_path, "w", encoding="utf-8") as file_obj:
        json.dump(manifest, file_obj, ensure_ascii=False, indent=2)


def has_persisted_vector_store() -> bool:
    persist_path = Path(settings.persist_dir)
    if not persist_path.exists() or not persist_path.is_dir():
        return False
    return any(child.name != Path(settings.manifest_path).name for child in persist_path.iterdir())


def should_rebuild_vector_store(current_manifest: List[Dict[str, Any]]) -> bool:
    if not has_persisted_vector_store():
        return True
    return load_saved_manifest() != current_manifest


def reset_persist_directory(persist_dir: str = settings.persist_dir) -> None:
    if os.path.exists(persist_dir):
        shutil.rmtree(persist_dir)


def load_campus_docs(docs_dir: str = settings.docs_dir):
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
                docs.extend(PyPDFLoader(file_path).load())
                logger.info(f"✅ 加载校园PDF文档：{file_name}")
            elif lower.endswith(".txt") or lower.endswith(".md"):
                docs.extend(TextLoader(file_path, encoding="utf-8").load())
                logger.info(f"✅ 加载校园文档：{file_name}")
            else:
                logger.info(f"⚠️ 不支持的文件格式：{file_name}")
        except Exception as exc:
            logger.exception(f"❌ 加载文档 {file_name} 失败：{exc}")
    return docs


def create_vector_store(docs, persist_dir: str = settings.persist_dir, docs_manifest: Optional[List[Dict[str, Any]]] = None):
    embeddings = get_embeddings()
    reset_persist_directory(persist_dir)

    if not docs:
        logger.warning("⚠️ 没有加载到校园文档，将创建空的知识库（可先上传文档后再更新）")
        vector_store = Chroma(embedding_function=embeddings, persist_directory=persist_dir)
        save_manifest(docs_manifest or [])
        logger.info("✅ 空的校园知识库创建成功")
        return vector_store

    split_docs = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_documents(docs)
    vector_store = Chroma.from_documents(
        documents=split_docs,
        embedding=embeddings,
        persist_directory=persist_dir,
    )
    save_manifest(docs_manifest or [])
    logger.info(f"✅ 校园知识库创建成功，共存储 {len(split_docs)} 个文档片段")
    return vector_store


def load_existing_vector_store(persist_dir: str = settings.persist_dir) -> Chroma:
    logger.info("✅ 检测到文档未变化，直接加载已有知识库，跳过重复 embedding")
    return Chroma(
        embedding_function=get_embeddings(),
        persist_directory=persist_dir,
    )


def initialize_vector_store(force_rebuild: bool = False) -> Chroma:
    current_manifest = build_docs_manifest(settings.docs_dir)
    if not force_rebuild and not should_rebuild_vector_store(current_manifest):
        return load_existing_vector_store()

    docs = load_campus_docs(settings.docs_dir)
    refreshed_manifest = build_docs_manifest(settings.docs_dir)
    return create_vector_store(docs, docs_manifest=refreshed_manifest)
