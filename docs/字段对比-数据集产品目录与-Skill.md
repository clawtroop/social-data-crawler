# 字段对比：Dataset Product Catalog v2 · 与 social-data-crawler Skill

> 对比基准：`Dataset_Product_Catalog_v2.md`、`references/enrichment_catalog/*.json` / `crawler/enrich/schemas/field_group_registry.py`  
> 文档日期：2026-03-30  

本文用**表格逐字段**标明：产品目录（及 JSON 清单）中的 **LLM 增强类字段**，在当前 skill **enrich 运行时**是否落地。**不包含**各平台抓取层自带的原始/HTML/API 字段（如 ASIN、标题、链上原始 JSON）；那些见 `docs/skill-overview.md`。

---

## 状态列说明

| Skill enrich 状态 | 含义 |
|-------------------|------|
| **已实现** | `FIELD_GROUP_REGISTRY` 中已注册，且输出字段与目录**同名、语义一致** |
| **部分实现** | 仅有子集、或形态弱于目录（如单字符串 vs `linkable_identifiers` 对象） |
| **未实现** | 目录 / `enrichment_catalog` 有定义，**无**对应 enrich 注册与稳定输出 |

通用 enrich（`summaries` / `classifications`）见文末 **§10**，**不**视作目录某一行的「已实现」。

---

### 按数据集汇总（仅统计 enrichment_catalog 中「LLM 增强类」字段 + §10 除外）

| 数据集 / 子集 | 目录字段条数 | 已实现 | 部分实现 | 未实现 |
|---------------|-------------|--------|----------|--------|
| LinkedIn · Profiles | 35 | 8 | 1 | 26 |
| LinkedIn · Company | 25 | 0 | 1 | 24 |
| LinkedIn · Jobs | 27 | 0 | 0 | 27 |
| LinkedIn · Posts | 20 | 0 | 0 | 20 |
| arXiv | 58 | 0 | 0 | 58 |
| Wikipedia | 46 | 0 | 0 | 46 |
| Amazon · Products | 54 | 0 | 0 | 54 |
| Amazon · Reviews | 25 | 0 | 0 | 25 |
| Amazon · Sellers | 17 | 0 | 0 | 17 |
| Base · 四章合计（§9.1–9.4） | 109 | 0 | 0 | 109 |

> **部分实现**仅指 `linkable_identifiers`：目录为对象，Skill 为 `linkable_identifier` 单串。Company 行计 1 是因含该字段。

---

## 1. Skill 运行时：`FIELD_GROUP_REGISTRY` 输出一览

| 字段组（代码） | 输出字段名 | 与目录关系 |
|----------------|------------|------------|
| `standardized_job_title` | `standardized_job_title`, `seniority_level`, `job_function_category` | 对齐 LinkedIn Profile · Current Role |
| `about_summary` | `about_summary`, `about_topics`, `about_sentiment` | 对齐 Profile · About（缺 `career_narrative_type`） |
| `skills_extraction` | `skills_extracted`, `skill_categories` | 对齐 Profile · Skills（缺 `skill_proficiency_inferred`） |
| `linkables` | `linkable_identifier` | 弱对齐各平台「可链接 ID」（目录为对象 `linkable_identifiers`） |
| `summaries` | `summary` | 通用，**非**目录中某一条「Multi-level Summary」 |
| `classifications` | `classification` | 通用 lookup，**非**目录细粒度分类 |

---

## 2. LinkedIn · 1.1 Profiles（逐字段）

