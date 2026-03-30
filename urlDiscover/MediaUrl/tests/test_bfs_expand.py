import time

from linkedin_url.bfs_expand import run_bfs_expand


def test_bfs_max_depth_1_only_expands_seed():
    """max_expand_depth=1：仅扩展 depth=0 的种子，子节点入队但不再 fetch。"""

    def fetch(u: str) -> str:
        return (
            '<a href="https://www.linkedin.com/company/acme-corp/">c</a>'
            '<a href="https://www.linkedin.com/in/other/">o</a>'
        )

    br, stats = run_bfs_expand(
        ["https://www.linkedin.com/in/seeduser/"],
        fetch,
        max_expand_depth=1,
    )
    assert stats["expansions_run"] == 1
    assert any("acme-corp" in c for c in br.companies)
    assert any("other" in p for p in br.profiles)


def test_bfs_max_depth_2_expands_two_layers():
    def fetch(u: str) -> str:
        if "/in/seeduser" in u:
            return '<a href="https://www.linkedin.com/company/acme-corp/">c</a>'
        if "/company/acme-corp" in u:
            return '<a href="https://www.linkedin.com/in/deeper/">d</a>'
        return ""

    br, stats = run_bfs_expand(
        ["https://www.linkedin.com/in/seeduser/"],
        fetch,
        max_expand_depth=2,
    )
    assert stats["expansions_run"] == 2
    assert any("deeper" in p for p in br.profiles)


def test_bfs_unlimited_depth():
    calls: list[str] = []

    def fetch(u: str) -> str:
        calls.append(u)
        if "/in/a" in u:
            return '<a href="https://www.linkedin.com/in/b/">b</a>'
        if "/in/b" in u:
            return ""
        return ""

    br, stats = run_bfs_expand(
        ["https://www.linkedin.com/in/a/"],
        fetch,
        max_expand_depth=None,
    )
    assert stats["expansions_run"] == 2
    assert any("linkedin.com/in/b" in p for p in br.profiles)


def test_bfs_stops_on_time_limit_and_keeps_partial():
    counter = [0]

    def fetch(u: str) -> str:
        time.sleep(0.04)
        counter[0] += 1
        return f'<a href="https://www.linkedin.com/in/u{counter[0]}/">x</a>'

    br, stats = run_bfs_expand(
        ["https://www.linkedin.com/in/seed/"],
        fetch,
        max_expand_depth=999,
        max_runtime_seconds=0.2,
    )
    assert stats["stopped_by_time_limit"] is True
    assert stats["expansions_run"] >= 1
    assert stats["queue_remaining"] > 0
    assert stats["elapsed_seconds"] <= 0.35
    assert len(br.profiles) >= 1
