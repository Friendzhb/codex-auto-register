# ChatGPT 批量自动注册工具

> 使用 Cloudflare 域名 Catch-All 路由 + QQ邮箱 IMAP，并发自动注册 ChatGPT 账号与提取授权凭证

## 功能

- 📨 自动本地生成别名邮箱并通过 Cloudflare 路由至您的主信箱
- 📥 自动登陆 QQ 邮箱 IMAP 获取 OpenAI OTP 验证码
- ⚡ 高并发支持，雪球滚出海量独立账号
- 🔄 自动处理 OAuth 登录协议及环境检测
- ☁️ 支持代理配置防止 IP 风控
- 📤 提取出极其符合业务标准 `auth.json` 结构的凭证，可直通下游面板

## 环境

```bash
pip install curl_cffi
```

## 配置 (config.json)

```json
{
  "total_accounts": 5,
  "qq_email": "你的qqy邮箱",
  "qq_imap_password": "你的QQ邮箱16位IMAP授权码",
  "forward_domain": "你的域名",
  "proxy": "http://127.0.0.1:7890",
  "output_file": "registered_accounts.txt",
  "enable_oauth": true,
  "oauth_redirect_uri": "http://localhost:1455/auth/callback"
}
```

| 配置项           | 说明                                              |
| ---------------- | ------------------------------------------------- |
| total_accounts   | 注册账号数量                                      |
| qq_email         | 接收转发验证码信件的QQ邮箱地址                    |
| qq_imap_password | 该QQ邮箱开启的 16位 IMAP 专用授权码               |
| forward_domain   | 在Cloudflare绑定的域名路由（如 `@youdomain.com`） |
| proxy            | 代理地址 (可选，防止主IP被墙。推荐使用)           |
| output_file      | 纯文本格式输出的文件名                            |
| enable_oauth     | 开启提取下游面板用的全量 Auth token（必需）       |

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
- Cloudflare Catch-All (电子路由) 设置需**真实绑定**到您预设的 QQ 邮箱以产生流转。
- QQ 邮箱需至 “设置 -> 账户 -> IMAP服务” 进行手签开启并生成随机授权白条。