| 目录字段名 | 目录分组 | Skill enrich 状态 | 说明 |
|------------|----------|-------------------|------|
| `name_gender_inference` | Identity | 未实现 | — |
| `name_ethnicity_estimation` | Identity | 未实现 | — |
| `profile_language_detected` | Identity | 未实现 | — |
| `standardized_job_title` | Current Role | **已实现** | 字段组 `standardized_job_title` |
| `seniority_level` | Current Role | **已实现** | 同上 |
| `job_function_category` | Current Role | **已实现** | 同上 |
| `about_summary` | About | **已实现** | 字段组 `about_summary` |
| `about_topics` | About | **已实现** | 同上 |
| `about_sentiment` | About | **已实现** | 同上 |
| `career_narrative_type` | About | 未实现 | — |
| `experience_structured` | Experience | 未实现 | — |
| `education_structured` | Education | 未实现 | — |
| `skills_extracted` | Skills | **已实现** | 字段组 `skills_extraction` |
| `skill_categories` | Skills | **已实现** | 同上 |
| `skill_proficiency_inferred` | Skills | 未实现 | — |
| `influence_score` | Social | 未实现 | — |
| `engagement_rate` | Social | 未实现 | — |
| `content_creator_tier` | Social | 未实现 | — |
| `professional_cluster` | Network | 未实现 | — |
| `career_trajectory_vector` | Network | 未实现 | — |
| `certification_validity` | Certifications | 未实现 | — |
| `language_proficiency_level` | Certifications | 未实现 | — |
| `profile_completeness_score` | Metadata | 未实现 | — |
| `last_active_estimate` | Metadata | 未实现 | — |
| `profile_freshness_grade` | Metadata | 未实现 | — |
| `avatar_quality_assessment` | Multimodal | 未实现 | — |
| `banner_content_analysis` | Multimodal | 未实现 | — |
| `one_line_summary` | Multi-level Summary | 未实现 | 非通用 `summary`；目录为独立字段 |
| `recruiter_brief` | Multi-level Summary | 未实现 | — |
| `investor_brief` | Multi-level Summary | 未实现 | — |
| `full_profile_narrative` | Multi-level Summary | 未实现 | — |
| `writing_style_profile` | Behavioral Signals | 未实现 | — |
| `job_change_signal_strength` | Behavioral Signals | 未实现 | — |
| `culture_fit_indicators` | Behavioral Signals | 未实现 | — |
| `linkable_identifiers` | Cross-dataset Linkable IDs | **部分实现** | Skill 仅有 `linkable_identifier`（字符串），无目录中的多键对象 |

---

## 3. LinkedIn · 1.2 Company（逐字段）

| 目录字段名 | 目录分组 | Skill enrich 状态 | 说明 |
|------------|----------|-------------------|------|
| `company_legal_name_inferred` | Basic | 未实现 | — |
| `parent_company` | Basic | 未实现 | — |
| `subsidiary_tree` | Basic | 未实现 | — |
| `about_summary` | Profile | 未实现 | Profile 组针对 **个人** `about_summary`；公司无同名注册 |
| `core_business_extracted` | Profile | 未实现 | — |
| `value_proposition` | Profile | 未实现 | — |
| `target_market_inferred` | Profile | 未实现 | — |
| `industry_standardized` | Profile | 未实现 | — |
| `employee_growth_trend` | Scale | 未实现 | — |
| `hiring_velocity` | Scale | 未实现 | — |
| `attrition_signal` | Scale | 未实现 | — |
| `department_distribution_estimated` | Scale | 未实现 | — |
| `content_strategy_analysis` | Content | 未实现 | — |
| `posting_frequency` | Content | 未实现 | — |
| `top_topics` | Content | 未实现 | — |
| `brand_voice_profile` | Content | 未实现 | — |
| `tech_stack_inferred` | Tech | 未实现 | — |
| `engineering_team_size_estimated` | Tech | 未实现 | — |
| `funding_stage_inferred` | Financials | 未实现 | — |
| `revenue_range_estimated` | Financials | 未实现 | — |
| `business_model_type` | Financials | 未实现 | — |
| `elevator_pitch` | Multi-level Summary | 未实现 | — |
| `investor_brief` | Multi-level Summary | 未实现 | — |
| `competitor_brief` | Multi-level Summary | 未实现 | — |
| `linkable_identifiers` | Cross-dataset Linkable IDs | **部分实现** | 同上：仅 `linkable_identifier` |

---

## 4. LinkedIn · 1.3 Jobs（逐字段）

| 目录字段名 | 目录分组 | Skill enrich 状态 | 说明 |
|------------|----------|-------------------|------|
| `job_title_standardized` | Basic | 未实现 | 与 Profile 的 `standardized_job_title` **不同名**，未单独注册 |
| `remote_policy` | Basic | 未实现 | — |
| `location_parsed` | Basic | 未实现 | — |
| `responsibilities_extracted` | Content | 未实现 | — |
| `requirements_extracted` | Content | 未实现 | — |
| `salary_range_inferred` | Content | 未实现 | — |
| `benefits_extracted` | Content | 未实现 | — |
| `team_size_hint` | Content | 未实现 | — |
| `reporting_to_level` | Content | 未实现 | — |
| `role_category_fine_grained` | Classification | 未实现 | — |
| `industry_vertical` | Classification | 未实现 | — |
| `visa_sponsorship_signal` | Classification | 未实现 | — |
| `equity_compensation_signal` | Classification | 未实现 | — |
| `required_skills` | Skills | 未实现 | — |
| `preferred_skills` | Skills | 未实现 | — |
| `tools_and_platforms` | Skills | 未实现 | — |
| `programming_languages` | Skills | 未实现 | — |
| `frameworks` | Skills | 未实现 | — |
| `competition_level` | Market | 未实现 | — |
| `days_to_fill_estimated` | Market | 未实现 | — |
| `urgency_signal` | Market | 未实现 | — |
| `reposting_frequency` | Market | 未实现 | — |
| `candidate_facing_summary` | Multi-level Summary | 未实现 | — |
| `hiring_manager_brief` | Multi-level Summary | 未实现 | — |
| `red_flags_detected` | Domain-specific | 未实现 | — |
| `culture_signals_extracted` | Domain-specific | 未实现 | — |
| `tech_stack_full_picture` | Domain-specific | 未实现 | — |

