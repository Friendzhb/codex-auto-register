"""
ChatGPT 批量自动注册工具 (并发版) - MoeMail 临时邮箱版
依赖: pip install curl_cffi
功能: 使用 mail.zhouhongbin.top 临时邮箱 API 自动接收验证码，并发自动注册 ChatGPT 账号
"""

import os
import re
import uuid
import json
import random
import string
import time
import sys
import threading
import traceback
import secrets
import hashlib
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs, urlencode

try:
    from curl_cffi import requests as curl_requests
    from importlib.metadata import version as _pkg_version, PackageNotFoundError as _PkgNotFound
    try:
        _installed = tuple(int(x) for x in _pkg_version("curl_cffi").split(".")[:3])
    except (_PkgNotFound, ValueError):
        _installed = (0, 0, 0)
    if _installed < (0, 7, 0):
        raise ImportError(f"curl_cffi version too old: {_installed}")
except ImportError:
    print(
        "\n❌ 缺少依赖 curl_cffi（或版本过低，需 >=0.7.0）\n"
        "   国内镜像源（如阿里云）可能不含此包的最新版，请改用官方 PyPI 源安装：\n"
        "     pip3 install -r requirements.txt -i https://pypi.org/simple/\n"
        "   若只想单独安装 curl_cffi：\n"
        "     pip3 install 'curl_cffi>=0.7.0' -i https://pypi.org/simple/\n",
        file=sys.stderr,
    )
    sys.exit(1)

# ================= 加载配置 =================
def _load_config():
    """从 config.json 加载配置，环境变量优先级更高"""
    config = {
        "total_accounts": 3,
        "concurrent_workers": 3,
        "moemail_api_url": "https://mail.zhouhongbin.top",
        "moemail_api_key": "",
        "moemail_domain": "moemail.app",
        "moemail_expiry_time": 3600000,
        "proxy": "",
        "flaresolverr_url": "",
        "flaresolverr_refresh_interval": 600,
        "flaresolverr_timeout": 60,
        "output_file": "registered_accounts.txt",
        "enable_oauth": True,
        "oauth_required": True,
        "oauth_issuer": "https://auth.openai.com",
        "oauth_client_id": "app_EMoamEEZ73f0CkXaXp7hrann",
        "oauth_redirect_uri": "http://localhost:1455/auth/callback",
        "ak_file": "ak.txt",
        "rk_file": "rk.txt",
        "token_json_dir": "codex_tokens",
        "upload_api_url": "",
        "upload_api_token": "",
    }

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_config = json.load(f)
                config.update(file_config)
        except json.JSONDecodeError as e:
            print(
                f"\n❌ config.json 解析失败: {e}\n"
                f"   文件: {config_path}\n"
                f"   请用以下命令验证 JSON 格式:\n"
                f"     python3 -m json.tool config.json\n",
                file=sys.stderr,
            )
            sys.exit(1)
        except Exception as e:
            print(f"⚠️ 加载 config.json 失败: {e}", file=sys.stderr)

    # 环境变量优先级更高
    config["moemail_api_url"] = os.environ.get("MOEMAIL_API_URL", config["moemail_api_url"])
    config["moemail_api_key"] = os.environ.get("MOEMAIL_API_KEY", config["moemail_api_key"])
    config["moemail_domain"] = os.environ.get("MOEMAIL_DOMAIN", config["moemail_domain"])
    try:
        config["moemail_expiry_time"] = int(os.environ.get("MOEMAIL_EXPIRY_TIME", config["moemail_expiry_time"]))
    except (ValueError, TypeError):
        print("⚠️ MOEMAIL_EXPIRY_TIME 格式无效，使用默认值 3600000", file=sys.stderr)
        config["moemail_expiry_time"] = 3600000
    config["proxy"] = os.environ.get("PROXY", config["proxy"])
    try:
        config["total_accounts"] = int(os.environ.get("TOTAL_ACCOUNTS", config["total_accounts"]))
    except (ValueError, TypeError):
        config["total_accounts"] = 3
    try:
        config["concurrent_workers"] = int(os.environ.get("CONCURRENT_WORKERS", config["concurrent_workers"]))
    except (ValueError, TypeError):
        config["concurrent_workers"] = 3
    config["enable_oauth"] = os.environ.get("ENABLE_OAUTH", config["enable_oauth"])
    config["oauth_required"] = os.environ.get("OAUTH_REQUIRED", config["oauth_required"])
    config["oauth_issuer"] = os.environ.get("OAUTH_ISSUER", config["oauth_issuer"])
    config["oauth_client_id"] = os.environ.get("OAUTH_CLIENT_ID", config["oauth_client_id"])
    config["oauth_redirect_uri"] = os.environ.get("OAUTH_REDIRECT_URI", config["oauth_redirect_uri"])
    config["ak_file"] = os.environ.get("AK_FILE", config["ak_file"])
    config["rk_file"] = os.environ.get("RK_FILE", config["rk_file"])
    config["token_json_dir"] = os.environ.get("TOKEN_JSON_DIR", config["token_json_dir"])
    config["upload_api_url"] = os.environ.get("UPLOAD_API_URL", config["upload_api_url"])
    config["upload_api_token"] = os.environ.get("UPLOAD_API_TOKEN", config["upload_api_token"])
    config["flaresolverr_url"] = os.environ.get("FLARESOLVERR_URL", config["flaresolverr_url"])
    try:
        config["flaresolverr_refresh_interval"] = int(
            os.environ.get("FLARESOLVERR_REFRESH_INTERVAL", config["flaresolverr_refresh_interval"])
        )
    except (ValueError, TypeError):
        config["flaresolverr_refresh_interval"] = 600
    try:
        config["flaresolverr_timeout"] = int(
            os.environ.get("FLARESOLVERR_TIMEOUT", config["flaresolverr_timeout"])
        )
    except (ValueError, TypeError):
        config["flaresolverr_timeout"] = 60

    return config


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


_CONFIG = _load_config()
MOEMAIL_API_URL = _CONFIG["moemail_api_url"].rstrip("/")
MOEMAIL_API_KEY = _CONFIG["moemail_api_key"]
MOEMAIL_DOMAIN = _CONFIG["moemail_domain"]
MOEMAIL_EXPIRY_TIME = _CONFIG["moemail_expiry_time"]
DEFAULT_TOTAL_ACCOUNTS = _CONFIG["total_accounts"]
DEFAULT_PROXY = _CONFIG["proxy"]
DEFAULT_OUTPUT_FILE = _CONFIG["output_file"]
ENABLE_OAUTH = _as_bool(_CONFIG.get("enable_oauth", True))
OAUTH_REQUIRED = _as_bool(_CONFIG.get("oauth_required", True))
OAUTH_ISSUER = _CONFIG["oauth_issuer"].rstrip("/")
OAUTH_CLIENT_ID = _CONFIG["oauth_client_id"]
OAUTH_REDIRECT_URI = _CONFIG["oauth_redirect_uri"]
AK_FILE = _CONFIG["ak_file"]
RK_FILE = _CONFIG["rk_file"]
TOKEN_JSON_DIR = _CONFIG["token_json_dir"]
UPLOAD_API_URL = _CONFIG["upload_api_url"]
UPLOAD_API_TOKEN = _CONFIG["upload_api_token"]
FLARESOLVERR_URL = _CONFIG.get("flaresolverr_url", "").strip()
FLARESOLVERR_REFRESH_INTERVAL = int(_CONFIG.get("flaresolverr_refresh_interval", 600))
FLARESOLVERR_TIMEOUT = int(_CONFIG.get("flaresolverr_timeout", 60))
DEFAULT_CONCURRENT_WORKERS = _CONFIG.get("concurrent_workers", 3)

_PLACEHOLDER_API_KEY = "YOUR_API_KEY"


def _eprint(*args, **kwargs):
    """将错误/警告信息输出到 stderr，确保即使 stdout 被重定向也能在终端看到。"""
    print(*args, file=sys.stderr, **kwargs)


def _validate_startup_config():
    """
    启动时校验必要的配置项。
    发现致命问题时将错误信息输出到 stderr 并以状态码 1 退出。
    """
    errors = []

    # MoeMail API Key 是必需的
    key = (MOEMAIL_API_KEY or "").strip()
    if not key or key.upper() == _PLACEHOLDER_API_KEY.upper():
        errors.append(
            "缺少 MOEMAIL_API_KEY\n"
            "     → 在 config.json 中填写:  \"moemail_api_key\": \"your_key\"\n"
            "     → 或设置环境变量:          export MOEMAIL_API_KEY=your_key"
        )

    if errors:
        _eprint("\n" + "=" * 62)
        _eprint("  ❌ 启动失败 — 配置校验未通过，请修复后重新运行")
        _eprint("=" * 62)
        for i, err in enumerate(errors, 1):
            _eprint(f"\n  [{i}] {err}")
        _eprint("\n" + "=" * 62 + "\n")
        sys.exit(1)


# _validate_startup_config() is called inside main() so interactive input
# can supply missing values before the check runs.

# 全局线程锁
_print_lock = threading.Lock()
_file_lock = threading.Lock()


