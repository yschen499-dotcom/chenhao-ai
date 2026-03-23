import logging
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Tuple

from campus_assistant_v3.config import settings
from campus_assistant_v3.knowledge_base import initialize_vector_store


logger = logging.getLogger(__name__)


def build_safe_upload_filename(filename: str) -> str:
    original_name = os.path.basename(filename or "uploaded_file")
    suffix = Path(original_name).suffix.lower()
    if suffix not in settings.supported_extensions:
        raise ValueError(f"不支持的文件类型：{suffix or '无扩展名'}")

    stem = Path(original_name).stem
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    if not safe_stem:
        safe_stem = "campus_doc"
    return f"{safe_stem[:40]}_{uuid.uuid4().hex[:8]}{suffix}"


def handle_upload(files) -> Tuple[str, object]:
    if not files:
        return "请先选择要上传的校园文档", None

    os.makedirs(settings.docs_dir, exist_ok=True)
    saved = 0
    rejected = []

    for file_obj in files:
        src_path = getattr(file_obj, "path", None) or getattr(file_obj, "name", None)
        orig_name = getattr(file_obj, "orig_name", None) or os.path.basename(str(src_path or "uploaded_file"))
        if not src_path or not os.path.exists(src_path):
            continue

        try:
            safe_name = build_safe_upload_filename(orig_name)
            dst_path = os.path.join(settings.docs_dir, safe_name)
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
            return f"未保存任何文件，仅支持：{', '.join(sorted(settings.supported_extensions))}", None
        return "未保存任何文件，请检查上传文件后重试", None

    vector_store = initialize_vector_store(force_rebuild=True)

    message_lines = [f"✅ 成功上传并保存 {saved} 个文档，校园知识库已更新！"]
    if rejected:
        message_lines.append(f"⚠️ 已跳过不支持的文件：{', '.join(rejected)}")
    return "\n".join(message_lines), vector_store
