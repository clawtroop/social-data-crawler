# Dataset Product Catalog v2 · 完整字段对比（中文含义 · API · Playwright）

> 基准文档：仓库根目录 `Dataset_Product_Catalog_v2.md`  
> 项目语境：`social-data-crawler` 主链路（`crawler/platforms/*` 默认 backend）+ `urlDiscover` 下实验脚本（LinkedIn BFS、Amazon 统一爬取、arXiv/Wikipedia 发现等）  
> 更新：2026-03-30  

---

## 列说明


| 列                    | 含义                                                                                                                                                                           |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **中文含义**             | 字段在业务/数据上的简要中文解释                                                                                                                                                             |
| **API**              | 是否**不依赖浏览器渲染**即可稳定拿到**该字段本身或等价原始数据**（含：维基 MediaWiki API、arXiv export API、Base JSON-RPC / Basescan、LinkedIn **Voyager 内部 JSON**，需有效登录态 Cookie；**不含**亚马逊官方 PA-API 等需单独签约的商用接口） |
| **Playwright（当前项目）** | 在**现有** skill 的 `playwright`/`camoufox` 回退与 `urlDiscover` 脚本能力下，能否从 **DOM/HTML** 侧拿到**该字段或强相关原始片段**（**不等于**目录中的 LLM 增强成品）                                                    |


**关于「LLM 增强 / 🔥」类字段**：目录中标记为 LLM 专有的列，**任何** API 与 Playwright 都不会直接返回「成品字段值」；实现上需 **enrich（规则 + LLM）**。下表对这类字段：**API / Playwright 列记为「否（成品）」**，并在说明列写**可支撑 enrich 的原始信号**从哪里来。

**图例**：`可` = 主路径可覆盖 · `部分` = 需条件/仅子集/易变 · `否` = 当前架构下不可得或仅能通过 enrich 产出成品 · `—` = 不适用（纯派生字段）

---

## 1. LinkedIn Dataset

### 1.1 Profiles（个人档案）

#### 标准字段（与目录 `Standard Fields` 列逐条对齐）

目录原文按 **Category** 分组；下列 **字段名** 与 `Dataset_Product_Catalog_v2.md` §1.1 表格第一列 **Standard Fields** 中的名称一致（含合并单元格语义）。

| 目录 Category | 字段名（目录原文） | 中文含义 | API | Playwright（当前项目） |
|---------------|-------------------|----------|-----|------------------------|
| **Identity** | ID | 档案/实体内部标识（常与 `linkedin_id`、vanity 对应） | 部分（Voyager） | 部分（URL/HTML） |
| **Identity** | name | 姓名 | 可 | 可 |
| **Identity** | city | 所在城市 | 部分 | 部分 |
| **Identity** | country_code | 国家/地区代码 | 部分 | 部分 |
| **Identity** | avatar | 头像图片 URL | 可 | 可 |
| **Identity** | banner_image | 顶部横幅图 URL | 部分 | 部分 |
| **Identity** | URL | 规范公开档案链接 | 可 | 可 |
| **Identity** | linkedin_num_id | 数字型会员 id（若可得） | 部分（内嵌 JSON） | 否 |
| **Current Role** | position | 当前职位标题 | 可 | 可 |
| **Current Role** | current_company | 当前雇主（名称或 id，视实现） | 部分 | 部分 |
| **Current Role** | current_company_id | 当前公司实体 id | 部分 | 部分 |
| **Current Role** | current_company_name | 当前公司显示名称 | 可 | 可 |
| **About** | about | About 区原始文本 | 可 | 可 |
| **Experience** | experience | 工作经历（原始条目数组） | 部分 | 部分 |
| **Education** | education | 教育经历（主字段） | 部分 | 部分 |
| **Education** | educations_details | 教育经历（补充明细） | 部分 | 部分 |
| **Skills** | — | 目录注明 *not directly extracted*：无单独标准列，技能由 LLM 自 About/Experience 抽取 | — | — |
| **Social** | followers | 关注者/粉丝数 | 部分 | 部分 |
| **Social** | connections | 人脉数 | 部分 | 部分 |
| **Social** | posts | 动态相关计数或引用 | 部分 | 部分 |
| **Social** | recommendations_count | 推荐信/推荐数量 | 部分 | 部分 |
| **Network** | people_also_viewed | 「看过还看过」推荐列表 | 否/部分 | 部分（需更重页面/接口） |
| **Certifications** | certifications | 认证资质条目 | 部分 | 部分 |
| **Certifications** | languages | 语言能力条目 | 部分 | 部分 |
| **Certifications** | courses | 课程条目 | 部分 | 部分 |
| **Metadata** | timestamp | 采集时间戳（管道自建） | 可（自建） | 可（自建） |
| **Metadata** | input_url | 采集入口 URL | 可（自建） | 可（自建） |
| **🆕 Multimodal（标准侧）** | avatar | 与 Identity 同源：头像 URL，供多模态分析输入 | 可 | 可 |
| **🆕 Multimodal（标准侧）** | banner_image | 与 Identity 同源：横幅 URL，供多模态分析输入 | 部分 | 部分 |

> 上表 **Skills** 行：与目录一致，**不提供**独立「技能标准列」；`skills_extracted` 等见下方 LLM 增强字段。


#### LLM 增强字段（成品需 enrich）