# Chrome 指纹配置: impersonate 与 sec-ch-ua 必须匹配真实浏览器
_CHROME_PROFILES = [
    {
        "major": 131, "impersonate": "chrome131",
        "build": 6778, "patch_range": (69, 205),
        "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    },
    {
        "major": 133, "impersonate": "chrome133a",
        "build": 6943, "patch_range": (33, 153),
        "sec_ch_ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
    },
    {
        "major": 136, "impersonate": "chrome136",
        "build": 7103, "patch_range": (48, 175),
        "sec_ch_ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    },
    {
        "major": 142, "impersonate": "chrome142",
        "build": 7540, "patch_range": (30, 150),
        "sec_ch_ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
    },
]


def _random_chrome_version():
    profile = random.choice(_CHROME_PROFILES)
    major = profile["major"]
    build = profile["build"]
    patch = random.randint(*profile["patch_range"])
    full_ver = f"{major}.0.{build}.{patch}"
    ua = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{full_ver} Safari/537.36"
    return profile["impersonate"], major, full_ver, ua, profile["sec_ch_ua"]


# =================== FlareSolverr CF 过墙客户端 ===================

class _FlareSolverrClient:
    """
    FlareSolverr 客户端 — 通过本地 FlareSolverr 服务获取 Cloudflare CF Clearance。

    FlareSolverr 文档: https://github.com/FlareSolverr/FlareSolverr
    默认端口: 8191

    功能:
      - 调用 FlareSolverr /v1 接口获取 cf_clearance cookie 和浏览器 User-Agent
      - 按域名缓存结果，refresh_interval 秒后自动刷新
      - challenge_timeout 秒内未解决则视为失败
    """

    def __init__(self, url: str, refresh_interval: int = 600, challenge_timeout: int = 60):
        self._url = url.rstrip("/")
        self._refresh_interval = refresh_interval
        self._max_timeout_ms = challenge_timeout * 1000  # FlareSolverr 接口使用毫秒
        self._lock = threading.Lock()
        # 缓存格式: domain -> {"cookies": [...], "user_agent": str, "ts": float}
        self._cache: dict = {}

    def get_clearance(self, target_url: str):
        """
        获取目标域名的 CF Clearance 数据（cookies + User-Agent）。

        命中缓存且未超过 refresh_interval 时直接返回；
        否则通过 FlareSolverr 刷新，challenge_timeout 为最大等待秒数。

        返回: (cookies_list, user_agent_str) 或 (None, None) 表示失败
        """
        from urllib.parse import urlparse as _urlparse
        domain = _urlparse(target_url).netloc
        now = time.time()

        with self._lock:
            cached = self._cache.get(domain)
            if cached and now - cached["ts"] < self._refresh_interval:
                return cached["cookies"], cached["user_agent"]

        print(f"  🔓 [FlareSolverr] 正在获取 {domain} 的 CF Clearance（超时 {self._max_timeout_ms // 1000}s）...")
        try:
            import urllib.request as _urlreq
            payload = json.dumps(
                {"cmd": "request.get", "url": target_url, "maxTimeout": self._max_timeout_ms}
            ).encode("utf-8")
            req = _urlreq.Request(
                f"{self._url}/v1",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            http_timeout = self._max_timeout_ms / 1000 + 15  # 额外 15s 留给网络延迟和 FlareSolverr 自身开销
            with _urlreq.urlopen(req, timeout=http_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "ok":
                solution = data.get("solution", {})
                cookies = solution.get("cookies", [])
                ua = solution.get("userAgent", "")
                with self._lock:
                    self._cache[domain] = {"cookies": cookies, "user_agent": ua, "ts": time.time()}
                cf_names = [c["name"] for c in cookies if "cf_" in c.get("name", "")]
                print(
                    f"  ✅ [FlareSolverr] CF Clearance 已获取 "
                    f"(cookies={cf_names}, UA长度={len(ua)})"
                )
                return cookies, ua
            else:
                print(
                    f"  ❌ [FlareSolverr] 状态: {data.get('status')} — "
                    f"{data.get('message', '')[:200]}"
                )
        except Exception as e:
            print(f"  ❌ [FlareSolverr] 调用失败: {e}")

        return None, None

    def apply_to_session(self, session, target_url: str) -> bool:
        """
        将 CF Clearance cookie（含 cf_clearance）和 User-Agent 注入到 HTTP 会话中。

        注入后，该会话对目标域名的后续请求将自动带上 CF 验证凭证。
        User-Agent 将更新为 FlareSolverr 浏览器的 UA，以确保与 cf_clearance 一致。
        对于 curl_cffi 会话，TLS 指纹仍由 impersonate 参数负责，两者互补。

        返回: True 表示已成功注入，False 表示 FlareSolverr 不可用或未配置
        """
        from urllib.parse import urlparse as _urlparse
        domain = _urlparse(target_url).netloc

        cookies, ua = self.get_clearance(target_url)
        if not cookies and not ua:
            return False

        # 注入所有 cookie（重点是 cf_clearance）
        for c in cookies:
            name = c.get("name", "")
            value = c.get("value", "")
            cookie_domain = c.get("domain", f".{domain}")
            if name and value:
                try:
                    session.cookies.set(name, value, domain=cookie_domain)
                except Exception:
                    pass

        # 更新 User-Agent（必须与 FlareSolverr 浏览器一致，否则 CF 可能拒绝）
        if ua:
            try:
                session.headers.update({"User-Agent": ua})
            except Exception:
                try:
                    session.headers["User-Agent"] = ua
                except Exception:
                    pass

        return True


# FlareSolverr 全局实例（None 表示未启用）
# 在 main() 中通过 _init_flaresolverr() 正式初始化，
# 以便让用户在交互式提示后更新 FLARESOLVERR_URL 再初始化。
_flaresolverr = None


def _init_flaresolverr():
    """初始化（或重新初始化）全局 FlareSolverr 客户端实例。"""
    global _flaresolverr
    if FLARESOLVERR_URL:
        _flaresolverr = _FlareSolverrClient(
            FLARESOLVERR_URL, FLARESOLVERR_REFRESH_INTERVAL, FLARESOLVERR_TIMEOUT
        )
        print(f"🔓 FlareSolverr 已启用: {FLARESOLVERR_URL} "
              f"(刷新间隔 {FLARESOLVERR_REFRESH_INTERVAL}s, 挑战超时 {FLARESOLVERR_TIMEOUT}s)")
    else:
        _flaresolverr = None


def _random_delay(low=0.3, high=1.0):
    time.sleep(random.uniform(low, high))


def _make_trace_headers():
    trace_id = random.randint(10**17, 10**18 - 1)
    parent_id = random.randint(10**17, 10**18 - 1)
    tp = f"00-{uuid.uuid4().hex}-{format(parent_id, '016x')}-01"
    return {
        "traceparent": tp, "tracestate": "dd=s:1;o:rum",
        "x-datadog-origin": "rum", "x-datadog-sampling-priority": "1",
        "x-datadog-trace-id": str(trace_id), "x-datadog-parent-id": str(parent_id),
    }


def _generate_pkce():
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


class SentinelTokenGenerator:
    """纯 Python 版本 sentinel token 生成器（PoW）"""

    MAX_ATTEMPTS = 500000
    ERROR_PREFIX = "wQ8Lk5FbGpA2NcR9dShT6gYjU7VxZ4D"

    def __init__(self, device_id=None, user_agent=None):
        self.device_id = device_id or str(uuid.uuid4())
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36"
        )
        self.requirements_seed = str(random.random())
        self.sid = str(uuid.uuid4())

    @staticmethod
    def _fnv1a_32(text: str):
        h = 2166136261
        for ch in text:
            h ^= ord(ch)
            h = (h * 16777619) & 0xFFFFFFFF
        h ^= (h >> 16)
        h = (h * 2246822507) & 0xFFFFFFFF
        h ^= (h >> 13)
        h = (h * 3266489909) & 0xFFFFFFFF
        h ^= (h >> 16)
        h &= 0xFFFFFFFF
        return format(h, "08x")

    def _get_config(self):
        now_str = time.strftime(
            "%a %b %d %Y %H:%M:%S GMT+0000 (Coordinated Universal Time)",
            time.gmtime(),
        )
        perf_now = random.uniform(1000, 50000)
        time_origin = time.time() * 1000 - perf_now
        nav_prop = random.choice([
            "vendorSub", "productSub", "vendor", "maxTouchPoints",
            "scheduling", "userActivation", "doNotTrack", "geolocation",
            "connection", "plugins", "mimeTypes", "pdfViewerEnabled",
            "webkitTemporaryStorage", "webkitPersistentStorage",
            "hardwareConcurrency", "cookieEnabled", "credentials",
            "mediaDevices", "permissions", "locks", "ink",
        ])
        nav_val = f"{nav_prop}-undefined"

        return [
            "1920x1080",
            now_str,
            4294705152,
            random.random(),
            self.user_agent,
            "https://sentinel.openai.com/sentinel/20260124ceb8/sdk.js",
            None,
            None,
            "en-US",
            "en-US,en",
            random.random(),
            nav_val,
            random.choice(["location", "implementation", "URL", "documentURI", "compatMode"]),
            random.choice(["Object", "Function", "Array", "Number", "parseFloat", "undefined"]),
            perf_now,
            self.sid,
            "",
            random.choice([4, 8, 12, 16]),
            time_origin,
        ]

    @staticmethod
    def _base64_encode(data):
        raw = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return base64.b64encode(raw).decode("ascii")

    def _run_check(self, start_time, seed, difficulty, config, nonce):
        config[3] = nonce
        config[9] = round((time.time() - start_time) * 1000)
        data = self._base64_encode(config)
        hash_hex = self._fnv1a_32(seed + data)
        diff_len = len(difficulty)
        if hash_hex[:diff_len] <= difficulty:
            return data + "~S"
        return None

    def generate_token(self, seed=None, difficulty=None):
        seed = seed if seed is not None else self.requirements_seed
        difficulty = str(difficulty or "0")
        start_time = time.time()
        config = self._get_config()

        for i in range(self.MAX_ATTEMPTS):
            result = self._run_check(start_time, seed, difficulty, config, i)
            if result:
                return "gAAAAAB" + result
        return "gAAAAAB" + self.ERROR_PREFIX + self._base64_encode(str(None))

    def generate_requirements_token(self):
        config = self._get_config()
        config[3] = 1
        config[9] = round(random.uniform(5, 50))
        data = self._base64_encode(config)
        return "gAAAAAC" + data


def fetch_sentinel_challenge(session, device_id, flow="authorize_continue", user_agent=None,
                             sec_ch_ua=None, impersonate=None):
    generator = SentinelTokenGenerator(device_id=device_id, user_agent=user_agent)
    req_body = {
        "p": generator.generate_requirements_token(),
        "id": device_id,
        "flow": flow,
    }
    headers = {
        "Content-Type": "text/plain;charset=UTF-8",
        "Referer": "https://sentinel.openai.com/backend-api/sentinel/frame.html",
        "Origin": "https://sentinel.openai.com",
        "User-Agent": user_agent or "Mozilla/5.0",
        "sec-ch-ua": sec_ch_ua or '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }

    kwargs = {
        "data": json.dumps(req_body),
        "headers": headers,
        "timeout": 20,
    }
    if impersonate:
        kwargs["impersonate"] = impersonate

    try:
        resp = session.post("https://sentinel.openai.com/backend-api/sentinel/req", **kwargs)
    except Exception:
        return None

    if resp.status_code != 200:
        return None

    try:
        return resp.json()
    except Exception:
        return None


def build_sentinel_token(session, device_id, flow="authorize_continue", user_agent=None,
                         sec_ch_ua=None, impersonate=None):
    challenge = fetch_sentinel_challenge(
        session,
        device_id,
        flow=flow,
        user_agent=user_agent,
        sec_ch_ua=sec_ch_ua,
        impersonate=impersonate,
    )
    if not challenge:
        return None

    c_value = challenge.get("token", "")
    if not c_value:
        return None

    pow_data = challenge.get("proofofwork") or {}
    generator = SentinelTokenGenerator(device_id=device_id, user_agent=user_agent)

    if pow_data.get("required") and pow_data.get("seed"):
        p_value = generator.generate_token(
            seed=pow_data.get("seed"),
            difficulty=pow_data.get("difficulty", "0"),
        )
    else:
        p_value = generator.generate_requirements_token()

    return json.dumps({
        "p": p_value,
        "t": "",
        "c": c_value,
        "id": device_id,
        "flow": flow,
    }, separators=(",", ":"))


def _extract_code_from_url(url: str):
    if not url or "code=" not in url:
        return None
    try:
        return parse_qs(urlparse(url).query).get("code", [None])[0]
    except Exception:
        return None


def _decode_jwt_payload(token: str):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception:
        return {}


def _save_codex_tokens(email: str, tokens: dict):
    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    id_token = tokens.get("id_token", "")

    if access_token:
        with _file_lock:
            with open(AK_FILE, "a", encoding="utf-8") as f:
                f.write(f"{access_token}\n")

    if refresh_token:
        with _file_lock:
            with open(RK_FILE, "a", encoding="utf-8") as f:
                f.write(f"{refresh_token}\n")

    if not access_token:
        return

    payload = _decode_jwt_payload(access_token)
    auth_info = payload.get("https://api.openai.com/auth", {})
    account_id = auth_info.get("chatgpt_account_id", "")

    now_ts = int(time.time())

    # 1. 组装单条数据
    auth_data = {
        "tokens": {
            "id_token": id_token,
            "access_token": access_token,
            "refresh_token": refresh_token
        }
    }

    # 2. 保存单条 auth.json
    base_dir = os.path.dirname(os.path.abspath(__file__))
    token_dir = TOKEN_JSON_DIR if os.path.isabs(TOKEN_JSON_DIR) else os.path.join(base_dir, TOKEN_JSON_DIR)
    
    # 每个邮箱一个目录，里面放 auth.json
    account_dir = os.path.join(token_dir, email)
    os.makedirs(account_dir, exist_ok=True)
    
    token_path = os.path.join(account_dir, "auth.json")
    with _file_lock:
        with open(token_path, "w", encoding="utf-8") as f:
            json.dump(auth_data, f, indent=2, ensure_ascii=False)

    # 3. 维护全局账号数组 batch.json
    batch_file = os.path.join(base_dir, "registered_accounts.json")
    with _file_lock:
        batch_data = []
        if os.path.exists(batch_file):
            try:
                with open(batch_file, "r", encoding="utf-8") as bf:
                    batch_data = json.load(bf)
            except Exception:
                pass
        
        batch_data.append({
            "id": account_id or f"codex_{now_ts}_{random.randint(1000, 9999)}",
            "email": email,
            "tokens": {
                "id_token": id_token,
                "access_token": access_token,
                "refresh_token": refresh_token
            },
            "created_at": now_ts,
            "last_used": now_ts
        })
        
        with open(batch_file, "w", encoding="utf-8") as bf:
            json.dump(batch_data, bf, indent=2, ensure_ascii=False)

    # 4. 上传到管理平台
    if UPLOAD_API_URL:
        _upload_token_json(token_path)


def _upload_token_json(filepath):
    """上传 Token JSON 文件到 CPA 管理平台"""
    mp = None
    try:
        from curl_cffi import CurlMime

        filename = os.path.basename(filepath)
        mp = CurlMime()
        mp.addpart(
            name="file",
            content_type="application/json",
            filename=filename,
            local_path=filepath,
        )

        session = curl_requests.Session()
        if DEFAULT_PROXY:
            session.proxies = {"http": DEFAULT_PROXY, "https": DEFAULT_PROXY}

        resp = session.post(
            UPLOAD_API_URL,
            multipart=mp,
            headers={"Authorization": f"Bearer {UPLOAD_API_TOKEN}"},
            verify=False,
            timeout=30,
        )

        if resp.status_code == 200:
            with _print_lock:
                print(f"  [CPA] Token JSON 已上传到 CPA 管理平台")
        else:
            with _print_lock:
                print(f"  [CPA] 上传失败: {resp.status_code} - {resp.text[:200]}")
    except Exception as e:
        with _print_lock:
            print(f"  [CPA] 上传异常: {e}")
    finally:
        if mp:
            mp.close()


def _generate_password(length=14):
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%&*"
    pwd = [random.choice(lower), random.choice(upper),
           random.choice(digits), random.choice(special)]
    all_chars = lower + upper + digits + special
    pwd += [random.choice(all_chars) for _ in range(length - 4)]
    random.shuffle(pwd)
    return "".join(pwd)





def _random_name():
    first = random.choice([
        "James", "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia",
        "Lucas", "Mia", "Mason", "Isabella", "Logan", "Charlotte", "Alexander",
        "Amelia", "Benjamin", "Harper", "William", "Evelyn", "Henry", "Abigail",
        "Sebastian", "Emily", "Jack", "Elizabeth",
    ])
    last = random.choice([
        "Smith", "Johnson", "Brown", "Davis", "Wilson", "Moore", "Taylor",
        "Clark", "Hall", "Young", "Anderson", "Thomas", "Jackson", "White",
        "Harris", "Martin", "Thompson", "Garcia", "Robinson", "Lewis",
        "Walker", "Allen", "King", "Wright", "Scott", "Green",
    ])
    return f"{first} {last}"


def _random_birthdate():
    y = random.randint(1985, 2002)
    m = random.randint(1, 12)
    d = random.randint(1, 28)
    return f"{y}-{m:02d}-{d:02d}"


class ChatGPTRegister:
    BASE = "https://chatgpt.com"
    AUTH = "https://auth.openai.com"

    def __init__(self, proxy: str = None, tag: str = ""):
        self.tag = tag  # 线程标识，用于日志
        self.device_id = str(uuid.uuid4())
        self.auth_session_logging_id = str(uuid.uuid4())
        self.impersonate, self.chrome_major, self.chrome_full, self.ua, self.sec_ch_ua = _random_chrome_version()

        self.session = curl_requests.Session(impersonate=self.impersonate)

        self.proxy = proxy
        if self.proxy:
            self.session.proxies = {"http": self.proxy, "https": self.proxy}

        self.session.headers.update({
            "User-Agent": self.ua,
            "Accept-Language": random.choice([
                "en-US,en;q=0.9", "en-US,en;q=0.9,zh-CN;q=0.8",
                "en,en-US;q=0.9", "en-US,en;q=0.8",
            ]),
            "sec-ch-ua": self.sec_ch_ua, "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"', "sec-ch-ua-arch": '"x86"',
            "sec-ch-ua-bitness": '"64"',
            "sec-ch-ua-full-version": f'"{self.chrome_full}"',
            "sec-ch-ua-platform-version": f'"{random.randint(10, 15)}.0.0"',
        })

        self.session.cookies.set("oai-did", self.device_id, domain="chatgpt.com")
        self._callback_url = None

        # 通过 FlareSolverr 获取 CF Clearance（cf_clearance cookie + User-Agent）
        # 浏览器指纹（TLS 指纹）由 curl_cffi 的 impersonate 参数负责
        if _flaresolverr:
            applied = _flaresolverr.apply_to_session(self.session, self.BASE)
            if applied:
                # 同步更新实例 UA，保持与 FlareSolverr 浏览器一致
                fs_ua = self.session.headers.get("User-Agent", "")
                if fs_ua:
                    self.ua = fs_ua

    def _log(self, step, method, url, status, body=None):
        prefix = f"[{self.tag}] " if self.tag else ""
        lines = [
            f"\n{'='*60}",
            f"{prefix}[Step] {step}",
            f"{prefix}[{method}] {url}",
            f"{prefix}[Status] {status}",
        ]
        if body:
            try:
                lines.append(f"{prefix}[Response] {json.dumps(body, indent=2, ensure_ascii=False)[:1000]}")
            except Exception:
                lines.append(f"{prefix}[Response] {str(body)[:1000]}")
        lines.append(f"{'='*60}")
        with _print_lock:
            print("\n".join(lines))

    def _print(self, msg):
        prefix = f"[{self.tag}] " if self.tag else ""
        with _print_lock:
            print(f"{prefix}{msg}")

    # ==================== MoeMail 临时邮箱 ====================

    def create_temp_email(self):
        """通过 mail.zhouhongbin.top API 生成临时邮箱"""
        if not MOEMAIL_API_KEY:
            raise Exception("MOEMAIL_API_KEY 未设置，无法生成临时邮箱")

        chars = string.ascii_lowercase + string.digits
        length = random.randint(8, 13)
        email_name = "".join(random.choice(chars) for _ in range(length))

        url = f"{MOEMAIL_API_URL}/api/emails/generate"
        headers = {
            "X-API-Key": MOEMAIL_API_KEY,
            "Content-Type": "application/json",
        }
        payload = {
            "name": email_name,
            "expiryTime": MOEMAIL_EXPIRY_TIME,
            "domain": MOEMAIL_DOMAIN,
        }

        resp = curl_requests.post(url, json=payload, headers=headers,
                                  proxies={"http": self.proxy, "https": self.proxy} if self.proxy else None,
                                  timeout=30)
        if resp.status_code != 200:
            raise Exception(f"生成临时邮箱失败 ({resp.status_code}): {resp.text[:500]}")

        data = resp.json()
        # API 返回格式: {"email": "xxx@domain", "id": "xxx", ...}
        email_address = data.get("email") or data.get("address")
        email_id = data.get("id") or data.get("emailId")
        if not email_address or not email_id:
            raise Exception(f"生成临时邮箱响应格式异常: {data}")

        self._moemail_id = email_id
        password = _generate_password()
        return email_address, password, email_id

    def delete_temp_email(self, email_id: str):
        """注册完成后通过 MoeMail API 删除临时邮箱，释放资源"""
        if not email_id or not MOEMAIL_API_KEY:
            return
        try:
            url = f"{MOEMAIL_API_URL}/api/emails/{email_id}"
            headers = {"X-API-Key": MOEMAIL_API_KEY}
            resp = curl_requests.delete(
                url, headers=headers,
                proxies={"http": self.proxy, "https": self.proxy} if self.proxy else None,
                timeout=10,
            )
            if resp.status_code in (200, 204):
                self._print(f"[MoeMail] 临时邮箱已删除 (id={email_id})")
            else:
                self._print(f"[MoeMail] 删除临时邮箱失败: HTTP {resp.status_code}")
        except Exception as e:
            self._print(f"[MoeMail] 删除临时邮箱异常: {e}")

    def _extract_verification_code(self, text: str):
        """从邮件内容提取 6 位验证码"""
        if not text:
            return None

        patterns = [
            r"Verification code:?\s*(\d{6})",
            r"code is\s*(\d{6})",
            r"代码为[:：]?\s*(\d{6})",
            r"验证码[:：]?\s*(\d{6})",
            r">\s*(\d{6})\s*<",
            r"(?<![#&])\b(\d{6})\b",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for code in matches:
                if code == "177010":  # 已知误判
                    continue
                return code
        return None

    def wait_for_verification_email(self, email_or_id: str, timeout: int = 120):
        """轮询 MoeMail API 等待 OpenAI 验证码邮件"""
        # 优先使用实例上存储的 email ID
        email_id = getattr(self, "_moemail_id", None) or email_or_id
        self._print(f"[OTP] 轮询 MoeMail 邮箱等待验证码 (最多 {timeout}s, emailId={email_id})...")

        headers = {"X-API-Key": MOEMAIL_API_KEY}
        proxy_map = {"http": self.proxy, "https": self.proxy} if self.proxy else None
        start_time = time.time()
        seen_message_ids = set()

        while time.time() - start_time < timeout:
            try:
                list_url = f"{MOEMAIL_API_URL}/api/emails/{email_id}"
                resp = curl_requests.get(list_url, headers=headers, proxies=proxy_map, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    # API 返回格式: {"messages": [...], "nextCursor": "..."}
                    messages = data.get("messages") or []
                    for msg in messages:
                        msg_id = msg.get("id") or msg.get("messageId")
                        if not msg_id or msg_id in seen_message_ids:
                            continue
                        seen_message_ids.add(msg_id)
                        # 获取单封邮件内容
                        msg_url = f"{MOEMAIL_API_URL}/api/emails/{email_id}/{msg_id}"
                        msg_resp = curl_requests.get(msg_url, headers=headers, proxies=proxy_map, timeout=15)
                        if msg_resp.status_code == 200:
                            msg_data = msg_resp.json()
                            # API 返回格式: {"html": "...", "text": "...", "subject": "...", ...}
                            content = msg_data.get("html") or msg_data.get("text") or ""
                            code = self._extract_verification_code(content)
                            if code:
                                self._print(f"[OTP] 验证码: {code}")
                                return code
            except Exception as e:
                self._print(f"[OTP] 轮询失败: {e}")

            elapsed = int(time.time() - start_time)
            self._print(f"[OTP] 等待中... ({elapsed}s/{timeout}s)")
            time.sleep(5)

        self._print(f"[OTP] 超时 ({timeout}s)")
        return None

    # ==================== 注册流程 ====================

    def visit_homepage(self):
        url = f"{self.BASE}/"
        r = self.session.get(url, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
        }, allow_redirects=True)
        self._log("0. Visit homepage", "GET", url, r.status_code,
                   {"cookies_count": len(self.session.cookies)})

    def get_csrf(self) -> str:
        url = f"{self.BASE}/api/auth/csrf"
        r = self.session.get(url, headers={"Accept": "application/json", "Referer": f"{self.BASE}/"})
        data = r.json()
        token = data.get("csrfToken", "")
        self._log("1. Get CSRF", "GET", url, r.status_code, data)
        if not token:
            raise Exception("Failed to get CSRF token")
        return token

    def signin(self, email: str, csrf: str) -> str:
        url = f"{self.BASE}/api/auth/signin/openai"
        params = {
            "prompt": "login", "ext-oai-did": self.device_id,
            "auth_session_logging_id": self.auth_session_logging_id,
            "screen_hint": "login_or_signup", "login_hint": email,
        }
        form_data = {"callbackUrl": f"{self.BASE}/", "csrfToken": csrf, "json": "true"}
        r = self.session.post(url, params=params, data=form_data, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json", "Referer": f"{self.BASE}/", "Origin": self.BASE,
        })
        data = r.json()
        authorize_url = data.get("url", "")
        self._log("2. Signin", "POST", url, r.status_code, data)
        if not authorize_url:
            raise Exception("Failed to get authorize URL")
        return authorize_url

    def authorize(self, url: str) -> str:
        r = self.session.get(url, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{self.BASE}/", "Upgrade-Insecure-Requests": "1",
        }, allow_redirects=True)
        final_url = str(r.url)
        self._log("3. Authorize", "GET", url, r.status_code, {"final_url": final_url})
        return final_url

    def register(self, email: str, password: str):
        url = f"{self.AUTH}/api/accounts/user/register"
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                    "Referer": f"{self.AUTH}/create-account/password", "Origin": self.AUTH}
        headers.update(_make_trace_headers())
        r = self.session.post(url, json={"username": email, "password": password}, headers=headers)
        try: data = r.json()
        except Exception: data = {"text": r.text[:500]}
        self._log("4. Register", "POST", url, r.status_code, data)
        return r.status_code, data

    def send_otp(self):
        url = f"{self.AUTH}/api/accounts/email-otp/send"
        r = self.session.get(url, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{self.AUTH}/create-account/password", "Upgrade-Insecure-Requests": "1",
        }, allow_redirects=True)
        try: data = r.json()
        except Exception: data = {"final_url": str(r.url), "status": r.status_code}
        self._log("5. Send OTP", "GET", url, r.status_code, data)
        return r.status_code, data

    def validate_otp(self, code: str):
        url = f"{self.AUTH}/api/accounts/email-otp/validate"
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                    "Referer": f"{self.AUTH}/email-verification", "Origin": self.AUTH}
        headers.update(_make_trace_headers())
        r = self.session.post(url, json={"code": code}, headers=headers)
        try: data = r.json()
        except Exception: data = {"text": r.text[:500]}
        self._log("6. Validate OTP", "POST", url, r.status_code, data)
        return r.status_code, data

    def create_account(self, name: str, birthdate: str):
        url = f"{self.AUTH}/api/accounts/create_account"
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                    "Referer": f"{self.AUTH}/about-you", "Origin": self.AUTH}
        headers.update(_make_trace_headers())
        r = self.session.post(url, json={"name": name, "birthdate": birthdate}, headers=headers)
        try: data = r.json()
        except Exception: data = {"text": r.text[:500]}
        self._log("7. Create Account", "POST", url, r.status_code, data)
        if isinstance(data, dict):
            cb = data.get("continue_url") or data.get("url") or data.get("redirect_url")
            if cb:
                self._callback_url = cb
        return r.status_code, data

    def callback(self, url: str = None):
        if not url:
            url = self._callback_url
        if not url:
            self._print("[!] No callback URL, skipping.")
            return None, None
        r = self.session.get(url, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
        }, allow_redirects=True)
        self._log("8. Callback", "GET", url, r.status_code, {"final_url": str(r.url)})
        return r.status_code, {"final_url": str(r.url)}

    # ==================== 自动注册主流程 ====================

    def run_register(self, email, password, name, birthdate):
        """执行注册核心链路"""
        self.visit_homepage()
        _random_delay(0.3, 0.8)
        csrf = self.get_csrf()
        _random_delay(0.2, 0.5)
        auth_url = self.signin(email, csrf)
        _random_delay(0.3, 0.8)

        final_url = self.authorize(auth_url)
        final_path = urlparse(final_url).path
        _random_delay(0.3, 0.8)

        self._print(f"Authorize → {final_path}")

        need_otp = False

        if "create-account/password" in final_path:
            self._print("全新注册流程")
            _random_delay(0.5, 1.0)
            status, data = self.register(email, password)
            if status != 200:
                raise Exception(f"Register 失败 ({status}): {data}")
            # register 之后可能还需要 send_otp（全新注册流程中 OTP 不一定在 authorize 时发送）
            _random_delay(0.3, 0.8)
            self.send_otp()
            need_otp = True
        elif "email-verification" in final_path or "email-otp" in final_path:
            self._print("跳到 OTP 验证阶段 (authorize 已触发 OTP，不再重复发送)")
            # 不调用 send_otp()，因为 authorize 重定向到 email-verification 时服务器已发送 OTP
            need_otp = True
        elif "about-you" in final_path:
            self._print("跳到填写信息阶段")
            _random_delay(0.5, 1.0)
            self.create_account(name, birthdate)
            _random_delay(0.3, 0.5)
            self.callback()
            return True
        elif "callback" in final_path or "chatgpt.com" in final_url:
            self._print("账号已完成注册")
            return True
        else:
            self._print(f"未知跳转: {final_url}")
            self.register(email, password)
            self.send_otp()
            need_otp = True

        if need_otp:
            # 使用 MoeMail API 等待验证码
            otp_code = self.wait_for_verification_email(email)
            if not otp_code:
                raise Exception("未能获取验证码")

            _random_delay(0.3, 0.8)
            status, data = self.validate_otp(otp_code)
            if status != 200:
                self._print("验证码失败，重试...")
                self.send_otp()
                _random_delay(1.0, 2.0)
                otp_code = self.wait_for_verification_email(email, timeout=60)
                if not otp_code:
                    raise Exception("重试后仍未获取验证码")
                _random_delay(0.3, 0.8)
                status, data = self.validate_otp(otp_code)
                if status != 200:
                    raise Exception(f"验证码失败 ({status}): {data}")

        _random_delay(0.5, 1.5)
        status, data = self.create_account(name, birthdate)
        if status != 200:
            raise Exception(f"Create account 失败 ({status}): {data}")
        _random_delay(0.2, 0.5)
        self.callback()
        return True

    def _decode_oauth_session_cookie(self):
        jar = getattr(self.session.cookies, "jar", None)
        if jar is not None:
            cookie_items = list(jar)
        else:
            cookie_items = []

        for c in cookie_items:
            name = getattr(c, "name", "") or ""
            if "oai-client-auth-session" not in name:
                continue

            raw_val = (getattr(c, "value", "") or "").strip()
            if not raw_val:
                continue

            candidates = [raw_val]
            try:
                from urllib.parse import unquote

                decoded = unquote(raw_val)
                if decoded != raw_val:
                    candidates.append(decoded)
            except Exception:
                pass

            for val in candidates:
                try:
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]

                    part = val.split(".")[0] if "." in val else val
                    pad = 4 - len(part) % 4
                    if pad != 4:
                        part += "=" * pad
                    raw = base64.urlsafe_b64decode(part)
                    data = json.loads(raw.decode("utf-8"))
                    if isinstance(data, dict):
                        return data
                except Exception:
                    continue
        return None

    def _oauth_allow_redirect_extract_code(self, url: str, referer: str = None):
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": self.ua,
        }
        if referer:
            headers["Referer"] = referer

        try:
            resp = self.session.get(
                url,
                headers=headers,
                allow_redirects=True,
                timeout=30,
                impersonate=self.impersonate,
            )
            final_url = str(resp.url)
            code = _extract_code_from_url(final_url)
            if code:
                self._print("[OAuth] allow_redirect 命中最终 URL code")
                return code

            for r in getattr(resp, "history", []) or []:
                loc = r.headers.get("Location", "")
                code = _extract_code_from_url(loc)
                if code:
                    self._print("[OAuth] allow_redirect 命中 history Location code")
                    return code
                code = _extract_code_from_url(str(r.url))
                if code:
                    self._print("[OAuth] allow_redirect 命中 history URL code")
                    return code
        except Exception as e:
            maybe_localhost = re.search(r'(https?://localhost[^\s\'\"]+)', str(e))
            if maybe_localhost:
                code = _extract_code_from_url(maybe_localhost.group(1))
                if code:
                    self._print("[OAuth] allow_redirect 从 localhost 异常提取 code")
                    return code
            self._print(f"[OAuth] allow_redirect 异常: {e}")

        return None

    def _oauth_follow_for_code(self, start_url: str, referer: str = None, max_hops: int = 16):
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": self.ua,
        }
        if referer:
            headers["Referer"] = referer

        current_url = start_url
        last_url = start_url

        for hop in range(max_hops):
            try:
                resp = self.session.get(
                    current_url,
                    headers=headers,
                    allow_redirects=False,
                    timeout=30,
                    impersonate=self.impersonate,
                )
            except Exception as e:
                maybe_localhost = re.search(r'(https?://localhost[^\s\'\"]+)', str(e))
                if maybe_localhost:
                    code = _extract_code_from_url(maybe_localhost.group(1))
                    if code:
                        self._print(f"[OAuth] follow[{hop + 1}] 命中 localhost 回调")
                        return code, maybe_localhost.group(1)
                self._print(f"[OAuth] follow[{hop + 1}] 请求异常: {e}")
                return None, last_url

            last_url = str(resp.url)
            self._print(f"[OAuth] follow[{hop + 1}] {resp.status_code} {last_url[:140]}")
            code = _extract_code_from_url(last_url)
            if code:
                return code, last_url

            if resp.status_code in (301, 302, 303, 307, 308):
                loc = resp.headers.get("Location", "")
                if not loc:
                    return None, last_url
                if loc.startswith("/"):
                    loc = f"{OAUTH_ISSUER}{loc}"
                code = _extract_code_from_url(loc)
                if code:
                    return code, loc
                current_url = loc
                headers["Referer"] = last_url
                continue

            return None, last_url

        return None, last_url

    def _oauth_submit_workspace_and_org(self, consent_url: str):
        session_data = self._decode_oauth_session_cookie()
        if not session_data:
            jar = getattr(self.session.cookies, "jar", None)
            if jar is not None:
                cookie_names = [getattr(c, "name", "") for c in list(jar)]
            else:
                cookie_names = list(self.session.cookies.keys())
            self._print(f"[OAuth] 无法解码 oai-client-auth-session, cookies={cookie_names[:12]}")
            return None

        workspaces = session_data.get("workspaces", [])
        if not workspaces:
            self._print("[OAuth] session 中没有 workspace 信息")
            return None

        workspace_id = (workspaces[0] or {}).get("id")
        if not workspace_id:
            self._print("[OAuth] workspace_id 为空")
            return None

        h = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": OAUTH_ISSUER,
            "Referer": consent_url,
            "User-Agent": self.ua,
            "oai-device-id": self.device_id,
        }
        h.update(_make_trace_headers())

        resp = self.session.post(
            f"{OAUTH_ISSUER}/api/accounts/workspace/select",
            json={"workspace_id": workspace_id},
            headers=h,
            allow_redirects=False,
            timeout=30,
            impersonate=self.impersonate,
        )
        self._print(f"[OAuth] workspace/select -> {resp.status_code}")

        if resp.status_code in (301, 302, 303, 307, 308):
            loc = resp.headers.get("Location", "")
            if loc.startswith("/"):
                loc = f"{OAUTH_ISSUER}{loc}"
            code = _extract_code_from_url(loc)
            if code:
                return code
            code, _ = self._oauth_follow_for_code(loc, referer=consent_url)
            if not code:
                code = self._oauth_allow_redirect_extract_code(loc, referer=consent_url)
            return code

        if resp.status_code != 200:
            self._print(f"[OAuth] workspace/select 失败: {resp.status_code}")
            return None

        try:
            ws_data = resp.json()
        except Exception:
            self._print("[OAuth] workspace/select 响应不是 JSON")
            return None

        ws_next = ws_data.get("continue_url", "")
        orgs = ws_data.get("data", {}).get("orgs", [])
        ws_page = (ws_data.get("page") or {}).get("type", "")
        self._print(f"[OAuth] workspace/select page={ws_page or '-'} next={(ws_next or '-')[:140]}")

        org_id = None
        project_id = None
        if orgs:
            org_id = (orgs[0] or {}).get("id")
            projects = (orgs[0] or {}).get("projects", [])
            if projects:
                project_id = (projects[0] or {}).get("id")

        if org_id:
            org_body = {"org_id": org_id}
            if project_id:
                org_body["project_id"] = project_id

            h_org = dict(h)
            if ws_next:
                h_org["Referer"] = ws_next if ws_next.startswith("http") else f"{OAUTH_ISSUER}{ws_next}"

            resp_org = self.session.post(
                f"{OAUTH_ISSUER}/api/accounts/organization/select",
                json=org_body,
                headers=h_org,
                allow_redirects=False,
                timeout=30,
                impersonate=self.impersonate,
            )
            self._print(f"[OAuth] organization/select -> {resp_org.status_code}")
            if resp_org.status_code in (301, 302, 303, 307, 308):
                loc = resp_org.headers.get("Location", "")
                if loc.startswith("/"):
                    loc = f"{OAUTH_ISSUER}{loc}"
                code = _extract_code_from_url(loc)
                if code:
                    return code
                code, _ = self._oauth_follow_for_code(loc, referer=h_org.get("Referer"))
                if not code:
                    code = self._oauth_allow_redirect_extract_code(loc, referer=h_org.get("Referer"))
                return code

            if resp_org.status_code == 200:
                try:
                    org_data = resp_org.json()
                except Exception:
                    self._print("[OAuth] organization/select 响应不是 JSON")
                    return None

                org_next = org_data.get("continue_url", "")
                org_page = (org_data.get("page") or {}).get("type", "")
                self._print(f"[OAuth] organization/select page={org_page or '-'} next={(org_next or '-')[:140]}")
                if org_next:
                    if org_next.startswith("/"):
                        org_next = f"{OAUTH_ISSUER}{org_next}"
                    code, _ = self._oauth_follow_for_code(org_next, referer=h_org.get("Referer"))
                    if not code:
                        code = self._oauth_allow_redirect_extract_code(org_next, referer=h_org.get("Referer"))
                    return code

        if ws_next:
            if ws_next.startswith("/"):
                ws_next = f"{OAUTH_ISSUER}{ws_next}"
            code, _ = self._oauth_follow_for_code(ws_next, referer=consent_url)
            if not code:
                code = self._oauth_allow_redirect_extract_code(ws_next, referer=consent_url)
            return code

        return None

    def perform_codex_oauth_login_http(self, email: str, password: str, mail_token: str = None):
        self._print("[OAuth] 开始执行 Codex OAuth 纯协议流程...")

        # 兼容两种 domain 形式，确保 auth 域也带 oai-did
        self.session.cookies.set("oai-did", self.device_id, domain=".auth.openai.com")
        self.session.cookies.set("oai-did", self.device_id, domain="auth.openai.com")

        code_verifier, code_challenge = _generate_pkce()
        state = secrets.token_urlsafe(24)

        authorize_params = {
            "response_type": "code",
            "client_id": OAUTH_CLIENT_ID,
            "redirect_uri": OAUTH_REDIRECT_URI,
            "scope": "openid profile email offline_access",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        authorize_url = f"{OAUTH_ISSUER}/oauth/authorize?{urlencode(authorize_params)}"

        def _oauth_json_headers(referer: str):
            h = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": OAUTH_ISSUER,
                "Referer": referer,
                "User-Agent": self.ua,
                "oai-device-id": self.device_id,
            }
            h.update(_make_trace_headers())
            return h

        def _bootstrap_oauth_session():
            self._print("[OAuth] 1/7 GET /oauth/authorize")
            try:
                r = self.session.get(
                    authorize_url,
                    headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Referer": f"{self.BASE}/",
                        "Upgrade-Insecure-Requests": "1",
                        "User-Agent": self.ua,
                    },
                    allow_redirects=True,
                    timeout=30,
                    impersonate=self.impersonate,
                )
            except Exception as e:
                self._print(f"[OAuth] /oauth/authorize 异常: {e}")
                return False, ""

            final_url = str(r.url)
            redirects = len(getattr(r, "history", []) or [])
            self._print(f"[OAuth] /oauth/authorize -> {r.status_code}, final={(final_url or '-')[:140]}, redirects={redirects}")

            has_login = any(getattr(c, "name", "") == "login_session" for c in self.session.cookies)
            self._print(f"[OAuth] login_session: {'已获取' if has_login else '未获取'}")

            if not has_login:
                self._print("[OAuth] 未拿到 login_session，尝试访问 oauth2 auth 入口")
                oauth2_url = f"{OAUTH_ISSUER}/api/oauth/oauth2/auth"
                try:
                    r2 = self.session.get(
                        oauth2_url,
                        headers={
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            "Referer": authorize_url,
                            "Upgrade-Insecure-Requests": "1",
                            "User-Agent": self.ua,
                        },
                        params=authorize_params,
                        allow_redirects=True,
                        timeout=30,
                        impersonate=self.impersonate,
                    )
                    final_url = str(r2.url)
                    redirects2 = len(getattr(r2, "history", []) or [])
                    self._print(f"[OAuth] /api/oauth/oauth2/auth -> {r2.status_code}, final={(final_url or '-')[:140]}, redirects={redirects2}")
                except Exception as e:
                    self._print(f"[OAuth] /api/oauth/oauth2/auth 异常: {e}")

                has_login = any(getattr(c, "name", "") == "login_session" for c in self.session.cookies)
                self._print(f"[OAuth] login_session(重试): {'已获取' if has_login else '未获取'}")

            return has_login, final_url

        def _post_authorize_continue(referer_url: str):
            sentinel_authorize = build_sentinel_token(
                self.session,
                self.device_id,
                flow="authorize_continue",
                user_agent=self.ua,
                sec_ch_ua=self.sec_ch_ua,
                impersonate=self.impersonate,
            )
            if not sentinel_authorize:
                self._print("[OAuth] authorize_continue 的 sentinel token 获取失败")
                return None

            headers_continue = _oauth_json_headers(referer_url)
            headers_continue["openai-sentinel-token"] = sentinel_authorize

            try:
                return self.session.post(
                    f"{OAUTH_ISSUER}/api/accounts/authorize/continue",
                    json={"username": {"kind": "email", "value": email}},
                    headers=headers_continue,
                    timeout=30,
                    allow_redirects=False,
                    impersonate=self.impersonate,
                )
            except Exception as e:
                self._print(f"[OAuth] authorize/continue 异常: {e}")
                return None

        has_login_session, authorize_final_url = _bootstrap_oauth_session()
        if not authorize_final_url:
            return None

        continue_referer = authorize_final_url if authorize_final_url.startswith(OAUTH_ISSUER) else f"{OAUTH_ISSUER}/log-in"

        self._print("[OAuth] 2/7 POST /api/accounts/authorize/continue")
        resp_continue = _post_authorize_continue(continue_referer)
        if resp_continue is None:
            return None

        self._print(f"[OAuth] /authorize/continue -> {resp_continue.status_code}")
        if resp_continue.status_code == 400 and "invalid_auth_step" in (resp_continue.text or ""):
            self._print("[OAuth] invalid_auth_step，重新 bootstrap 后重试一次")
            has_login_session, authorize_final_url = _bootstrap_oauth_session()
            if not authorize_final_url:
                return None
            continue_referer = authorize_final_url if authorize_final_url.startswith(OAUTH_ISSUER) else f"{OAUTH_ISSUER}/log-in"
            resp_continue = _post_authorize_continue(continue_referer)
            if resp_continue is None:
                return None
            self._print(f"[OAuth] /authorize/continue(重试) -> {resp_continue.status_code}")

        if resp_continue.status_code != 200:
            self._print(f"[OAuth] 邮箱提交失败: {resp_continue.text[:180]}")
            return None

        try:
            continue_data = resp_continue.json()
        except Exception:
            self._print("[OAuth] authorize/continue 响应解析失败")
            return None

        continue_url = continue_data.get("continue_url", "")
        page_type = (continue_data.get("page") or {}).get("type", "")
        self._print(f"[OAuth] continue page={page_type or '-'} next={(continue_url or '-')[:140]}")

        self._print("[OAuth] 3/7 POST /api/accounts/password/verify")
        sentinel_pwd = build_sentinel_token(
            self.session,
            self.device_id,
            flow="password_verify",
            user_agent=self.ua,
            sec_ch_ua=self.sec_ch_ua,
            impersonate=self.impersonate,
        )
        if not sentinel_pwd:
            self._print("[OAuth] password_verify 的 sentinel token 获取失败")
            return None

        headers_verify = _oauth_json_headers(f"{OAUTH_ISSUER}/log-in/password")
        headers_verify["openai-sentinel-token"] = sentinel_pwd

        try:
            resp_verify = self.session.post(
                f"{OAUTH_ISSUER}/api/accounts/password/verify",
                json={"password": password},
                headers=headers_verify,
                timeout=30,
                allow_redirects=False,
                impersonate=self.impersonate,
            )
        except Exception as e:
            self._print(f"[OAuth] password/verify 异常: {e}")
            return None

        self._print(f"[OAuth] /password/verify -> {resp_verify.status_code}")
        if resp_verify.status_code != 200:
            self._print(f"[OAuth] 密码校验失败: {resp_verify.text[:180]}")
            return None

        try:
            verify_data = resp_verify.json()
        except Exception:
            self._print("[OAuth] password/verify 响应解析失败")
            return None

        continue_url = verify_data.get("continue_url", "") or continue_url
        page_type = (verify_data.get("page") or {}).get("type", "") or page_type
        self._print(f"[OAuth] verify page={page_type or '-'} next={(continue_url or '-')[:140]}")

        need_oauth_otp = (
            page_type == "email_otp_verification"
            or "email-verification" in (continue_url or "")
            or "email-otp" in (continue_url or "")
        )

        if need_oauth_otp:
            self._print("[OAuth] 4/7 检测到邮箱 OTP 验证")

            # mail_token 在 MoeMail 流程中为 emailId，用于轮询 API；此处使用 email 作为兜底
            target_email = mail_token or email

            headers_otp = _oauth_json_headers(f"{OAUTH_ISSUER}/email-verification")
            
            # 使用 MoeMail API 轮询等待验证邮件
            otp_code = self.wait_for_verification_email(target_email, timeout=120)
            
            if not otp_code:
                self._print("[OAuth] OAuth 阶段 OTP 验证失败，未获取到验证码")
                return None

            self._print(f"[OAuth] 尝试 OTP: {otp_code}")
            try:
                resp_otp = self.session.post(
                    f"{OAUTH_ISSUER}/api/accounts/email-otp/validate",
                    json={"code": otp_code},
                    headers=headers_otp,
                    timeout=30,
                    allow_redirects=False,
                    impersonate=self.impersonate,
                )
            except Exception as e:
                self._print(f"[OAuth] email-otp/validate 异常: {e}")
                return None

            self._print(f"[OAuth] /email-otp/validate -> {resp_otp.status_code}")
            if resp_otp.status_code != 200:
                self._print(f"[OAuth] OTP 无效: {resp_otp.text[:160]}")
                return None

            try:
                otp_data = resp_otp.json()
            except Exception:
                self._print("[OAuth] email-otp/validate 响应解析失败")
                return None

            continue_url = otp_data.get("continue_url", "") or continue_url
            page_type = (otp_data.get("page") or {}).get("type", "") or page_type
            self._print(f"[OAuth] OTP 验证通过 page={page_type or '-'} next={(continue_url or '-')[:140]}")

        code = None
        consent_url = continue_url
        if consent_url and consent_url.startswith("/"):
            consent_url = f"{OAUTH_ISSUER}{consent_url}"

        if not consent_url and "consent" in page_type:
            consent_url = f"{OAUTH_ISSUER}/sign-in-with-chatgpt/codex/consent"

        if consent_url:
            code = _extract_code_from_url(consent_url)

        if not code and consent_url:
            self._print("[OAuth] 5/7 跟随 continue_url 提取 code")
            code, _ = self._oauth_follow_for_code(consent_url, referer=f"{OAUTH_ISSUER}/log-in/password")

        consent_hint = (
            ("consent" in (consent_url or ""))
            or ("sign-in-with-chatgpt" in (consent_url or ""))
            or ("workspace" in (consent_url or ""))
            or ("organization" in (consent_url or ""))
            or ("consent" in page_type)
            or ("organization" in page_type)
        )

        if not code and consent_hint:
            if not consent_url:
                consent_url = f"{OAUTH_ISSUER}/sign-in-with-chatgpt/codex/consent"
            self._print("[OAuth] 6/7 执行 workspace/org 选择")
            code = self._oauth_submit_workspace_and_org(consent_url)

        if not code:
            fallback_consent = f"{OAUTH_ISSUER}/sign-in-with-chatgpt/codex/consent"
            self._print("[OAuth] 6/7 回退 consent 路径重试")
            code = self._oauth_submit_workspace_and_org(fallback_consent)
            if not code:
                code, _ = self._oauth_follow_for_code(fallback_consent, referer=f"{OAUTH_ISSUER}/log-in/password")

        if not code:
            self._print("[OAuth] 未获取到 authorization code")
            return None

        self._print("[OAuth] 7/7 POST /oauth/token")
        token_resp = self.session.post(
            f"{OAUTH_ISSUER}/oauth/token",
            headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": self.ua},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": OAUTH_REDIRECT_URI,
                "client_id": OAUTH_CLIENT_ID,
                "code_verifier": code_verifier,
            },
            timeout=60,
            impersonate=self.impersonate,
        )
        self._print(f"[OAuth] /oauth/token -> {token_resp.status_code}")

        if token_resp.status_code != 200:
            self._print(f"[OAuth] token 交换失败: {token_resp.status_code} {token_resp.text[:200]}")
            return None

        try:
            data = token_resp.json()
        except Exception:
            self._print("[OAuth] token 响应解析失败")
            return None

        if not data.get("access_token"):
            self._print("[OAuth] token 响应缺少 access_token")
            return None

        self._print("[OAuth] Codex Token 获取成功")
        return data


