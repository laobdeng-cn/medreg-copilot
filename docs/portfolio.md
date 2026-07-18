# MedReg Copilot 作品集案例

## 项目定位

面向医疗器械注册团队的资料智能预审与编制平台。系统把法规版本、申报证据、确定性规则、混合检索、Agent 草稿和人工审批组织成可追溯业务闭环，避免把合规结论直接交给大模型。

## 页面预览

- [申报项目](../output/portfolio/01-applications.jpg)
- [资料预审](../output/portfolio/02-precheck.jpg)
- [Agent 编制](../output/portfolio/03-agent.jpg)
- [评测中心](../output/portfolio/04-evaluation.jpg)
- [权限审计](../output/portfolio/05-audit.jpg)
- [受控文档与结构化表格](../output/portfolio/06-document-security-tables.jpg)
- [法规关系图谱](../output/portfolio/07-regulation-knowledge-graph.jpg)

## 个人实现范围

- 使用 FastAPI、SQLAlchemy AsyncIO、Alembic 和 PostgreSQL 构建模块化领域后端。
- 使用 MinIO、Celery、Redis 完成原文归档、异步解析、任务幂等和中断恢复。
- 实现上传前文件签名、OOXML 压缩安全、宏与主动内容检查，并结构化持久化 Word/Excel 表格。
- 构建 Neo4j 可重建法规投影，关联版本替代、上位法引用、器械范围、七类资料要求与原文证据。
- 实现中文法规层级切分、字符坐标、内容哈希，以及 Qdrant Dense + BM25 + RRF 检索。
- 使用 LangGraph 编排六节点 Agent，接入 DeepSeek，提供确定性演示与失败降级。
- 实现证据上下文压缩、结构化事实主张、中英文术语审计和人工终态审批。
- 建设 60 条版本化合成演示评测集、基线对照、质量门禁和 PostgreSQL 运行历史。
- 实现四级 RBAC、申报与 Agent SQL 租户隔离，以及关键写操作和受控报告导出审计事件流。
- 使用 React、TypeScript 和 TanStack Query 完成申报、法规、预审、Agent、评测及权限审计工作台。

## 可核验结果

- 第 47 号令文档可解析为带父级路径、字符区间和哈希的引用 Chunk。
- 固定 XLSX 演示资料在 MinIO 写入前通过受控安全检查，申报资料矩阵的表头、数据行、工作表坐标和哈希可从 PostgreSQL 恢复。
- 第 47 号令演示图谱包含 15 个节点和 20 条已核验关系，其中资料要求与第五十二条 Chunk 保留引用路径、摘录和内容哈希。
- 便携式心电记录仪演示申请含 3 类已接受资料，可识别型号及性能跨文档冲突。
- Agent 草稿输出 6 个章节、7 条带证据主张、5 条法规引用和 4 个受控双语术语。
- `medreg-eval-v1-60` 演示集上，当前管线 Recall@5 为 `91.67%`、引用覆盖率为 `95.00%`、冲突 F1 为 `92.68%`、Schema 通过率为 `91.67%`、演示采纳率为 `83.33%`。
- 68 个单元与接口测试、8 个 PostgreSQL/MinIO/Redis/Qdrant/Neo4j 集成测试、前端类型构建和环境诊断形成自动验收基线。

## 简历项目描述

**MedReg Copilot｜医疗器械注册申报资料智能预审与编制 Agent 平台**

- 设计医疗器械注册资料业务闭环，基于 FastAPI、PostgreSQL、MinIO、Celery 与 Redis 实现 7 类资料清单、证据归档、预审快照和问题整改状态流。
- 构建受控文档入口，校验 PDF/OOXML 文件签名、压缩边界、宏与主动内容；使用 parser v3 结构化提取 Word/Excel 表格并保留来源坐标和内容哈希。
- 基于 Neo4j 构建可重建法规关系投影，串联第 47 号令版本替代、上位法引用、二/三类器械适用范围、七类申报资料与第五十二条证据，并记录同步审计。
- 构建 Qdrant Dense + BM25 + RRF 混合检索，法规证据保留版本、条款路径、原文字符坐标和 SHA-256，实现可回溯引用而非无来源问答。
- 使用 LangGraph 编排 Intake、Regulation、Retrieval、Consistency、Drafting、Reviewer 六节点，支持 DeepSeek、确定性降级、结构化主张、双语术语审计与人工批准/驳回。
- 建设 60 条版本化合成演示评测集和 10 项质量门禁，当前管线在演示集上达到 Recall@5 `91.67%`、引用覆盖率 `95.00%`、冲突 F1 `92.68%`，并将 P95 从 `656 ms` 降至 `297 ms`。
- 构建 Owner/Reviewer/Editor/Viewer 四级权限和不可变审计事件流，在 PostgreSQL 查询层隔离企业申报及 Agent 运行，并通过双租户集成测试验证跨租户不可见。

所有指标必须保留“合成演示集”限定，不应写成真实客户生产效果。
