import ast
import json
import operator
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# Learn 5 的目标：
# 1. 模型先返回 function_call，表达“我想调用哪个工具”。
# 2. 程序解析 function_call，执行真正的 Python 函数。
# 3. 程序把工具结果用 function_call_output 回传给模型。
# 4. 模型基于工具结果生成最终回答。
#
# 这一节只做一次工具调用闭环，不做 agent loop。


# 这是给模型看的工具 schema，不是真正执行的 Python 函数。
# 格式参考 OpenAI Function Calling 文档：
# https://developers.openai.com/api/docs/guides/function-calling
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


# search 工具使用的小型内置资料库。
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


# calculator 工具允许的运算符。
# 用 ast 手写一个小计算器，是为了避免 eval 执行任意 Python 代码。
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

    # 安全限制：只允许读取本节目录内的文件。
    if not target_path.is_relative_to(lesson_dir):
        return "读取失败：只能读取本节目录下的文件。"

    if not target_path.exists():
        return f"读取失败：文件不存在：{path}"

    if not target_path.is_file():
        return f"读取失败：这不是一个文件：{path}"

    return target_path.read_text(encoding="utf-8")


# 这是给程序看的工具分发表。
# 模型返回 name="calculator" 后，程序会在这里找到真正的 calculator 函数。
TOOL_FUNCTIONS = {
    "search": search,
    "calculator": calculator,
    "read_file": read_file,
}


def parse_arguments(arguments: str) -> dict:
    # function_call.arguments 是 JSON 字符串，执行工具前要先转成 Python dict。
    return json.loads(arguments)


def call_tool(name: str, arguments: dict) -> str:
    # 根据模型返回的工具名找到本地函数。
    tool_function = TOOL_FUNCTIONS.get(name)
    if tool_function is None:
        return f"工具执行失败：未知工具 {name}"

    # **arguments 会把 {"expression": "1 + 2"} 展开成 expression="1 + 2"。
    return tool_function(**arguments)


def output_item_to_input(item) -> dict:
    # OpenAI 文档建议把模型返回的 output item 继续放回下一次 input。
    # 这样模型能看到自己刚才发出的 function_call。
    if hasattr(item, "model_dump"):
        return item.model_dump(exclude_none=True)
    return dict(item)


def main() -> None:
    stage_dir = Path(__file__).resolve().parents[1]
    load_dotenv(stage_dir / ".env")

    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("OPENAI_MODEL", "gpt-5.5")

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=base_url if base_url else None,
    )

    print("Execute Tool Demo")
    print("这一节会执行模型选择的工具，并把工具结果回传给模型。")

    user_input = input("\nUser: ").strip()

    input_messages = [
        {
            "role": "developer",
            "content": (
                "你是一个会使用工具的中文助手。"
                "需要查询、计算或读文件时，请先调用合适的工具。"
                "拿到工具结果后，再用中文给用户一个简洁回答。"
            ),
        },
        {
            "role": "user",
            "content": user_input,
        },
    ]

    # 第一次请求：让模型判断是否需要工具。
    first_response = client.responses.create(
        model=model,
        input=input_messages,
        tools=TOOLS,
    )

    function_calls = [item for item in first_response.output if item.type == "function_call"]

    if not function_calls:
        print("\nModel final answer:")
        print(first_response.output_text)
        return

    # 把模型第一轮输出放回 input，保留 function_call 的上下文。
    input_messages.extend(output_item_to_input(item) for item in first_response.output)

    for tool_call in function_calls:
        print("\nModel selected tool:")
        print(f"name: {tool_call.name}")
        print(f"call_id: {tool_call.call_id}")
        print(f"arguments(raw): {tool_call.arguments}")

        arguments = parse_arguments(tool_call.arguments)
        print("arguments(dict):")
        print(json.dumps(arguments, indent=2, ensure_ascii=False))

        tool_result = call_tool(tool_call.name, arguments)

        print("\nTool result:")
        print(tool_result)

        # function_call_output 是把工具结果回传模型的关键。
        # call_id 必须和模型刚才返回的 tool_call.call_id 对上。
        input_messages.append(
            {
                "type": "function_call_output",
                "call_id": tool_call.call_id,
                "output": tool_result,
            }
        )

    # 第二次请求：模型读取工具结果，组织最终回答。
    final_response = client.responses.create(
        model=model,
        input=input_messages,
        tools=TOOLS,
    )

    print("\nModel final answer:")
    print(final_response.output_text)


if __name__ == "__main__":
    main()
