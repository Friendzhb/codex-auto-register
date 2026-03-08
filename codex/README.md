# Codex 协议密钥生成工具 (protocol_keygen)

> 为 ChatGPT 注册生成 Codex 协议所需的 Access Key 和 Refresh Key

## 功能

- 🔑 自动生成 Access Key (ak) 和 Refresh Key (rk)
- 📤 支持上传到 Codex / CPA 面板
- ⚡ 支持并发生成
- 🛡️ 集成 FlareSolverr 自动绕过 Cloudflare 人机验证

---

## Linux 服务器部署

### 1. 系统要求

| 组件   | 最低版本 |
| ------ | -------- |
| Python | 3.10+    |
| pip    | 22+      |

### 2. 进入目录并安装依赖

```bash
cd codex-auto-register/codex
pip3 install -r requirements.txt
```

### 3. 编辑配置

```bash
cp config.json config.json.bak
nano config.json
```

**必填项**（二选一）：

- **MoeMail（推荐）**：填写 `moemail_api_key`
- **Cloudflare Worker（旧方式）**：填写 `cf_worker_domain` + `cf_admin_password`

### 4. 运行

**交互 / 前台运行**：

```bash
python3 protocol_keygen.py
```

**非交互后台运行（nohup）**：

```bash
nohup python3 protocol_keygen.py > run.log 2>&1 &
echo "PID: $!"
tail -f run.log
```

**screen / tmux 会话**（断开 SSH 后继续运行）：

```bash
# screen
screen -S keygen
python3 protocol_keygen.py
# Ctrl+A D → 退出 screen，程序继续运行
# screen -r keygen → 重连

# tmux
tmux new -s keygen
python3 protocol_keygen.py
# Ctrl+B D → 退出 tmux，程序继续运行
# tmux attach -t keygen → 重连
```

### 5. 常见部署问题

| 现象 | 原因 | 解决办法 |
| ---- | ---- | -------- |
| `❌ 启动失败 — 缺少邮箱服务配置` | 未填写 API Key | 填写 `moemail_api_key` 字段 |
| `❌ config.json 解析失败` | JSON 格式错误 | 执行 `python3 -m json.tool config.json` 检查 |
| `ModuleNotFoundError: requests` | 未安装依赖 | 执行 `pip3 install -r requirements.txt` |
| 注册失败率高 | IP 被 CF 拦截 | 配置 `proxy` 或启动 FlareSolverr |
| SSH 断开后程序停止 | 未用 screen/tmux | 用 `nohup` 或 `screen`/`tmux` 运行 |

---

## 配置 (config.json)

```json
{
  "total_accounts": 800,
  "concurrent_workers": 8,
  "proxy": "",
  "moemail_api_url": "https://mail.zhouhongbin.top",
  "moemail_api_key": "你的 MoeMail API Key",
  "moemail_domain": "moemail.app",
  "moemail_expiry_time": 3600000,
  "flaresolverr_url": "http://localhost:8191",
  "flaresolverr_refresh_interval": 600,
  "flaresolverr_timeout": 60,
  "upload_api_url": "",
  "upload_api_token": "",
  "accounts_file": "accounts.txt",
  "csv_file": "registered_accounts.csv",
  "ak_file": "ak.txt",
  "rk_file": "rk.txt"
}
```

| 配置项                          | 说明                                               |
| ------------------------------- | -------------------------------------------------- |
| `total_accounts`                | 生成账号数量                                       |
| `concurrent_workers`            | 并发线程数                                         |
| `proxy`                         | 代理地址                                           |
| `moemail_api_key`               | MoeMail API Key（**推荐填写**）                    |
| `flaresolverr_url`              | FlareSolverr 服务地址（留空则禁用）                |
| `flaresolverr_refresh_interval` | CF Clearance 刷新间隔（秒），默认 600              |
| `flaresolverr_timeout`          | Cloudflare 挑战超时（秒），默认 60                 |
| `upload_api_url`                | CPA 上传 API（留空则不上传）                       |

### 环境变量覆盖（优先级高于 config.json）

```bash
export MOEMAIL_API_KEY=your_key
export FLARESOLVERR_URL=http://localhost:8191
# 输出文件路径也可以通过环境变量指定
export AK_FILE=/data/output/ak.txt
export RK_FILE=/data/output/rk.txt
export ACCOUNTS_FILE=/data/output/accounts.txt
export CSV_FILE=/data/output/registered_accounts.csv
export TOKEN_OUTPUT_DIR=/data/output/tokens
```

## FlareSolverr 配置

本工具支持通过本地 [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) 服务自动绕过 Cloudflare 人机验证。

### 部署 FlareSolverr

```bash
docker run -d \
  --name flaresolverr \
  -p 8191:8191 \
  -e LOG_LEVEL=info \
  --restart unless-stopped \
  ghcr.io/flaresolverr/flaresolverr:latest
```

> 当 `flaresolverr_url` 留空时，工具以纯 HTTP 模式运行（仍可工作，但无 CF Clearance）。

## 接入 CPA 面板（可选）

```json
{
  "upload_api_url": "https://your-cpa/v0/management/auth-files",
  "upload_api_token": "your_cpa_password"
}
```

文档：https://help.router-for.me/cn/

## 输出文件

| 文件                      | 内容                 |
| ------------------------- | -------------------- |
| `ak.txt`                  | Access Token 列表    |
| `rk.txt`                  | Refresh Token 列表   |
| `accounts.txt`            | 账号:密码 列表       |
| `registered_accounts.csv` | CSV 格式账号数据     |
| `{email}.json`            | 单账号完整 Token     |
