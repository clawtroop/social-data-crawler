"""LinkedIn platform field group definitions.

Covers all 4 subdatasets: profiles, company, jobs, posts.
Auto-generated from references/enrichment_catalog/linkedin.json
"""

from __future__ import annotations

from crawler.enrich.schemas.field_group_registry import (
    FieldGroupSpec,
    GenerativeConfig,
    OutputFieldSpec,
)

# ---------------------------------------------------------------------------
# 1. LinkedIn Profiles Dataset  (14 field groups)
# ---------------------------------------------------------------------------

_profiles_identity = FieldGroupSpec(
    name="linkedin_profiles_identity",
    description="Identity inference fields for LinkedIn profiles",
    required_source_fields=["name"],
    output_fields=[
        OutputFieldSpec(name="name_gender_inference", field_type="string"),
        OutputFieldSpec(name="name_ethnicity_estimation", field_type="string"),
        OutputFieldSpec(name="profile_language_detected", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_profiles_identity.jinja2"),
    platform="linkedin",
    subdataset="profiles",
)

_profiles_current_role = FieldGroupSpec(
    name="linkedin_profiles_current_role",
    description="Standardised current-role enrichment for LinkedIn profiles",
    required_source_fields=["headline"],
    output_fields=[
        OutputFieldSpec(name="standardized_job_title", field_type="string"),
        OutputFieldSpec(name="seniority_level", field_type="string"),
        OutputFieldSpec(name="job_function_category", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_profiles_current_role.jinja2"),
    platform="linkedin",
    subdataset="profiles",
)

_profiles_about = FieldGroupSpec(
    name="linkedin_profiles_about",
    description="About / bio section analysis for LinkedIn profiles",
    required_source_fields=["about"],
    output_fields=[
        OutputFieldSpec(name="about_summary", field_type="string"),
        OutputFieldSpec(name="about_topics", field_type="array<string>"),
        OutputFieldSpec(name="about_sentiment", field_type="string"),
        OutputFieldSpec(name="career_narrative_type", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_profiles_about.jinja2"),
    platform="linkedin",
    subdataset="profiles",
)

_profiles_experience = FieldGroupSpec(
    name="linkedin_profiles_experience",
    description="Structured experience extraction for LinkedIn profiles",
    required_source_fields=["experience"],
    output_fields=[
        OutputFieldSpec(
            name="experience_structured",
            field_type="array<object>",
            description="company, title, start_date, end_date, duration_months, responsibilities_extracted, technologies_mentioned, achievements_quantified, industry_standardized",
        ),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(
        prompt_template="linkedin_profiles_experience.jinja2",
        max_tokens=1024,
    ),
    platform="linkedin",
    subdataset="profiles",
)

_profiles_education = FieldGroupSpec(
    name="linkedin_profiles_education",
    description="Structured education extraction for LinkedIn profiles",
    required_source_fields=["education"],
    output_fields=[
        OutputFieldSpec(
            name="education_structured",
            field_type="array<object>",
            description="institution, degree_type, field_of_study_standardized, graduation_year, institution_ranking_tier",
        ),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_profiles_education.jinja2"),
    platform="linkedin",
    subdataset="profiles",
)

_profiles_skills = FieldGroupSpec(
    name="linkedin_profiles_skills",
    description="Skill extraction and categorisation for LinkedIn profiles",
    required_source_fields=["skills"],
    output_fields=[
        OutputFieldSpec(name="skills_extracted", field_type="array<string>"),
        OutputFieldSpec(name="skill_categories", field_type="array<string>"),
        OutputFieldSpec(name="skill_proficiency_inferred", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_profiles_skills.jinja2"),
    platform="linkedin",
    subdataset="profiles",
)

_profiles_social = FieldGroupSpec(
    name="linkedin_profiles_social",
    description="Social influence metrics for LinkedIn profiles",
    required_source_fields=["follower_count", "connection_count"],
    output_fields=[
        OutputFieldSpec(name="influence_score", field_type="number"),
        OutputFieldSpec(name="engagement_rate", field_type="number"),
        OutputFieldSpec(name="content_creator_tier", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_profiles_social.jinja2"),
    platform="linkedin",
    subdataset="profiles",
)

_profiles_network = FieldGroupSpec(
    name="linkedin_profiles_network",
    description="Network-level enrichment for LinkedIn profiles",
    required_source_fields=["connections", "experience"],
    output_fields=[
        OutputFieldSpec(name="professional_cluster", field_type="string"),
        OutputFieldSpec(name="career_trajectory_vector", field_type="array<number>"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_profiles_network.jinja2"),
    platform="linkedin",
    subdataset="profiles",
)

_profiles_certifications = FieldGroupSpec(
    name="linkedin_profiles_certifications",
    description="Certification and language proficiency validation for LinkedIn profiles",
    required_source_fields=["certifications"],
    output_fields=[
        OutputFieldSpec(name="certification_validity", field_type="string"),
        OutputFieldSpec(name="language_proficiency_level", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_profiles_certifications.jinja2"),
    platform="linkedin",
    subdataset="profiles",
)

_profiles_metadata = FieldGroupSpec(
    name="linkedin_profiles_metadata",
    description="Profile metadata and freshness assessment for LinkedIn profiles",
    required_source_fields=["profile_url"],
    output_fields=[
        OutputFieldSpec(name="profile_completeness_score", field_type="number"),
        OutputFieldSpec(name="last_active_estimate", field_type="string"),
        OutputFieldSpec(name="profile_freshness_grade", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_profiles_metadata.jinja2"),
    platform="linkedin",
    subdataset="profiles",
)

_profiles_multimodal = FieldGroupSpec(
    name="linkedin_profiles_multimodal",
    description="Multimodal image analysis for LinkedIn profile avatars and banners",
    required_source_fields=["avatar_url"],
    output_fields=[
        OutputFieldSpec(
            name="avatar_quality_assessment",
            field_type="object",
            description="is_professional_headshot, face_detected, lighting_quality, background_type",
        ),
        OutputFieldSpec(
            name="banner_content_analysis",
            field_type="object",
            description="depicts, brand_alignment_score, text_extracted_from_banner",
        ),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(
        prompt_template="linkedin_profiles_multimodal.jinja2",
        max_tokens=1024,
    ),
    requires_vision=True,
    platform="linkedin",
    subdataset="profiles",
)

_profiles_multi_level_summary = FieldGroupSpec(
    name="linkedin_profiles_multi_level_summary",
    description="Multi-audience summaries for LinkedIn profiles",
    required_source_fields=["name", "headline", "about"],
    output_fields=[
        OutputFieldSpec(name="one_line_summary", field_type="string"),
        OutputFieldSpec(name="recruiter_brief", field_type="string"),
        OutputFieldSpec(name="investor_brief", field_type="string"),
        OutputFieldSpec(name="full_profile_narrative", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(
        prompt_template="linkedin_profiles_multi_level_summary.jinja2",
        max_tokens=1024,
    ),
    platform="linkedin",
    subdataset="profiles",
)

_profiles_behavioral_signals = FieldGroupSpec(
    name="linkedin_profiles_behavioral_signals",
    description="Behavioral and writing style analysis for LinkedIn profiles",
    required_source_fields=["about", "posts"],
    output_fields=[
        OutputFieldSpec(
            name="writing_style_profile",
            field_type="object",
            description="formality_level, vocabulary_richness, jargon_density, persuasion_style",
        ),
        OutputFieldSpec(name="job_change_signal_strength", field_type="number"),
        OutputFieldSpec(
            name="culture_fit_indicators",
            field_type="object",
            description="work_style_inferred, values_expressed, communication_style",
        ),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(
        prompt_template="linkedin_profiles_behavioral_signals.jinja2",
        max_tokens=1024,
    ),
    platform="linkedin",
    subdataset="profiles",
)

_profiles_cross_dataset_linkable_ids = FieldGroupSpec(
    name="linkedin_profiles_cross_dataset_linkable_ids",
    description="Cross-dataset linkable identifiers for LinkedIn profiles",
    required_source_fields=["profile_url"],
    output_fields=[
        OutputFieldSpec(
            name="linkable_identifiers",
            field_type="object",
            description="github_urls, personal_website_url, twitter_handle, orcid_id, google_scholar_url, arxiv_author_query_hint, company_domains_mentioned, patent_numbers_mentioned, publication_titles_mentioned",
        ),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(
        prompt_template="linkedin_profiles_cross_dataset_linkable_ids.jinja2",
        max_tokens=512,
    ),
    platform="linkedin",
    subdataset="profiles",
)

# ---------------------------------------------------------------------------
# 2. LinkedIn Company Dataset  (8 field groups)
# ---------------------------------------------------------------------------

_company_basic = FieldGroupSpec(
    name="linkedin_company_basic",
    description="Basic corporate-structure enrichment for LinkedIn companies",
    required_source_fields=["company_name"],
    output_fields=[
        OutputFieldSpec(name="company_legal_name_inferred", field_type="string"),
        OutputFieldSpec(name="parent_company", field_type="string"),
        OutputFieldSpec(name="subsidiary_tree", field_type="array<string>"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_company_basic.jinja2"),
    platform="linkedin",
    subdataset="company",
)

_company_profile = FieldGroupSpec(
    name="linkedin_company_profile",
    description="Company profile analysis for LinkedIn companies",
    required_source_fields=["company_name", "about"],
    output_fields=[
        OutputFieldSpec(name="about_summary", field_type="string"),
        OutputFieldSpec(name="core_business_extracted", field_type="string"),
        OutputFieldSpec(name="value_proposition", field_type="string"),
        OutputFieldSpec(name="target_market_inferred", field_type="string"),
        OutputFieldSpec(name="industry_standardized", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_company_profile.jinja2"),
    platform="linkedin",
    subdataset="company",
)

_company_scale = FieldGroupSpec(
    name="linkedin_company_scale",
    description="Company scale and workforce signals for LinkedIn companies",
    required_source_fields=["employee_count"],
    output_fields=[
        OutputFieldSpec(name="employee_growth_trend", field_type="string"),
        OutputFieldSpec(name="hiring_velocity", field_type="string"),
        OutputFieldSpec(name="attrition_signal", field_type="string"),
        OutputFieldSpec(name="department_distribution_estimated", field_type="object"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_company_scale.jinja2"),
    platform="linkedin",
    subdataset="company",
)

_company_content = FieldGroupSpec(
    name="linkedin_company_content",
    description="Content strategy analysis for LinkedIn companies",
    required_source_fields=["company_posts"],
    output_fields=[
        OutputFieldSpec(name="content_strategy_analysis", field_type="string"),
        OutputFieldSpec(name="posting_frequency", field_type="string"),
        OutputFieldSpec(name="top_topics", field_type="array<string>"),
        OutputFieldSpec(name="brand_voice_profile", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_company_content.jinja2"),
    platform="linkedin",
    subdataset="company",
)

_company_tech = FieldGroupSpec(
    name="linkedin_company_tech",
    description="Technology stack inference for LinkedIn companies",
    required_source_fields=["about", "job_postings"],
    output_fields=[
        OutputFieldSpec(name="tech_stack_inferred", field_type="array<string>"),
        OutputFieldSpec(name="engineering_team_size_estimated", field_type="number"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_company_tech.jinja2"),
    platform="linkedin",
    subdataset="company",
)

_company_financials = FieldGroupSpec(
    name="linkedin_company_financials",
    description="Financial signals for LinkedIn companies",
    required_source_fields=["company_name", "about"],
    output_fields=[
        OutputFieldSpec(name="funding_stage_inferred", field_type="string"),
        OutputFieldSpec(name="revenue_range_estimated", field_type="string"),
        OutputFieldSpec(name="business_model_type", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_company_financials.jinja2"),
    platform="linkedin",
    subdataset="company",
)

_company_multi_level_summary = FieldGroupSpec(
    name="linkedin_company_multi_level_summary",
    description="Multi-audience summaries for LinkedIn companies",
    required_source_fields=["company_name", "about"],
    output_fields=[
        OutputFieldSpec(name="elevator_pitch", field_type="string"),
        OutputFieldSpec(name="investor_brief", field_type="string"),
        OutputFieldSpec(name="competitor_brief", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(
        prompt_template="linkedin_company_multi_level_summary.jinja2",
        max_tokens=1024,
    ),
    platform="linkedin",
    subdataset="company",
)

_company_cross_dataset_linkable_ids = FieldGroupSpec(
    name="linkedin_company_cross_dataset_linkable_ids",
    description="Cross-dataset linkable identifiers for LinkedIn companies",
    required_source_fields=["company_url"],
    output_fields=[
        OutputFieldSpec(
            name="linkable_identifiers",
            field_type="object",
            description="website_domain, amazon_seller_search_hint, wikipedia_entity_hint, github_org_url, crunchbase_hint, base_contract_deployer_hint",
        ),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(
        prompt_template="linkedin_company_cross_dataset_linkable_ids.jinja2",
        max_tokens=512,
    ),
    platform="linkedin",
    subdataset="company",
)

# ---------------------------------------------------------------------------
# 3. LinkedIn Jobs Dataset  (7 field groups)
# ---------------------------------------------------------------------------

_jobs_basic = FieldGroupSpec(
    name="linkedin_jobs_basic",
    description="Basic job posting enrichment for LinkedIn jobs",
    required_source_fields=["job_title", "location"],
    output_fields=[
        OutputFieldSpec(name="job_title_standardized", field_type="string"),
        OutputFieldSpec(name="remote_policy", field_type="string"),
        OutputFieldSpec(
            name="location_parsed",
            field_type="object",
            description="city, state, country",
        ),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_jobs_basic.jinja2"),
    platform="linkedin",
    subdataset="jobs",
)

_jobs_content = FieldGroupSpec(
    name="linkedin_jobs_content",
    description="Job description content extraction for LinkedIn jobs",
    required_source_fields=["job_description"],
    output_fields=[
        OutputFieldSpec(name="responsibilities_extracted", field_type="array<string>"),
        OutputFieldSpec(
            name="requirements_extracted",
            field_type="array<object>",
            description="skill, required_or_preferred, years_experience",
        ),
        OutputFieldSpec(name="salary_range_inferred", field_type="string"),
        OutputFieldSpec(name="benefits_extracted", field_type="array<string>"),
        OutputFieldSpec(name="team_size_hint", field_type="string"),
        OutputFieldSpec(name="reporting_to_level", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(
        prompt_template="linkedin_jobs_content.jinja2",
        max_tokens=1024,
    ),
    platform="linkedin",
    subdataset="jobs",
)

_jobs_classification = FieldGroupSpec(
    name="linkedin_jobs_classification",
    description="Job classification and signal extraction for LinkedIn jobs",
    required_source_fields=["job_title", "job_description"],
    output_fields=[
        OutputFieldSpec(name="role_category_fine_grained", field_type="string"),
        OutputFieldSpec(name="industry_vertical", field_type="string"),
        OutputFieldSpec(name="visa_sponsorship_signal", field_type="string"),
        OutputFieldSpec(name="equity_compensation_signal", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_jobs_classification.jinja2"),
    platform="linkedin",
    subdataset="jobs",
)

_jobs_skills = FieldGroupSpec(
    name="linkedin_jobs_skills",
    description="Skill and technology extraction from LinkedIn job postings",
    required_source_fields=["job_description"],
    output_fields=[
        OutputFieldSpec(name="required_skills", field_type="array<string>"),
        OutputFieldSpec(name="preferred_skills", field_type="array<string>"),
        OutputFieldSpec(name="tools_and_platforms", field_type="array<string>"),
        OutputFieldSpec(name="programming_languages", field_type="array<string>"),
        OutputFieldSpec(name="frameworks", field_type="array<string>"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_jobs_skills.jinja2"),
    platform="linkedin",
    subdataset="jobs",
)

_jobs_market = FieldGroupSpec(
    name="linkedin_jobs_market",
    description="Market and hiring signal analysis for LinkedIn jobs",
    required_source_fields=["job_title", "posted_date"],
    output_fields=[
        OutputFieldSpec(name="competition_level", field_type="string"),
        OutputFieldSpec(name="days_to_fill_estimated", field_type="number"),
        OutputFieldSpec(name="urgency_signal", field_type="string"),
        OutputFieldSpec(name="reposting_frequency", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_jobs_market.jinja2"),
    platform="linkedin",
    subdataset="jobs",
)

_jobs_multi_level_summary = FieldGroupSpec(
    name="linkedin_jobs_multi_level_summary",
    description="Multi-audience summaries for LinkedIn job postings",
    required_source_fields=["job_title", "job_description"],
    output_fields=[
        OutputFieldSpec(name="candidate_facing_summary", field_type="string"),
        OutputFieldSpec(name="hiring_manager_brief", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(
        prompt_template="linkedin_jobs_multi_level_summary.jinja2",
        max_tokens=1024,
    ),
    platform="linkedin",
    subdataset="jobs",
)

_jobs_domain_specific = FieldGroupSpec(
    name="linkedin_jobs_domain_specific",
    description="Domain-specific deep analysis for LinkedIn job postings",
    required_source_fields=["job_description"],
    output_fields=[
        OutputFieldSpec(name="red_flags_detected", field_type="array<string>"),
        OutputFieldSpec(
            name="culture_signals_extracted",
            field_type="object",
            description="management_style_hints, growth_opportunity_signals, work_life_balance_indicators",
        ),
        OutputFieldSpec(
            name="tech_stack_full_picture",
            field_type="object",
            description="must_have, nice_to_have, infrastructure, methodology",
        ),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(
        prompt_template="linkedin_jobs_domain_specific.jinja2",
        max_tokens=1024,
    ),
    platform="linkedin",
    subdataset="jobs",
)

# ---------------------------------------------------------------------------
# 4. LinkedIn Posts Dataset  (7 field groups)
# ---------------------------------------------------------------------------

_posts_content = FieldGroupSpec(
    name="linkedin_posts_content",
    description="Post content analysis for LinkedIn posts",
    required_source_fields=["post_text"],
    output_fields=[
        OutputFieldSpec(name="post_topic_tags", field_type="array<string>"),
        OutputFieldSpec(name="post_type", field_type="string"),
        OutputFieldSpec(name="key_claims_extracted", field_type="array<string>"),
        OutputFieldSpec(
            name="entities_mentioned",
            field_type="array<object>",
            description="name, type, sentiment",
        ),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_posts_content.jinja2"),
    platform="linkedin",
    subdataset="posts",
)

_posts_engagement = FieldGroupSpec(
    name="linkedin_posts_engagement",
    description="Engagement quality analysis for LinkedIn posts",
    required_source_fields=["like_count", "comment_count", "share_count"],
    output_fields=[
        OutputFieldSpec(name="engagement_quality_score", field_type="number"),
        OutputFieldSpec(name="comment_sentiment_distribution", field_type="object"),
        OutputFieldSpec(name="viral_coefficient_estimated", field_type="number"),
        OutputFieldSpec(name="controversial_flag", field_type="boolean"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_posts_engagement.jinja2"),
    platform="linkedin",
    subdataset="posts",
)

_posts_author = FieldGroupSpec(
    name="linkedin_posts_author",
    description="Author authority analysis for LinkedIn posts",
    required_source_fields=["author_profile_url"],
    output_fields=[
        OutputFieldSpec(name="author_authority_score", field_type="number"),
        OutputFieldSpec(name="author_industry", field_type="string"),
        OutputFieldSpec(name="is_corporate_voice", field_type="boolean"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_posts_author.jinja2"),
    platform="linkedin",
    subdataset="posts",
)

_posts_temporal = FieldGroupSpec(
    name="linkedin_posts_temporal",
    description="Temporal and trending analysis for LinkedIn posts",
    required_source_fields=["post_text", "posted_date"],
    output_fields=[
        OutputFieldSpec(name="trending_topic_relevance", field_type="number"),
        OutputFieldSpec(name="news_event_linkage", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_posts_temporal.jinja2"),
    platform="linkedin",
    subdataset="posts",
)

_posts_multimodal = FieldGroupSpec(
    name="linkedin_posts_multimodal",
    description="Multimodal analysis for images and links in LinkedIn posts",
    required_source_fields=["post_media_urls"],
    output_fields=[
        OutputFieldSpec(
            name="post_image_analysis",
            field_type="array<object>",
            description="image_type, text_extracted_from_image, chart_data_described, visual_sentiment",
        ),
        OutputFieldSpec(name="shared_link_content_summary", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(
        prompt_template="linkedin_posts_multimodal.jinja2",
        max_tokens=1024,
    ),
    requires_vision=True,
    platform="linkedin",
    subdataset="posts",
)

_posts_multi_level_summary = FieldGroupSpec(
    name="linkedin_posts_multi_level_summary",
    description="Multi-level summaries for LinkedIn posts",
    required_source_fields=["post_text"],
    output_fields=[
        OutputFieldSpec(name="post_one_liner", field_type="string"),
        OutputFieldSpec(name="post_takeaway", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_posts_multi_level_summary.jinja2"),
    platform="linkedin",
    subdataset="posts",
)

_posts_behavioral = FieldGroupSpec(
    name="linkedin_posts_behavioral",
    description="Behavioral and thought-leadership analysis for LinkedIn posts",
    required_source_fields=["post_text"],
    output_fields=[
        OutputFieldSpec(name="thought_leadership_depth", field_type="string"),
        OutputFieldSpec(name="self_promotion_score", field_type="number"),
        OutputFieldSpec(name="argument_structure", field_type="string"),
    ],
    strategy="generative_only",
    generative_config=GenerativeConfig(prompt_template="linkedin_posts_behavioral.jinja2"),
    platform="linkedin",
    subdataset="posts",
)

# ---------------------------------------------------------------------------
# Unified registry – keyed by field group name
# ---------------------------------------------------------------------------

LINKEDIN_FIELD_GROUPS: dict[str, FieldGroupSpec] = {
    # --- Profiles (14) ---
    _profiles_identity.name: _profiles_identity,
    _profiles_current_role.name: _profiles_current_role,
    _profiles_about.name: _profiles_about,
    _profiles_experience.name: _profiles_experience,
    _profiles_education.name: _profiles_education,
    _profiles_skills.name: _profiles_skills,
    _profiles_social.name: _profiles_social,
    _profiles_network.name: _profiles_network,
    _profiles_certifications.name: _profiles_certifications,
    _profiles_metadata.name: _profiles_metadata,
    _profiles_multimodal.name: _profiles_multimodal,
    _profiles_multi_level_summary.name: _profiles_multi_level_summary,
    _profiles_behavioral_signals.name: _profiles_behavioral_signals,
    _profiles_cross_dataset_linkable_ids.name: _profiles_cross_dataset_linkable_ids,
    # --- Company (8) ---
    _company_basic.name: _company_basic,
    _company_profile.name: _company_profile,
    _company_scale.name: _company_scale,
    _company_content.name: _company_content,
    _company_tech.name: _company_tech,
    _company_financials.name: _company_financials,
    _company_multi_level_summary.name: _company_multi_level_summary,
    _company_cross_dataset_linkable_ids.name: _company_cross_dataset_linkable_ids,
    # --- Jobs (7) ---
    _jobs_basic.name: _jobs_basic,
    _jobs_content.name: _jobs_content,
    _jobs_classification.name: _jobs_classification,
    _jobs_skills.name: _jobs_skills,
    _jobs_market.name: _jobs_market,
    _jobs_multi_level_summary.name: _jobs_multi_level_summary,
    _jobs_domain_specific.name: _jobs_domain_specific,
    # --- Posts (7) ---
    _posts_content.name: _posts_content,
    _posts_engagement.name: _posts_engagement,
    _posts_author.name: _posts_author,
    _posts_temporal.name: _posts_temporal,
    _posts_multimodal.name: _posts_multimodal,
    _posts_multi_level_summary.name: _posts_multi_level_summary,
    _posts_behavioral.name: _posts_behavioral,
}
