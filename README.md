# ChatGPT 批量自动注册工具

> 使用 MoeMail 临时邮箱，并发自动注册 ChatGPT 账号与提取授权凭证

## 功能

- 📨 自动生成 MoeMail 临时邮箱并接收 OpenAI OTP 验证码
- ⚡ 高并发支持，雪球滚出海量独立账号
- 🔄 自动处理 OAuth 登录协议及环境检测
- ☁️ 支持代理配置防止 IP 风控
- 🛡️ 集成 FlareSolverr 自动绕过 Cloudflare 人机验证（CF Clearance + 浏览器指纹 + User-Agent）
- �� 提取出极其符合业务标准 `auth.json` 结构的凭证，可直通下游面板

---

## Linux 服务器部署

### 1. 系统要求

| 组件        | 最低版本 |
| ----------- | -------- |
| Python      | 3.8+     |
| pip         | 19+      |
| 网络        | 能访问 OpenAI / MoeMail API（可走代理） |

### 2. 克隆代码

```bash
git clone https://github.com/Friendzhb/codex-auto-register.git
cd codex-auto-register
```

### 3. 升级 pip（推荐）

如果 pip 版本过旧（低于 19），建议先升级，否则可能出现找不到依赖包的错误：

```bash
# 方式一：使用 pip 自升级（推荐）
python3 -m pip install --upgrade pip

# 方式二：使用系统包管理器（CentOS/RHEL）
yum install -y python3-pip

# 方式三：使用系统包管理器（Debian/Ubuntu）
apt-get install -y python3-pip
```

升级后确认版本：

```bash
pip3 --version
```

### 4. 安装依赖

```bash
# 安装所有依赖（推荐，一条命令搞定）
pip3 install -r requirements.txt

# 若上述命令报 "Could not find a version" 错误，尝试先升级 pip 再安装：
python3 -m pip install --upgrade pip
pip3 install -r requirements.txt

# 若使用虚拟环境（推荐隔离环境）：
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. 编辑配置

```bash
cp config.json config.json.bak   # 先备份
nano config.json                  # 或用 vim / vi
```

**必填项**：

| 字段                 | 说明                                  |
| -------------------- | ------------------------------------- |
| `moemail_api_key`    | MoeMail API Key（必须，否则无法收信） |
| `total_accounts`     | 本次注册账号数量                      |
| `concurrent_workers` | 并发线程数（建议 1–5，视服务器带宽）  |
| `proxy`              | 代理地址，如 `http://127.0.0.1:7890`（无代理留空） |

### 6. （可选）启动 FlareSolverr

若 OpenAI 触发 Cloudflare 验证，先在本机启动 FlareSolverr：

```bash
# 需要已安装 Docker
docker run -d \
  --name flaresolverr \
  -p 8191:8191 \
  -e LOG_LEVEL=info \
  --restart unless-stopped \
  ghcr.io/flaresolverr/flaresolverr:latest
```

然后在 `config.json` 中设置：

```json
"flaresolverr_url": "http://localhost:8191"
```

不需要 FlareSolverr 时将该字段留空即可。

### 7. 运行

**交互模式**（推荐首次测试）：

```bash
python3 chatgpt_register.py
```

**非交互/后台模式**（参数全从 config.json 读取，适合定时任务或 `nohup`）：

```bash
# nohup 后台运行，日志写到 run.log
nohup python3 chatgpt_register.py > run.log 2>&1 &
echo "PID: $!"

# 实时查看日志
tail -f run.log
```

**screen / tmux 会话**（断开 SSH 后继续运行）：

```bash
# screen
screen -S register
python3 chatgpt_register.py
# Ctrl+A D  →  退出 screen，程序在后台继续
# screen -r register  →  重连

# tmux
tmux new -s register
python3 chatgpt_register.py
# Ctrl+B D  →  退出 tmux，程序在后台继续
# tmux attach -t register  →  重连
```

### 8. 常见部署问题

| 现象 | 原因 | 解决办法 |
| ---- | ---- | -------- |
| `❌ 启动失败 — 缺少 MOEMAIL_API_KEY` | config.json 未填 API Key | 填写 `moemail_api_key` 字段 |
| `❌ config.json 解析失败` | JSON 格式错误 | 执行 `python3 -m json.tool config.json` 检查 |
| `ModuleNotFoundError: curl_cffi` | 未安装依赖 | 执行 `pip3 install -r requirements.txt` |
| `Could not find a version that satisfies the requirement requests>=...` | pip 版本过旧，无法解析新版包 | 先升级 pip：`python3 -m pip install --upgrade pip`，再重新安装依赖 |
| `No matching distribution found for urllib3>=...` | pip 版本过旧或镜像源缺少新版 | 升级 pip 或换用 pypi 官方源：`pip3 install -r requirements.txt -i https://pypi.org/simple/` |
| 注册失败率高 | IP 被 CF 拦截 | 配置 `proxy` 或启动 FlareSolverr |
| SSH 断开后程序停止 | 未用 screen/tmux | 用 `nohup` 或 `screen`/`tmux` 运行 |

