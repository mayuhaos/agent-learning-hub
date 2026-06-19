import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import requests
from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams


# Learn 1 的目标：
# 跑通 RAG 的完整链路：
# 1. chunk：把本地文档切成文本块
# 2. embed：用 BGE-M3 把文本块转成向量
# 3. retrieve：用 Qdrant 检索和用户问题最相关的文本块
# 4. answer with citations：让模型基于检索结果回答，并给出来源
#
# 本节不做 tool calling、不做 memory、不做 agent loop。
# 这样学习者可以先把 RAG 的每一步看清楚。


# 每个 chunk 的最大字符数。
# 教学示例先用固定长度切分，便于理解。
# 真实项目通常还会结合标题、段落、Markdown 结构和重叠窗口来切分。
CHUNK_SIZE = 450

# 相邻 chunk 的重叠字符数。
# 重叠可以降低“答案刚好被切断在两个 chunk 中间”的概率。
CHUNK_OVERLAP = 80

# 从 Qdrant 检索多少个最相关的 chunk。
TOP_K = 4

# 低于这个分数的结果会被认为相关性不足。
# Qdrant 使用 cosine 距离时，score 越高通常代表越相似。
MIN_SCORE = 0.25


@dataclass
class Chunk:
    """一个可被向量化和检索的文本块。"""

    source: str
    chunk_id: int
    text: str


@dataclass
class RetrievedChunk:
    """从 Qdrant 检索回来的文本块。"""

    source: str
    chunk_id: int
    text: str
    score: float


def load_config() -> dict:
    """读取 Stage 2 共享的 .env 配置。"""
    stage_dir = Path(__file__).resolve().parents[1]
    load_dotenv(stage_dir / ".env")

    return {
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "openai_base_url": os.getenv("OPENAI_BASE_URL"),
        "openai_model": os.getenv("OPENAI_MODEL", "gpt-5.5"),
        "embedding_base_url": os.getenv("EMBEDDING_BASE_URL", "http://localhost:8080").rstrip("/"),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"),
        "qdrant_url": os.getenv("QDRANT_URL", "http://localhost:6333"),
        "qdrant_collection": os.getenv("QDRANT_COLLECTION", "stage2_learn1_rag"),
    }


def check_embedding_service(base_url: str) -> None:
    """检查 BGE-M3 embedding 服务是否可用。"""
    health_url = f"{base_url}/health"
    try:
        response = requests.get(health_url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            "BGE-M3 embedding 服务不可用。请先运行："
            "docker run -p 8080:8080 beloved70020/bge-m3"
        ) from exc

    data = response.json()
    if data.get("status") != "ok":
        raise RuntimeError(f"BGE-M3 health check 返回异常：{data}")


def check_qdrant(client: QdrantClient) -> None:
    """检查 Qdrant 是否可连接。"""
    try:
        client.get_collections()
    except Exception as exc:
        raise RuntimeError(
            "Qdrant 服务不可用。请先运行："
            "docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant"
        ) from exc


def load_markdown_documents(docs_dir: Path) -> list[tuple[str, str]]:
    """读取 docs 目录下的 Markdown 文档。"""
    documents = []
    for path in sorted(docs_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if text:
            documents.append((path.name, text))

    if not documents:
        raise RuntimeError(f"没有在 {docs_dir} 找到可用的 Markdown 文档。")

    return documents


def chunk_text(source: str, text: str) -> list[Chunk]:
    """把一篇文档切成多个 chunk。"""
    chunks = []
    start = 0
    chunk_id = 1

    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(Chunk(source=source, chunk_id=chunk_id, text=chunk))
            chunk_id += 1

        # 如果已经到文档末尾，就停止。
        if end == len(text):
            break

        # 下一段从 end - overlap 开始，保留一点上下文。
        start = max(0, end - CHUNK_OVERLAP)

    return chunks


def build_chunks(documents: list[tuple[str, str]]) -> list[Chunk]:
    """把多篇文档统一切成 chunk 列表。"""
    all_chunks = []
    for source, text in documents:
        all_chunks.extend(chunk_text(source, text))
    return all_chunks


def embed_texts(base_url: str, model: str, texts: list[str]) -> list[list[float]]:
    """调用本地 BGE-M3 服务，把文本列表转换成向量列表。"""
    if not texts:
        return []

    response = requests.post(
        f"{base_url}/v1/embeddings",
        headers={"Content-Type": "application/json"},
        json={
            "model": model,
            "input": texts,
        },
        timeout=120,
    )
    response.raise_for_status()

    data = response.json()
    embeddings = [item["embedding"] for item in sorted(data["data"], key=lambda item: item["index"])]

    if len(embeddings) != len(texts):
        raise RuntimeError("Embedding 返回数量和输入文本数量不一致。")

    return embeddings


def recreate_collection(client: QdrantClient, collection_name: str, vector_size: int) -> None:
    """每次运行都重建 collection，让课堂演示结果稳定。

    这里不用“自动 upsert 到旧 collection”的方式，是因为课堂演示更需要稳定：
    每次运行都从同一批 docs 重新建库，检索结果不会被上一次实验污染。
    """
    if client.collection_exists(collection_name=collection_name):
        client.delete_collection(collection_name=collection_name)

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE,
        ),
    )


def upsert_chunks(
    client: QdrantClient,
    collection_name: str,
    chunks: list[Chunk],
    vectors: list[list[float]],
) -> None:
    """把 chunk 向量和 payload 写入 Qdrant。"""
    points = []

    for chunk, vector in zip(chunks, vectors, strict=True):
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "source": chunk.source,
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                },
            )
        )

    client.upsert(collection_name=collection_name, points=points)