| 字段名                        | 中文含义                   | API           | Playwright（当前项目） |
| -------------------------- | ---------------------- | ------------- | ---------------- |
| name_gender_inference      | 由姓名推断性别（推断类）           | 否（成品）         | 否（成品）            |
| name_ethnicity_estimation  | 姓名族裔估计（敏感/推断）          | 否             | 否                |
| profile_language_detected  | 档案主要语言检测               | 部分（文本可来自 API） | 部分（页面文本）         |
| standardized_job_title     | O*NET/ISCO 标准化职衔       | 否             | 否                |
| seniority_level            | 资历层级（C/VP/总监等）         | 否             | 否                |
| job_function_category      | 职能大类                   | 否             | 否                |
| about_summary              | About 三句摘要             | 否             | 否                |
| about_topics               | About 主题标签             | 否             | 否                |
| about_sentiment            | About 情感倾向             | 否             | 否                |
| career_narrative_type      | 叙事类型（builder/leader 等） | 否             | 否                |
| experience_structured      | 经历结构化（职责/技术栈等）         | 否             | 否                |
| education_structured       | 学历结构化（层次/排名层级等）        | 否             | 否                |
| skills_extracted           | 从全文抽取的技能列表             | 否             | 否                |
| skill_categories           | 技能分类                   | 否             | 否                |
| skill_proficiency_inferred | 基于经历与上下文推断技能熟练度        | 否             | 否                |
| influence_score            | 影响力综合分                 | 否             | 否                |
| engagement_rate            | 互动率                    | 否             | 否                |
| content_creator_tier       | 创作者层级                  | 否             | 否                |
| professional_cluster       | 职业聚类/同伴群               | 否             | 否                |
| career_trajectory_vector   | 职业轨迹向量                 | 否             | 否                |
| certification_validity     | 认证有效性等                 | 否             | 否                |
| language_proficiency_level | 语言水平（如 CEFR）           | 否             | 否                |
| profile_completeness_score | 档案完整度评分                | 否             | 否                |
| last_active_estimate       | 最近活跃估计                 | 否             | 否                |
| profile_freshness_grade    | 新鲜度等级                  | 否             | 否                |
| avatar_quality_assessment  | 头像质量多维度评估              | 否（需 CV/LLM）   | 否                |
| banner_content_analysis    | 横幅内容分析                 | 否             | 否                |
| one_line_summary           | 一句话摘要                  | 否             | 否                |
| recruiter_brief            | 招聘方简报                  | 否             | 否                |
| investor_brief             | 投资方简报                  | 否             | 否                |
| full_profile_narrative     | 全文叙事传记                 | 否             | 否                |
| writing_style_profile      | 写作风格画像                 | 否             | 否                |
| job_change_signal_strength | 跳槽信号强度                 | 否             | 否                |
| culture_fit_indicators     | 文化契合指标                 | 否             | 否                |
| linkable_identifiers       | 跨数据集链接（GitHub/ORCID 等） | 否（成品对象）       | 否（成品对象）          |

##### `linkable_identifiers` 对象键（目录 §1.1 Cross-dataset）

| 键名（目录） | 中文含义 | API | Playwright（当前项目） |
|-------------|----------|-----|------------------------|
| `github_urls` | 从正文抽取的 GitHub 链接列表 | 否（成品） | 否（成品） |
| `personal_website_url` | 个人网站 | 部分（若正文可见） | 部分 |
| `twitter_handle` | X/Twitter 账号 | 部分 | 部分 |
| `orcid_id` | ORCID 标识 | 部分 | 部分 |
| `google_scholar_url` | Google Scholar 主页 | 部分 | 部分 |
| `arxiv_author_query_hint` | 供 arXiv 检索用的「姓名+单位」提示串 | 否（成品） | 否（成品） |
| `company_domains_mentioned` | 提及的公司域名（可链亚马逊/维基） | 否（成品） | 否（成品） |
| `patent_numbers_mentioned` | 提及的专利号 | 否（成品） | 否（成品） |
| `publication_titles_mentioned` | 提及的论文标题（可链 arXiv） | 否（成品） | 否（成品） |

**说明（urlDiscover/MediaUrl）**：当前脚本侧重 **URL 发现、轻量快照**（如 `title`、`og_description`），**不**等价于目录级全字段覆盖；完整结构化仍以 Voyager/API + enrich 为主。

---

### 1.2 Company（公司页）

#### 标准字段（与目录 `Standard Fields` 列逐条对齐）

| 目录 Category | 字段名（目录原文） | 中文含义 | API | Playwright（当前项目） |
|---------------|-------------------|----------|-----|------------------------|
| **Basic** | ID | 公司实体 id | 部分 | 部分 |
| **Basic** | name | 公司名称 | 可 | 可 |
| **Basic** | URL | 公司主页链接 | 可 | 可 |
| **Basic** | country_code | 国家/地区代码 | 部分 | 部分 |
| **Basic** | locations | 办公地点（列表或文本） | 部分 | 部分 |
| **Basic** | website | 官方网站 URL | 部分 | 部分 |
| **Profile** | about | 公司简介原文 | 可 | 可 |
| **Profile** | specialties | 专长/业务标签 | 部分 | 部分 |
| **Profile** | industry | 行业 | 部分 | 部分 |
| **Scale** | followers | 关注者数 | 部分 | 部分 |
| **Scale** | employees_in_linkedin | 领英展示的员工规模区间等 | 部分 | 部分 |
| **Content** | posts | 近期动态（引用或摘要列表） | 部分 | 部分 |
| **Tech** | — | 目录注明 *not available*：无标准字段 | — | — |
| **Financials** | — | 目录注明 *not available*：无标准字段 | — | — |


#### LLM 增强字段


| 字段名                               | 中文含义              | API   | Playwright（当前项目） |
| --------------------------------- | ----------------- | ----- | ---------------- |
| company_legal_name_inferred       | 推断法定名称            | 否     | 否                |
| parent_company                    | 母公司               | 否     | 否                |
| subsidiary_tree                   | 子公司树              | 否     | 否                |
| about_summary                     | 公司简介摘要            | 否     | 否                |
| core_business_extracted           | 核心业务抽取            | 否     | 否                |
| value_proposition                 | 价值主张              | 否     | 否                |
| target_market_inferred            | 目标市场推断            | 否     | 否                |
| industry_standardized             | NAICS/SIC 等行业编码   | 否     | 否                |
| employee_growth_trend             | 员工数增长趋势（3/6/12 月） | 否     | 否                |
| hiring_velocity                   | 招聘速度              | 否     | 否                |
| attrition_signal                  | 流失/裁员信号           | 否     | 否                |
| department_distribution_estimated | 部门分布估计            | 否     | 否                |
| content_strategy_analysis         | 内容策略分析            | 否     | 否                |
| posting_frequency                 | 发帖频率              | 否     | 否                |
| top_topics                        | 热门主题              | 否     | 否                |
| brand_voice_profile               | 品牌声线画像            | 否     | 否                |
| tech_stack_inferred               | 技术栈推断             | 否     | 否                |
| engineering_team_size_estimated   | 工程团队规模估计          | 否     | 否                |
| funding_stage_inferred            | 融资阶段推断            | 否     | 否                |
| revenue_range_estimated           | 收入区间估计            | 否     | 否                |
| business_model_type               | 商业模式类型            | 否     | 否                |
| elevator_pitch                    | 一句话电梯演讲           | 否     | 否                |
| investor_brief                    | 投资人简报             | 否     | 否                |
| competitor_brief                  | 竞品对比简报            | 否     | 否                |
| linkable_identifiers              | 域名、亚马逊/Wiki 等跨库提示（成品对象） | 否（成品） | 否（成品）            |

##### `linkable_identifiers` 对象键（目录 §1.2 Cross-dataset）

以下为目录示例中 **对象内键名**（非单独顶层标准字段），**成品**仍由 enrich 抽取；原始文本来自 about/website。

