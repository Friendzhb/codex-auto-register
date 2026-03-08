# ChatGPT 批量自动注册工具

> 使用 MoeMail 临时邮箱，并发自动注册 ChatGPT 账号与提取授权凭证

## 功能

- 📨 自动生成 MoeMail 临时邮箱并接收 OpenAI OTP 验证码
- ⚡ 高并发支持，雪球滚出海量独立账号
- 🔄 自动处理 OAuth 登录协议及环境检测
- ☁️ 支持代理配置防止 IP 风控
- 🛡️ 集成 FlareSolverr 自动绕过 Cloudflare 人机验证（CF Clearance + 浏览器指纹 + User-Agent）
- 📤 提取出极其符合业务标准 `auth.json` 结构的凭证，可直通下游面板

## 环境

```bash
pip install curl_cffi
```

## 配置 (config.json)

```json
{
  "total_accounts": 5,
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

| 配置项                          | 说明                                            |
| ------------------------------- | ----------------------------------------------- |
| total_accounts                  | 注册账号数量                                    |
| moemail_api_url                 | MoeMail API 地址                                |
| moemail_api_key                 | MoeMail API Key                                 |
| moemail_domain                  | MoeMail 邮箱域名                                |
| proxy                           | 代理地址 (可选，防止主IP被墙。推荐使用)         |
| flaresolverr_url                | FlareSolverr 服务地址（留空则禁用）             |
| flaresolverr_refresh_interval   | CF Clearance 刷新间隔（秒），默认 600           |
| flaresolverr_timeout            | Cloudflare 挑战超时（秒），默认 60              |
| output_file                     | 纯文本格式输出的文件名                          |
| enable_oauth                    | 开启提取下游面板用的全量 Auth token（必需）     |

## FlareSolverr 配置

本工具支持通过本地 [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) 服务自动绕过 Cloudflare 人机验证，
获取 `cf_clearance` cookie、浏览器指纹及 User-Agent，无需手动干预。

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

> 当 `flaresolverr_url` 留空时，工具退回到 curl_cffi 的内置浏览器指纹模式（仍可正常运行）。

## CPA 面板集成 (可选)

注册完成及跑通授权后，工具可将账号直推至内部管理的 CPA：

| 配置项           | 说明                                | 参考                           |
| ---------------- | ----------------------------------- | ------------------------------ |
| upload_api_url   | CPA 面板上传 API 地址（不传则留空） | https://help.router-for.me/cn/ |
| upload_api_token | CPA 面板登录密码                    | 你的 CPA 面板密码              |

> 该操作若留空则不执行推流网络请求，仅在本地生成产物

## 使用

```bash
python chatgpt_register.py
```

## 产出物结构

工具跑完后，除传统的文本外，现在会严格输出高标准的自动投喂 JSON 文件到工作目录：

1. **总账户数据追踪集成**: `registered_accounts.json`
   - 以数组呈现，每个单元包含：`id`, `email`, `tokens`, `created_at`, `last_used`
2. **每账号单独立属隔离源**: `codex_tokens/{email}/auth.json`
   - 精简内容：`tokens.id_token`, `tokens.access_token`, `tokens.refresh_token`

## 目录结构

```
chatgpt_register/
├── chatgpt_register.py      # 主程序
├── config.json              # 配置文件
├── README.md                # 本文档
├── registered_accounts.json # 全局聚合产出账号
├── codex_tokens/            # （每个账号一个文件夹 auth.json）
│   ├── account_a@doma.in/
│   │   └── auth.json
├── registered_accounts.txt  # 传统简单输出列表
├── ak.txt                   # Access Keys 流
└── rk.txt                   # Refresh Keys 流
```

## 注意事项

- **强风控警告**：必须保持有效节点注册以避密封 IP。
- 建议配合 FlareSolverr 使用，自动处理 Cloudflare 挑战，无需手动管理 cf_clearance。
- FlareSolverr 与 curl_cffi 浏览器指纹可叠加使用，提升成功率。
