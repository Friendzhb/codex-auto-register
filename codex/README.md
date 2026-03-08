# Codex 协议密钥生成工具

> 为 ChatGPT 注册生成 Codex 协议所需的 Access Key 和 Refresh Key

## 功能

- 🔑 自动生成 Access Key (ak)
- 🔄 自动生成 Refresh Key (rk)
- 📤 支持上传到 Codex / CPA 面板
- ⚡ 支持并发生成
- 🛡️ 集成 FlareSolverr 自动绕过 Cloudflare 人机验证（CF Clearance + User-Agent）

## 配置 (config.json)

```json
{
  "total_accounts": 800,
  "concurrent_workers": 8,
  "headless": false,
  "proxy": "http://127.0.0.1:7890",
  "moemail_api_url": "https://mail.zhouhongbin.top",
  "moemail_api_key": "你的 MoeMail API Key",
  "moemail_domain": "moemail.app",
  "moemail_expiry_time": 3600000,
  "flaresolverr_url": "http://localhost:8191",
  "flaresolverr_refresh_interval": 600,
  "flaresolverr_timeout": 60,
  "upload_api_url": "https://你的CPA地址/v0/management/auth-files",
  "upload_api_token": "你的CPA密码",
  "cli_proxy_api_base": "你的CPA基础URL",
  "cli_proxy_management_url": "http://你的CPA地址/management.html#/oauth",
  "cli_proxy_password": "你的CPA密码"
}
```

| 配置项                          | 说明                                               |
| ------------------------------- | -------------------------------------------------- |
| total_accounts                  | 生成账号数量                                       |
| concurrent_workers              | 并发数                                             |
| proxy                           | 代理地址                                           |
| moemail_api_key                 | MoeMail API Key（优先使用）                        |
| moemail_domain                  | MoeMail 邮箱域名                                   |
| flaresolverr_url                | FlareSolverr 服务地址（留空则禁用）                |
| flaresolverr_refresh_interval   | CF Clearance 刷新间隔（秒），默认 600              |
| flaresolverr_timeout            | Cloudflare 挑战超时（秒），默认 60                 |
| upload_api_url                  | CPA 上传 API                                       |
| cli_proxy_api_base              | CPA CLI 代理 API                                   |

> 默认已切换为与 ChatGPT 脚本一致的 MoeMail 临时邮箱服务；若未配置 `moemail_api_key`，代码会继续回退使用旧的 Cloudflare Worker 配置，此时需要额外填写 `cf_worker_domain`、`cf_email_domain`、`cf_admin_password`。

## FlareSolverr 配置

本工具支持通过本地 [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) 服务自动绕过 Cloudflare 人机验证，
获取 `cf_clearance` cookie 及 User-Agent，无需手动干预。

### 部署 FlareSolverr（Docker，一键启动）

```bash
docker run -d \
  --name flaresolverr \
  -p 8191:8191 \
  -e LOG_LEVEL=info \
  --restart unless-stopped \
  ghcr.io/flaresolverr/flaresolverr:latest
```

### 参数说明

| 参数                            | 说明                                              | 默认值                  |
| ------------------------------- | ------------------------------------------------- | ----------------------- |
| `flaresolverr_url`              | FlareSolverr 服务地址（留空=禁用）                | `http://localhost:8191` |
| `flaresolverr_refresh_interval` | CF Clearance 缓存有效期（秒），到期后自动刷新     | `600`                   |
| `flaresolverr_timeout`          | Cloudflare 挑战最大等待时间（秒）                 | `60`                    |

### 环境变量覆盖

| 环境变量                        | 对应配置项                        |
| ------------------------------- | --------------------------------- |
| `FLARESOLVERR_URL`              | `flaresolverr_url`                |
| `FLARESOLVERR_REFRESH_INTERVAL` | `flaresolverr_refresh_interval`   |
| `FLARESOLVERR_TIMEOUT`          | `flaresolverr_timeout`            |

> 当 `flaresolverr_url` 留空时，工具以纯 HTTP 模式运行（仍可正常运行，但无 CF 清除凭证）。

## 使用

```bash
python protocol_keygen.py
```

## 输出

- `ak.txt` - Access Keys
- `rk.txt` - Refresh Keys
- `registered_accounts.csv` - CSV 格式账号

## 接入 CPA 面板

生成后可以自动上传到 CPA 面板：

1. 部署 CPA 面板: https://github.com/dongshuyan/CPA-Dashboard
2. 配置 `upload_api_url` 和 `upload_api_token`
3. 运行后自动上传

> 文档: https://help.router-for.me/cn/