# ==================== 并发批量注册 ====================

def _register_one(idx, total, proxy, output_file):
    """单个注册任务 (在线程中运行) - 使用 MoeMail 临时邮箱"""
    reg = None
    # email_id 在 create_temp_email 成功后赋值；
    # 若在此之前发生异常则保持 None，finally 块中的条件检查会正确跳过删除。
    email_id = None
    try:
        reg = ChatGPTRegister(proxy=proxy, tag=f"{idx}")

        # 1. 创建临时邮箱
        reg._print("[MoeMail] 创建临时邮箱...")
        email, email_pwd, email_id = reg.create_temp_email()
        tag = email.split("@")[0]
        reg.tag = tag  # 更新 tag

        chatgpt_password = _generate_password()
        name = _random_name()
        birthdate = _random_birthdate()

        with _print_lock:
            print(f"\n{'='*60}")
            print(f"  [{idx}/{total}] 注册: {email}")
            print(f"  ChatGPT密码: {chatgpt_password}")
            print(f"  临时邮箱ID: {email_id}")
            print(f"  姓名: {name} | 生日: {birthdate}")
            print(f"{'='*60}")

        # 2. 执行注册流程
        reg.run_register(email, chatgpt_password, name, birthdate)

        # 3. OAuth（可选）
        oauth_ok = True
        if ENABLE_OAUTH:
            reg._print("[OAuth] 开始获取 Codex Token...")
            tokens = reg.perform_codex_oauth_login_http(email, chatgpt_password)
            oauth_ok = bool(tokens and tokens.get("access_token"))
            if oauth_ok:
                _save_codex_tokens(email, tokens)
                reg._print("[OAuth] Token 已保存")
            else:
                msg = "OAuth 获取失败"
                if OAUTH_REQUIRED:
                    raise Exception(f"{msg}（oauth_required=true）")
                reg._print(f"[OAuth] {msg}（按配置继续）")

        # 4. 线程安全写入结果
        with _file_lock:
            with open(output_file, "a", encoding="utf-8") as out:
                out.write(f"{email}----{chatgpt_password}----{email_pwd}----oauth={'ok' if oauth_ok else 'fail'}\n")

        with _print_lock:
            print(f"\n[OK] [{tag}] {email} 注册成功!")
        return True, email, None

    except Exception as e:
        error_msg = str(e)
        with _print_lock:
            print(f"\n[FAIL] [{idx}] 注册失败: {error_msg}")
            traceback.print_exc()
        return False, None, error_msg

    finally:
        # 注册完成后（无论成功/失败）立即删除临时邮箱，释放 MoeMail 资源
        if reg and email_id:
            reg.delete_temp_email(email_id)


