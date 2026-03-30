# Skill 功能实现对比清单

> 本清单对比 `url发现机制调研(1).md` 协议要求与当前 Skill 实现情况。
>
> **图例**：✅ 已实现 | ⚠️ 部分实现 | ❌ 未实现 | ➖ 不适用

---

## 1. URL 发现机制

### 1.1 模板拼接 (Template-based Construction)

| 场景 | 协议要求 | 实现状态 | 当前实现 |
| --- | --- | --- | --- |
| URL 模板引擎 | 根据 dataset 字段套用模板生成 URL | ✅ 已实现 | `crawler/discovery/url_builder.py` |
| 模板配置文件 | JSON 配置表管理所有平台模板 | ✅ 已实现 | `references/url_templates.json` |
| 字段映射配置 | dataset 字段别名映射 | ✅ 已实现 | `references/field_mappings.json` |
| 模板热加载 | 修改配置后不重启生效 | ✅ 已实现 | 每次调用 `build_url()` 重新加载 JSON |

### 1.2 ~ 1.5 其他 URL 发现机制

> 以下机制由其他团队成员实现，待合并后更新状态。

| 机制 | 状态 | 备注 |
| --- | --- | --- |
| API 驱动发现 | 🔄 待合并 | 从种子扩展、分页遍历 |
| 图谱遍历 | 🔄 待合并 | BFS/DFS 社交关系 |
| 搜索驱动发现 | 🔄 待合并 | 关键词/话题搜索 |
| 内容解析发现 | 🔄 待合并 | 引用链、外链提取 |

---

## 2. 平台适配器

### 2.1 适配器架构

| 场景 | 协议要求 | 实现状态 | 当前实现 |
| --- | --- | --- | --- |
| 适配器基类 | 统一接口定义 | ✅ 已实现 | `crawler/platforms/base.py` → `PlatformAdapter` |
| 适配器注册表 | 自动发现和注册 | ✅ 已实现 | `crawler/platforms/registry.py` |
| 统一数据格式 | `StructuredData` 返回格式 | ✅ 已实现 | 标准化的 extracted/normalized 结构 |

### 2.2 已实现的适配器

| 平台 | 实现文件 | 资源类型 | 后端支持 |
| --- | --- | --- | --- |
| Wikipedia | `wikipedia.py` | article | api → http → playwright |
| arXiv | `arxiv.py` | paper | api → http → playwright |
| Amazon | `amazon.py` | product, seller, search | playwright → camoufox |
| Base Chain | `base_chain.py` | address, transaction, token, contract | api → http → playwright |
| LinkedIn | `linkedin.py` | profile, company, post, job, search | playwright → camoufox (需认证) |
| Generic | `generic.py` | page | http → playwright |

---

## 3. 基础设施

### 3.1 任务队列与 URL 去重

> 任务队列、URL 去重、断点续爬由**后端 API** 管理，Skill 不负责。
> 见 [plugin_api_checklist.md](plugin_api_checklist.md) 中的 `/url-occupancies/check` 等接口。

| 场景 | 实现层 | 状态 |
| --- | --- | --- |
| URL 去重 | 后端 API | ➖ 不在 Skill 范围 |
| 任务队列 | 后端 API | ➖ 不在 Skill 范围 |
| 断点续爬 | 后端 API | ➖ 不在 Skill 范围 |

### 3.2 限流控制

| 场景 | 协议要求 | 实现状态 | 当前实现 |
| --- | --- | --- | --- |
| 平台限流配置 | 各平台 rate limit 参数 | ✅ 已实现 | `references/rate_limits.json` |
| 固定间隔限流 | 请求间隔控制 | ⚠️ 部分实现 | 有配置，执行层未强制 |
| 429 响应处理 | 自动退避等待 | ⚠️ 部分实现 | 有 backoff_seconds 配置 |
| 指数退避 | 重试间隔指数增长 | ✅ 已实现 | `backoff_seconds: [2, 5, 10]` |
| 限流配置热加载 | 不重启生效 | ❌ 未实现 | |

**当前限流配置**：

| 平台 | requests_per_minute | max_retries | preferred_backend |
| --- | --- | --- | --- |
| Wikipedia | 60 | 2 | http |
| arXiv | 30 | 2 | http |
| Amazon | 12 | 4 | playwright |
| Base | 24 | 3 | http |
| LinkedIn | 6 | 4 | playwright |

### 3.3 错误处理与重试

| 场景 | 协议要求 | 实现状态 | 当前实现 |
| --- | --- | --- | --- |
| 可重试错误识别 | 429, 5xx | ✅ 已实现 | `contracts.py` → `NormalizedError` |
| 不可重试错误识别 | 404, 403 | ✅ 已实现 | |
| 最大重试次数 | 超过后放弃 | ✅ 已实现 | `max_retries` 配置 |
| 后端回退 | 失败后切换后端 | ✅ 已实现 | `fallback_backends` 链 |
| 认证错误分类 | AUTH_REQUIRED, AUTH_EXPIRED | ✅ 已实现 | `dispatcher.py` |

### 3.4 反爬对抗

