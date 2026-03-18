from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt


OUTPUT_PATH = Path("/workspace/thesis/zust_undergraduate_thesis_template.docx")


def set_run_font(run, size=12, bold=False):
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    run.font.size = Pt(size)
    run.bold = bold


def add_paragraph(document, text="", size=12, bold=False, align=WD_ALIGN_PARAGRAPH.LEFT):
    paragraph = document.add_paragraph()
    paragraph.alignment = align
    run = paragraph.add_run(text)
    set_run_font(run, size=size, bold=bold)
    return paragraph


def add_heading(document, text, level=1):
    paragraph = document.add_paragraph()
    run = paragraph.add_run(text)
    set_run_font(run, size=16 if level == 1 else 14 if level == 2 else 12, bold=True)
    return paragraph


def add_placeholder_paragraph(document, text):
    paragraph = document.add_paragraph()
    run = paragraph.add_run(text)
    set_run_font(run, size=12, bold=False)
    return paragraph


def build_cover(document):
    for _ in range(4):
        add_paragraph(document, "")
    add_paragraph(document, "浙江科技学院计算机学院", size=16, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_paragraph(document, "本科生毕业设计（论文）", size=18, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_paragraph(document, "")
    add_paragraph(document, "论文题目：校园智能问答助手设计与实现", size=16, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_paragraph(document, "")
    add_paragraph(document, "学生姓名：__________", size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_paragraph(document, "学    号：__________", size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_paragraph(document, "专    业：计算机科学与技术", size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_paragraph(document, "指导教师：__________", size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_paragraph(document, "完成日期：____年__月", size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    document.add_page_break()


def build_abstract_pages(document):
    add_heading(document, "中文摘要", level=1)
    add_placeholder_paragraph(
        document,
        "【摘要撰写提示】中文摘要一般不超过300字，应概括课题背景、研究内容、实现方法、主要成果与结论，不写公式、图表和参考文献编号。",
    )
    add_placeholder_paragraph(
        document,
        "【摘要占位】本课题面向浙江科技学院校园服务场景，设计并实现了一套基于大模型与本地知识库的校园智能问答助手。系统围绕校园问答中信息分散、检索效率不足和回答自然度不高等问题，完成了知识库构建、查询改写、检索增强、结构化回答与模块化重构等核心功能设计。实验结果表明，该系统能够在图书馆开放时间、学籍管理、奖学金申请等典型校园问题上提供较为准确、自然且具有一定上下文理解能力的回答。该研究为校园服务智能化提供了一种可行实现方案。",
    )
    add_placeholder_paragraph(document, "关键词：校园问答助手；大语言模型；知识库问答；查询改写；模块化设计")
    document.add_page_break()

    add_heading(document, "Abstract", level=1)
    add_placeholder_paragraph(
        document,
        "[Abstract Notes] The English abstract should be consistent with the Chinese abstract in meaning. Keep it concise, independent, and complete.",
    )
    add_placeholder_paragraph(
        document,
        "[Abstract Placeholder] This thesis designs and implements a campus intelligent question-answering assistant based on a large language model and a local knowledge base for campus service scenarios. The system addresses problems such as scattered information, insufficient retrieval efficiency, and weak answer naturalness in campus Q&A. It integrates knowledge base construction, query rewriting, retrieval enhancement, structured response generation, and modular refactoring. Experimental results show that the system can provide relatively accurate, natural, and context-aware answers for typical campus questions such as library opening hours, academic status management, and scholarship applications. This study provides a feasible solution for the intelligent upgrade of campus services.",
    )
    add_placeholder_paragraph(document, "Keywords: campus question answering; large language model; knowledge base QA; query rewriting; modular design")
    document.add_page_break()


def build_toc_page(document):
    add_heading(document, "目录", level=1)
    add_placeholder_paragraph(
        document,
        "【目录生成提示】请在 Word 中使用“引用 -> 目录 -> 自动目录”生成，不要手工输入页码。目录应至少包含：中英文摘要、各章标题（最多到第三级标题）、致谢、参考文献、附录。",
    )
    add_placeholder_paragraph(document, "摘要")
    add_placeholder_paragraph(document, "Abstract")
    add_placeholder_paragraph(document, "第1章 引言")
    add_placeholder_paragraph(document, "第2章 相关技术与理论基础")
    add_placeholder_paragraph(document, "第3章 需求分析")
    add_placeholder_paragraph(document, "第4章 系统总体设计")
    add_placeholder_paragraph(document, "第5章 系统详细设计与实现")
    add_placeholder_paragraph(document, "第6章 系统测试与结果分析")
    add_placeholder_paragraph(document, "第7章 结束语")
    add_placeholder_paragraph(document, "致谢")
    add_placeholder_paragraph(document, "参考文献")
    add_placeholder_paragraph(document, "附录1")
    document.add_page_break()


def build_body(document):
    chapters = [
        (
            "第1章 引言",
            [
                "1.1 选题背景与研究意义",
                "1.2 国内外研究现状",
                "1.3 研究内容与目标",
                "1.4 论文结构安排",
            ],
        ),
        (
            "第2章 相关技术与理论基础",
            [
                "2.1 大语言模型技术概述",
                "2.2 知识库问答相关技术",
                "2.3 向量数据库与文本切分技术",
                "2.4 Web交互与系统开发框架",
            ],
        ),
        (
            "第3章 需求分析",
            [
                "3.1 系统建设目标",
                "3.2 功能需求分析",
                "3.3 非功能需求分析",
                "3.4 可行性分析",
            ],
        ),
        (
            "第4章 系统总体设计",
            [
                "4.1 系统架构设计",
                "4.2 功能模块设计",
                "4.3 数据流程设计",
                "4.4 数据存储与知识库设计",
            ],
        ),
        (
            "第5章 系统详细设计与实现",
            [
                "5.1 知识库构建模块实现",
                "5.2 查询改写模块实现",
                "5.3 检索增强模块实现",
                "5.4 自然化回答生成模块实现",
                "5.5 系统模块化重构实现",
            ],
        ),
        (
            "第6章 系统测试与结果分析",
            [
                "6.1 测试环境与测试方法",
                "6.2 功能测试",
                "6.3 典型问答效果分析",
                "6.4 系统存在的问题与分析",
            ],
        ),
        (
            "第7章 结束语",
            [
                "7.1 研究工作总结",
                "7.2 创新点与特色",
                "7.3 不足与后续展望",
            ],
        ),
    ]

    for chapter_title, sections in chapters:
        add_heading(document, chapter_title, level=1)
        add_placeholder_paragraph(
            document,
            "【写作提示】本章应围绕章标题展开，段落通顺，重点突出。章标题建议另起一页，标题不要使用标点符号。",
        )
        for section_title in sections:
            add_heading(document, section_title, level=2)
            add_placeholder_paragraph(document, "【内容占位】请在此补充本节正文内容。写作时可根据需要扩展至第三级标题（如 1.1.1），不建议超过第三级标题。")
        document.add_page_break()


def build_acknowledgement(document):
    add_heading(document, "致谢", level=1)
    add_placeholder_paragraph(
        document,
        "【致谢占位】感谢指导教师在课题选题、系统设计、论文撰写与修改过程中给予的悉心指导；感谢学院老师在毕业设计过程中提供的帮助；感谢同学与家人在研究和学习过程中给予的支持与鼓励。",
    )
    document.add_page_break()


def build_references(document):
    add_heading(document, "参考文献", level=1)
    add_placeholder_paragraph(
        document,
        "【参考文献要求】一般不少于10篇，其中外文文献不少于2篇。正文中必须使用上标形式引用文献编号，参考文献格式应符合 GB7714—1987 的书写规范。",
    )
    sample_references = [
        "[1] Lewis P, Perez E, Piktus A, et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks[J]. Advances in Neural Information Processing Systems, 2020, 33: 9459-9474.",
        "[2] Zhao W X, Zhou K, Li J, et al. A Survey of Large Language Models[EB/OL]. https://arxiv.org/abs/2303.18223, 2023.",
        "[3] 刘洋, 张伟. 基于大模型的智能问答系统研究[J]. 计算机工程与应用, 2024, 60(8): 15-24.",
        "[4] 陈某某. 智能问答系统设计与实现[D]. 杭州: 某高校, 2023.",
    ]
    for reference in sample_references:
        add_placeholder_paragraph(document, reference)
    document.add_page_break()


def build_appendices(document):
    add_heading(document, "附录1", level=1)
    add_placeholder_paragraph(document, "【附录占位】可放系统关键代码、流程图、数据表、测试用例截图等内容。")
    document.add_page_break()

    add_heading(document, "附录2", level=1)
    add_placeholder_paragraph(document, "【附录占位】如无第二个附录，可删除本页。")


def main():
    document = Document()
    build_cover(document)
    build_abstract_pages(document)
    build_toc_page(document)
    build_body(document)
    build_acknowledgement(document)
    build_references(document)
    build_appendices(document)
    document.save(OUTPUT_PATH)
    print(f"Generated: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
