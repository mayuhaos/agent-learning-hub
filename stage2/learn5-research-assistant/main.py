import os
import re
from dataclasses import dataclass
from pathlib import Path

import requests
from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient


# Learn 5 的目标：
# 做一个最小“资料研究助手”。
#
# 它不是完整 Agent 平台，而是把 Stage 2 学过的能力串成一个稳定流程：
# 1. 根据用户主题检索资料
# 2. 筛选证据
# 3. 让模型基于证据总结
# 4. 输出引用
# 5. 程序校验引用是否真实来自本次检索

TOP_K = 5
MIN_SCORE = 0.25
CITATION_PATTERN = re.compile(r"\[source:\s*([^,\]]+),\s*chunk:\s*(\d+)\]")


@dataclass
class Evidence:
    source: str
    chunk_id: int
    text: str
    score: float


def load_config() -> dict[str, str | None]:
    """读取 Stage 2 共享配置。"""
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


def embed_text(text: str, config: dict[str, str | None]) -> list[float]:
    """调用本地 BGE-M3，把研究主题转成向量。"""
    response = requests.post(
        f"{config['embedding_base_url']}/v1/embeddings",
        headers={"Content-Type": "application/json"},
        json={"model": config["embedding_model"], "input": text},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]


def retrieve_evidence(topic: str, config: dict[str, str | None]) -> list[Evidence]:
    """从 Learn 1 的 Qdrant collection 中检索证据。"""
    query_vector = embed_text(topic, config)
    client = QdrantClient(url=str(config["qdrant_url"]))
    response = client.query_points(
        collection_name=str(config["qdrant_collection"]),
        query=query_vector,
        limit=TOP_K,
        with_payload=True,
        score_threshold=MIN_SCORE,
    )

    evidences = []
    for point in response.points:
        payload = point.payload or {}
        evidences.append(
            Evidence(
                source=str(payload.get("source", "unknown")),
                chunk_id=int(payload.get("chunk_id", 0)),
                text=str(payload.get("text", "")),
                score=float(point.score),
            )
        )
    return evidences


def format_evidence(evidences: list[Evidence]) -> str:
    """把证据整理成模型输入。"""
    if not evidences:
        return "没有检索到足够相关的资料。"

    parts = []
    for index, item in enumerate(evidences, start=1):
        parts.append(
            "\n".join(
                [
                    f"证据 {index}",
                    f"source: {item.source}",
                    f"chunk: {item.chunk_id}",
                    f"score: {item.score:.4f}",
                    "text:",
                    item.text,
                ]
            )
        )
    return "\n\n---\n\n".join(parts)


def allowed_citations(evidences: list[Evidence]) -> set[tuple[str, int]]:
    """列出本次回答允许使用的 citation。"""
    return {(item.source, item.chunk_id) for item in evidences}


def validate_citations(answer: str, allowed: set[tuple[str, int]]) -> list[str]:
    """校验答案里的引用是否真实来自本次检索结果。

    这里同时检查两件事：
    1. 答案有没有 citation。
    2. citation 是否来自本次 Qdrant 检索结果。
    """
    errors = []
    citations = CITATION_PATTERN.findall(answer)

    if allowed and "根据当前资料不足以回答这个问题" not in answer and not citations:
        errors.append("答案没有包含 citation。")

    for source, chunk_text in citations:
        citation = (source.strip(), int(chunk_text))
        if citation not in allowed:
            errors.append(f"[source: {source.strip()}, chunk: {chunk_text}]")
    return errors


def generate_research_answer(
    client: OpenAI,
    model: str,
    topic: str,
    evidences: list[Evidence],
) -> str:
    """让模型基于证据生成研究总结。"""
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "developer",
                "content": (
                    "你是一个严谨的中文资料研究助手。"
                    "你只能基于用户提供的证据回答。"
                    "如果证据不足，请回答：根据当前资料不足以回答这个问题。"
                    "输出必须包含四个小标题：问题、结论、依据、引用。"
                    "引用格式必须是 [source: 文件名, chunk: 编号]。"
                    "引用只能来自证据里的 source 和 chunk 字段。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"研究主题：\n{topic}\n\n"
                    f"证据材料：\n{format_evidence(evidences)}\n\n"
                    "请输出一份简洁研究结论。"
                ),
            },
        ],
    )
    return response.output_text


def print_evidence(evidences: list[Evidence]) -> None:
    """打印检索命中的证据，方便课堂上观察筛选过程。"""
    if not evidences:
        print("没有检索到超过相关性阈值的证据。")
        return

    print("\n检索到的证据：")
    for index, item in enumerate(evidences, start=1):
        preview = item.text.replace("\n", " ")[:120]
        print(f"{index}. score={item.score:.4f} source={item.source} chunk={item.chunk_id}")
        print(f"   {preview}...")


def main() -> None:
    config = load_config()
    client = OpenAI(
        api_key=config["openai_api_key"],
        base_url=config["openai_base_url"] or None,
    )

    print("Stage 2 Learn 5: 带证据的资料研究助手")
    print("运行前请先启动 BGE-M3、Qdrant，并运行 Learn 1 写入知识库。")

    topic = input("\n请输入研究主题: ").strip()
    if not topic:
        print("研究主题不能为空。")
        return

    try:
        evidences = retrieve_evidence(topic, config)
    except requests.RequestException as exc:
        print("Embedding 服务不可用，请先启动：docker run -p 8080:8080 beloved70020/bge-m3")
        print(f"原始错误：{exc}")
        return
    except Exception as exc:
        print("Qdrant 检索失败，请确认 Qdrant 已启动，并且先运行 Learn 1 建库。")
        print(f"原始错误：{exc}")
        return

    print_evidence(evidences)

    if not evidences:
        print("\n最终回答：")
        print("根据当前资料不足以回答这个问题。")
        return

    answer = generate_research_answer(
        client=client,
        model=str(config["openai_model"]),
        topic=topic,
        evidences=evidences,
    )

    citation_errors = validate_citations(answer, allowed_citations(evidences))

    print("\n最终回答：")
    print(answer)

    print("\nCitation check:")
    if citation_errors:
        print("发现无效引用，下面这些引用没有出现在本次检索证据中：")
        for error in citation_errors:
            print(f"- {error}")
        print("课堂讲解重点：即使提示词要求引用，程序仍然需要做引用校验。")
    else:
        print("引用校验通过，所有 citation 都来自本次检索证据。")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\n程序运行失败：")
        print(exc)