| 键名（目录） | 中文含义 | API | Playwright（当前项目） |
|-------------|----------|-----|------------------------|
| `website_domain` | 官网域名 | 部分 | 部分 |
| `amazon_seller_search_hint` | 用于匹配亚马逊卖家的品牌+关键词提示 | 否（成品） | 否（成品） |
| `wikipedia_entity_hint` | 用于查找维基条目的规范公司名 | 否（成品） | 否（成品） |
| `github_org_url` | 提及的 GitHub 组织 URL | 部分（若正文可见） | 部分 |
| `crunchbase_hint` | Crunchbase 检索提示 | 否（成品） | 否（成品） |
| `base_contract_deployer_hint` | Web3 场景下合约/协议名提示 | 否（成品） | 否（成品） |

---

### 1.3 Jobs（职位）

#### 标准字段（与目录 `Standard Fields` 列逐条对齐）

| 目录 Category | 字段名（目录原文） | 中文含义 | API | Playwright（当前项目） |
|---------------|-------------------|----------|-----|------------------------|
| **Basic** | job_posting_id | 职位唯一标识 | 部分 | 部分 |
| **Basic** | job_title | 职位名称 | 可 | 可 |
| **Basic** | company_name | 招聘公司名称 | 可 | 可 |
| **Basic** | company_id | 公司实体 id | 部分 | 部分 |
| **Basic** | job_location | 工作地点（原始字符串） | 可 | 可 |
| **Content** | job_summary | 职位摘要（若有） | 部分 | 部分 |
| **Content** | job_description | 职位描述（HTML/文本） | 可 | 可 |
| **Classification** | job_seniority_level | 职级（若页面/接口提供） | 部分 | 部分 |
| **Classification** | job_function | 职能分类（若提供） | 部分 | 部分 |
| **Skills** | — | 目录注明 *not directly extracted*：无单独标准技能列，技能见 LLM 表 | — | — |
| **Market** | applicants_count | 申请人数等 | 部分 | 部分 |
| **Market** | date_posted | 发布日期 | 部分 | 部分 |


#### LLM 增强字段


| 字段名                        | 中文含义           | API | Playwright（当前项目） |
| -------------------------- | -------------- | --- | ---------------- |
| job_title_standardized     | 标准化职衔          | 否   | 否                |
| remote_policy              | 远程政策（远程/混合/现场） | 否   | 否                |
| location_parsed            | 解析后的城市/州/国家    | 否   | 否                |
| responsibilities_extracted | 职责要点列表         | 否   | 否                |
| requirements_extracted     | 要求结构化（技能、年限等）  | 否   | 否                |
| salary_range_inferred      | 推断薪资区间         | 否   | 否                |
| benefits_extracted         | 福利要点           | 否   | 否                |
| team_size_hint             | 团队规模线索         | 否   | 否                |
| reporting_to_level         | 汇报层级线索         | 否   | 否                |
| role_category_fine_grained | 细粒度角色类别        | 否   | 否                |
| industry_vertical          | 行业垂直           | 否   | 否                |
| visa_sponsorship_signal    | 是否赞助工签信号       | 否   | 否                |
| equity_compensation_signal | 股权/期权信号        | 否   | 否                |
| required_skills            | 必备技能           | 否   | 否                |
| preferred_skills           | 优先技能           | 否   | 否                |
| tools_and_platforms        | 工具与平台          | 否   | 否                |
| programming_languages      | 编程语言           | 否   | 否                |
| frameworks                 | 框架             | 否   | 否                |
| competition_level          | 竞争激烈度          | 否   | 否                |
| days_to_fill_estimated     | 预计填补天数         | 否   | 否                |
| urgency_signal             | 紧急程度信号         | 否   | 否                |
| reposting_frequency        | 重复发布频率         | 否   | 否                |
| candidate_facing_summary   | 候选人友好摘要        | 否   | 否                |
| hiring_manager_brief       | 用人经理简报         | 否   | 否                |
| red_flags_detected         | 风险/红旗列表        | 否   | 否                |
| culture_signals_extracted  | 文化与管理风格信号      | 否   | 否                |
| tech_stack_full_picture    | 技术栈全景          | 否   | 否                |


---

### 1.4 Posts（动态）

#### 标准字段（与目录 `Standard Fields` 列逐条对齐）

| 目录 Category | 字段名（目录原文） | 中文含义 | API | Playwright（当前项目） |
|---------------|-------------------|----------|-----|------------------------|
| **Content** | post_text | 动态正文 | 部分 | 部分 |
| **Content** | title | 标题（若有） | 部分 | 部分 |
| **Content** | headline | 摘要行/引题 | 部分 | 部分 |
| **Content** | hashtags | 话题标签 | 部分 | 部分 |
| **Content** | images | 图片 URL 列表 | 部分 | 部分 |
| **Content** | videos | 视频 URL 列表 | 部分 | 部分 |
| **Engagement** | num_likes | 点赞数 | 部分 | 部分 |
| **Engagement** | num_comments | 评论数 | 部分 | 部分 |
| **Engagement** | top_visible_comments | 可见热评/首屏评论 | 部分 | 部分 |
| **Author** | user_id | 作者用户 id | 部分 | 部分 |
| **Author** | user_url | 作者主页链接 | 可 | 可 |
| **Author** | user_followers | 作者粉丝数 | 部分 | 部分 |
| **Temporal** | date_posted | 发布时间 | 部分 | 部分 |
| **🆕 Multimodal（标准侧）** | images[] | 与 Content 同源：图片 URL，供多模态分析 | 部分 | 部分 |
| **🆕 Multimodal（标准侧）** | videos[] | 与 Content 同源：视频 URL，供多模态分析 | 部分 | 部分 |


#### LLM 增强字段


| 字段名                            | 中文含义              | API | Playwright（当前项目） |
| ------------------------------ | ----------------- | --- | ---------------- |
| post_topic_tags                | 帖子主题标签            | 否   | 否                |
| post_type                      | 帖子类型（思想领导/招聘/公关等） | 否   | 否                |
| key_claims_extracted           | 关键论点抽取            | 否   | 否                |
| entities_mentioned             | 实体及情感             | 否   | 否                |
| engagement_quality_score       | 互动质量分             | 否   | 否                |
| comment_sentiment_distribution | 评论情感分布            | 否   | 否                |
| viral_coefficient_estimated    | 传播系数估计            | 否   | 否                |
| controversial_flag             | 争议内容标记            | 否   | 否                |
| author_authority_score         | 作者权威分             | 否   | 否                |
| author_industry                | 作者行业推断            | 否   | 否                |
| is_corporate_voice             | 是否企业号口吻           | 否   | 否                |
| trending_topic_relevance       | 热点相关性             | 否   | 否                |
| news_event_linkage             | 新闻事件关联            | 否   | 否                |
| post_image_analysis            | 配图多模态分析           | 否   | 否                |
| shared_link_content_summary    | 外链内容摘要            | 否   | 否                |
| post_one_liner                 | 一句话概括             | 否   | 否                |
| post_takeaway                  | 可执行洞见             | 否   | 否                |
| thought_leadership_depth       | 思想深度层级            | 否   | 否                |
| self_promotion_score           | 自我推广程度            | 否   | 否                |
| argument_structure             | 论证结构类型            | 否   | 否                |


