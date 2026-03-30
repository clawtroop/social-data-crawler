"""命令行：登录保存会话、拉取单页 HTML。"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from linkedin_url.auth.paths import default_storage_state_path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="linkedin_url", description="LinkedIn 会话与带登录页面抓取")
    sub = p.add_subparsers(dest="cmd", required=True)

    login = sub.add_parser("login", help="打开浏览器登录领英并保存 storage_state")
    login.add_argument(
        "--state",
        type=str,
        default=None,
        help="会话 JSON 路径（默认 .secrets/linkedin_storage_state.json）",
    )
    login.add_argument(
        "--headless",
        action="store_true",
        help="无头启动（通常无法完成登录；仅调试）",
    )
    login.add_argument(
        "--no-wait",
        action="store_true",
        help="不等待 Enter，页面加载后立即保存（仅当你已提前登录同一 profile 时）",
    )
    login.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="代理，如 http://127.0.0.1:7890（不填则用 LINKEDIN_PROXY / HTTPS_PROXY 等环境变量）",
    )

    fetch = sub.add_parser("fetch", help="使用已保存会话拉取页面 HTML")
    fetch.add_argument("url", help="LinkedIn URL")
    fetch.add_argument("--state", type=str, default=None, help="会话 JSON 路径")
    fetch.add_argument(
        "--headed",
        action="store_true",
        help="有头浏览器（风控/空白页时尝试）",
    )
    fetch.add_argument("-o", "--output", type=str, default=None, help="写入文件而非 stdout")
    fetch.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="代理（不填则用 LINKEDIN_PROXY / HTTPS_PROXY 等环境变量）",
    )

    verify = sub.add_parser(
        "verify",
        help="用已保存会话访问一条动态 URL，检查是否仍显示访客登录墙（快速验会话）",
    )
    verify.add_argument(
        "--url",
        type=str,
        default="https://www.linkedin.com/feed/update/urn:li:activity:7406859439900827648/",
        help="要检测的领英 URL（默认示例动态）",
    )
    verify.add_argument("--state", type=str, default=None, help="会话 JSON 路径")
    verify.add_argument(
        "--headed",
        action="store_true",
        help="有头浏览器（便于观察）",
    )
    verify.add_argument(
        "--save-html",
        type=str,
        default=None,
        metavar="FILE",
        help="把本次抓到的 HTML 写入文件便于人工查看",
    )
    verify.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="代理（不填则用环境变量）",
    )

    schema = sub.add_parser("schema-apply", help="执行 phase1+phase2 DDL（需 DATABASE_URL）")
    schema.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Postgres 连接串（默认环境变量 DATABASE_URL）",
    )

    seed = sub.add_parser("seed", help="将一条领英 URL 归一化并入队 frontier")
    seed.add_argument("url", help="种子 URL")
    seed.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Postgres 连接串",
    )
    seed.add_argument("--label", type=str, default="cli", help="seed_label")

    crawl = sub.add_parser("crawl", help="从 frontier 消费 pending：抓取→发现→扩边（需已 login + DB）")
    crawl.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Postgres 连接串",
    )
    crawl.add_argument("--max-steps", type=int, default=10, help="本轮最多处理条数")
    crawl.add_argument("--max-depth", type=int, default=2, help="相对种子的最大发现深度")
    crawl.add_argument("--label", type=str, default="cli", help="seed_label 写入新前沿")
    crawl.add_argument("--state", type=str, default=None, help="storage_state.json 路径")
    crawl.add_argument("--proxy", type=str, default=None, help="代理")

    args = p.parse_args(argv)

    if args.cmd == "login":
        from linkedin_url.auth.playwright_session import interactive_save_storage_state

        state = Path(args.state) if args.state else default_storage_state_path()
        interactive_save_storage_state(
            state_path=state,
            headless=args.headless,
            wait_for_enter=not args.no_wait,
            proxy=args.proxy,
        )
        print(f"OK: {state}")
        return 0

    if args.cmd == "fetch":
        from linkedin_url.auth.fetch import fetch_html_sync

        state = Path(args.state) if args.state else default_storage_state_path()
        try:
            html = fetch_html_sync(
                args.url,
                state_path=state,
                headless=not args.headed,
                proxy=args.proxy,
            )
        except FileNotFoundError as e:
            logger.error("%s", e)
            return 2
        if args.output:
            Path(args.output).write_text(html, encoding="utf-8")
            print(args.output)
        else:
            sys.stdout.write(html)
        return 0

    if args.cmd == "verify":
        from linkedin_url.auth.verify import verify_session_on_activity_url

        state = Path(args.state) if args.state else default_storage_state_path()
        try:
            r = verify_session_on_activity_url(
                args.url,
                state_path=state,
                proxy=args.proxy,
                headless=not args.headed,
            )
        except FileNotFoundError as e:
            logger.error("%s", e)
            return 2
        print(f"HTTP 状态: {r.http_status}")
        print(f"最终 URL: {r.url_final}")
        print(f"HTML 长度: {r.html_length}")
        print(f"访客墙特征: {r.looks_like_guest_wall}")
        print(f"动态结构特征: {r.looks_like_feed_content}")
        print(r.message)
        if args.save_html:
            Path(args.save_html).write_text(r.html, encoding="utf-8")
            print(f"已写入: {args.save_html}")
        return 0 if not r.looks_like_guest_wall else 3

    if args.cmd == "schema-apply":
        from linkedin_url.store.pg import connect, get_database_url, run_phase1_phase2_schema

        dsn = get_database_url(args.database_url)
        with connect(dsn) as conn:
            run_phase1_phase2_schema(conn)
        print("schema OK")
        return 0

    if args.cmd == "seed":
        from linkedin_url.pipeline import enqueue_seed
        from linkedin_url.store.pg import connect, get_database_url

        dsn = get_database_url(args.database_url)
        with connect(dsn) as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    out = enqueue_seed(cur, args.url, seed_label=args.label, depth=0)
        print(out)
        return 0 if out.get("ok") else 4

    if args.cmd == "crawl":
        from linkedin_url.pipeline import CrawlConfig, run_crawl
        from linkedin_url.store.pg import connect, get_database_url

        dsn = get_database_url(args.database_url)
        cfg = CrawlConfig(
            max_depth=args.max_depth,
            max_steps=args.max_steps,
            seed_label=args.label,
            state_path=Path(args.state) if args.state else None,
            proxy=args.proxy,
        )
        with connect(dsn) as conn:
            n = run_crawl(conn, cfg)
        print(f"本轮处理 frontier 条数: {n}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
