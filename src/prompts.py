"""
MCP 提示词模板。

为 AI Agent 提供常用的搜索和研究提示词。
参考：free-search-mcp 的 prompts.py 实现。
"""

from __future__ import annotations


def research_prompt(question: str, depth: int = 3) -> str:
    """研究提示词：指导模型进行深入研究。"""
    return (
        f"You have access to the Scout search tools. Research the following "
        f"question thoroughly and produce a well-cited answer.\n\n"
        f"QUESTION: {question}\n\n"
        f"PROCEDURE:\n"
        f"1. Call the `research` tool with question={question!r} and depth={depth}.\n"
        f"2. Read each fetched source. If a source seems unreliable, call "
        f"`search` for a corroborating source.\n"
        f"3. If any document was truncated, call `fetch` again with that URL.\n"
        f"4. Write a synthesis (3-8 paragraphs) that:\n"
        f"   - Answers the question directly in the first sentence.\n"
        f"   - Cites sources inline using [1], [2], ... markers that match the\n"
        f"     order returned by `research`.\n"
        f"   - Notes any disagreement between sources.\n"
        f"   - Lists the full source URLs at the end under a 'Sources' header.\n"
        f"5. If you could not find a confident answer, say so explicitly and\n"
        f"   show what was checked."
    )


def factcheck_prompt(claim: str) -> str:
    """事实核查提示词：指导模型验证声明。"""
    return (
        f"Fact-check the following claim using the Scout tools.\n\n"
        f"CLAIM: {claim}\n\n"
        f"PROCEDURE:\n"
        f"1. Call `search` with a focused query (key entities + date if any).\n"
        f"2. Call `fetch` on the 3-5 most authoritative-looking URLs.\n"
        f"3. For each source, quote the supporting or contradicting passage.\n"
        f"4. Output a verdict on a 5-point scale: TRUE / MOSTLY TRUE / MIXED /\n"
        f"   MOSTLY FALSE / FALSE, followed by a one-paragraph justification\n"
        f"   with [n]-style citations matching the source order.\n"
        f"5. End with a 'Sources' list of URLs.\n"
        f"6. If sources disagree, surface that explicitly rather than picking\n"
        f"   one side silently."
    )


def compare_sources(question: str, urls: str | list[str]) -> str:
    """比较来源提示词：指导模型比较多个来源。

    Args:
        question: 要回答的问题。
        urls: URL 列表，可以是逗号分隔的字符串或 list。
    """
    if isinstance(urls, str):
        urls_list = [u.strip() for u in urls.split(",") if u.strip()]
    else:
        urls_list = urls
    urls_str = ", ".join(urls_list)
    return (
        f"Use the `fetch` tool to read the following URLs: {urls_str}\n\n"
        f"Then answer the question with [n] citations to the URL it came from.\n"
        f"QUESTION: {question}\n\n"
        f"If the excerpts disagree, surface that explicitly rather than "
        f"picking one side silently."
    )


def news_brief(topic: str, since: str = "day") -> str:
    """新闻简报提示词：指导模型生成新闻摘要。"""
    return (
        f"Use the `search` tool with query={topic!r}, freshness={since!r}.\n"
        f"Then fetch the top 3 results via `fetch`.\n"
        f"Produce a 5-bullet brief, with [n] citations "
        f"matching the order returned by `search`.\n"
        f"End with a 'Sources' list of URLs."
    )
