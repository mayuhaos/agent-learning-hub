# Stage 2: 学习工具调用、RAG 与记忆

这一阶段会继续沿着 Datawhale Agent Learning Hub 的路线推进：工具调用、RAG、记忆、失败处理和引用证据。

当前先完成第一节：用真实的 BGE-M3 embedding 服务和 Qdrant 向量数据库实现一个最小 RAG 闭环。

## 环境配置

Stage 2 下的所有示例共享同一份环境配置和依赖文件：

- `.env.example`：环境变量示例
- `.env`：本地私有环境变量，不提交到 Git
- `requirements.txt`：本阶段所有示例共用的 Python 依赖

安装依赖：

```bash
pip install -r requirements.txt
```

Windows 如果没有配置 `pip` 命令，可以使用：

```bash
py -3 -m pip install -r requirements.txt
```

复制 `.env.example` 为 `.env`，并按你的本地服务修改配置：

```bash
OPENAI_API_KEY=你的 API Key
OPENAI_BASE_URL=https://你的中转站地址/v1
OPENAI_MODEL=你的模型名

EMBEDDING_BASE_URL=http://localhost:8080
EMBEDDING_MODEL=BAAI/bge-m3

QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=stage2_learn1_rag
```

## 本地服务

启动 BGE-M3 embedding 服务：

```bash
docker run -p 8080:8080 beloved70020/bge-m3
```

启动 Qdrant：

```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

服务检查：

```bash
curl http://localhost:8080/health
curl http://localhost:6333
```

## 章节

| 小节 | 主题 | 状态 |
| --- | --- | --- |
| Learn 1 | 会做检索增强生成：chunk、embed、retrieve、answer with citations | 已完成 |
| Learn 2 | 会把搜索、数据库、文件、浏览器、代码执行接成工具 | 待更新 |
| Learn 3 | 会区分短期上下文、会话记忆、长期记忆 | 待更新 |
| Learn 4 | 会处理工具失败、空结果、重复调用、幻觉引用 | 待更新 |
| Learn 5 | 会让 agent 在回答里给出来源或证据 | 待更新 |

## 当前代码

- [learn1-rag-qdrant-basic](./learn1-rag-qdrant-basic)：一个用 BGE-M3 和 Qdrant 实现的最小 RAG 程序。