---

## 2. arXiv Dataset

### 标准字段（元数据 + 全文）


| 字段名                                      | 中文含义          | API                     | Playwright（当前项目） |
| ---------------------------------------- | ------------- | ----------------------- | ---------------- |
| arxiv_id                                 | 论文 arXiv 编号   | 可（export.arxiv.org API） | 部分               |
| DOI                                      | 数字对象标识符       | 部分（元数据内）                | 部分               |
| URL                                      | 摘要页链接         | 可                       | 可                |
| title                                    | 标题            | 可                       | 可                |
| abstract                                 | 摘要            | 可                       | 可                |
| authors[]                                | 作者与单位         | 可                       | 可                |
| categories / primary_category            | arXiv 分类      | 可                       | 可                |
| submission_date / update_date / versions | 提交与版本日期       | 可                       | 部分               |
| raw_text                                 | 全文文本（来源因实现而异） | 部分（LaTeX/HTML）          | 部分               |
| PDF_url                                  | PDF 链接        | 可                       | 可                |
| references[]                             | 参考文献串         | 部分                      | 部分               |


### LLM 增强字段（目录逐字段）

> 说明：**成品**列均为目录中的 LLM 输出 → API/Playwright 列填 **否**；全文/元数据常经 **export API** 取得，故「enrich 输入」侧 API 多为 **部分~可**。


| 字段名                               | 中文含义                  | API       | Playwright（当前项目） |
| --------------------------------- | --------------------- | --------- | ---------------- |
| title_normalized                  | 去 LaTeX 的规范标题         | 否         | 否                |
| abstract_plain_text               | 去公式的纯文本摘要             | 否         | 否                |
| authors_structured                | 作者结构化（姓名拆分、单位标准化等）    | 否         | 否                |
| topic_hierarchy                   | 主题层级（领域>子领域>主题）       | 否         | 否                |
| keywords_extracted                | 抽取关键词                 | 否         | 否                |
| research_area_plain_english       | 研究领域白话说明              | 否         | 否                |
| interdisciplinary_score           | 跨学科程度                 | 否         | 否                |
| acceptance_status_inferred        | 推断发表状态                | 否         | 否                |
| venue_published                   | 发表会议/期刊名              | 否         | 否                |
| venue_tier                        | venue 等级（A*/A/B 等）    | 否         | 否                |
| sections_structured               | 按章节结构化摘要              | 否         | 否                |
| main_contributions                | 主要贡献陈述                | 否         | 否                |
| novelty_type                      | 创新类型                  | 否         | 否                |
| problem_statement                 | 问题陈述                  | 否         | 否                |
| proposed_solution_summary         | 方案摘要                  | 否         | 否                |
| methods_used                      | 方法列表及是否新颖             | 否         | 否                |
| baselines_compared                | 对比基线                  | 否         | 否                |
| evaluation_metrics                | 评估指标                  | 否         | 否                |
| datasets_used                     | 使用数据集                 | 否         | 否                |
| experimental_setup_summary        | 实验设置摘要                | 否         | 否                |
| key_results                       | 关键结果（指标、提升等）          | 否         | 否                |
| state_of_art_claimed              | 是否声称 SOTA             | 否         | 否                |
| statistical_significance_reported | 显著性是否报告               | 否         | 否                |
| reproducibility_indicators        | 可复现性线索                | 否         | 否                |
| limitations_stated                | 文中局限                  | 否         | 否                |
| future_work_directions            | 未来工作方向                | 否         | 否                |
| threats_to_validity               | 效度威胁                  | 否         | 否                |
| references_structured             | 结构化参考文献               | 否         | 否                |
| total_citation_count              | 总被引量                  | 否         | 否                |
| influential_citation_count        | 高影响力引用数               | 否         | 否                |
| code_available                    | 是否有公开代码               | 否         | 否                |
| code_url                          | 代码链接                  | 部分（全文/页内） | 部分               |
| code_framework                    | 框架（PyTorch 等）         | 否         | 否                |
| dataset_released                  | 是否发布数据集               | 否         | 否                |
| dataset_url                       | 数据集链接                 | 部分        | 部分               |
| open_access_status                | 开放获取状态                | 否         | 否                |
| title_embedding                   | 标题向量                  | 否         | 否                |
| abstract_embedding                | 摘要向量                  | 否         | 否                |
| full_paper_embedding              | 全文向量                  | 否         | 否                |
| builds_upon                       | 延伸自哪些论文               | 否         | 否                |
| contradicts                       | 与哪些观点冲突               | 否         | 否                |
| replicates                        | 复现哪些工作                | 否         | 否                |
| uses_dataset_from                 | 使用哪些数据集来源             | 否         | 否                |
| uses_method_from                  | 方法来自哪些文献              | 否         | 否                |
| figures_analyzed                  | 图表多模态分析               | 否         | 否                |
| key_equations                     | 关键公式与解释               | 否         | 否                |
| tweet_summary                     | 推文级短摘要                | 否         | 否                |
| one_line_summary                  | 一句话技术摘要               | 否         | 否                |
| executive_summary                 | 高管/非技术摘要              | 否         | 否                |
| layman_summary                    | 外行可读长摘要               | 否         | 否                |
| technical_abstract_enhanced       | 增强版摘要                 | 否         | 否                |
| review_style_summary              | 模拟审稿意见结构              | 否         | 否                |
| mathematical_complexity_score     | 数学复杂度 1–5             | 否         | 否                |
| mathematical_complexity_evidence  | 复杂度依据                 | 否         | 否                |
| novelty_delta_assessment          | 创新度相对先验的评估            | 否         | 否                |
| methodology_transferability       | 方法可迁移领域               | 否         | 否                |
| claim_verification_notes          | 主张—证据核对               | 否         | 否                |
| linkable_identifiers              | 跨库链接（GitHub、Wiki 概念等） | 否（成品）     | 否（成品）            |


 `total_citation_count` / `influential_citation_count` / 各 `embedding`：需 **外部学术 API 或自建嵌入流水线**，非 arXiv export 默认字段。

---

## 3. Wikipedia Dataset

