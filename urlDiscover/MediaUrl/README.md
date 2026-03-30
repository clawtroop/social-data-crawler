# MediaUrl
从 **Wikipedia**（MediaWiki API）与 **LinkedIn**（Playwright 登录会话 + HTML 解析）发现、归一化并收集媒体相关 URL 的实验代码。
当前版本有可能存在收集不全、去重、重复迭代等问题
## wikipedia
### 规范 URL 形式
主命名空间词条：https://{lang}.wikipedia.org/wiki/{Title}
### 发现方式
#### 使用随机条目
官方提供了获取随机条目的接口
#### 使用content
维基提供了非常多的分类，包含子分类

## 领英
### 规范 URL 形式
Profile: https://www.linkedin.com/in/{vanityName}/
Company: https://www.linkedin.com/company/{companyVanity}/
Job:     https://www.linkedin.com/jobs/view/{jobId}/
Post:    https://www.linkedin.com/feed/update/urn:li:activity:{activityId}/
### 发现方式
#### 从本人profile进行扩展，也可以提供额外种子。4种url可迭代遍历扩展。


## 环境准备

1. Python 3.10+。
2. 在项目根目录安装依赖：
  ```bash
   pip install -r requirements.txt
  ```
3. 使用领英抓取前需安装 Chromium 浏览器驱动：
  ```bash
   playwright install chromium
  ```
4. 运行脚本时，将项目根目录加入 `PYTHONPATH`（Windows PowerShell 示例）：
  ```powershell
   $env:PYTHONPATH = "d:\Code\MediaUrl"
  ```
   或每次在命令前设置（见下文各节）。
5. **可选**：PostgreSQL（仅在使用 `linkedin_url` 的 `schema-apply` / `seed` / `crawl` 流水线时需要）。连接串通过环境变量 `DATABASE_URL` 或各子命令的 `--database-url` 传入。

---

## Wikipedia 部分---提供random和contents两种扩展方法

### 程序入口概览


| 入口                                  | 说明                                                     |
| ----------------------------------- | ------------------------------------------------------ |
| `scripts/wikipedia_random_urls.py`  | 调用 `list=random`，批量生成主命名空间词条 URL（默认英文维基）               |
| `scripts/wikipedia_contents_dfs.py` | 从 `Wikipedia:Contents` 树做 DFS，收集主命名空间条目 URL 与元数据       |
| 包 `wikipedia_url/`                  | 被上述脚本引用：`mw_client`、`wiki_url`、`user_agent`、`http_env` |


### `scripts/wikipedia_random_urls.py`


| 参数                    | 说明                                               |
| --------------------- | ------------------------------------------------ |
| `-n, --count N`       | 随机词条数量，1–500，默认 `10`                             |
| `-o, --output PATH`   | 输出 JSON 路径；默认 `output/wikipedia_random_<N>.json` |
| `--include-redirects` | 包含重定向页（默认仅非重定向）                                  |
| `--timeout SEC`       | HTTP 超时秒数（默认见环境变量或 60）                           |


**环境变量**


| 变量                       | 说明                                                                      |
| ------------------------ | ----------------------------------------------------------------------- |
| `WIKIPEDIA_HTTP_TIMEOUT` | HTTP 超时（秒），未传 `--timeout` 时使用                                           |
| `WIKIPEDIA_USER_AGENT`   | 或写入 `.secrets/wikipedia_user_agent.txt`；见 `wikipedia_url/user_agent.py` |


**调用示例**

```powershell
$env:PYTHONPATH = "d:\Code\MediaUrl"
python scripts/wikipedia_random_urls.py
python scripts/wikipedia_random_urls.py -n 20
python scripts/wikipedia_random_urls.py -n 50 -o output/my_random.json --timeout 90
```

### `scripts/wikipedia_contents_dfs.py`


| 参数                                       | 说明                                                  |
| ---------------------------------------- | --------------------------------------------------- |
| `--lang LANG`                            | 语言子域，默认 `en`（用于 `https://{lang}.wikipedia.org/...`） |
| `--seed TITLE`                           | 起始页标题，默认 `Wikipedia:Contents`                       |
| `--prefix PREFIX`                        | 仅扩展此前缀下的 `Wikipedia:` 项目页，默认 `Wikipedia:Contents`   |
| `--max-depth D`                          | 目录树深度上限（根为 0）；不设则不限                                 |
| `--max-pages N`                          | 最多访问的 Contents **目录页**数；`0` 表示不限制（默认 `0`）           |
| `--max-seconds SEC` 或 `--time-limit SEC` | 墙钟时间上限（秒），到点即停并保存已抓取 URL                            |
| `--timeout SEC`                          | 单次 HTTP 超时（默认 60 或 `WIKIPEDIA_HTTP_TIMEOUT`）        |
| `--output-dir DIR`                       | 输出根目录；默认 `<项目根>/output/content/<lang>/`             |


**输出（默认目录下）**

- `crawl.json`：元数据与 `articles` 列表  
- `articles/<标题路径>/page.json`：单条条目的 `title`、`url`、`discovered_from` 等

**调用示例**

```powershell
$env:PYTHONPATH = "d:\Code\MediaUrl"
python scripts/wikipedia_contents_dfs.py --max-seconds 300
python scripts/wikipedia_contents_dfs.py --lang en --time-limit 120 --output-dir output/content/en
python scripts/wikipedia_contents_dfs.py --lang zh --max-depth 4 --max-pages 500
```

---

## LinkedIn 部分---入口scripts/post_expand_[test.py](http://test.py)



### 统一 CLI：`python -m linkedin_url`

主模块：`linkedin_url.cli`，等价于 `python -m linkedin_url`。


