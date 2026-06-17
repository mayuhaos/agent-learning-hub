import ast
import json
import operator
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# Learn 6 的目标：
# 在 Learn 5 的“一次工具调用闭环”基础上，做一个最小 agent loop。
#
# agent loop 的基本形状是：
# 1. 调用模型
# 2. 如果模型返回 function_call，就执行工具
# 3. 把工具结果回传模型
# 4. 重复以上步骤，直到模型给出普通文本回答


# 最大步数保护。
# 如果模型一直要求调用工具，程序不能无限循环下去。
MAX_STEPS = 5

# 总超时时间保护，单位是秒。
# 这里限制整个 agent loop 的运行时间，而不是单个工具的时间。
TIMEOUT_SECONDS = 30


TOOLS = [
    {
        "type": "function",
        "name": "search",
        "description": "查询已有知识，适合回答 Agent、工具函数、课程概念等问题。",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "要查询的关键词或问题。",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "calculator",
        "description": "计算简单数学表达式，适合处理精确算术。",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "要计算的数学表达式，例如 1 + 2 * 3。",
                }
            },
            "required": ["expression"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "read_file",
        "description": "读取指定文件内容，适合用户明确要求查看某个文件时使用。",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要读取的文件路径，例如 sample_note.txt。",
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
]


KNOWLEDGE_BASE = [
    {
        "title": "Agent",
        "content": "Agent 是能根据目标决定下一步动作的软件系统，通常会结合模型、工具和循环控制。",
    },
    {
        "title": "Tool Function",
        "content": "工具函数是普通函数，但它的名字、参数和返回值会被整理成模型可以理解的能力。",
    },
    {
        "title": "Tool Call",
        "content": "Tool call 是模型返回的结构化调用意图，包含工具名、call_id 和参数。",
    },
    {
        "title": "Agent Loop",
        "content": "Agent loop 会重复执行模型思考、选择工具、运行工具、回传结果这些步骤。",
    },
]


ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def search(query: str) -> str:
    """Search a tiny built-in knowledge base."""
    keyword = query.strip().lower()
    if not keyword:
        return "搜索失败：关键词不能为空。"

    matches = []
    for item in KNOWLEDGE_BASE:
        text = f"{item['title']} {item['content']}".lower()
        if keyword in text:
            matches.append(f"- {item['title']}: {item['content']}")

    if not matches:
        return f"没有找到和「{query}」相关的资料。"

    return "\n".join(matches)


def calculator(expression: str) -> str:
    """Calculate a simple math expression safely."""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_math_node(tree.body)
    except Exception as exc:
        return f"计算失败：{exc}"

    return str(result)


def _eval_math_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return node.value

    if isinstance(node, ast.BinOp):
        operator_type = type(node.op)
        if operator_type not in ALLOWED_OPERATORS:
            raise ValueError("只支持 +、-、*、/、//、%、** 这些运算符。")
        left = _eval_math_node(node.left)
        right = _eval_math_node(node.right)
        return ALLOWED_OPERATORS[operator_type](left, right)

    if isinstance(node, ast.UnaryOp):
        operator_type = type(node.op)
        if operator_type not in ALLOWED_OPERATORS:
            raise ValueError("只支持正号和负号。")
        value = _eval_math_node(node.operand)
        return ALLOWED_OPERATORS[operator_type](value)

    raise ValueError("只支持数字和简单数学表达式。")


def read_file(path: str) -> str:
    """Read a file from this lesson directory."""
    lesson_dir = Path(__file__).resolve().parent
    target_path = (lesson_dir / path).resolve()

    if not target_path.is_relative_to(lesson_dir):
        return "读取失败：只能读取本节目录下的文件。"

    if not target_path.exists():
        return f"读取失败：文件不存在：{path}"

    if not target_path.is_file():
        return f"读取失败：这不是一个文件：{path}"

    return target_path.read_text(encoding="utf-8")


TOOL_FUNCTIONS = {
    "search": search,
    "calculator": calculator,
    "read_file": read_file,
}