def run_batch(total_accounts: int = 3, output_file="registered_accounts.txt",
              max_workers=3, proxy=None):
    """并发批量注册 - MoeMail 临时邮箱版"""

    actual_workers = min(max_workers, total_accounts)
    print(f"\n{'#'*60}")
    print(f"  ChatGPT 批量自动注册 (MoeMail 临时邮箱版)")
    print(f"  注册数量: {total_accounts} | 并发数: {actual_workers}")
    print(f"  OAuth: {'开启' if ENABLE_OAUTH else '关闭'} | required: {'是' if OAUTH_REQUIRED else '否'}")
    if ENABLE_OAUTH:
        print(f"  OAuth Issuer: {OAUTH_ISSUER}")
        print(f"  OAuth Client: {OAUTH_CLIENT_ID}")
        print(f"  Token输出: {TOKEN_JSON_DIR}/, {AK_FILE}, {RK_FILE}")
    print(f"  输出文件: {output_file}")
    print(f"{'#'*60}\n")

    success_count = 0
    fail_count = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=actual_workers) as executor:
        futures = {}
        for idx in range(1, total_accounts + 1):
            future = executor.submit(
                _register_one, idx, total_accounts, proxy, output_file
            )
            futures[future] = idx

        for future in as_completed(futures):
            idx = futures[future]
            try:
                ok, email, err = future.result()
                if ok:
                    success_count += 1
                else:
                    fail_count += 1
                    print(f"  [账号 {idx}] 失败: {err}")
            except Exception as e:
                fail_count += 1
                with _print_lock:
                    print(f"[FAIL] 账号 {idx} 线程异常: {e}")

    elapsed = time.time() - start_time
    avg = elapsed / total_accounts if total_accounts else 0
    print(f"\n{'#'*60}")
    print(f"  注册完成! 耗时 {elapsed:.1f} 秒")
    print(f"  总数: {total_accounts} | 成功: {success_count} | 失败: {fail_count}")
    print(f"  平均速度: {avg:.1f} 秒/个")
    if success_count > 0:
        print(f"  结果文件: {output_file}")
    print(f"{'#'*60}")