| 子命令            | 作用                                    |
| -------------- | ------------------------------------- |
| `login`        | 打开浏览器登录并保存 `storage_state`            |
| `fetch`        | 用已保存会话抓取单页 HTML                       |
| `verify`       | 访问一条动态 URL，检查是否仍显示访客登录墙               |
| `schema-apply` | 执行 Phase1+Phase2 DDL（需 PostgreSQL）    |
| `seed`         | 将一条 URL 归一化并入队 frontier               |
| `crawl`        | 从 frontier 消费：抓取 → 发现 → 扩边（需 DB + 会话） |


#### `login`


| 参数             | 说明                                                    |
| -------------- | ----------------------------------------------------- |
| `--state PATH` | 会话 JSON 路径（默认 `.secrets/linkedin_storage_state.json`） |
| `--headless`   | 无头模式（通常难以完成登录）                                        |
| `--no-wait`    | 不等待 Enter，加载后即保存                                      |
| `--proxy URL`  | 代理；未填则用 `LINKEDIN_PROXY` / `HTTPS_PROXY` 等            |


```powershell
python -m linkedin_url login
python -m linkedin_url login --proxy http://127.0.0.1:7890
```

#### `fetch`


| 参数                  | 说明                |
| ------------------- | ----------------- |
| `url`               | 要抓取的 LinkedIn URL |
| `--state PATH`      | 会话路径              |
| `--headed`          | 有头浏览器             |
| `-o, --output FILE` | 写入文件；否则打印到 stdout |
| `--proxy URL`       | 代理                |


```powershell
python -m linkedin_url fetch "https://www.linkedin.com/in/jianli-wang-926768a9/" -o page.html
```

#### `verify`


| 参数                 | 说明                |
| ------------------ | ----------------- |
| `--url URL`        | 检测用 URL（默认内置示例动态） |
| `--state PATH`     | 会话路径              |
| `--headed`         | 有头浏览器             |
| `--save-html FILE` | 保存本次 HTML 便于排查    |
| `--proxy URL`      | 代理                |


```powershell
python -m linkedin_url verify --save-html post.html
```

退出码：`0` 表示未检测到访客墙；`3` 表示疑似访客墙。

#### `schema-apply` / `seed` / `crawl`（需数据库）


| 变量             | 说明                                         |
| -------------- | ------------------------------------------ |
| `DATABASE_URL` | PostgreSQL 连接串；各子命令也可用 `--database-url` 覆盖 |


`**schema-apply**`

```powershell
python -m linkedin_url schema-apply
python -m linkedin_url schema-apply --database-url "postgresql://..."
```

`**seed**`


| 参数               | 说明                    |
| ---------------- | --------------------- |
| `url`            | 种子 URL                |
| `--label STR`    | `seed_label`，默认 `cli` |
| `--database-url` | 覆盖 `DATABASE_URL`     |


```powershell
python -m linkedin_url seed "https://www.linkedin.com/in/jianli-wang-926768a9/"
```

`**crawl**`


| 参数              | 说明                           |
| --------------- | ---------------------------- |
| `--max-steps N` | 本轮最多处理条数，默认 `10`             |
| `--max-depth N` | 相对种子的最大发现深度，默认 `2`           |
| `--label STR`   | 写入新前沿的 `seed_label`，默认 `cli` |
| `--state PATH`  | `storage_state.json`         |
| `--proxy URL`   | 代理                           |


```powershell
python -m linkedin_url crawl --max-steps 20 --max-depth 2
```

### 脚本入口（实验 / 调试用）


| 脚本                               | 默认行为概要                                                                                                                 |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `scripts/linkedin_expand_bfs.py` | 以会话解析的本人 profile + 脚本内 `EXTRA_SEED_URLS` 为种子，对四类标准 URL 做 BFS；结果写入项目根 `linkedin_bfs_output.json` 与 `output/bfs_expand/` |
| `scripts/profile_expand_test.py` | 单个人主页 URL（`PROFILE_URL`），扩展并保存 HTML/JSON                                                                               |
| `scripts/company_expand_test.py` | 单个公司页（`COMPANY_URL`），扩展 Overview/Jobs/People/Posts 等                                                                   |
| `scripts/post_expand_test.py`    | 单条或多条动态 URL（`POST_URLS`），扩展评论/侧栏等                                                                                      |


上述脚本均依赖 **已执行 `python -m linkedin_url login`** 生成的会话文件；多数通过脚本内常量或下方环境变量配置。

**常用环境变量（脚本）**


| 变量                                 | 说明                                             |
| ---------------------------------- | ---------------------------------------------- |
| `LINKEDIN_PROXY` / `HTTPS_PROXY`   | 代理（脚本未写死 `PROXY` 时）                            |
| `LINKEDIN_PROFILE_SEED`            | 覆盖 `linkedin_expand_bfs.py` 中从会话解析的 profile 种子 |
| `LINKEDIN_BFS_MAX_RUNTIME_SECONDS` | 覆盖 BFS 脚本的运行时间上限（秒）                            |


**调用示例**

```powershell
$env:PYTHONPATH = "d:\Code\MediaUrl"
python scripts/linkedin_expand_bfs.py
python scripts/profile_expand_test.py
python scripts/company_expand_test.py
python scripts/post_expand_test.py
```

各脚本顶部的 `PARSE_ONLY`、`PROFILE_URL`、`COMPANY_URL`、`POST_URLS`、`MAX_EXPAND_DEPTH` 等常量可直接编辑后再运行。

---

## 测试

```powershell
$env:PYTHONPATH = "d:\Code\MediaUrl"
pytest tests -q
```

---

## 仓库说明

- `output/`：爬虫输出（JSON/HTML），体积可能很大，按需保留或清理。  
- `.secrets/`：会话与 User-Agent 等敏感文件勿提交版本库（若使用请自行加入 `.gitignore`）。

