import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from qdrant_client import QdrantClient


# Learn 2 的目标：
# 把常见的外部能力包装成“工具”。
#
# 注意：本节暂时不让模型自动调用工具。
# 这里先用命令行菜单手动选择工具，是为了把“接工具”这件事讲清楚：
# 1. 一个工具有名字
# 2. 一个工具有说明
# 3. 一个工具有参数
# 4. 一个工具会执行真实能力
# 5. 一个工具需要返回统一格式的结果
#
# 后续章节再把这些工具交给模型，让模型决定何时调用哪个工具。


# Qdrant 检索返回的默认数量。
# 这里的 top_k 是工具参数也可以覆盖的默认值。
DEFAULT_TOP_K = 3

# 浏览器读取工具最多返回多少正文字符。
# 网页正文可能很长，教学示例只截取前面一段，避免终端刷屏。
WEB_TEXT_LIMIT = 1200

# 代码执行工具的超时时间。
# 真实生产环境不要只靠这个做安全隔离，本节只是演示“代码执行工具”的基本形态。
CODE_TIMEOUT_SECONDS = 3


@dataclass
class ToolResult:
    """所有工具统一返回这个结构。

    统一返回结构的好处是：调用方不需要关心每个工具内部怎么实现，
    只需要看 ok、result、error 这三个字段。
    """

    ok: bool
    result: Any = None
    error: str | None = None


@dataclass
class ToolSpec:
    """工具注册表里的工具说明。

    handler 是真正执行工具的 Python 函数。
    parameters 是给学习者看的参数说明；后续如果接入模型，也可以把它转换成
    function calling 需要的 JSON Schema。
    """

    name: str
    description: str
    parameters: dict[str, str]
    handler: Callable[..., ToolResult]


class SimpleHTMLTextParser(HTMLParser):
    """非常轻量的 HTML 解析器，用来提取网页标题和正文片段。"""

    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._in_title = False
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return

        if self._in_title:
            self.title_parts.append(text)
        elif self._skip_depth == 0:
            self.text_parts.append(text)

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()

    @property
    def text(self) -> str:
        return " ".join(self.text_parts).strip()


def load_stage2_config() -> dict[str, str]:
    """读取 Stage 2 共享的环境变量。

    本节的搜索工具会复用 Learn 1 的 BGE-M3 和 Qdrant 配置。
    如果用户还没有启动服务，工具会返回清晰错误，而不是让程序直接崩溃。
    """

    stage_dir = Path(__file__).resolve().parents[1]
    load_dotenv(stage_dir / ".env")

    return {
        "embedding_base_url": os.getenv("EMBEDDING_BASE_URL", "http://localhost:8080").rstrip("/"),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"),
        "qdrant_url": os.getenv("QDRANT_URL", "http://localhost:6333"),
        "qdrant_collection": os.getenv("QDRANT_COLLECTION", "stage2_learn1_rag"),
    }


def to_jsonable(result: ToolResult) -> dict[str, Any]:
    """把 ToolResult 转成方便打印的 dict。"""

    return {
        "ok": result.ok,
        "result": result.result,
        "error": result.error,
    }


def embed_query(text: str, config: dict[str, str]) -> list[float]:
    """调用本地 BGE-M3 服务，把查询文本转换成向量。"""

    response = requests.post(
        f"{config['embedding_base_url']}/v1/embeddings",
        headers={"Content-Type": "application/json"},
        json={
            "model": config["embedding_model"],
            "input": text,
        },
        timeout=60,
    )
    response.raise_for_status()

    data = response.json()
    return data["data"][0]["embedding"]


def search_knowledge(query: str, top_k: int = DEFAULT_TOP_K) -> ToolResult:
    """搜索工具：用 BGE-M3 + Qdrant 检索 Learn 1 写入的知识库。"""

    query = query.strip()
    if not query:
        return ToolResult(ok=False, error="query 不能为空。")

    try:
        top_k = int(top_k)
    except ValueError:
        return ToolResult(ok=False, error="top_k 必须是整数。")

    if top_k <= 0:
        return ToolResult(ok=False, error="top_k 必须大于 0。")

    config = load_stage2_config()

    try:
        query_vector = embed_query(query, config)
    except requests.RequestException as exc:
        return ToolResult(
            ok=False,
            error=(
                "Embedding 服务不可用，请先启动："
                "docker run -p 8080:8080 beloved70020/bge-m3。"
                f" 原始错误：{exc}"
            ),
        )
    except Exception as exc:
        return ToolResult(ok=False, error=f"生成查询向量失败：{exc}")

    try:
        client = QdrantClient(url=config["qdrant_url"])
        response = client.query_points(
            collection_name=config["qdrant_collection"],
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )
    except Exception as exc:
        return ToolResult(
            ok=False,
            error=(
                "Qdrant 检索失败。请确认 Qdrant 已启动，并且先运行过 Learn 1 建库。"
                f" 原始错误：{exc}"
            ),
        )

    hits = []
    for point in response.points:
        payload = point.payload or {}
        hits.append(
            {
                "score": point.score,
                "source": payload.get("source"),
                "chunk_id": payload.get("chunk_id"),
                "text": payload.get("text"),
            }
        )

    if not hits:
        return ToolResult(ok=True, result="没有检索到相关资料。")

    return ToolResult(ok=True, result=hits)


