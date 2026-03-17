def build_query_rewrite_prompt(question: str, history_text: str) -> str:
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


def build_answer_style_prompt(question_type: str, natural_style_enabled: bool) -> str:
    if not natural_style_enabled:
        if question_type == "process":
            return "请先回答办理结论，再补充流程、条件或材料，以及必要提醒。"
        if question_type == "policy":
            return "请先回答规则结论，再补充适用情况、关键要求和注意事项。"
        if question_type == "fact":
            return "请先直接回答事实信息，再补充必要说明或提醒。"
        return "请先回答核心结论，再补充最关键的信息点。"

    if question_type == "process":
        return """
请把答案组织得清晰自然，像校园老师或办事老师在耐心说明，而不是在写模板。
- 先用1-2句话直接告诉用户能不能办、怎么做最关键
- 再按自然顺序补充1-3个关键步骤或要求
- 只有信息较多时才使用简短条目，不要机械写“1.2.3.”
- 如有材料、时间节点或负责部门，再顺势补充一句提醒
""".strip()

    if question_type == "policy":
        return """
请把答案组织得清晰自然，像校园规则说明，而不是公文条款复述。
- 先直接说清规则核心或结论
- 再自然补充适用情况、关键要求或限制条件
- 如果规则点较多，可以用短条目列出，但不要每次都强行分标题
- 结尾可简短提醒特殊情况或建议咨询相关部门
""".strip()

    if question_type == "fact":
        return """
请把答案说得直接、简洁、自然。
- 开头直接给出时间、地点、电话或事实答案
- 如有必要，再补一句特殊情况、例外说明或最新通知提醒
- 这类问题一般不需要分很多段，也不要为了完整性硬凑结构
""".strip()

    return """
请把答案组织得自然、清晰、有条理。
- 先直接回答核心问题
- 再补充2-3个最关键的信息点
- 只有在信息确实较多时才使用条目，不要机械套模板
""".strip()
