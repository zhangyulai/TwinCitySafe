# 演示数据库准备与保留

比赛版本使用 `.env` 指定的本地 PostgreSQL。`prepare-demo.sh` 只执行迁移、幂等资产 seed、模型校验和前端构建；不清空表，不修改已有模型，不自动启动事故。`DEMO_BUILD=0 ./prepare-demo.sh` 可跳过构建。

已有数据库直接运行准备脚本即可；P01/P02/P03、34 节点、32 管段、10 阀门和三个应急模板缺失时才新增。已有资产修改、关闭事件、工单、快照和报告保留。准备脚本不会恢复关闭的阀门。

如需独立的干净比赛库，请先手动创建空 PostgreSQL 数据库，再将 `.env` 的 `POSTGRES_DB`（或 `DATABASE_URL`）明确指向它，随后运行 `./prepare-demo.sh`。不要将准备新库与覆盖已有库混为一件事。比赛前应保留至少一个真实完成的 Flood 和 Leak 档案；它们由完整演示闭环生成，启动脚本不会伪造。

运行 `./start-demo.sh` 后，在演示控制中确认“将重置当前软件演示状态，但不会删除历史事故档案。”恢复到无活动事故、晴天、1×、P01/P02 备用、P03 正常运行、十个演示阀门开启、入口开放。原未完成事故记为 ABORTED，正式 CLOSED 档案不改变。Close 与 Demo Reset 不同：Close 保留积水、阀门隔离和服务影响，Demo Reset 才恢复本地演示资产。

## 只读检查

```bash
backend/.venv/bin/python scripts/prepare-demo.py --check-only --json
backend/.venv/bin/python scripts/demo-runtime-check.py
```

前者读取迁移、模型、数据库资产；后者检查 HTTP、同源代理和真实 WebSocket 首帧。页面系统自检还需要确认当前浏览器的连接和 WebGL 上下文。模型缺失允许降级，准备与启动都不会重新训练；恢复随项目提供的模型文件后重启后端。

## 备份与显式恢复

准备与启动不会备份或恢复数据库。可选脚本需要与服务端兼容的 `pg_dump` / `pg_restore`；若使用本项目 Compose 数据库，可明确设置 `DEMO_DB_CLIENT=compose` 使用容器内客户端。比赛前离线准备好客户端，不会自动安装或拉取镜像。

```bash
./scripts/backup-demo-db.sh /path/to/twincitysafe-demo.dump
# 使用项目数据库容器时：
DEMO_DB_CLIENT=compose ./scripts/backup-demo-db.sh /path/to/twincitysafe-demo.dump
```

备份路径已存在时拒绝覆盖。密码只通过子进程环境传递，不打印到终端。

恢复会替换目标数据库对象和历史：先停止前后端、备份当前库，并核对 `.env` 的数据库目标。交互恢复要求输入准确数据库名；非交互必须显式传 `--confirm-replace`，不能因为执行准备/启动而自动覆盖。

```bash
./scripts/restore-demo-db.sh /path/to/twincitysafe-demo.dump
# 非交互时必须由操作者明确授权：
./scripts/restore-demo-db.sh /path/to/twincitysafe-demo.dump --confirm-replace
./prepare-demo.sh
```

恢复使用 PostgreSQL custom 格式及单事务。恢复失败不会自动尝试删除数据库或创建新库。模型文件、前端资源不在数据库备份中，需要一起保留完整项目目录。
