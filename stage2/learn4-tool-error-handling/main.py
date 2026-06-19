import ast
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient


# Learn 4 的目标：
# 处理工具失败、空结果、重复调用、幻觉引用。
#
# 这一节不是为了增加更多工具，而是学习“工具调用周围的保护层”：
# 1. 工具失败时，程序要把失败原因变成模型能读懂的信息。
# 2. 工具没有结果时，模型不能硬编。
# 3. 模型重复调用同一个工具同一组参数时，程序要能停止。
# 4. 模型给出的引用必须能被程序校验。

TOP_K = 4
MIN_SCORE = 0.25
MAX_STEPS = 4
MAX_REPEAT_CALLS = 1
CITATION_PATTERN = re.compile(r"\[source:\s*([^,\]]+),\s*chunk:\s*(\d+)\]")


@dataclass
class ToolResult:
    ok: bool
    result: Any = None
    error: str | None = None


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
    """调用本地 BGE-M3，把查询文本转成向量。"""
    response = requests.post(
        f"{config['embedding_base_url']}/v1/embeddings",
        headers={"Content-Type": "application/json"},
        json={"model": config["embedding_model"], "input": text},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]


def search_knowledge(query: str, config: dict[str, str | None], top_k: int = TOP_K) -> ToolResult:
    """知识检索工具。

    这里复用 Learn 1 已经写入 Qdrant 的 collection。
    如果还没有运行 Learn 1 建库，本工具会返回清晰错误。
    """
    query = query.strip()
    if not query:
        return ToolResult(ok=False, error="query 不能为空。")

    try:
        query_vector = embed_text(query, config)
        client = QdrantClient(url=str(config["qdrant_url"]))
        response = client.query_points(
            collection_name=str(config["qdrant_collection"]),
            query=query_vector,
            limit=top_k,
            with_payload=True,
            score_threshold=MIN_SCORE,
        )
    except requests.RequestException as exc:
        return ToolResult(
            ok=False,
            error=(
                "Embedding 服务不可用。请先启动："
                "docker run -p 8080:8080 beloved70020/bge-m3。"
                f"原始错误：{exc}"
            ),
        )
    except Exception as exc:
        return ToolResult(
            ok=False,
            error=(
                "Qdrant 检索失败。请确认 Qdrant 已启动，并且先运行 Learn 1 建库。"
                f"原始错误：{exc}"
            ),
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

    if not evidences:
        return ToolResult(ok=True, result=[])

    return ToolResult(
        ok=True,
        result=[
            {
                "source": item.source,
                "chunk_id": item.chunk_id,
                "score": item.score,
                "text": item.text,
            }
            for item in evidences
        ],
    )


def read_file(path: str) -> ToolResult:
    """读取本节 sample_files 下的文件。

    只允许读取 sample_files 目录内文件，避免教学脚本误读项目外文件。
    """
    lesson_dir = Path(__file__).resolve().parent
    allowed_dir = (lesson_dir / "sample_files").resolve()
    target = (allowed_dir / path).resolve()

    if allowed_dir not in target.parents and target != allowed_dir:
        return ToolResult(ok=False, error="只能读取 learn4 sample_files 目录内的文件。")

    if not target.exists() or not target.is_file():
        return ToolResult(ok=False, error=f"文件不存在：{path}")

    return ToolResult(ok=True, result=target.read_text(encoding="utf-8"))


def calculator(expression: str) -> ToolResult:
    """计算简单数学表达式。

    只允许数字、四则运算和括号，不开放任意 Python 代码执行。
    """
    expression = expression.strip()
    if not expression:
        return ToolResult(ok=False, error="expression 不能为空。")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        return ToolResult(ok=False, error=f"表达式语法错误：{exc}")

    allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Load,
    )
    if not all(isinstance(node, allowed_nodes) for node in ast.walk(tree)):
        return ToolResult(ok=False, error="只允许简单数学表达式，不允许函数调用或变量。")

    try:
        value = eval(compile(tree, "<calculator>", "eval"), {"__builtins__": {}}, {})
    except Exception as exc:
        return ToolResult(ok=False, error=f"计算失败：{exc}")

    return ToolResult(ok=True, result=str(value))


def tool_schemas() -> list[dict[str, Any]]:
    """声明给模型看的工具 schema。"""
    return [
        {
            "type": "function",
            "name": "search_knowledge",
            "description": "检索课程资料，适合回答 RAG、Agent、工具调用等问题。",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "要检索的问题或关键词。"}
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "read_file",
            "description": "读取本节 sample_files 目录中的示例文件。",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件名，例如 agent_note.md。"}
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "calculator",
            "description": "计算简单数学表达式。",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式，例如 1 + 2 * 3。"}
                },
                "required": ["expression"],
                "additionalProperties": False,
            },
        },
    ]


def get_function_calls(response: Any) -> list[Any]:
    """从 Responses API 返回值中取出 function_call。"""
    return [item for item in response.output if getattr(item, "type", None) == "function_call"]


def output_item_to_input(item: Any) -> dict[str, Any]:
    """把模型输出转换成下一轮 Responses API 可以接收的 dict。

    Responses API 返回的 output item 通常是 SDK 模型对象。
    下一轮继续对话时，需要把它转成普通 dict 后追加回 input。
    """
    if hasattr(item, "model_dump"):
        return item.model_dump(exclude_none=True)
    return dict(item)


