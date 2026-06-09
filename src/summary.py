"""
结果摘要辅助模块。

为 AI Agent 提供结构化的多源内容摘要素材：
- 关键信息提取（从页面内容中提取要点）
- 可信度评估（基于来源多样性、域名信誉等）
- 多源对比格式化
"""

from __future__ import annotations

import re
from typing import Any


def extract_key_points(content: str, max_points: int = 5) -> list[str]:
    """从页面内容中提取关键要点。

    使用启发式方法：
    - 优先提取包含数字/统计数据的句子
    - 优先提取包含关键词的句子（定义、原因、结论）
    - 去除过短或过长的句子
    """
    if not content:
        return []

    # 按句子分割
    sentences = re.split(r'[。.!！?？\n]+', content)
    sentences = [s.strip() for s in sentences if s.strip()]

    scored: list[tuple[float, str]] = []

    for sentence in sentences:
        if len(sentence) < 10 or len(sentence) > 300:
            continue

        score = 0.0

        # 包含数字/统计数据的句子更重要
        if re.search(r'\d+\.?\d*\s*(%|万|亿|千|百|million|billion|thousand)', sentence):
            score += 0.3
        elif re.search(r'\d{4}[-/]\d{2}', sentence):  # 日期
            score += 0.1

        # 包含定义/解释关键词
        definition_words = ['是', '指', 'means', 'defined', 'refers to', 'consists of']
        if any(w in sentence.lower() for w in definition_words):
            score += 0.2

        # 包含因果/结论关键词
        conclusion_words = ['因此', '所以', '导致', '表明', '证明', 'therefore', 'thus', 'shows', 'indicates', 'proves']
        if any(w in sentence.lower() for w in conclusion_words):
            score += 0.2

        # 包含重要性标记
        importance_words = ['重要', '关键', '主要', '核心', 'essential', 'important', 'key', 'main', 'critical']
        if any(w in sentence.lower() for w in importance_words):
            score += 0.15

        # 句子长度适中加分
        if 20 <= len(sentence) <= 150:
            score += 0.1

        scored.append((score, sentence))

    # 按分数排序，取 top N
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:max_points]]


def compute_credibility(
    sources: list[dict[str, Any]],
    domain_scores: dict[str, float] | None = None,
) -> dict[str, Any]:
    """评估搜索结果的可信度。

    因素：
    - 来源数量：更多来源 = 更可信
    - 来源多样性：不同域名 = 更可信
    - 域名信誉：白名单域名加分
    - 内容一致性：多个来源提到相同信息 = 更可信

    Returns:
        {
            "score": float,  # 0.0 ~ 1.0
            "level": str,    # "high" / "medium" / "low"
            "factors": dict, # 各因素详情
        }
    """
    if not sources:
        return {"score": 0.0, "level": "low", "factors": {"reason": "no sources"}}

    factors: dict[str, Any] = {}

    # 1. 来源数量 (0.0 ~ 0.3)
    source_count = len(sources)
    count_score = min(0.3, source_count * 0.1)
    factors["source_count"] = source_count

    # 2. 来源多样性 (0.0 ~ 0.3)
    from urllib.parse import urlparse
    unique_domains = set()
    for s in sources:
        try:
            host = urlparse(s.get("url", "")).hostname or ""
            if host.startswith("www."):
                host = host[4:]
            unique_domains.add(host)
        except Exception:
            pass
    diversity_score = min(0.3, len(unique_domains) * 0.1)
    factors["unique_domains"] = len(unique_domains)

    # 3. 域名信誉 (0.0 ~ 0.3)
    from .scoring import domain_reputation_score
    reputation_scores = []
    for s in sources:
        url = s.get("url", "")
        rep = domain_reputation_score(url)
        reputation_scores.append(rep)
    avg_reputation = sum(reputation_scores) / len(reputation_scores) if reputation_scores else 0.0
    reputation_score = max(0.0, min(0.3, 0.15 + avg_reputation))  # 基线 0.15
    factors["avg_domain_reputation"] = round(avg_reputation, 3)

    # 4. 多引擎验证 (0.0 ~ 0.1)
    multi_engine_count = sum(1 for s in sources if len(s.get("engines", [])) > 1)
    multi_engine_score = min(0.1, multi_engine_count * 0.05)
    factors["multi_engine_sources"] = multi_engine_count

    # 综合分数
    total = count_score + diversity_score + reputation_score + multi_engine_score
    total = max(0.0, min(1.0, total))

    # 等级
    if total >= 0.7:
        level = "high"
    elif total >= 0.4:
        level = "medium"
    else:
        level = "low"

    return {
        "score": round(total, 3),
        "level": level,
        "factors": factors,
    }


def format_summary_for_agent(
    question: str,
    sources: list[dict[str, Any]],
    documents: list[dict[str, Any]] | None = None,
) -> str:
    """格式化摘要素材供 AI Agent 使用。

    返回结构化的 Markdown，包含：
    - 问题
    - 来源列表（带可信度）
    - 各来源的关键要点
    - 综合可信度评估
    """
    lines = [f"# 摘要素材: {question}", ""]

    # 可信度评估
    credibility = compute_credibility(sources)
    lines.append(f"## 可信度评估")
    lines.append(f"- 综合评分: **{credibility['score']:.2f}** ({credibility['level']})")
    factors = credibility["factors"]
    lines.append(f"- 来源数: {factors.get('source_count', 0)}")
    lines.append(f"- 独立域名: {factors.get('unique_domains', 0)}")
    lines.append(f"- 多引擎验证: {factors.get('multi_engine_sources', 0)}")
    lines.append("")

    # 来源列表
    lines.append("## 来源列表")
    for i, s in enumerate(sources, 1):
        title = s.get("title", "(无标题)")
        url = s.get("url", "")
        engines = s.get("engines", [])
        lines.append(f"{i}. **{title}**")
        lines.append(f"   <{url}>")
        if engines:
            lines.append(f"   引擎: {', '.join(engines)}")
    lines.append("")

    # 各来源关键要点
    if documents:
        lines.append("## 关键要点")
        for doc in documents:
            title = doc.get("title", "(无标题)")
            content = doc.get("content", "")
            points = extract_key_points(content)
            if points:
                lines.append(f"### {title}")
                for point in points:
                    lines.append(f"- {point}")
                lines.append("")

    return "\n".join(lines)
