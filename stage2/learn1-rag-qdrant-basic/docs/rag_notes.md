# RAG Notes

## Chunk

Chunk 是把长文档切成较小文本块的过程。长文档通常不能直接全部塞给模型，也不适合直接向量化后作为一个整体检索。切成 chunk 后，每一段都可以单独生成向量，并在查询时被独立召回。

好的 chunk 应该尽量保持语义完整。太短会丢失上下文，太长会降低检索精度。教学示例里可以先按固定字符长度切分，真实项目中还会考虑标题、段落、Markdown 结构和重叠窗口。

## Embed

Embed 是把文本转换成向量的过程。向量可以理解成文本在语义空间中的坐标。意思相近的文本，它们的向量距离通常更近。

本课程使用本地 BGE-M3 embedding 服务生成向量。服务接口兼容 OpenAI embeddings API，请求地址是 `/v1/embeddings`，模型名固定为 `BAAI/bge-m3`。

## Retrieve

Retrieve 是检索阶段。用户问题也会先被转换成向量，然后拿这个 query vector 去向量数据库里查找最相似的 chunk。

在本节中，Qdrant 负责保存 chunk 向量和 payload，并根据 query vector 返回最相似的 top-k 结果。payload 里保存 `source`、`chunk_id` 和 `text`，后续回答引用来源时会用到这些字段。

## Answer with Citations

Answer with citations 是指模型回答时不仅给出答案，还要标明答案来自哪些资料片段。

引用的价值在于让用户可以追溯答案来源，也能减少模型凭空编造的风险。如果检索结果里没有足够证据，模型应该说明“根据当前资料不足以回答这个问题”，而不是硬编一个看起来很合理的答案。

## Qdrant

Qdrant 是一个向量数据库。它在本节负责三件事：创建 collection、存储向量和 payload、根据 query vector 做相似度检索。

Embedding 服务和 Qdrant 的职责不同。BGE-M3 负责把文本变成向量；Qdrant 负责保存向量并查找相似向量。把这两个职责分开，有助于理解真实 RAG 系统的结构。