---

## 5. LinkedIn · 1.4 Posts（逐字段）

| 目录字段名 | 目录分组 | Skill enrich 状态 | 说明 |
|------------|----------|-------------------|------|
| `post_topic_tags` | Content | 未实现 | — |
| `post_type` | Content | 未实现 | — |
| `key_claims_extracted` | Content | 未实现 | — |
| `entities_mentioned` | Content | 未实现 | — |
| `engagement_quality_score` | Engagement | 未实现 | — |
| `comment_sentiment_distribution` | Engagement | 未实现 | — |
| `viral_coefficient_estimated` | Engagement | 未实现 | — |
| `controversial_flag` | Engagement | 未实现 | — |
| `author_authority_score` | Author | 未实现 | — |
| `author_industry` | Author | 未实现 | — |
| `is_corporate_voice` | Author | 未实现 | — |
| `trending_topic_relevance` | Temporal | 未实现 | — |
| `news_event_linkage` | Temporal | 未实现 | — |
| `post_image_analysis` | Multimodal | 未实现 | — |
| `shared_link_content_summary` | Multimodal | 未实现 | — |
| `post_one_liner` | Multi-level Summary | 未实现 | — |
| `post_takeaway` | Multi-level Summary | 未实现 | — |
| `thought_leadership_depth` | Behavioral | 未实现 | — |
| `self_promotion_score` | Behavioral | 未实现 | — |
| `argument_structure` | Behavioral | 未实现 | — |

---

## 6. arXiv（逐字段）

以下均来自 `references/enrichment_catalog/arxiv.json`；**Skill enrich 状态全部为 未实现**（无平台专用字段组）。

| 目录字段名 | 目录分组 |
|------------|----------|
| `title_normalized` | Identity |
| `abstract_plain_text` | Identity |
| `authors_structured` | Authors |
| `topic_hierarchy` | Classification |
| `keywords_extracted` | Classification |
| `research_area_plain_english` | Classification |
| `interdisciplinary_score` | Classification |
| `acceptance_status_inferred` | Dates |
| `venue_published` | Dates |
| `venue_tier` | Dates |
| `sections_structured` | Full Text |
| `main_contributions` | Contribution |
| `novelty_type` | Contribution |
| `problem_statement` | Contribution |
| `proposed_solution_summary` | Contribution |
| `methods_used` | Methodology |
| `baselines_compared` | Methodology |
| `evaluation_metrics` | Methodology |
| `datasets_used` | Methodology |
| `experimental_setup_summary` | Methodology |
| `key_results` | Results |
| `state_of_art_claimed` | Results |
| `statistical_significance_reported` | Results |
| `reproducibility_indicators` | Results |
| `limitations_stated` | Limitations |
| `future_work_directions` | Limitations |
| `threats_to_validity` | Limitations |
| `references_structured` | References |
| `total_citation_count` | References |
| `influential_citation_count` | References |
| `code_available` | Code & Data |
| `code_url` | Code & Data |
| `code_framework` | Code & Data |
| `dataset_released` | Code & Data |
| `dataset_url` | Code & Data |
| `open_access_status` | Code & Data |
| `title_embedding` | Embeddings |
| `abstract_embedding` | Embeddings |
| `full_paper_embedding` | Embeddings |
| `builds_upon` | Relations |
| `contradicts` | Relations |
| `replicates` | Relations |
| `uses_dataset_from` | Relations |
| `uses_method_from` | Relations |
| `figures_analyzed` | Multimodal Figures |
| `key_equations` | Multimodal Equations |
| `tweet_summary` | Multi-level Summary |
| `one_line_summary` | Multi-level Summary |
| `executive_summary` | Multi-level Summary |
| `layman_summary` | Multi-level Summary |
| `technical_abstract_enhanced` | Multi-level Summary |
| `review_style_summary` | Multi-level Summary |
| `mathematical_complexity_score` | Research Depth Analysis |
| `mathematical_complexity_evidence` | Research Depth Analysis |
| `novelty_delta_assessment` | Research Depth Analysis |
| `methodology_transferability` | Research Depth Analysis |
| `claim_verification_notes` | Research Depth Analysis |
| `linkable_identifiers` | Cross-dataset Linkable IDs |