### 标准字段


| 字段名             | 中文含义       | API                       | Playwright（当前项目） |
| --------------- | ---------- | ------------------------- | ---------------- |
| URL             | 条目 URL     | 可                         | 可                |
| page_id         | 页面数字 id    | 可（MediaWiki API）          | 部分               |
| title           | 标题         | 可                         | 可                |
| language        | 语言         | 可                         | 可                |
| raw_text / HTML | 维基源码或 HTML | 可（API: revisions / parse） | 部分               |
| categories[]    | 分类         | 可                         | 部分               |
| images[]        | 图片 URL 列表  | 部分                        | 部分               |


### LLM 增强字段（目录逐字段）


| 字段名                         | 中文含义             | API                   | Playwright（当前项目） |
| --------------------------- | ---------------- | --------------------- | ---------------- |
| title_disambiguated         | 消歧后的标题           | 否                     | 否                |
| canonical_entity_name       | 规范实体名            | 否                     | 否                |
| entity_type                 | 实体类型（人/地/组织/概念等） | 否                     | 否                |
| wikidata_id                 | Wikidata Q 号     | 部分（需 Wikidata API 另查） | 否                |
| sections_structured         | 章节结构化            | 否                     | 否                |
| table_of_contents           | 目录结构             | 否                     | 否                |
| article_summary             | 3–5 句摘要          | 否                     | 否                |
| reading_level               | 可读性（如 Flesch）    | 否                     | 否                |
| tables_structured           | 表格结构化            | 否                     | 否                |
| infobox_structured          | 信息框键值对           | 否                     | 否                |
| categories_cleaned          | 清洗后的分类           | 否                     | 否                |
| topic_hierarchy             | 主题层级             | 否                     | 否                |
| domain                      | 领域（科学/历史等）       | 否                     | 否                |
| subject_tags                | 主题标签             | 否                     | 否                |
| entities_extracted          | 实体抽取（PER/ORG 等）  | 否                     | 否                |
| structured_facts            | 可用于图谱的三元组        | 否                     | 否                |
| temporal_events             | 时间线事件            | 否                     | 否                |
| related_entities            | 相关实体与关系          | 否                     | 否                |
| external_links_classified   | 外链分类与可信度         | 否                     | 否                |
| article_quality_class       | 条目质量等级（FA/GA 等）  | 部分（部分元数据 API）         | 部分               |
| neutrality_score            | 中立性评分            | 否                     | 否                |
| citation_density            | 引用密度             | 否                     | 否                |
| last_major_edit             | 最近大改时间           | 部分（API: revisions）    | 部分               |
| edit_controversy_score      | 编辑争议度            | 否                     | 否                |
| cross_language_links        | 跨语言链接            | 部分（API: langlinks）    | 部分               |
| translation_coverage_score  | 翻译覆盖度            | 否                     | 否                |
| entity_name_translations    | 实体各语言名称          | 部分（Wikidata）          | 否                |
| article_embedding           | 条目向量             | 否                     | 否                |
| section_embeddings          | 分节向量             | 否                     | 否                |
| images_annotated            | 配图详细标注           | 否                     | 否                |
| one_line_summary            | 一句话概括            | 否                     | 否                |
| eli5_summary                | 儿童友好解释           | 否                     | 否                |
| standard_summary            | 百科口吻标准摘要         | 否                     | 否                |
| academic_summary            | 学术综述式摘要          | 否                     | 否                |
| key_takeaways               | 要点列表             | 否                     | 否                |
| prerequisite_concepts       | 先修概念链            | 否                     | 否                |
| difficulty_level            | 难度等级             | 否                     | 否                |
| quiz_questions_generated    | 自动生成测验题          | 否                     | 否                |
| common_misconceptions       | 常见误解与纠正          | 否                     | 否                |
| bias_detection              | 偏见检测条目           | 否                     | 否                |
| missing_perspectives        | 缺失视角             | 否                     | 否                |
| weasel_words_detected       | 含糊用语检测           | 否                     | 否                |
| information_freshness_score | 信息新鲜度            | 否                     | 否                |
| potentially_outdated_claims | 可能过时陈述           | 否                     | 否                |
| temporal_coverage_gap       | 时间覆盖缺口           | 否                     | 否                |
| linkable_identifiers        | 跨库链接提示           | 否（成品）                 | 否（成品）            |


 向量需自建嵌入管线。

---

## 4. Amazon Dataset

### 4.1 Products（商品）

#### 标准字段


| 字段名                                               | 中文含义    | API       | Playwright（当前项目） |
| ------------------------------------------------- | ------- | --------- | ---------------- |
| ASIN                                              | 商品编码    | 可（页内/URL） | 可                |
| URL                                               | 商品页     | 可         | 可                |
| title                                             | 标题      | 可         | 可                |
| brand                                             | 品牌      | 可         | 可                |
| seller_name / seller_id                           | 卖家名与 id | 部分        | 部分               |
| initial_price / final_price / currency / discount | 价格与折扣   | 部分        | 部分               |
| description / bullet_points / features            | 描述与要点   | 可         | 可                |
| categories[] / breadcrumbs                        | 类目与面包屑  | 部分        | 部分               |
| images[] / main_image                             | 图集与主图   | 可         | 可                |
| availability / stock_status                       | 库存状态    | 部分        | 部分               |
| reviews_count / rating                            | 评论数与星级  | 部分        | 部分               |
| sizes[] / colors[] / styles[]                     | 变体维度    | 部分        | 部分               |


**说明**：skill 默认 **http**，**playwright** 为反爬/动态内容回退；**无**内置亚马逊**官方** Product Advertising API（若接入需单独密钥与合规）。

#### LLM 增强字段


