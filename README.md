# MedReg Copilot

医疗器械注册申报资料智能预审与编制 Agent 平台。项目面向企业法规事务、临床评价、质量和研发人员，围绕“申报项目、法规版本、资料清单、证据矩阵、跨文档一致性、辅助编制、人工审核”建立可追溯工作流。

> 系统只辅助企业准备和内部预审申报资料，不替代法规专业人员、检测机构或药品监督管理部门作出合规结论。

## 当前里程碑

M0 至 M6 已完成，系统已建立可审计的预审、Agent 编制、评测与单机生产部署闭环：

- 产品范围、角色、业务流程和 MVP 验收指标
- 公开法规与演示数据使用边界
- FastAPI 模块化后端和版本化 API
- NMPA 二、三类器械申报项目领域模型
- 7 类注册资料清单初始化规则
- React + TypeScript 申报工作台和项目创建流程
- 后端单元/API 测试和前端构建基线
- PostgreSQL、Qdrant、Neo4j、Redis、MinIO 独立基础设施配置
- SQLAlchemy 异步仓储、PostgreSQL 持久化和 Alembic 版本迁移
- 数据库就绪探针与跨进程重启持久化验证
- 官方法规来源登记、版本追加与人工核验状态流
- 按申报基准日期计算法规生命周期和唯一适用版本
- 法规知识库工作台、版本时间线与官方来源追溯
- 国家市场监督管理总局第 47 号令演示来源及日期边界验证
- MinIO 法规原文归档、SHA-256 去重与 20 MB 上传边界
- PDF、DOCX、XLSX、TXT、Markdown、HTML 受控文本解析
- 上传前文件签名、OOXML 压缩边界、危险路径、宏、嵌入对象和主动 HTML 检查
- Word/Excel 表格结构化提取、PostgreSQL 持久化和来源坐标回溯
- 解析状态、错误、尝试次数和人工重试闭环
- PostgreSQL + MinIO 跨会话集成验证与联合就绪探针
- Celery + Redis 异步解析、任务编号和前端状态轮询
- Worker 中断后的陈旧任务定时恢复与旧任务写回保护
- 官方来源受控抓取申请、人工审批、域名白名单和归档去重
- PostgreSQL、MinIO 与 Redis 联合就绪探针
- HTML 解析噪声过滤与 parser v2 可追踪版本
- 中文法规章、节、条确定性层级识别与父子关系
- 自然边界重叠分块、字符坐标、内容哈希与可读引用路径
- 结构化引用查询 API 与前端 Section/Chunk 检查器
- 第 47 号令 143 个结构节点、124 个 Chunk 的真实数据验证
- Celery 异步向量索引、内容指纹、失败重试与索引状态追踪
- BGE 中文 Dense 向量、BM25 稀疏向量和 Qdrant RRF 融合检索
- 法规版本、文档维度过滤与中文短语覆盖重排
- 法规名称、文号、条款路径、原文坐标和检索分数完整回传
- Neo4j 可重建法规图谱、版本替代链、上位法引用、适用范围与资料证据关系
- 图谱关系生成依据、原文摘录、核验状态和人工同步审计
- 法规证据检索工作台与文档级索引状态控件
- 第 47 号令 124 个 Qdrant 点和两类真实业务问法验证
- 七类申报证据归档、人工审核、完整性预审和证据矩阵
- 产品名称、型号、预期用途、性能及警示语跨文档一致性检查
- 带完整 SHA-256 指纹、问题整改状态和审计附录的内部预审 PDF
- LangGraph 六节点编制链和 PostgreSQL 输入/提示词/输出快照
- DeepSeek 实时生成、无密钥确定性演示和调用失败受控降级
- 带法规版本、条款路径、字符坐标及分数的草稿引用回溯
- 已接受项目证据的目标章节相关性分段、字符预算压缩和片段哈希追溯
- 固定章节、事实主张、证据标记和置信度的结构化草稿输出
- 产品及章节受控中英文术语表、缺失/错译检查和运行级审计报告
- 独立人工批准/驳回和不可重复终态决定
- 60 条版本化合成专家标注演示集和数据集 SHA-256
- 检索、引用、冲突、Schema、采纳与 P95 耗时的基线对照
- PostgreSQL 评测运行、10 项质量门禁和领域专家复核状态隔离
- 固定法规/申报/Agent/评测数据与 `make demo-up` 一键演示
- 租户、成员与 Owner/Reviewer/Editor/Viewer 四级角色权限
- 申报项目和 Agent 运行 SQL 租户隔离、关键写操作及报告导出审计
- 权限审计工作台、不可变事件流和跨租户集成验证
- 后端非 root 镜像、Nginx 反向代理与仅暴露 Web 的独立生产 Compose
- 文件密钥、生产配置强校验、健康探针、迁移门禁和日志轮转
- 五类持久化数据卷的一致性备份、校验与恢复演练

MVP 作品集版本已收口，并完成企业级权限、受控文件入口与法规关系图谱强化。进入真实多人协作或医疗器械业务验证前，仍需接入企业身份提供方、密钥轮换策略、独立恶意软件扫描服务，并由医疗器械法规专家正式复核标注集及图谱关系。

## 快速开始

```bash
make bootstrap
make demo-up
```

`make demo-up` 会启动 PostgreSQL、MinIO、Redis、Qdrant 与 Neo4j，执行迁移，幂等写入固定法规、图谱、申报、预审、Agent、评测和审计演示数据，再并行运行 API、Celery Worker、定时恢复器和前端。首次构建向量索引时会下载本地 ONNX 嵌入模型。日常开发可继续使用 `make dev`。

单机生产部署基线使用独立配置、网络和数据卷：

```bash
make prod-init
# 检查 .env.production，并填写 secrets/production/deepseek_api_key
make prod-deploy
```

默认仅在 `http://127.0.0.1:8080` 暴露 Web 入口。公网部署必须在其前方配置 HTTPS 终止、可信域名和访问控制；完整步骤见[生产部署运行手册](docs/production-deployment.md)。

Agent 编制默认运行确定性演示模式。启用 DeepSeek 实时生成时，在本机 `.env` 中配置：

```bash
DEEPSEEK_API_KEY=your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

API Key 只在后端进程中读取，不写入运行快照、日志或前端响应。实时调用失败时，系统会保存失败原因并切换到受控模板，不会伪装成模型生成结果。

- Web：http://localhost:5273
- API：http://localhost:8200/api/v1/health
- API 文档：http://localhost:8200/docs
- 评测中心：http://localhost:5273/evaluation
- 权限审计：http://localhost:5273/audit

数据库与迁移可单独管理：

```bash
make db-up
make migrate
make db-current
make test-integration
make worker
make beat
```

开始法规入库与文档解析前，可启动完整基础设施：

```bash
make infra-up
```

## 目录

```text
medreg-copilot/
├── backend/       FastAPI API、领域服务和 Agent 工作流
├── frontend/      React 法规事务工作台
├── docs/          PRD、架构、数据与验收说明
├── scripts/       环境与开发脚本
├── compose.yaml   数据与检索基础设施
├── compose.production.yaml  单机生产部署基线
└── Makefile       常用命令
```

## 产品文档

- [产品规格与 MVP](docs/product-spec.md)
- [系统架构](docs/architecture.md)
- [数据与合规边界](docs/data-policy.md)
- [实施路线图](docs/roadmap.md)
- [M5 评测说明](docs/evaluation.md)
- [作品集案例](docs/portfolio.md)
- [三分钟演示脚本](docs/demo-script.md)
- [生产部署运行手册](docs/production-deployment.md)