# =================== 交互式配置向导 ===================

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def _save_config():
    """将当前全局配置写回 config.json（仅更新可交互的字段）。"""
    try:
        # 读取现有 JSON，避免覆盖用户手动设置的其他字段
        existing = {}
        if os.path.exists(_CONFIG_PATH):
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
    except Exception:
        existing = {}

    existing.update({
        "moemail_api_url":  MOEMAIL_API_URL,
        "moemail_api_key":  MOEMAIL_API_KEY,
        "moemail_domain":   MOEMAIL_DOMAIN,
        "proxy":            DEFAULT_PROXY,
        "flaresolverr_url": FLARESOLVERR_URL,
        "total_accounts":   DEFAULT_TOTAL_ACCOUNTS,
        "concurrent_workers": DEFAULT_CONCURRENT_WORKERS,
    })
    try:
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        print(f"✅ 配置已保存到 {_CONFIG_PATH}")
    except Exception as e:
        _eprint(f"⚠️ 保存配置文件失败: {e}")


def _test_moemail(api_url: str, api_key: str, domain: str, proxy: str = "") -> tuple:
    """
    快速测试 MoeMail API 连通性：生成一个临时邮箱然后立即删除。
    返回 (True, "") 表示成功，(False, "错误描述") 表示失败。
    """
    try:
        test_name = "testconn" + secrets.token_hex(4)
        url = api_url.rstrip("/") + "/api/emails/generate"
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        payload = {"name": test_name, "expiryTime": 60000, "domain": domain}
        proxies = {"http": proxy, "https": proxy} if proxy else None

        resp = curl_requests.post(url, json=payload, headers=headers,
                                  proxies=proxies, timeout=15)
        if resp.status_code == 401:
            return False, f"API Key 无效 (401 Unauthorized)"
        if resp.status_code == 403:
            return False, f"API Key 权限不足 (403 Forbidden)"
        if resp.status_code != 200:
            return False, f"API 响应异常: HTTP {resp.status_code} — {resp.text[:200]}"

        data = resp.json()
        email_id = data.get("id") or data.get("emailId")
        email_addr = data.get("email") or data.get("address")
        if not email_addr:
            return False, f"API 响应格式异常，未返回邮箱地址: {data}"

        # 尝试删除测试邮箱（忽略失败）
        if email_id:
            try:
                curl_requests.delete(
                    api_url.rstrip("/") + f"/api/emails/{email_id}",
                    headers={"X-API-Key": api_key},
                    proxies=proxies, timeout=10,
                )
            except Exception:
                pass

        return True, ""
    except Exception as e:
        return False, f"连接失败: {e}"