| 字段名                                    | 中文含义         | API   | Playwright（当前项目） |
| -------------------------------------- | ------------ | ----- | ---------------- |
| title_cleaned                          | 去关键词堆砌的标题    | 否     | 否                |
| brand_standardized                     | 规范品牌名        | 否     | 否                |
| is_brand_official_store                | 是否品牌官方店      | 否     | 否                |
| price_tier                             | 价位带（入门/中端等）  | 否     | 否                |
| price_vs_category_avg                  | 相对类目均价       | 否     | 否                |
| historical_price_trend                 | 历史价格趋势       | 否     | 否                |
| deal_quality_score                     | 促销质量分        | 否     | 否                |
| features_structured                    | 结构化卖点参数      | 否     | 否                |
| key_specs_table                        | 关键规格表        | 否     | 否                |
| use_cases_extracted                    | 使用场景         | 否     | 否                |
| target_audience_inferred               | 目标受众推断       | 否     | 否                |
| category_standardized                  | 映射到标准类目体系    | 否     | 否                |
| niche_tags                             | 细分标签         | 否     | 否                |
| seasonal_relevance                     | 季节性相关        | 否     | 否                |
| image_count                            | 图片数量（可规则化）   | 部分    | 部分               |
| has_lifestyle_images                   | 含生活方式图       | 否     | 否                |
| has_infographic                        | 含信息图         | 否     | 否                |
| has_video                              | 含视频          | 部分    | 部分               |
| visual_quality_score                   | 视觉质量分        | 否     | 否                |
| fulfillment_type                       | FBA/FBM 等    | 部分    | 部分               |
| shipping_speed_tier                    | 配送速度层级       | 部分    | 部分               |
| prime_eligible                         | Prime 资格     | 部分    | 部分               |
| estimated_monthly_sales                | 月销量估计        | 否     | 否                |
| competitive_position                   | 类目排名与竞品      | 否     | 否                |
| listing_quality_score                  | Listing 质量分  | 否     | 否                |
| seo_keyword_density                    | SEO 关键词密度    | 否     | 否                |
| rating_trend                           | 评分趋势         | 否     | 否                |
| review_velocity                        | 评论速度         | 否     | 否                |
| fake_review_risk_score                 | 虚假评论风险       | 否     | 否                |
| verified_purchase_ratio                | 验证购买占比       | 部分    | 部分               |
| variant_matrix_structured              | 变体矩阵         | 否     | 否                |
| best_seller_variant                    | 最热卖变体        | 否     | 否                |
| variant_price_range                    | 变体价格区间       | 部分    | 部分               |
| certifications_mentioned               | 认证提及         | 否     | 否                |
| country_of_origin                      | 原产国          | 部分    | 部分               |
| material_composition_extracted         | 材质成分         | 否     | 否                |
| safety_warnings                        | 安全警告         | 部分    | 部分               |
| main_image_analysis                    | 主图多模态分析      | 否     | 否                |
| all_images_analysis                    | 全图分析         | 否     | 否                |
| image_text_consistency_score           | 图文一致性        | 否     | 否                |
| listing_visual_completeness            | 视觉素材完整度      | 否     | 否                |
| buyer_quick_take                       | 买家一句话结论      | 否     | 否                |
| product_elevator_pitch                 | 产品电梯演讲       | 否     | 否                |
| seller_competitive_brief               | 相对竞品简报       | 否     | 否                |
| seo_optimized_description              | SEO 优化描述     | 否     | 否                |
| product_lifecycle_stage_inferred       | 生命周期阶段       | 否     | 否                |
| lifecycle_evidence                     | 生命周期证据       | 否     | 否                |
| unique_selling_points                  | 独特卖点         | 否     | 否                |
| purchase_decision_factors_from_listing | 购买决策因素       | 否     | 否                |
| cross_sell_category_hints              | 交叉销售类目提示     | 否     | 否                |
| listing_optimization_score             | Listing 优化分  | 否     | 否                |
| listing_issues_detected                | Listing 问题列表 | 否     | 否                |
| listing_completeness                   | 各块完整度        | 否     | 否                |
| linkable_identifiers                   | 跨库链接         | 否（成品） | 否（成品）            |


 历史价/趋势需 **价格历史 API 或长期抓取**，当前单次页面多为 **部分/否**。

### 4.2 Reviews（评论）

#### 标准字段


| 字段名               | 中文含义     | API | Playwright（当前项目） |
| ----------------- | -------- | --- | ---------------- |
| review_id         | 评论 id    | 部分  | 部分               |
| ASIN              | 商品编码     | 可   | 可                |
| URL               | 评论或商品页链接 | 可   | 可                |
| author_name       | 评论者名     | 可   | 可                |
| author_id         | 评论者 id   | 部分  | 部分               |
| rating            | 星级       | 可   | 可                |
| review_text       | 评论正文     | 可   | 可                |
| review_headline   | 评论标题     | 可   | 可                |
| date_posted       | 发布日期     | 可   | 可                |
| helpful_count     | 有用投票     | 部分  | 部分               |
| verified_purchase | 是否验证购买   | 部分  | 部分               |
| review_images[]   | 评论配图     | 部分  | 部分               |


#### LLM 增强字段


| 字段名                           | 中文含义     | API | Playwright（当前项目） |
| ----------------------------- | -------- | --- | ---------------- |
| reviewer_profile_type         | 评论者类型    | 否   | 否                |
| sentiment_overall             | 整体情感     | 否   | 否                |
| sentiment_aspects             | 方面级情感    | 否   | 否                |
| product_pros_extracted        | 优点抽取     | 否   | 否                |
| product_cons_extracted        | 缺点抽取     | 否   | 否                |
| feature_satisfaction_map      | 功能满意度映射  | 否   | 否                |
| use_case_mentioned            | 使用场景     | 否   | 否                |
| comparison_to_alternatives    | 与竞品对比    | 否   | 否                |
| review_quality_score          | 评论质量分    | 否   | 否                |
| review_type                   | 评论类型     | 否   | 否                |
| authenticity_score            | 真实性分     | 否   | 否                |
| information_density           | 信息密度     | 否   | 否                |
| issues_reported               | 问题与严重度   | 否   | 否                |
| customer_segment_inferred     | 客户细分     | 否   | 否                |
| purchase_context              | 购买场景     | 否   | 否                |
| image_content_described       | 配图内容描述   | 否   | 否                |
| shows_product_in_use          | 是否展示使用场景 | 否   | 否                |
| shows_defect                  | 是否展示缺陷   | 否   | 否                |
| review_image_analysis         | 评论图多模态分析 | 否   | 否                |
| review_one_liner              | 一句话评论摘要  | 否   | 否                |
| purchase_decision_factor      | 决策主因     | 否   | 否                |
| usage_duration_mentioned      | 使用时长提及   | 否   | 否                |
| expertise_level_inferred      | 专业度推断    | 否   | 否                |
| actionable_feedback           | 可执行反馈    | 否   | 否                |
| competitor_products_mentioned | 提及的竞品    | 否   | 否                |


### 4.3 Sellers（卖家）

#### 标准字段


| 字段名                         | 中文含义    | API | Playwright（当前项目） |
| --------------------------- | ------- | --- | ---------------- |
| seller_id                   | 卖家 id   | 可   | 可                |
| URL                         | 卖家页     | 可   | 可                |
| seller_name                 | 卖家显示名   | 可   | 可                |
| seller_email / seller_phone | 联系邮箱/电话 | 部分  | 部分               |
| stars                       | 卖家星级    | 部分  | 部分               |
| feedbacks                   | 反馈统计    | 部分  | 部分               |
| return_policy               | 退货政策    | 部分  | 部分               |
| description                 | 卖家描述    | 可   | 可                |
| detailed_info               | 详细信息块   | 部分  | 部分               |


