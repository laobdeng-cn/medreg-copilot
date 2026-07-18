# 生产部署运行手册

## 适用范围

本方案是 MedReg Copilot 的单机生产部署基线，适合受控内网试点、作品集验收和小规模业务验证。它包含独立镜像、密钥隔离、迁移、健康检查、日志轮转、备份与恢复，但不等同于完成医疗器械合规认证或企业高可用建设。

正式商用前仍需接入企业 OIDC/SSO、集中密钥管理、TLS/WAF、恶意软件扫描或 CDR、集中监控告警、异地备份，并由医疗器械法规专家确认规则、标注集和输出审核制度。

## 拓扑与暴露面

`web` 是唯一主机端口入口，默认绑定 `127.0.0.1:8080`。Nginx 提供静态前端并将 `/api` 反向代理到内部 API。PostgreSQL、Redis、MinIO、Qdrant 和 Neo4j 只接入内部数据网络，不发布主机端口。API、Worker 和 Beat 使用非 root 后端镜像，DeepSeek Key 通过只读 Docker secret 文件注入。

远程访问时，在主机前方使用可信反向代理终止 HTTPS，并将 `.env.production` 中的 `MEDREG_HTTP_BIND`、`APP_ALLOWED_HOSTS` 和 `APP_CORS_ORIGINS` 调整为实际网络与域名。不要直接把数据库或向量库端口暴露到公网。

## 首次部署

要求 Docker Engine、Docker Compose v2、OpenSSL、curl 和至少 8 GB 可用内存。首次构建会下载 Python、ONNX Runtime 和前端依赖。

```bash
make prod-init
chmod 600 .env.production secrets/production/deepseek_api_key
make prod-config
make prod-deploy
```

`prod-init` 会生成 PostgreSQL、Redis、MinIO、Neo4j 和 Qdrant 的随机凭据，并尝试从本机 `.env` 导入 DeepSeek Key。生成文件均被 Git 忽略。`prod-deploy` 构建镜像、等待基础设施健康、执行 Alembic 迁移、启动应用并运行冒烟测试。

默认入口为 `http://127.0.0.1:8080`。生产 API 文档已关闭，`/api/v1/health` 检查进程存活，`/api/v1/ready` 检查依赖就绪。

## 日常发布与巡检

```bash
make prod-deploy
make prod-ps
make prod-smoke
make prod-logs
```

发布前先执行 `make prod-backup`。迁移是一次性容器，必须以退出码 0 结束后 API、Worker 和 Beat 才会启动。发布后确认全部常驻服务为 `healthy`，并在 Agent 页面确认运行环境为 `live`。模型调用失败时业务会进入受控 fallback，需结合运行记录中的 `model_error` 排查，不能把 fallback 当成实时模型成功。

## 备份与恢复

备份脚本进入维护窗口，停止所有写入后归档五个固定数据卷，生成 `SHA256SUMS` 和镜像清单，再自动拉起服务：

```bash
make prod-backup
```

默认备份位于 `backups/<UTC 时间戳>/`。应将备份目录、`.env.production` 和 `secrets/production/` 分开加密保存到异地主机或对象存储；数据卷备份本身不包含运行密钥。

恢复会覆盖当前五个生产数据卷，必须使用备份目录名进行显式确认：

```bash
BACKUP_DIR=backups/20260718T091032Z
CONFIRM=restore:20260718T091032Z
make prod-restore BACKUP_DIR="$BACKUP_DIR" CONFIRM="$CONFIRM"
```

恢复脚本先校验所有归档的 SHA-256，再停止服务、清空并恢复数据卷，最后等待全栈健康并运行冒烟测试。恢复前保留当前数据的另一份备份。

## 密钥轮换

DeepSeek Key 可原子替换 `secrets/production/deepseek_api_key` 后重建后端容器：

```bash
chmod 600 secrets/production/deepseek_api_key
docker compose --env-file .env.production -f compose.production.yaml up -d --force-recreate api worker beat
make prod-smoke
```

数据库、中间件凭据与数据卷绑定，不能只修改 `.env.production` 后重启。应先备份，在维护窗口内按各服务的官方流程同步更新服务端凭据和应用配置。`make prod-init --force` 不应用于已有数据卷的原地轮换。

## 回滚

应用回滚以不可变镜像标签为单位。发布时将 `MEDREG_IMAGE_TAG` 设置为版本号或提交哈希并预先构建或推送镜像；需要回滚时恢复旧标签并执行 `docker compose ... up -d --no-build --wait`。如果新版本执行了不可逆迁移，必须先恢复发布前数据备份，再启动旧镜像。

单机故障会同时影响所有服务。高可用阶段应迁移到托管 PostgreSQL、Redis 和对象存储，部署独立 Qdrant、Neo4j、外部任务调度与集中可观测平台，并制定 RPO、RTO、备份保留和季度恢复演练制度。