---

## 7. Wikipedia（逐字段）

**Skill enrich 状态全部为 未实现**。

| 目录字段名 | 目录分组 |
|------------|----------|
| `title_disambiguated` | Identity |
| `canonical_entity_name` | Identity |
| `entity_type` | Identity |
| `wikidata_id` | Identity |
| `sections_structured` | Content |
| `table_of_contents` | Content |
| `article_summary` | Content |
| `reading_level` | Content |
| `tables_structured` | Tables |
| `infobox_structured` | Infobox |
| `categories_cleaned` | Categories |
| `topic_hierarchy` | Categories |
| `domain` | Categories |
| `subject_tags` | Categories |
| `entities_extracted` | Entities |
| `structured_facts` | Facts |
| `temporal_events` | Timeline |
| `related_entities` | Relations |
| `external_links_classified` | Relations |
| `article_quality_class` | Quality |
| `neutrality_score` | Quality |
| `citation_density` | Quality |
| `last_major_edit` | Quality |
| `edit_controversy_score` | Quality |
| `cross_language_links` | Multi-lingual |
| `translation_coverage_score` | Multi-lingual |
| `entity_name_translations` | Multi-lingual |
| `article_embedding` | Embeddings |
| `section_embeddings` | Embeddings |
| `images_annotated` | Multimodal Images |
| `one_line_summary` | Multi-level Summary |
| `eli5_summary` | Multi-level Summary |
| `standard_summary` | Multi-level Summary |
| `academic_summary` | Multi-level Summary |
| `key_takeaways` | Multi-level Summary |
| `prerequisite_concepts` | Educational |
| `difficulty_level` | Educational |
| `quiz_questions_generated` | Educational |
| `common_misconceptions` | Educational |
| `bias_detection` | Bias & Neutrality |
| `missing_perspectives` | Bias & Neutrality |
| `weasel_words_detected` | Bias & Neutrality |
| `information_freshness_score` | Content Freshness |
| `potentially_outdated_claims` | Content Freshness |
| `temporal_coverage_gap` | Content Freshness |
| `linkable_identifiers` | Cross-dataset Linkable IDs |

---

## 8. Amazon（逐字段）

**Skill enrich 状态全部为 未实现**。

### 8.1 Products

| 目录字段名 | 目录分组 |
|------------|----------|
| `title_cleaned` | Identity |
| `brand_standardized` | Identity |
| `is_brand_official_store` | Identity |
| `price_tier` | Pricing |
| `price_vs_category_avg` | Pricing |
| `historical_price_trend` | Pricing |
| `deal_quality_score` | Pricing |
| `features_structured` | Description |
| `key_specs_table` | Description |
| `use_cases_extracted` | Description |
| `target_audience_inferred` | Description |
| `category_standardized` | Category |
| `niche_tags` | Category |
| `seasonal_relevance` | Category |
| `image_count` | Visual |
| `has_lifestyle_images` | Visual |
| `has_infographic` | Visual |
| `has_video` | Visual |
| `visual_quality_score` | Visual |
| `fulfillment_type` | Availability |
| `shipping_speed_tier` | Availability |
| `prime_eligible` | Availability |
| `estimated_monthly_sales` | Availability |
| `competitive_position` | Competition |
| `listing_quality_score` | Competition |
| `seo_keyword_density` | Competition |
| `rating_trend` | Reviews Summary |
| `review_velocity` | Reviews Summary |
| `fake_review_risk_score` | Reviews Summary |
| `verified_purchase_ratio` | Reviews Summary |
| `variant_matrix_structured` | Variants |
| `best_seller_variant` | Variants |
| `variant_price_range` | Variants |
| `certifications_mentioned` | Compliance |
| `country_of_origin` | Compliance |
| `material_composition_extracted` | Compliance |
| `safety_warnings` | Compliance |
| `main_image_analysis` | Multimodal Product Images |
| `all_images_analysis` | Multimodal Product Images |
| `image_text_consistency_score` | Multimodal Product Images |
| `listing_visual_completeness` | Multimodal Product Images |
| `buyer_quick_take` | Multi-level Summary |
| `product_elevator_pitch` | Multi-level Summary |
| `seller_competitive_brief` | Multi-level Summary |
| `seo_optimized_description` | Multi-level Summary |
| `product_lifecycle_stage_inferred` | Market Positioning |
| `lifecycle_evidence` | Market Positioning |
| `unique_selling_points` | Market Positioning |
| `purchase_decision_factors_from_listing` | Market Positioning |
| `cross_sell_category_hints` | Market Positioning |
| `listing_optimization_score` | Listing Quality |
| `listing_issues_detected` | Listing Quality |
| `listing_completeness` | Listing Quality |
| `linkable_identifiers` | Cross-dataset Linkable IDs |

