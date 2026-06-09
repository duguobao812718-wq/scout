"""
语义搜索模块。

使用 Sentence Transformers + FAISS 进行语义搜索。
参考：free-search-mcp 的语义搜索设计。
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("scout.semantic")


class SemanticIndex:
    """语义搜索索引。

    特性：
    - 懒加载模型（首次使用时加载）
    - FAISS 索引持久化
    - 与缓存层集成
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model = None
        self._index = None
        self._documents: list[dict[str, Any]] = []
        self._dimension = 384  # all-MiniLM-L6-v2 的维度

    def _load_model(self):
        """懒加载模型。"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name)
                logger.info("语义模型已加载: %s", self._model_name)
            except ImportError:
                logger.warning("sentence-transformers 未安装")
                raise

    def _ensure_index(self):
        """确保 FAISS 索引存在。"""
        if self._index is None:
            try:
                import faiss
                self._index = faiss.IndexFlatIP(self._dimension)  # 内积相似度
            except ImportError:
                logger.warning("faiss-cpu 未安装")
                raise

    async def add(self, url: str, title: str, content: str) -> None:
        """添加文档到索引。"""
        await asyncio.to_thread(self._add_sync, url, title, content)

    def _add_sync(self, url: str, title: str, content: str) -> None:
        """同步添加文档。"""
        self._load_model()
        self._ensure_index()

        # 组合文本
        text = f"{title}\n{content[:1000]}"  # 限制长度

        # 编码
        embedding = self._model.encode([text], normalize_embeddings=True)

        # 添加到索引
        import faiss
        import numpy as np
        self._index.add(embedding.astype(np.float32))

        # 保存文档信息
        self._documents.append({
            "url": url,
            "title": title,
            "content": content[:500],  # 限制存储长度
        })

    async def search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """语义搜索。"""
        return await asyncio.to_thread(self._search_sync, query, top_k)

    def _search_sync(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """同步语义搜索。"""
        if self._index is None or len(self._documents) == 0:
            return []

        self._load_model()

        # 编码查询
        import numpy as np
        query_embedding = self._model.encode([query], normalize_embeddings=True).astype(np.float32)

        # 搜索
        k = min(top_k, len(self._documents))
        scores, indices = self._index.search(query_embedding, k)

        # 构建结果
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self._documents):
                doc = self._documents[idx].copy()
                doc["score"] = float(score)
                results.append(doc)

        return results

    async def save(self, path: str) -> None:
        """保存索引到文件。"""
        await asyncio.to_thread(self._save_sync, path)

    def _save_sync(self, path: str) -> None:
        """同步保存索引。"""
        if self._index is None:
            return

        import faiss
        import json

        # 保存 FAISS 索引
        faiss.write_index(self._index, f"{path}.faiss")

        # 保存文档信息
        with open(f"{path}.json", "w", encoding="utf-8") as f:
            json.dump(self._documents, f, ensure_ascii=False, indent=2)

        logger.info("语义索引已保存: %s", path)

    async def load(self, path: str) -> None:
        """从文件加载索引。"""
        await asyncio.to_thread(self._load_sync, path)

    def _load_sync(self, path: str) -> None:
        """同步加载索引。"""
        import faiss
        import json

        faiss_path = f"{path}.faiss"
        json_path = f"{path}.json"

        # 加载 FAISS 索引
        self._index = faiss.read_index(faiss_path)

        # 加载文档信息
        with open(json_path, "r", encoding="utf-8") as f:
            self._documents = json.load(f)

        logger.info("语义索引已加载: %s（%d 个文档）", path, len(self._documents))


# 全局语义索引实例
semantic_index = SemanticIndex()