---

## 配置 (config.json)

```json
{
  "total_accounts": 5,
  "concurrent_workers": 3,
  "moemail_api_url": "https://mail.zhouhongbin.top",
  "moemail_api_key": "YOUR_API_KEY",
  "moemail_domain": "moemail.app",
  "moemail_expiry_time": 3600000,
  "proxy": "",
  "flaresolverr_url": "http://localhost:8191",
  "flaresolverr_refresh_interval": 600,
  "flaresolverr_timeout": 60,
  "output_file": "registered_accounts.txt",
  "enable_oauth": true,
  "oauth_redirect_uri": "http://localhost:1455/auth/callback"
}
```

| 配置项                          | 说明                                                  |
| ------------------------------- | ----------------------------------------------------- |
| `total_accounts`                | 注册账号数量                                          |
| `concurrent_workers`            | 并发线程数（同时注册的账号数）                        |
| `moemail_api_url`               | MoeMail API 地址                                      |
| `moemail_api_key`               | MoeMail API Key（**必填**）                           |
| `moemail_domain`                | MoeMail 邮箱域名                                      |
| `proxy`                         | 代理地址（可选，防止主 IP 被风控）                    |
| `flaresolverr_url`              | FlareSolverr 服务地址（留空则禁用）                   |
| `flaresolverr_refresh_interval` | CF Clearance 刷新间隔（秒），默认 600                 |
| `flaresolverr_timeout`          | Cloudflare 挑战超时（秒），默认 60                    |
| `output_file`                   | 账号明文输出文件名                                    |
| `enable_oauth`                  | 是否同步获取 Codex OAuth Token                        |

### 环境变量覆盖（优先级高于 config.json）

所有配置项均可通过同名大写环境变量覆盖，无需修改 config.json：

```bash
export MOEMAIL_API_KEY=your_key
export TOTAL_ACCOUNTS=10
export CONCURRENT_WORKERS=3
export PROXY=http://127.0.0.1:7890
export FLARESOLVERR_URL=http://localhost:8191
```

## FlareSolverr 配置

本工具支持通过本地 [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) 服务自动绕过 Cloudflare 人机验证，
获取 `cf_clearance` cookie、浏览器指纹及 User-Agent，无需手动干预。

| 参数                            | 说明                                              | 默认值                  |
| ------------------------------- | ------------------------------------------------- | ----------------------- |
| `flaresolverr_url`              | FlareSolverr 服务地址（留空=禁用）                | `http://localhost:8191` |
| `flaresolverr_refresh_interval` | CF Clearance 缓存有效期（秒），到期后自动刷新     | `600`                   |
| `flaresolverr_timeout`          | Cloudflare 挑战最大等待时间（秒）                 | `60`                    |

> 当 `flaresolverr_url` 留空时，工具退回到 curl_cffi 的内置浏览器指纹模式（仍可正常运行）。

## CPA 面板集成 (可选)

| 配置项           | 说明                                | 参考                           |
| ---------------- | ----------------------------------- | ------------------------------ |
| upload_api_url   | CPA 面板上传 API 地址（不传则留空） | https://help.router-for.me/cn/ |
| upload_api_token | CPA 面板登录密码                    | 你的 CPA 面板密码              |

> 该操作若留空则不执行推流网络请求，仅在本地生成产物

## 产出物结构

```
codex-auto-register/
├── chatgpt_register.py       # 主程序
├── config.json               # 配置文件
├── requirements.txt          # Python 依赖
├── registered_accounts.json  # 全局聚合产出账号（JSON 数组）
├── registered_accounts.txt   # 账号明文列表
├── codex_tokens/             # 每个账号独立 auth.json
│   └── account@domain.com/
│       └── auth.json
├── ak.txt                    # Access Token 列表
└── rk.txt                    # Refresh Token 列表
```

## 注意事项

- **强风控警告**：必须保持有效节点注册以避密封 IP。
- 建议配合 FlareSolverr 使用，自动处理 Cloudflare 挑战，无需手动管理 cf_clearance。
- FlareSolverr 与 curl_cffi 浏览器指纹可叠加使用，提升成功率。