### 8.2 Reviews

| 目录字段名 | 目录分组 |
|------------|----------|
| `reviewer_profile_type` | Identity |
| `sentiment_overall` | Content |
| `sentiment_aspects` | Content |
| `product_pros_extracted` | Analysis |
| `product_cons_extracted` | Analysis |
| `feature_satisfaction_map` | Analysis |
| `use_case_mentioned` | Analysis |
| `comparison_to_alternatives` | Analysis |
| `review_quality_score` | Quality |
| `review_type` | Quality |
| `authenticity_score` | Quality |
| `information_density` | Quality |
| `issues_reported` | Structured |
| `customer_segment_inferred` | Structured |
| `purchase_context` | Structured |
| `image_content_described` | Media |
| `shows_product_in_use` | Media |
| `shows_defect` | Media |
| `review_image_analysis` | Multimodal Review Images |
| `review_one_liner` | Multi-level Summary |
| `purchase_decision_factor` | Multi-level Summary |
| `usage_duration_mentioned` | Review Depth |
| `expertise_level_inferred` | Review Depth |
| `actionable_feedback` | Review Depth |
| `competitor_products_mentioned` | Review Depth |

### 8.3 Sellers

| 目录字段名 | 目录分组 |
|------------|----------|
| `seller_type` | Identity |
| `business_name_registered` | Identity |
| `seller_health_score` | Performance |
| `response_time_tier` | Performance |
| `dispute_rate_estimated` | Performance |
| `product_count` | Portfolio |
| `category_focus` | Portfolio |
| `brand_portfolio` | Portfolio |
| `price_range` | Portfolio |
| `avg_product_rating` | Portfolio |
| `years_on_amazon` | Business Intel |
| `growth_trajectory` | Business Intel |
| `geographic_focus` | Business Intel |
| `fulfillment_strategy` | Business Intel |
| `seller_one_liner` | Multi-level Summary |
| `seller_profile_narrative` | Multi-level Summary |
| `linkable_identifiers` | Cross-dataset Linkable IDs |

---

## 9. Base 链上（逐字段）

**Skill enrich 状态全部为 未实现**。

### 9.1 Transactions

| 目录字段名 | 目录分组 |
|------------|----------|
| `value_usd` | Basic |
| `gas_fee_usd` | Basic |
| `tx_fee_tier` | Basic |
| `function_name` | Input Data |
| `function_signature` | Input Data |
| `decoded_parameters` | Input Data |
| `human_readable_action` | Input Data |
| `tx_type` | Classification |
| `protocol_name` | Classification |
| `protocol_category` | Classification |
| `token_transfers` | Token Transfers |
| `is_mev` | Context |
| `mev_type` | Context |
| `is_contract_interaction` | Context |
| `is_internal_tx_parent` | Context |
| `related_tx_hashes` | Context |
| `sender_risk_label` | Risk |
| `receiver_risk_label` | Risk |
| `anomaly_flags` | Risk |
| `fund_source_trace` | Risk |
| `compliance_narrative` | Multi-level Summary |
| `investor_narrative` | Multi-level Summary |
| `strategy_signal` | Strategy Detection |
| `linkable_identifiers` | Cross-dataset Linkable IDs |

### 9.2 Addresses / Wallets

