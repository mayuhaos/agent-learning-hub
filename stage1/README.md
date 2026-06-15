# Stage 1: 构建最小 Agent Loop

这一阶段先从最小可运行程序开始：普通对话、结构化输出、工具函数、tool call 解析、执行工具、把工具结果回传模型。

## 章节

| 小节 | 主题 | 状态 |
| --- | --- | --- |
| Learn 1 | 用一个 LLM API 完成普通多轮对话 | 已完成 |
| Learn 2 | 让模型输出结构化 JSON | 待更新 |
| Learn 3 | 定义一个工具函数 | 待更新 |
| Learn 4 | 解析模型的 tool call / function call | 待更新 |
| Learn 5 | 执行工具并把结果喂回模型 | 待更新 |
| Learn 6 | 给 agent loop 加最大步数、超时和错误处理 | 待更新 |

## 当前代码

- [learn1-llm-chat](./learn1-llm-chat)：一个命令行多轮聊天程序。
