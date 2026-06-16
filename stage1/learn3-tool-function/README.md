# Learn 3: 定义一个工具函数

这是 Stage 1 的第三个代码示例。

## 这个示例做了什么

这一节先不接入大模型，也不讲 tool calling。我们只做一件事：定义几个普通 Python 函数，并把它们当成“工具”来执行。

程序里包含三个工具函数：

- `search(query: str) -> str`：从内置小型资料库里搜索内容。
- `calculator(expression: str) -> str`：计算简单数学表达式。
- `read_file(path: str) -> str`：读取本节目录下的示例文件。

工具函数本质上还是普通函数。区别在于：后面的章节会把这些函数整理成模型可以选择和调用的能力。

## 准备环境

下面的命令都在 `stage1` 目录下执行。

这一节不调用 OpenAI API，也不需要新增第三方依赖。如果你已经为前两节安装过依赖，可以直接运行。

如果还没有安装 Stage 1 的共享依赖，可以执行：

```bash
pip install -r requirements.txt
```

Windows 如果没有配置 `pip` 命令，可以使用：

```bash
py -3 -m pip install -r requirements.txt
```

## 运行

```bash
python learn3-tool-function/main.py
```

Windows 如果没有配置 `python` 命令，可以使用：

```bash
py -3 learn3-tool-function/main.py
```

运行后会看到一个简单菜单：

```text
1. search      查询内置资料
2. calculator  计算数学表达式
3. read_file   读取本节目录下的文件
0. exit        退出
```

可以尝试这些输入：

```text
search: Agent
calculator: 1 + 2 * 3
calculator: 10 / 0
read_file: sample_note.txt
read_file: missing.txt
```

## 代码核心

一个工具函数通常有四个要素：

1. 工具名：例如 `search`、`calculator`、`read_file`
2. 参数：调用工具时需要传入的数据
3. 返回值：工具执行后的结果
4. 失败信息：工具无法完成任务时的解释

比如 `calculator("1 + 2 * 3")` 会返回 `7`，而 `read_file("missing.txt")` 会返回“文件不存在”的失败信息。

这也是为什么工具对 Agent 很重要：模型不需要自己完成所有事情，它可以把搜索、计算、读文件这类任务交给外部函数。

## 课堂讲解重点

这一节只讲工具函数定义，不讲模型如何调用工具。

可以把这一节总结成一句话：

> 工具函数 = 一个有清晰名字、参数、返回值和失败信息的普通函数。

下一节会继续学习：模型如何用 tool call 表达“我要调用哪个工具，以及参数是什么”。
