from html import escape
from typing import Annotated

from fastapi import APIRouter, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import repository
from ..codes import referrer_host
from ..deps import DbConn
from ..errors import AppError
from ..schemas import CODE_PATTERN

router = APIRouter(tags=["redirect"])

# What people see when a link no longer works: (HTTP status, error code, message).
UNAVAILABLE = {
    "missing": (404, "not_found", "This short link doesn't exist or was deleted."),
    "expired": (410, "gone", "This short link has expired."),
    "click_limit": (410, "gone", "This short link has reached its click limit."),
}

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; background: #f4f1ea;
         color: #1f2328; font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
  main {{ max-width: 26rem; padding: 2rem; text-align: center; }}
  code {{ font-size: 1.25rem; background: #fff; padding: 0.15rem 0.5rem; border-radius: 4px; }}
  h1 {{ font-size: 1.4rem; margin: 1rem 0 0.5rem; }}
  p {{ color: #57606a; margin: 0; }}
</style></head>
<body><main><code>/r/{code}</code><h1>{title}</h1>
<p>If someone shared it with you, ask them for a new link.</p></main></body></html>"""


@router.get("/r/{code}", response_class=RedirectResponse, status_code=302)
def follow_link(code: Annotated[str, Path(pattern=CODE_PATTERN)], request: Request, conn: DbConn):
    outcome, target = repository.follow(conn, code, referrer_host(request.headers.get("referer")))
    if outcome == "ok":
        # 302, not 301: browsers cache 301s and would skip this server (and the click count) next time.
        return RedirectResponse(target, status_code=302, headers={"Cache-Control": "no-store"})

    status, error_code, message = UNAVAILABLE[outcome]
    # People open short links in a browser, so give them a readable page, not JSON.
    if "text/html" in request.headers.get("accept", ""):
        html = PAGE.format(code=escape(code), title=escape(message))
        return HTMLResponse(html, status_code=status, headers={"Cache-Control": "no-store"})
    raise AppError(status, error_code, message)