| 场景 | 协议要求 | 实现状态 | 备注 |
| --- | --- | --- | --- |
| User-Agent 设置 | UA 头 | ⚠️ 部分实现 | 固定 UA，无轮换 |
| User-Agent 轮换 | 每次不同 UA | ❌ 未实现 | |
| 代理池支持 | 请求通过代理 | ❌ 未实现 | |
| 代理失效切换 | 自动换代理 | ❌ 未实现 | |
| 请求间隔随机化 | 范围内随机 | ❌ 未实现 | |
| CAPTCHA 检测 | 识别验证码并暂停 | ❌ 未实现 | |
| Camoufox 反检测 | 高级反爬浏览器 | ✅ 已实现 | `camoufox_backend.py` |

### 3.5 Session 管理

| 场景 | 协议要求 | 实现状态 | 当前实现 |
| --- | --- | --- | --- |
| 浏览器 Session 存储 | 保存登录状态 | ✅ 已实现 | `fetch/session_store.py` |
| Session 复用 | 避免重复登录 | ✅ 已实现 | `session_reuse_required` 配置 |
| Cookies 导入 | 从文件导入 cookies | ✅ 已实现 | `--cookies-path` CLI 参数 |
| 自动登录 | LinkedIn auto-browser | ✅ 已实现 | `--auto-login` + VNC 模式 |

---

## 4. 内容抓取与解析

### 4.1 抓取后端

| 后端 | 实现状态 | 实现文件 | 用途 |
| --- | --- | --- | --- |
| HTTP | ✅ 已实现 | `fetch/http_backend.py` | 静态页面 |
| API | ✅ 已实现 | `fetch/api_backend.py` | JSON API 调用 |
| Playwright | ✅ 已实现 | `fetch/playwright_backend.py` | JS 渲染页面 |
| Camoufox | ✅ 已实现 | `fetch/camoufox_backend.py` | 反爬对抗 |

**统一抓取入口**：`fetch/unified.py` → `fetch/engine.py` (FetchEngine)

### 4.2 内容提取

| 提取器 | 实现状态 | 实现文件 | 用途 |
| --- | --- | --- | --- |
| HTML 结构提取 | ✅ 已实现 | `extract/html_extract.py` | 通用 HTML |
| 文章正文提取 | ✅ 已实现 | `extract/trafilatura_extract.py` | 新闻/博客文章 |
| PDF/文档提取 | ✅ 已实现 | `extract/unstructured_extract.py` | PDF 等文档 |
| CSS 选择器提取 | ✅ 已实现 | `extract/structured/css_extractor.py` | 自定义规则 |
| LLM Schema 提取 | ✅ 已实现 | `extract/structured/llm_schema_extractor.py` | AI 结构化提取 |
| 内容清洗 | ✅ 已实现 | `extract/content_cleaner.py` | 噪声去除 |
| 内容分块 | ✅ 已实现 | `extract/chunking/hybrid_chunker.py` | RAG 分块 |

### 4.3 输出格式

| 格式 | 实现状态 | 实现文件 |
| --- | --- | --- |
| JSONL | ✅ 已实现 | `output/jsonl_writer.py` |
| JSON artifacts | ✅ 已实现 | `output/artifact_writer.py` |
| Summary | ✅ 已实现 | `output/summary_writer.py` |
| CSV | ❌ 未实现 | |

---

## 5. 配置文件状态

| 文件 | 协议要求 | 实现状态 | 路径 |
| --- | --- | --- | --- |
| `url_templates.json` | 各平台 URL 模板 | ✅ 已实现 | `references/url_templates.json` |
| `field_mappings.json` | 字段别名映射 | ✅ 已实现 | `references/field_mappings.json` |
| `rate_limits.json` | 限流参数 | ✅ 已实现 | `references/rate_limits.json` |
| `backend_routing.json` | 后端路由规则 | ✅ 已实现 | `references/backend_routing.json` |
| `wait_strategies.json` | 等待策略 | ✅ 已实现 | `references/wait_strategies.json` |

---

## 6. 实现进度总结

### 按模块统计

| 模块 | 总项数 | 已实现 | 部分实现 | 未实现 |
| --- | --- | --- | --- | --- |
| URL 发现机制 | 4 | 4 | 0 | 0 |
| 平台适配器 | 6 | 6 | 0 | 0 |
| 限流控制 | 5 | 2 | 2 | 1 |
| 错误处理 | 5 | 5 | 0 | 0 |
| 反爬对抗 | 7 | 1 | 1 | 5 |
| Session 管理 | 4 | 4 | 0 | 0 |
| 内容抓取与解析 | 12 | 11 | 0 | 1 |
| 配置文件 | 5 | 5 | 0 | 0 |
| **合计** | **48** | **38 (79%)** | **3 (6%)** | **7 (15%)** |

> **注**：
> - URL 发现机制中的 API 驱动、图谱遍历、搜索驱动、内容解析发现由其他人实现，待合并
> - 任务队列、URL 去重、断点续爬由后端 API 管理，不在 Skill 范围
> - 后端 API 协同在 Plugin 层实现，见 [plugin_api_checklist.md](plugin_api_checklist.md)

### 核心差距

- **反爬对抗**：无代理池、无 UA 轮换、无 CAPTCHA 处理
- **限流执行层**：有配置但执行层未强制间隔控制