#### LLM 增强字段


| 字段名                      | 中文含义         | API   | Playwright（当前项目） |
| ------------------------ | ------------ | ----- | ---------------- |
| seller_type              | 卖家类型（品牌/倒爷等） | 否     | 否                |
| business_name_registered | 注册企业名        | 否     | 否                |
| seller_health_score      | 健康度综合分       | 否     | 否                |
| response_time_tier       | 响应时间层级       | 否     | 否                |
| dispute_rate_estimated   | 纠纷率估计        | 否     | 否                |
| product_count            | 商品数量         | 部分    | 部分               |
| category_focus           | 类目聚焦         | 否     | 否                |
| brand_portfolio          | 品牌组合         | 否     | 否                |
| price_range              | 价格区间         | 部分    | 部分               |
| avg_product_rating       | 平均商品评分       | 部分    | 部分               |
| years_on_amazon          | 在亚马逊年数       | 部分    | 部分               |
| growth_trajectory        | 增长轨迹         | 否     | 否                |
| geographic_focus         | 地理侧重         | 否     | 否                |
| fulfillment_strategy     | 履约策略         | 否     | 否                |
| seller_one_liner         | 卖家一句话画像      | 否     | 否                |
| seller_profile_narrative | 卖家叙事简介       | 否     | 否                |
| linkable_identifiers     | 跨库链接         | 否（成品） | 否（成品）            |


---

## 5. Base Onchain Dataset

### 5.1 Transactions（交易）


| 字段名                                   | 中文含义        | API             | Playwright（当前项目） |
| ------------------------------------- | ----------- | --------------- | ---------------- |
| tx_hash                               | 交易哈希        | 可（RPC/Basescan） | 否                |
| block_number / block_timestamp        | 区块与时间       | 可               | 否                |
| from_address / to_address             | 收发地址        | 可               | 否                |
| value (wei)                           | 原生币数值       | 可               | 否                |
| gas_used / gas_price / nonce / status | Gas 与状态     | 可               | 否                |
| input_data                            | 输入 calldata | 可               | 否                |


#### LLM / 派生字段（目录）


| 字段名                     | 中文含义           | API           | Playwright（当前项目） |
| ----------------------- | -------------- | ------------- | ---------------- |
| value_usd               | 交易时美元价值        | 部分（需价源+时间戳）   | 否                |
| gas_fee_usd             | Gas 美元费用       | 部分            | 否                |
| tx_fee_tier             | 费用档位           | 否             | 否                |
| function_name           | 调用函数名          | 部分（解码库）       | 否                |
| function_signature      | 函数选择器/签名       | 部分            | 否                |
| decoded_parameters      | 解码参数           | 部分            | 否                |
| human_readable_action   | 人类可读动作描述       | 否             | 否                |
| tx_type                 | 交易类型（转账/兑换等）   | 否             | 否                |
| protocol_name           | 协议名称           | 部分（地址簿/解码）    | 否                |
| protocol_category       | 协议类别           | 否             | 否                |
| token_transfers         | 代币转账列表         | 部分（需 logs 解析） | 否                |
| is_mev                  | 是否 MEV 相关      | 否             | 否                |
| mev_type                | MEV 类型         | 否             | 否                |
| is_contract_interaction | 是否合约交互         | 可（推导）         | 否                |
| is_internal_tx_parent   | 是否内部交易父级       | 部分            | 否                |
| related_tx_hashes       | 关联交易           | 否             | 否                |
| sender_risk_label       | 发送方风险标签        | 否             | 否                |
| receiver_risk_label     | 接收方风险标签        | 否             | 否                |
| anomaly_flags           | 异常标记           | 否             | 否                |
| fund_source_trace       | 资金来源追踪         | 否             | 否                |
| compliance_narrative    | 合规叙事段落         | 否             | 否                |
| investor_narrative      | 投资视角叙事         | 否             | 否                |
| strategy_signal         | 策略信号（DCA/套利等）  | 否             | 否                |
| linkable_identifiers    | 协议站/GitHub 等提示 | 否（成品）         | 否（成品）            |


 MEV、风险、资金流通常需 **专业链上索引或商业 API**，非默认 RPC。

### 5.2 Addresses / Wallets（地址）

#### 标准 / 可解析字段


| 字段名                          | 中文含义  | API | Playwright（当前项目） |
| ---------------------------- | ----- | --- | ---------------- |
| address                      | 地址    | 可   | 否                |
| eth_balance                  | 原生币余额 | 可   | 否                |
| first_tx_date / last_tx_date | 首末笔日期 | 部分  | 否                |
| tx_count                     | 交易笔数  | 部分  | 否                |


#### LLM / 聚合字段（目录）


| 字段名                        | 中文含义        | API        | Playwright（当前项目） |
| -------------------------- | ----------- | ---------- | ---------------- |
| balance_usd                | 余额美元        | 部分         | 否                |
| total_value_locked_usd     | TVL 美元      | 否          | 否                |
| portfolio_composition      | 资产组合        | 否          | 否                |
| label                      | 标签（交易所/合约等） | 部分（标签服务）   | 否                |
| entity_name                | 实体名         | 部分         | 否                |
| ens_name                   | ENS 域名      | 部分（合约/API） | 否                |
| is_contract                | 是否合约        | 可          | 否                |
| contract_type              | 合约类型        | 部分         | 否                |
| activity_summary           | 活动摘要统计      | 否          | 否                |
| defi_positions             | DeFi 头寸     | 否          | 否                |
| nft_holdings               | NFT 持仓      | 否          | 否                |
| nft_trading_pnl            | NFT 交易盈亏    | 否          | 否                |
| wallet_archetype           | 钱包画像类型      | 否          | 否                |
| trading_pattern            | 交易风格        | 否          | 否                |
| risk_appetite_score        | 风险偏好        | 否          | 否                |
| sophistication_score       | 老练度         | 否          | 否                |
| risk_score                 | 风险分         | 否          | 否                |
| sanctions_match            | 制裁匹配        | 否          | 否                |
| mixer_interaction_count    | 混币交互次数      | 否          | 否                |
| high_risk_counterparties   | 高风险对手方      | 否          | 否                |
| fund_flow_risk_path        | 资金流风险路径     | 否          | 否                |
| wallet_one_liner           | 钱包一句话       | 否          | 否                |
| compliance_profile_summary | 合规侧写        | 否          | 否                |
| investor_profile_summary   | 投资侧写        | 否          | 否                |
| cross_chain_address_hint   | 跨链同控线索      | 否          | 否                |
| deployer_analysis          | 部署合约分析      | 部分         | 否                |
| token_approval_risk        | 授权风险        | 否          | 否                |


 需 **索引/聚合服务** 或 enrich；Playwright **不适用**链上 JSON-RPC 场景。