| 目录字段名 | 目录分组 |
|------------|----------|
| `balance_usd` | Basic |
| `total_value_locked_usd` | Basic |
| `portfolio_composition` | Basic |
| `label` | Identity |
| `entity_name` | Identity |
| `ens_name` | Identity |
| `is_contract` | Identity |
| `contract_type` | Identity |
| `activity_summary` | Activity |
| `defi_positions` | DeFi |
| `nft_holdings` | NFT |
| `nft_trading_pnl` | NFT |
| `wallet_archetype` | Behavioral |
| `trading_pattern` | Behavioral |
| `risk_appetite_score` | Behavioral |
| `sophistication_score` | Behavioral |
| `risk_score` | Risk |
| `sanctions_match` | Risk |
| `mixer_interaction_count` | Risk |
| `high_risk_counterparties` | Risk |
| `fund_flow_risk_path` | Risk |
| `wallet_one_liner` | Multi-level Summary |
| `compliance_profile_summary` | Multi-level Summary |
| `investor_profile_summary` | Multi-level Summary |
| `cross_chain_address_hint` | Address Intelligence |
| `deployer_analysis` | Address Intelligence |
| `token_approval_risk` | Address Intelligence |

### 9.3 Smart Contracts

| 目录字段名 | 目录分组 |
|------------|----------|
| `contract_name` | Basic |
| `is_verified` | Basic |
| `compiler_version` | Basic |
| `contract_type_classified` | Code |
| `protocol_name` | Code |
| `implements_standards` | Code |
| `functions_summary` | Analysis |
| `admin_functions` | Analysis |
| `upgrade_mechanism` | Analysis |
| `has_pausable` | Analysis |
| `has_blacklist` | Analysis |
| `owner_privileges` | Analysis |
| `known_vulnerabilities` | Security |
| `audit_status` | Security |
| `audit_firms` | Security |
| `reentrancy_risk` | Security |
| `centralization_risk_score` | Security |
| `proxy_implementation_history` | Security |
| `total_interactions` | Usage |
| `unique_users` | Usage |
| `tvl_current_usd` | Usage |
| `tvl_30d_trend` | Usage |
| `daily_active_users_avg` | Usage |
| `contract_purpose_summary` | Code Comprehension |
| `function_explanations` | Code Comprehension |
| `admin_risk_narrative` | Code Comprehension |
| `code_quality_indicators` | Code Comprehension |
| `contract_one_liner` | Multi-level Summary |
| `security_summary` | Multi-level Summary |
| `developer_summary` | Multi-level Summary |
| `linkable_identifiers` | Cross-dataset Linkable IDs |

### 9.4 DeFi Protocol Aggregated

| 目录字段名 | 目录分组 |
|------------|----------|
| `protocol_name` | Protocol |
| `protocol_category` | Protocol |
| `main_contracts` | Protocol |
| `website` | Protocol |
| `documentation_url` | Protocol |
| `governance_token` | Protocol |
| `tvl_usd` | Metrics |
| `tvl_change_24h/7d/30d` | Metrics |
| `total_volume_24h` | Metrics |
| `total_users` | Metrics |
| `daily_active_users` | Metrics |
| `total_fees_24h` | Metrics |
| `total_revenue_24h` | Metrics |
| `pools` | Pools |
| `protocol_risk_score` | Risk |
| `smart_contract_risk` | Risk |
| `centralization_risk` | Risk |
| `oracle_dependency` | Risk |
| `insurance_coverage` | Risk |
| `protocol_summary` | LLM-Enhanced |
| `competitive_landscape` | LLM-Enhanced |
| `key_differentiators` | LLM-Enhanced |
| `risk_narrative` | LLM-Enhanced |
| `recent_governance_decisions` | LLM-Enhanced |
| `governance_proposal_analysis` | Governance Analysis |
| `linkable_identifiers` | Cross-dataset Linkable IDs |

---

## 10. Skill 独有输出（目录无同名单列）

| 输出 | 注册名 | 说明 |
|------|--------|------|
| `summary` | `summaries` | 通用短文摘要；**不等于**各平台目录里的 `one_line_summary` 等 |
| `classification` | `classifications` | 基于 `resource_type` 等的 lookup |
| `linkable_identifier` | `linkables` / 模板 | 单字符串 |

`FIELD_GROUP_TEMPLATES`（`templates/__init__.py`）另有：`multimodal_signal`、`behavior_signal`、`risk_signal`、`code_signal`、`figure_signal` 等占位输出，**均非**目录列名。

---

## 11. 维护路径

| 资源 | 路径 |
|------|------|
| 产品目录 | `Dataset_Product_Catalog_v2.md`（仓库根） |
| JSON 字段清单 | `references/enrichment_catalog/*.json` |
| 已实现 enrich | `crawler/enrich/schemas/field_group_registry.py` |

字段在代码中落地后，建议在对应 `enrichment_catalog` 条目中更新 `support_status`，并与本表同步。
