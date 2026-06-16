import ast
import operator
from pathlib import Path


# 一个非常小的内置资料库，用来演示 search 工具。
# 真实项目里 search 可能连接搜索引擎、数据库、向量库或文档系统。
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

# ast 解析出来的运算符节点不能直接执行。
# 这里把“允许的 AST 运算符类型”映射到 Python 的安全函数。
# 没放进这个表的运算符，就不会被 calculator 执行。
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
    # 工具函数的输入通常先做清洗。
    # strip 去掉首尾空格，lower 让搜索不区分大小写。
    keyword = query.strip().lower()
    if not keyword:
        return "搜索关键词不能为空。"

    # 遍历资料库，把标题和内容拼起来做简单关键词匹配。
    matches = []
    for item in KNOWLEDGE_BASE:
        text = f"{item['title']} {item['content']}".lower()
        if keyword in text:
            matches.append(f"- {item['title']}: {item['content']}")

    # 工具失败时也要返回清晰信息，而不是直接崩溃。
    if not matches:
        return f"没有找到和「{query}」相关的资料。"

    return "\n".join(matches)


def calculator(expression: str) -> str:
    """Calculate a simple math expression safely."""
    try:
        # 不使用 eval(expression)，因为 eval 会执行任意 Python 代码，风险很高。
        # ast.parse 只把输入解析成语法树，后面由我们自己决定哪些节点允许执行。
        tree = ast.parse(expression, mode="eval")
        result = _eval_math_node(tree.body)
    except Exception as exc:
        # 对学习示例来说，返回错误文本比抛出异常更容易观察。
        return f"计算失败：{exc}"

    return str(result)


def _eval_math_node(node: ast.AST) -> float:
    # 数字常量是递归计算的最小单位，例如 1、2.5。
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return node.value

    # 二元运算：例如 1 + 2、3 * 4。
    if isinstance(node, ast.BinOp):
        operator_type = type(node.op)
        if operator_type not in ALLOWED_OPERATORS:
            raise ValueError("只支持 +、-、*、/、//、%、** 这些运算符。")
        # 先递归计算左边和右边，再把对应运算符函数应用上去。
        left = _eval_math_node(node.left)
        right = _eval_math_node(node.right)
        return ALLOWED_OPERATORS[operator_type](left, right)

    # 一元运算：例如 -1、+2。
    if isinstance(node, ast.UnaryOp):
        operator_type = type(node.op)
        if operator_type not in ALLOWED_OPERATORS:
            raise ValueError("只支持正号和负号。")
        value = _eval_math_node(node.operand)
        return ALLOWED_OPERATORS[operator_type](value)

    raise ValueError("只支持数字和简单数学表达式。")


def read_file(path: str) -> str:
    """Read a file from this lesson directory."""
    # 只允许读取本节目录下的文件。
    # 这样既能演示 read_file 工具，又不会误读用户电脑上的其他文件。
    lesson_dir = Path(__file__).resolve().parent
    target_path = (lesson_dir / path).resolve()

    # resolve 后再判断路径是否仍在 lesson_dir 里面。
    # 这可以拦住 ../README.md 这类试图跳出目录的路径。
    if not target_path.is_relative_to(lesson_dir):
        return "读取失败：只能读取本节目录下的文件。"

    if not target_path.exists():
        return f"读取失败：文件不存在：{path}"

    if not target_path.is_file():
        return f"读取失败：这不是一个文件：{path}"

    # 明确使用 utf-8，避免中文示例文件在不同系统上出现编码问题。
    return target_path.read_text(encoding="utf-8")


def print_menu() -> None:
    # 命令行菜单只是为了让学习者手动选择工具。
    # 真正的 Agent 里，这个选择动作会逐步交给模型完成。
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

        # 退出分支。
        if choice in {"0", "exit", "quit", "退出"}:
            print("Bye.")
            break

        # 根据用户选择，收集对应参数，然后调用本地函数。
        # 本节的重点是：工具函数本质上就是普通函数。
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