### 5.3 Smart Contracts（合约）

#### 标准 / 链上可拉取


| 字段名                         | 中文含义    | API          | Playwright（当前项目） |
| --------------------------- | ------- | ------------ | ---------------- |
| contract_address            | 合约地址    | 可            | 否                |
| creator_address             | 创建者     | 可            | 否                |
| creation_tx / creation_date | 创建交易与时间 | 可            | 否                |
| bytecode                    | 字节码     | 部分           | 否                |
| ABI                         | 接口（若验证） | 部分（Basescan） | 否                |
| source_code                 | 源码（若验证） | 部分           | 否                |


#### LLM / 分析字段（目录）


| 字段名                                                                | 中文含义         | API     | Playwright（当前项目） |
| ------------------------------------------------------------------ | ------------ | ------- | ---------------- |
| contract_name                                                      | 合约名          | 部分      | 否                |
| is_verified                                                        | 是否验证         | 部分      | 否                |
| compiler_version                                                   | 编译器版本        | 部分      | 否                |
| contract_type_classified                                           | 合约类型分类       | 否       | 否                |
| protocol_name                                                      | 协议名          | 部分      | 否                |
| implements_standards                                               | 实现标准（ERC 等）  | 部分      | 否                |
| functions_summary                                                  | 函数摘要列表       | 否       | 否                |
| admin_functions                                                    | 管理函数         | 否       | 否                |
| upgrade_mechanism                                                  | 升级机制         | 否       | 否                |
| has_pausable / has_blacklist                                       | 是否可暂停/黑名单    | 否       | 否                |
| owner_privileges                                                   | 所有者权限        | 否       | 否                |
| known_vulnerabilities                                              | 已知漏洞         | 否       | 否                |
| audit_status / audit_firms                                         | 审计状态与机构      | 部分（外部库） | 否                |
| reentrancy_risk                                                    | 重入风险         | 否       | 否                |
| centralization_risk_score                                          | 中心化风险        | 否       | 否                |
| proxy_implementation_history                                       | 代理实现历史       | 部分      | 否                |
| total_interactions / unique_users / tvl_* / daily_active_users_avg | 用量与 TVL 指标   | 否       | 否                |
| contract_purpose_summary                                           | 合约目的段落       | 否       | 否                |
| function_explanations                                              | 函数级解释        | 否       | 否                |
| admin_risk_narrative                                               | 管理权限风险叙事     | 否       | 否                |
| code_quality_indicators                                            | 代码质量指标       | 否       | 否                |
| contract_one_liner                                                 | 一句话说明        | 否       | 否                |
| security_summary                                                   | 安全总结         | 否       | 否                |
| developer_summary                                                  | 开发者向总结       | 否       | 否                |
| linkable_identifiers                                               | GitHub/审计链接等 | 否（成品）   | 否（成品）            |


### 5.4 DeFi Protocol Aggregated（协议聚合）

#### 标准 / 指标字段


| 字段名                                                 | 中文含义    | API         | Playwright（当前项目） |
| --------------------------------------------------- | ------- | ----------- | ---------------- |
| protocol_name / protocol_category                   | 协议名与类别  | 部分（第三方 API） | 否                |
| main_contracts                                      | 主合约列表   | 部分          | 否                |
| website / documentation_url                         | 官网与文档   | 部分          | 部分               |
| governance_token                                    | 治理代币    | 部分          | 否                |
| tvl_usd / tvl_change_*                              | TVL 及变化 | 部分          | 否                |
| total_volume_24h / total_users / daily_active_users | 量与用户    | 部分          | 否                |
| total_fees_24h / total_revenue_24h                  | 费用与收入   | 部分          | 否                |
| pools                                               | 池子列表与指标 | 部分          | 否                |
| protocol_risk_score 等 Risk 列                        | 协议风险维度  | 否           | 否                |


#### LLM 增强字段


| 字段名                          | 中文含义            | API   | Playwright（当前项目） |
| ---------------------------- | --------------- | ----- | ---------------- |
| protocol_summary             | 协议白话说明          | 否     | 否                |
| competitive_landscape        | 竞争格局            | 否     | 否                |
| key_differentiators          | 关键差异化           | 否     | 否                |
| risk_narrative               | 风险叙事            | 否     | 否                |
| recent_governance_decisions  | 近期治理决策摘要        | 否     | 否                |
| governance_proposal_analysis | 提案分析            | 否     | 否                |
| linkable_identifiers         | 团队/论文/GitHub 提示 | 否（成品） | 否（成品）            |


 DeFi 指标通常来自 **DeFiLlama 类 API 或自建索引**，非浏览器主路径。

---

## 6. 汇总规则（便于扫表）


| 类型                       | API                                                                          | Playwright（当前项目）                                                |
| ------------------------ | ---------------------------------------------------------------------------- | --------------------------------------------------------------- |
| 目录 **标准字段**（各平台原始页/接口可见） | 维基/arXiv/Base **可偏高**；LinkedIn **Voyager 可偏高（需登录）**；Amazon **页内 HTTP/解析可部分** | 多用于 **补动态 HTML、反爬、登录态页面**；**urlDiscover** 偏 **发现 + 轻量元数据**，非全字段 |
| 目录 **LLM 增强字段**          | **不**返回成品；仅提供 **文本/元数据** 时标为 enrich 输入来源                                     | 同上；多模态/复杂页面 **需** Playwright + CV/LLM                           |
| **合规与产品约束**              | LinkedIn/Amazon 需遵守 ToS；商用 API 以合同为准                                         | 浏览器自动化成本高、易碎，宜作 **fallback**                                    |


---

## 7. 与主仓库文档的关系

- 更细的 **skill enrich 是否实现** 对照见：`docs/字段对比-数据集产品目录与-Skill.md`。  
- 本文侧重 **数据获取通道**（API vs 浏览器脚本）与 **中文含义**，与 enrich 实现进度正交。  
- **§1.1–§1.4（LinkedIn）** 标准字段已按 `Dataset_Product_Catalog_v2.md` 的 **Category + Standard Fields** 逐条对齐（含 *not directly extracted*、*not available* 占位行）；§1.1 / §1.2 另附 **`linkable_identifiers` 对象键** 子表。

---

*若你后续接入亚马逊 PA-API、第三方链上索引或统一价源，可将对应行的「API」列从「部分」升为「可」，并在此文档注明版本与依赖。*