def _test_flaresolverr(url: str) -> tuple:
    """
    测试 FlareSolverr 服务是否可达。
    返回 (True, "") 或 (False, "错误描述")。
    """
    try:
        resp = curl_requests.get(url.rstrip("/") + "/health", timeout=8)
        if resp.status_code == 200:
            return True, ""
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, f"连接失败: {e}"


def _prompt(prompt_text: str, default: str = "", secret: bool = False) -> str:
    """
    交互式单行输入。显示当前默认值（敏感字段只显示 *）。
    直接回车保留默认值。
    """
    if default:
        display = ("*" * min(len(default), 8)) if secret else default
        full_prompt = f"{prompt_text} [当前: {display}]: "
    else:
        full_prompt = f"{prompt_text} [留空跳过]: "
    val = input(full_prompt).strip()
    return val if val else default


def _interactive_setup():
    """
    启动时交互式配置向导：
    - 依次询问关键参数
    - 立即验证连通性
    - 验证通过后保存到 config.json；失败则重新询问
    """
    global MOEMAIL_API_URL, MOEMAIL_API_KEY, MOEMAIL_DOMAIN
    global FLARESOLVERR_URL
    global DEFAULT_PROXY, DEFAULT_TOTAL_ACCOUNTS, DEFAULT_CONCURRENT_WORKERS

    print("\n" + "─" * 60)
    print("  配置向导 — 请依次输入以下参数（直接回车保留当前值）")
    print("─" * 60)

    # ── 1. MoeMail API URL ──────────────────────────────────────
    while True:
        url = _prompt("MoeMail API 地址", default=MOEMAIL_API_URL)
        if not url:
            print("  ❌ API 地址不能为空，请重新输入")
            continue
        MOEMAIL_API_URL = url.rstrip("/")
        break

    # ── 2. MoeMail API Key ─────────────────────────────────────
    while True:
        key = _prompt("MoeMail API Key", default=MOEMAIL_API_KEY, secret=True)
        if not key or key.upper() == _PLACEHOLDER_API_KEY.upper():
            print("  ❌ API Key 不能为空，请输入真实的 API Key")
            continue
        MOEMAIL_API_KEY = key
        break

    # ── 3. MoeMail 邮箱域名 ────────────────────────────────────
    while True:
        domain = _prompt("MoeMail 邮箱域名", default=MOEMAIL_DOMAIN)
        if not domain:
            print("  ❌ 邮箱域名不能为空")
            continue
        MOEMAIL_DOMAIN = domain
        break

    # ── 4. 代理 ────────────────────────────────────────────────
    DEFAULT_PROXY = _prompt("代理地址（如 http://127.0.0.1:7890，留空不使用）",
                            default=DEFAULT_PROXY) or ""

    # ── 5. 验证 MoeMail（带重试）──────────────────────────────
    print("\n🔍 正在验证 MoeMail API 连通性...")
    while True:
        ok, err = _test_moemail(MOEMAIL_API_URL, MOEMAIL_API_KEY, MOEMAIL_DOMAIN,
                                proxy=DEFAULT_PROXY)
        if ok:
            print("  ✅ MoeMail API 验证通过")
            break
        print(f"  ❌ MoeMail 验证失败: {err}")
        print("  请重新输入正确的参数（或 Ctrl+C 退出）")

        url = _prompt("MoeMail API 地址", default=MOEMAIL_API_URL)
        if url:
            MOEMAIL_API_URL = url.rstrip("/")
        key = _prompt("MoeMail API Key", default=MOEMAIL_API_KEY, secret=True)
        if key and key.upper() != _PLACEHOLDER_API_KEY.upper():
            MOEMAIL_API_KEY = key
        domain = _prompt("MoeMail 邮箱域名", default=MOEMAIL_DOMAIN)
        if domain:
            MOEMAIL_DOMAIN = domain

    # ── 6. FlareSolverr（可选）───────────────────────────────
    fs_url = _prompt("FlareSolverr 地址（留空不使用）", default=FLARESOLVERR_URL)
    if fs_url:
        print(f"🔍 正在验证 FlareSolverr ({fs_url})...")
        while True:
            ok, err = _test_flaresolverr(fs_url)
            if ok:
                FLARESOLVERR_URL = fs_url
                print("  ✅ FlareSolverr 验证通过")
                break
            print(f"  ❌ FlareSolverr 验证失败: {err}")
            fs_url = _prompt("FlareSolverr 地址（留空跳过）", default=fs_url)
            if not fs_url:
                FLARESOLVERR_URL = ""
                print("  ℹ️ 已跳过 FlareSolverr")
                break
    else:
        FLARESOLVERR_URL = ""

    # ── 7. 注册数量 / 并发数 ───────────────────────────────────
    count_raw = _prompt("注册账号数量", default=str(DEFAULT_TOTAL_ACCOUNTS))
    try:
        DEFAULT_TOTAL_ACCOUNTS = max(1, int(count_raw))
    except ValueError:
        print(f"  ⚠️ 无效数字，保持 {DEFAULT_TOTAL_ACCOUNTS}")

    workers_raw = _prompt("并发数", default=str(DEFAULT_CONCURRENT_WORKERS))
    try:
        DEFAULT_CONCURRENT_WORKERS = max(1, int(workers_raw))
    except ValueError:
        print(f"  ⚠️ 无效数字，保持 {DEFAULT_CONCURRENT_WORKERS}")

    # ── 8. 保存配置 ────────────────────────────────────────────
    _save_config()
    print("─" * 60 + "\n")


