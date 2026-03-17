import logging

import gradio as gr

from campus_assistant_v3.assistant_service import CampusAssistantService
from campus_assistant_v3.config import settings
from campus_assistant_v3.llm import ensure_str, initialize_dashscope


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - [浙科大校园助手] - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )


logger = logging.getLogger(__name__)


def create_gradio_ui(service: CampusAssistantService):
    with gr.Blocks(title=settings.app_title) as demo:
        gr.Markdown(
            f"""
# 🎓 {settings.app_title}
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
            return "", chat_history + [{"role": "user", "content": question}]

        def bot_response_handler(chat_history):
            chat_history = chat_history or []
            if not chat_history:
                return chat_history

            question = None
            for message in reversed(chat_history):
                if isinstance(message, dict) and message.get("role") == "user":
                    question = ensure_str(message.get("content", ""))
                    break
            if not question:
                return chat_history

            try:
                answer, sources = service.answer_question(question, session_id="default")
                logger.info(f"🔍 回答来源文档：{sources}")
                return chat_history + [{"role": "assistant", "content": answer}]
            except Exception as exc:
                logger.exception("❌ 回答失败（这里会打印完整堆栈）")
                return chat_history + [{"role": "assistant", "content": f"😔 回答失败：{str(exc)}"}]

        def upload_docs_handler(files):
            return service.refresh_knowledge_base(files)

        def clear_all():
            service.clear_session("default")
            return []

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

        clear_btn.click(clear_all, None, chatbot, queue=False)
        upload_btn.click(upload_docs_handler, inputs=[file_upload], outputs=[upload_status])

    return demo


def main():
    setup_logging()
    initialize_dashscope()
    logger.info("🚀 启动浙科大校园智能问答助手 v3.0-A ...")

    service = CampusAssistantService()
    service.initialize()

    demo = create_gradio_ui(service)
    demo.launch(
        theme=gr.themes.Soft(),
        share=False,
        server_name=settings.server_name,
        server_port=settings.server_port,
        debug=settings.debug,
    )


if __name__ == "__main__":
    main()