def retrieve(
    client: QdrantClient,
    collection_name: str,
    query_vector: list[float],
    top_k: int = TOP_K,
) -> list[RetrievedChunk]:
    """用用户问题的向量，从 Qdrant 检索最相关的 chunk。"""
    response = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=top_k,
        with_payload=True,
        score_threshold=MIN_SCORE,
    )

    retrieved = []
    for result in response.points:
        payload = result.payload or {}
        retrieved.append(
            RetrievedChunk(
                source=str(payload.get("source", "unknown")),
                chunk_id=int(payload.get("chunk_id", 0)),
                text=str(payload.get("text", "")),
                score=float(result.score),
            )
        )

    return retrieved


def format_context(chunks: list[RetrievedChunk]) -> str:
    """把检索结果整理成模型容易阅读、也容易引用的上下文。"""
    if not chunks:
        return "没有检索到足够相关的资料。"

    parts = []
    for index, chunk in enumerate(chunks, start=1):
        parts.append(
            "\n".join(
                [
                    f"证据 {index}",
                    f"source: {chunk.source}",
                    f"chunk: {chunk.chunk_id}",
                    f"score: {chunk.score:.4f}",
                    "text:",
                    chunk.text,
                ]
            )
        )

    return "\n\n---\n\n".join(parts)


def answer_with_citations(
    client: OpenAI,
    model: str,
    question: str,
    retrieved_chunks: list[RetrievedChunk],
) -> str:
    """让 LLM 基于检索结果回答，并要求它给出 citation。"""
    context = format_context(retrieved_chunks)

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "developer",
                "content": (
                    "你是一个严谨的中文 RAG 助手。"
                    "你只能根据用户提供的检索资料回答问题。"
                    "如果资料不足，请回答：根据当前资料不足以回答这个问题。"
                    "回答中必须使用引用格式：[source: 文件名, chunk: 编号]。"
                    "引用只能来自检索资料里的 source 和 chunk 字段，不要编造引用。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"用户问题：\n{question}\n\n"
                    f"检索资料：\n{context}\n\n"
                    "请基于检索资料回答，并附上 citation。"
                ),
            },
        ],
    )

    return response.output_text


def print_retrieved_chunks(chunks: list[RetrievedChunk]) -> None:
    """把检索命中结果打印出来，方便课堂上观察 retrieve 发生了什么。"""
    if not chunks:
        print("没有检索到超过相关性阈值的 chunk。")
        return

    for index, chunk in enumerate(chunks, start=1):
        print(f"{index}. score={chunk.score:.4f} source={chunk.source} chunk={chunk.chunk_id}")
        preview = chunk.text.replace("\n", " ")
        print(f"   {preview[:120]}...")


def main() -> None:
    config = load_config()

    lesson_dir = Path(__file__).resolve().parent
    docs_dir = lesson_dir / "docs"

    llm_client = OpenAI(
        api_key=config["openai_api_key"],
        base_url=config["openai_base_url"] or None,
    )
    qdrant = QdrantClient(url=config["qdrant_url"])

    print("Stage 2 Learn 1: RAG with Qdrant + BGE-M3")
    print("本节会执行：chunk -> embed -> retrieve -> answer with citations")

    print("\n1. 检查 BGE-M3 embedding 服务...")
    check_embedding_service(config["embedding_base_url"])
    print("BGE-M3 服务可用。")

    print("\n2. 检查 Qdrant 服务...")
    check_qdrant(qdrant)
    print("Qdrant 服务可用。")

    print("\n3. 读取并切分本地文档...")
    documents = load_markdown_documents(docs_dir)
    chunks = build_chunks(documents)
    print(f"读取文档数量：{len(documents)}")
    print(f"生成 chunk 数量：{len(chunks)}")

    print("\n4. 调用 BGE-M3 生成 chunk 向量...")
    chunk_vectors = embed_texts(
        base_url=config["embedding_base_url"],
        model=config["embedding_model"],
        texts=[chunk.text for chunk in chunks],
    )
    vector_size = len(chunk_vectors[0])
    print(f"向量维度：{vector_size}")

    print("\n5. 重建 Qdrant collection 并写入向量...")
    recreate_collection(qdrant, config["qdrant_collection"], vector_size)
    upsert_chunks(qdrant, config["qdrant_collection"], chunks, chunk_vectors)
    print(f"已写入 collection：{config['qdrant_collection']}")

    question = input("\nUser: ").strip()
    if not question:
        print("问题不能为空。")
        return

    print("\n6. 将用户问题向量化...")
    query_vector = embed_texts(
        base_url=config["embedding_base_url"],
        model=config["embedding_model"],
        texts=[question],
    )[0]

    print("\n7. 从 Qdrant 检索相关 chunk...")
    retrieved_chunks = retrieve(qdrant, config["qdrant_collection"], query_vector)
    print_retrieved_chunks(retrieved_chunks)

    print("\n8. 调用模型生成带引用回答...")
    answer = answer_with_citations(
        client=llm_client,
        model=config["openai_model"],
        question=question,
        retrieved_chunks=retrieved_chunks,
    )

    print("\nFinal answer:")
    print(answer)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # 教学脚本里把常见环境问题打印成短提示，比直接暴露 traceback 更容易理解。
        # 例如：BGE-M3 没启动、Qdrant 没启动、embedding 接口返回异常等。
        print("\n程序运行失败：")
        print(exc)