def main():
    print("=" * 60)
    print("  ChatGPT 批量自动注册工具 (MoeMail 临时邮箱版)")
    print("=" * 60)

    # ── 非交互模式 ──────────────────────────────────────────────
    # 当 stdin 不是终端时（nohup / 后台运行 / 管道重定向），跳过所有
    # input() 调用，直接使用 config.json 或环境变量中的参数。
    if not sys.stdin.isatty():
        print("[Info] 非交互模式：直接使用 config.json / 环境变量中的配置")
        _validate_startup_config()
        _init_flaresolverr()
        proxy = DEFAULT_PROXY or None
        if proxy:
            print(f"[Info] 使用代理: {proxy}")
        else:
            print("[Info] 不使用代理")
        print(f"[Info] 注册数量: {DEFAULT_TOTAL_ACCOUNTS}  并发数: {DEFAULT_CONCURRENT_WORKERS}")
        run_batch(
            total_accounts=DEFAULT_TOTAL_ACCOUNTS,
            output_file=DEFAULT_OUTPUT_FILE,
            max_workers=DEFAULT_CONCURRENT_WORKERS,
            proxy=proxy,
        )
        return

    # ── 交互模式 ─────────────────────────────────────────────────
    # 配置向导：询问所有关键参数，验证后保存到 config.json
    _interactive_setup()
    _init_flaresolverr()

    run_batch(total_accounts=DEFAULT_TOTAL_ACCOUNTS, output_file=DEFAULT_OUTPUT_FILE,
              max_workers=DEFAULT_CONCURRENT_WORKERS, proxy=DEFAULT_PROXY or None)


if __name__ == "__main__":
    main()
