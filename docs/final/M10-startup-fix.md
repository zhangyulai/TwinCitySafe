# 正式启动时发现并修正的检查问题

第一次停止开发服务后，`start-demo.sh` 的预检查显示 `Frontend port 5173 is already in use`，同时 curl 连接拒绝；实际服务已经停止，旧 TCP 连接尚处 TIME_WAIT。

修正 `demo-runtime-check.py` 的临时 bind 探针，启用与服务端一致的 SO_REUSEADDR，避免把可复用的 TIME_WAIT 当作监听占用。未使用 SO_REUSEPORT，没有忽略真正监听进程。

实际重新启动后 Database / Models / Backend / Frontend / WebSocket 全部 Ready。再次对已启动的8000端口执行检查仍以非零退出并明确提示占用。未重启数据库、未清理任何历史。该修正仅涉及启动预检查，不修改核心业务或模型。