def init_sample_database() -> Path:
    """初始化本节专用 SQLite 示例数据库。

    数据库文件放在 learn2-tool-registry/sample_data/ 下。
    这个文件是运行时生成的，不需要提交到 Git。
    """

    lesson_dir = Path(__file__).resolve().parent
    data_dir = lesson_dir / "sample_data"
    data_dir.mkdir(exist_ok=True)

    db_path = data_dir / "courses.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                stage TEXT NOT NULL,
                topic TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        connection.execute("DELETE FROM courses")
        connection.executemany(
            "INSERT INTO courses (name, stage, topic, status) VALUES (?, ?, ?, ?)",
            [
                ("Learn 1", "Stage 2", "RAG with Qdrant + BGE-M3", "已完成"),
                ("Learn 2", "Stage 2", "把搜索、数据库、文件、浏览器、代码执行接成工具", "学习中"),
                ("Learn 3", "Stage 2", "短期上下文、会话记忆、长期记忆", "待更新"),
                ("Learn 4", "Stage 2", "工具失败、空结果、重复调用、幻觉引用", "待更新"),
                ("Learn 5", "Stage 2", "回答里给出来源或证据", "待更新"),
            ],
        )
        connection.commit()
    finally:
        connection.close()

    return db_path


def query_database(sql: str) -> ToolResult:
    """数据库工具：只允许执行 SELECT 查询。"""

    sql = sql.strip()
    if not sql:
        return ToolResult(ok=False, error="sql 不能为空。")

    # 教学示例只开放只读查询，避免用户在课堂演示中误删数据。
    # 这里只做简单判断；生产项目应使用更严格的 SQL 解析和权限控制。
    lowered = sql.lower()
    if not lowered.startswith("select"):
        return ToolResult(ok=False, error="本节数据库工具只允许 SELECT 查询。")

    blocked_words = ["insert", "update", "delete", "drop", "alter", "create", "replace", "truncate"]
    if any(word in lowered for word in blocked_words):
        return ToolResult(ok=False, error="SQL 中包含可能修改数据库的关键词，已拒绝执行。")

    db_path = init_sample_database()

    try:
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        rows = connection.execute(sql).fetchmany(10)
    except sqlite3.Error as exc:
        return ToolResult(ok=False, error=f"SQL 执行失败：{exc}")
    finally:
        try:
            connection.close()
        except UnboundLocalError:
            pass

    result = [dict(row) for row in rows]
    return ToolResult(ok=True, result=result)


def read_file(path: str) -> ToolResult:
    """文件工具：只允许读取本节 sample_files 目录下的文件。"""

    filename = path.strip()
    if not filename:
        return ToolResult(ok=False, error="path 不能为空。")

    lesson_dir = Path(__file__).resolve().parent
    allowed_dir = (lesson_dir / "sample_files").resolve()
    target_path = (allowed_dir / filename).resolve()

    # is_relative_to 用来防止 ../ 逃逸到 sample_files 之外。
    if not target_path.is_relative_to(allowed_dir):
        return ToolResult(ok=False, error="只能读取 sample_files 目录内的文件。")

    if not target_path.exists():
        return ToolResult(ok=False, error=f"文件不存在：{filename}")

    if not target_path.is_file():
        return ToolResult(ok=False, error=f"这不是一个文件：{filename}")

    try:
        return ToolResult(ok=True, result=target_path.read_text(encoding="utf-8"))
    except OSError as exc:
        return ToolResult(ok=False, error=f"读取文件失败：{exc}")


def fetch_webpage(url: str) -> ToolResult:
    """浏览器/网页读取工具：获取网页标题和正文摘要。"""

    url = url.strip()
    if not url:
        return ToolResult(ok=False, error="url 不能为空。")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return ToolResult(ok=False, error="只允许访问 http:// 或 https:// URL。")

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "agent-learning-hub/0.1"},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return ToolResult(ok=False, error=f"网页读取失败：{exc}")

    parser = SimpleHTMLTextParser()
    parser.feed(response.text)

    return ToolResult(
        ok=True,
        result={
            "url": url,
            "status_code": response.status_code,
            "title": parser.title or "(未解析到标题)",
            "text_preview": parser.text[:WEB_TEXT_LIMIT],
        },
    )