def output_item_to_input(item) -> dict:
    # 把模型输出转换成可以追加到下一轮 input 的普通 dict。
    if hasattr(item, "model_dump"):
        return item.model_dump(exclude_none=True)
    return dict(item)


def parse_arguments(arguments: str) -> tuple[dict | None, str | None]:
    # Learn 6 开始显式处理 JSON 解析失败。
    # 返回 (参数字典, 错误信息)，方便调用方决定下一步。
    try:
        return json.loads(arguments), None
    except json.JSONDecodeError as exc:
        return None, f"参数 JSON 解析失败：{exc}"


def call_tool(name: str, arguments: dict) -> str:
    # 未知工具名是 agent loop 里的常见错误之一。
    tool_function = TOOL_FUNCTIONS.get(name)
    if tool_function is None:
        return f"工具执行失败：未知工具 {name}"

    try:
        return tool_function(**arguments)
    except Exception as exc:
        # 工具函数本身也可能抛异常。
        # 这里把异常变成字符串回传给模型，而不是让整个程序崩溃。
        return f"工具执行异常：{exc}"


def summarize(text: str, limit: int = 200) -> str:
    # 打印日志时避免长文件内容刷屏。
    if len(text) <= limit:
        return text
    return text[:limit] + "...(已截断)"


def is_timeout(start_time: float) -> bool:
    return time.monotonic() - start_time > TIMEOUT_SECONDS


def main() -> None:
    stage_dir = Path(__file__).resolve().parents[1]
    load_dotenv(stage_dir / ".env")

    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("OPENAI_MODEL", "gpt-5.5")

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=base_url if base_url else None,
    )

    print("Agent Loop Demo")
    print(f"最大步数：{MAX_STEPS}")
    print(f"总超时：{TIMEOUT_SECONDS} 秒")

    user_input = input("\nUser: ").strip()

    input_messages = [
        {
            "role": "developer",
            "content": (
                "你是一个会使用工具的中文助手。"
                "需要查询、计算或读文件时，请调用合适的工具。"
                "拿到工具结果后，如果已经足够回答用户，就给出最终答案。"
            ),
        },
        {
            "role": "user",
            "content": user_input,
        },
    ]

    start_time = time.monotonic()

    for step in range(1, MAX_STEPS + 1):
        if is_timeout(start_time):
            print("\nStopped: timeout")
            print("Agent loop 超过总超时时间，已停止。")
            return

        print(f"\nStep {step}: call model")

        try:
            response = client.responses.create(
                model=model,
                input=input_messages,
                tools=TOOLS,
            )
        except Exception as exc:
            print("\nStopped: model request failed")
            print(f"模型请求失败：{exc}")
            return

        function_calls = [item for item in response.output if item.type == "function_call"]

        # 没有 function_call，说明模型已经给出了最终文本回答。
        if not function_calls:
            print("\nFinal answer:")
            print(response.output_text)
            return

        # 保留模型本轮输出。对于包含 reasoning 的模型，这一步也很重要。
        input_messages.extend(output_item_to_input(item) for item in response.output)

        for tool_call in function_calls:
            print("\nTool call:")
            print(f"name: {tool_call.name}")
            print(f"call_id: {tool_call.call_id}")
            print(f"arguments(raw): {tool_call.arguments}")

            arguments, parse_error = parse_arguments(tool_call.arguments)
            if parse_error:
                tool_result = parse_error
            else:
                print("arguments(dict):")
                print(json.dumps(arguments, indent=2, ensure_ascii=False))
                tool_result = call_tool(tool_call.name, arguments)

            print("tool result:")
            print(summarize(tool_result))

            input_messages.append(
                {
                    "type": "function_call_output",
                    "call_id": tool_call.call_id,
                    "output": tool_result,
                }
            )

    print("\nStopped: max steps reached")
    print("Agent loop 达到最大步数，已停止。")


if __name__ == "__main__":
    main()
