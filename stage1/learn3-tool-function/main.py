import ast
import operator
from pathlib import Path


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
        "title": "Calculator",
        "content": "计算器工具适合处理精确数学计算，因为语言模型本身不适合依赖猜测做算术。",
    },
    {
        "title": "Read File",
        "content": "读文件工具可以把外部文件内容提供给程序，后续也可以提供给模型继续推理。",
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
        return "搜索关键词不能为空。"

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


def print_menu() -> None:
    print("\n请选择一个工具：")
    print("1. search      查询内置资料")
    print("2. calculator  计算数学表达式")
    print("3. read_file   读取本节目录下的文件")
    print("0. exit        退出")


def main() -> None:
    print("Tool Function Demo")
    print("这一节不调用大模型，只练习定义和执行普通工具函数。")

    while True:
        print_menu()
        choice = input("\nTool: ").strip().lower()

        if choice in {"0", "exit", "quit", "退出"}:
            print("Bye.")
            break

        if choice in {"1", "search"}:
            query = input("Query: ").strip()
            result = search(query)
        elif choice in {"2", "calculator"}:
            expression = input("Expression: ").strip()
            result = calculator(expression)
        elif choice in {"3", "read_file"}:
            path = input("Path: ").strip()
            result = read_file(path)
        else:
            print("未知工具，请重新选择。")
            continue

        print("\nTool result:")
        print(result)


if __name__ == "__main__":
    main()
