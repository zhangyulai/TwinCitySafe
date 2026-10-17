#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
[[ -f .env ]] || { cp .env.example .env; echo "已创建本地 .env，请按需修改数据库配置。"; }
[[ -x backend/.venv/bin/python ]] || { echo "请先按照 README 创建 backend/.venv 并安装后端依赖。"; exit 1; }
[[ -d frontend/node_modules ]] || { echo "请先执行：cd frontend && npm ci"; exit 1; }
if ! backend/.venv/bin/python scripts/check-db.py; then
  if [[ "${START_POSTGRES:-0}" == "1" ]] && command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
    docker compose up -d --wait postgres || echo "数据库自动启动失败，请检查 Docker 与 .env。"
    backend/.venv/bin/python scripts/check-db.py || echo "数据库仍未就绪；API 可启动，数据库相关功能不可用。"
  else
    echo "请启动 PostgreSQL；使用项目 Docker 数据库时执行 docker compose up -d --wait postgres。"
    echo "也可使用 START_POSTGRES=1 ./start-dev.sh 自动启动项目数据库。"
  fi
fi
children=()
cleanup() {
  trap - EXIT INT TERM
  for pid in "${children[@]}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  wait || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
command -v setsid >/dev/null || { echo "此脚本需要 Linux setsid；其他系统请按 README 分别启动前后端。"; exit 1; }
setsid backend/.venv/bin/python scripts/start-backend.py &
children+=("$!")
(cd frontend && exec setsid npm run dev) &
children+=("$!")
echo "前后端正在启动，访问地址见 Vite 输出；Ctrl+C 停止两项服务。PostgreSQL 将继续运行。"
wait -n "${children[@]}"