def run_python(code: str) -> ToolResult:
    """代码执行工具：用受限内置函数运行一段 Python 代码。

    这个工具故意使用子进程执行，并设置 timeout。
    这样即使用户写了 while True，也不会把主程序卡死。
    """

    code = code.strip()
    if not code:
        return ToolResult(ok=False, error="code 不能为空。")

    # 用 JSON 把用户代码安全地嵌入 wrapper，避免引号和换行破坏命令。
    code_json = json.dumps(code, ensure_ascii=False)
    wrapper = f"""
import contextlib
import io

safe_builtins = {{
    "abs": abs,
    "len": len,
    "sum": sum,
    "min": min,
    "max": max,
    "sorted": sorted,
    "range": range,
    "round": round,
    "print": print,
}}

code = {code_json}
namespace = {{"__builtins__": safe_builtins}}
stdout = io.StringIO()

with contextlib.redirect_stdout(stdout):
    try:
        result = eval(code, namespace, namespace)
    except SyntaxError:
        exec(code, namespace, namespace)
        result = None

printed = stdout.getvalue()
if result is not None:
    print(result)
if printed:
    print(printed, end="")
"""

    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", wrapper],
            capture_output=True,
            text=True,
            timeout=CODE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(ok=False, error=f"代码执行超过 {CODE_TIMEOUT_SECONDS} 秒，已停止。")

    if completed.returncode != 0:
        return ToolResult(ok=False, error=completed.stderr.strip() or "代码执行失败。")

    output = completed.stdout.strip()
    return ToolResult(ok=True, result=output or "(代码执行成功，但没有输出。)")


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "search_knowledge": ToolSpec(
        name="search_knowledge",
        description="用 BGE-M3 + Qdrant 检索 Learn 1 写入的知识库。",
        parameters={
            "query": "要检索的问题或关键词，例如：RAG 为什么需要 chunk？",
            "top_k": "返回多少条结果，默认 3。",
        },
        handler=search_knowledge,
    ),
    "query_database": ToolSpec(
        name="query_database",
        description="查询本节内置的 SQLite 课程表示例，只允许 SELECT。",
        parameters={
            "sql": "SQL 查询语句，例如：SELECT * FROM courses;",
        },
        handler=query_database,
    ),
    "read_file": ToolSpec(
        name="read_file",
        description="读取 sample_files 目录下的示例文件。",
        parameters={
            "path": "文件名，例如：agent_tool_note.md",
        },
        handler=read_file,
    ),
    "fetch_webpage": ToolSpec(
        name="fetch_webpage",
        description="读取网页标题和正文摘要。",
        parameters={
            "url": "网页地址，例如：https://datawhalechina.github.io/Agent-Learning-Hub/",
        },
        handler=fetch_webpage,
    ),
    "run_python": ToolSpec(
        name="run_python",
        description="执行一段受限制的 Python 表达式或代码片段。",
        parameters={
            "code": "Python 代码，例如：sum([1, 2, 3])",
        },
        handler=run_python,
    ),
}


def print_tool_list() -> None:
    """打印工具列表。"""

    print("\n可用工具：")
    for index, spec in enumerate(TOOL_REGISTRY.values(), start=1):
        print(f"{index}. {spec.name} - {spec.description}")
    print("0. 退出")


def read_multiline_input(prompt: str) -> str:
    """读取多行输入。

    Python 代码经常不止一行，例如 for 循环、if 判断、函数定义。
    普通 input() 只能读取一行，所以这里约定用户输入单独一行 END 表示结束。
    """

    print(prompt)
    print("请输入代码，单独输入一行 END 结束：")

    lines = []
    while True:
        line = input()
        if line == "END":
            break
        lines.append(line)

    return "\n".join(lines).strip()


def read_tool_arguments(spec: ToolSpec) -> dict[str, Any]:
    """根据 ToolSpec 里的参数说明，从命令行读取参数。"""

    print(f"\n工具：{spec.name}")
    print(spec.description)
    print("\n参数：")

    arguments: dict[str, Any] = {}
    for name, description in spec.parameters.items():
        # search_knowledge 的 top_k 给一个默认值，直接回车即可使用 DEFAULT_TOP_K。
        if spec.name == "search_knowledge" and name == "top_k":
            value = input(f"- {name} ({description}) [默认 {DEFAULT_TOP_K}]: ").strip()
            arguments[name] = value if value else DEFAULT_TOP_K
        elif spec.name == "run_python" and name == "code":
            arguments[name] = read_multiline_input(f"- {name} ({description})")
        else:
            value = input(f"- {name} ({description}): ").strip()
            arguments[name] = value

    return arguments


def choose_tool() -> ToolSpec | None:
    """读取用户选择，并返回对应工具。"""

    specs = list(TOOL_REGISTRY.values())
    choice = input("\n请选择工具编号：").strip()

    if choice == "0":
        return None

    try:
        index = int(choice)
    except ValueError:
        print("请输入数字编号。")
        return choose_tool()

    if index < 1 or index > len(specs):
        print("工具编号不存在。")
        return choose_tool()

    return specs[index - 1]


def main() -> None:
    print("Stage 2 Learn 2: Tool Registry")
    print("本节不调用模型，只演示如何把外部能力包装成统一工具。")

    # 提前初始化数据库，让用户一进入菜单就可以查询 courses 表。
    init_sample_database()

    while True:
        print_tool_list()
        spec = choose_tool()
        if spec is None:
            print("已退出。")
            return

        arguments = read_tool_arguments(spec)
        print("\n正在执行工具...")
        result = spec.handler(**arguments)

        print("\n工具返回：")
        print(json.dumps(to_jsonable(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