def normalize_call_key(name: str, arguments: dict[str, Any]) -> str:
    """把工具名和参数变成可比较的字符串，用来检测重复调用。"""
    return f"{name}:{json.dumps(arguments, ensure_ascii=False, sort_keys=True)}"


def run_tool(name: str, arguments: dict[str, Any], config: dict[str, str | None]) -> ToolResult:
    """根据工具名分发到真实 Python 函数。"""
    if name == "search_knowledge":
        return search_knowledge(str(arguments.get("query", "")), config)
    if name == "read_file":
        return read_file(str(arguments.get("path", "")))
    if name == "calculator":
        return calculator(str(arguments.get("expression", "")))
    return ToolResult(ok=False, error=f"未知工具：{name}")


def result_to_output(result: ToolResult) -> str:
    """把工具结果变成 function_call_output 能承载的字符串。"""
    return json.dumps(
        {"ok": result.ok, "result": result.result, "error": result.error},
        ensure_ascii=False,
        indent=2,
    )


def collect_allowed_citations(tool_results: list[ToolResult]) -> set[tuple[str, int]]:
    """从检索结果中收集允许出现的 citation。"""
    allowed = set()
    for result in tool_results:
        if not result.ok or not isinstance(result.result, list):
            continue
        for item in result.result:
            if isinstance(item, dict) and "source" in item and "chunk_id" in item:
                allowed.add((str(item["source"]), int(item["chunk_id"])))
    return allowed


def validate_citations(answer: str, allowed: set[tuple[str, int]]) -> list[str]:
    """检查模型答案里的引用是否都来自本次工具结果。"""
    errors = []
    citations = CITATION_PATTERN.findall(answer)

    for source, chunk_text in citations:
        citation = (source.strip(), int(chunk_text))
        if citation not in allowed:
            errors.append(f"引用不存在：{source.strip()}, chunk: {chunk_text}")

    return errors


def main() -> None:
    config = load_config()
    client = OpenAI(
        api_key=config["openai_api_key"],
        base_url=config["openai_base_url"] or None,
    )

    print("Stage 2 Learn 4: 工具失败、空结果、重复调用、幻觉引用处理")
    print("示例输入：读取 missing.md / 计算 1 + 2 * 3 / RAG 为什么需要 chunk？")

    question = input("\nUser: ").strip()
    if not question:
        print("输入不能为空。")
        return

    input_items: list[dict[str, Any]] = [
        {
            "role": "developer",
            "content": (
                "你是一个严谨的中文 Agent。"
                "需要资料时可以调用工具。"
                "工具失败时要基于失败信息回答，不要假装成功。"
                "如果检索结果为空，必须回答：根据当前资料不足以回答这个问题。"
                "如果使用检索资料，引用格式必须是 [source: 文件名, chunk: 编号]。"
            ),
        },
        {"role": "user", "content": question},
    ]

    seen_calls: dict[str, int] = {}
    tool_results: list[ToolResult] = []
    final_answer = ""

    for step in range(1, MAX_STEPS + 1):
        print(f"\n--- step {step} ---")
        response = client.responses.create(
            model=str(config["openai_model"]),
            input=input_items,
            tools=tool_schemas(),
        )

        function_calls = get_function_calls(response)
        if not function_calls:
            final_answer = response.output_text
            break

        input_items.extend(output_item_to_input(item) for item in response.output)

        for call in function_calls:
            try:
                arguments = json.loads(call.arguments)
            except json.JSONDecodeError as exc:
                result = ToolResult(ok=False, error=f"参数 JSON 解析失败：{exc}")
                input_items.append(
                    {"type": "function_call_output", "call_id": call.call_id, "output": result_to_output(result)}
                )
                continue

            key = normalize_call_key(call.name, arguments)
            seen_calls[key] = seen_calls.get(key, 0) + 1

            print(f"模型请求工具：{call.name}")
            print(f"参数：{json.dumps(arguments, ensure_ascii=False)}")

            if seen_calls[key] > MAX_REPEAT_CALLS:
                result = ToolResult(
                    ok=False,
                    error="检测到同一工具使用相同参数重复调用，程序已停止继续执行该工具。",
                )
            else:
                result = run_tool(call.name, arguments, config)

            print("工具结果：")
            print(result_to_output(result))
            tool_results.append(result)
            input_items.append(
                {"type": "function_call_output", "call_id": call.call_id, "output": result_to_output(result)}
            )
    else:
        final_answer = "达到最大步骤限制，程序停止，避免工具调用无限循环。"

    print("\nFinal answer:")
    print(final_answer)

    allowed_citations = collect_allowed_citations(tool_results)
    citation_errors = validate_citations(final_answer, allowed_citations)
    if citation_errors:
        print("\nCitation check:")
        print("发现无效引用：")
        for error in citation_errors:
            print(f"- {error}")
        print("这就是本节说的“幻觉引用”：答案里的来源没有出现在本次工具结果中。")
    else:
        print("\nCitation check:")
        print("未发现无效引用。")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\n程序运行失败：")
        print(exc)
