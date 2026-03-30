from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def _start_http_server(root: Path) -> tuple[ThreadingHTTPServer, threading.Thread]:
    handler = partial(SimpleHTTPRequestHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    pythonpath = str(cwd)
    env["PYTHONPATH"] = pythonpath if not env.get("PYTHONPATH") else pythonpath + os.pathsep + env["PYTHONPATH"]
    return subprocess.run(
        [sys.executable, *args],
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    help_result = _run("-m", "crawler", "--help", cwd=root)
    if help_result.returncode != 0:
      print(help_result.stdout)
      print(help_result.stderr, file=sys.stderr)
      raise SystemExit("crawler CLI help failed")

    with tempfile.TemporaryDirectory(prefix="crawler-smoke-") as tmp:
        tmp_path = Path(tmp)
        site_dir = tmp_path / "site"
        site_dir.mkdir(parents=True, exist_ok=True)
        (site_dir / "index.html").write_text(
            """
            <html>
              <head>
                <title>Smoke Test Page</title>
                <meta name="description" content="Bootstrap smoke test page">
              </head>
              <body>
                <article>
                  <h1>Smoke Test Page</h1>
                  <p>This page validates generic HTML crawling after bootstrap.</p>
                </article>
              </body>
            </html>
            """,
            encoding="utf-8",
        )

        server, thread = _start_http_server(site_dir)
        try:
            port = server.server_port
            input_path = tmp_path / "input.jsonl"
            output_dir = tmp_path / "out"
            input_path.write_text(
                json.dumps(
                    {
                        "platform": "generic",
                        "resource_type": "page",
                        "url": f"http://127.0.0.1:{port}/index.html",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            crawl_result = _run(
                "-m",
                "crawler",
                "crawl",
                "--input",
                str(input_path),
                "--output",
                str(output_dir),
                "--strict",
                cwd=root,
            )
            if crawl_result.returncode != 0:
                print(crawl_result.stdout)
                print(crawl_result.stderr, file=sys.stderr)
                raise SystemExit("crawl smoke test failed")

            records = (output_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()
            if len(records) != 1:
                raise SystemExit(f"expected 1 record, got {len(records)}")
            record = json.loads(records[0])
            if record["metadata"].get("title") != "Smoke Test Page":
                raise SystemExit("smoke record title mismatch")
            if "generic HTML crawling" not in record.get("plain_text", ""):
                raise SystemExit("smoke record plain_text mismatch")

            summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            if summary.get("status") != "success":
                raise SystemExit("smoke summary status mismatch")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    print("smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
