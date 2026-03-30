from linkedin_url.company_expand import job_ids_from_jobs_search_url
from linkedin_url.profile_expand import classify_linkedin_url


def test_jobs_search_url_parses_origin_postings():
    u = (
        "https://www.linkedin.com/jobs/search/?currentJobId=4378267253&"
        "originToLandingJobPostings=4378267253%2C4379162900%2C4378263287"
    )
    ids = job_ids_from_jobs_search_url(u)
    assert "4378267253" in ids
    assert "4379162900" in ids
    assert "4378263287" in ids


def test_classify_jobs_search():
    assert (
        classify_linkedin_url(
            "https://www.linkedin.com/jobs/search/?f_C=123"
        )
        == "jobs_search"
    )


def test_classify_company_tab():
    assert (
        classify_linkedin_url("https://www.linkedin.com/company/pop-mart/jobs/")
        == "company_tab"
    )


def test_classify_company_main():
    assert (
        classify_linkedin_url("https://www.linkedin.com/company/pop-mart/")
        == "company"
    )
