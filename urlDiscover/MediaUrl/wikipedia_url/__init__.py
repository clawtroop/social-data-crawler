"""Wikipedia / MediaWiki API 辅助（User-Agent、urllib 客户端等）。"""

from wikipedia_url.http_env import wikipedia_requests
from wikipedia_url.user_agent import get_wikipedia_user_agent

__all__ = ["get_wikipedia_user_agent", "wikipedia_requests"]
