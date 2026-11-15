"""Expiry dates, click limits, the 410 page and QR codes."""
import threading
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_settings, register_and_login, requires_db

pytestmark = requires_db

URL = "https://example.com/sale"


def in_future(**delta) -> str:
    return (datetime.now(timezone.utc) + timedelta(**delta)).isoformat()


def make_link(client, auth, **extra):
    res = client.post("/api/links", json={"target_url": URL, "custom_code": "sale", **extra}, headers=auth)
    assert res.status_code == 201, res.text
    return res.json()


def test_new_link_has_no_limits_and_is_active(client, auth):
    link = make_link(client, auth)
    assert link["expires_at"] is None and link["max_clicks"] is None
    assert link["active"] is True and link["inactive_reason"] is None


def test_click_limit_stops_redirects_with_410(client, auth):
    link = make_link(client, auth, max_clicks=2)
    assert client.get("/r/sale", follow_redirects=False).status_code == 302
    assert client.get("/r/sale", follow_redirects=False).status_code == 302

    blocked = client.get("/r/sale", follow_redirects=False)
    assert blocked.status_code == 410
    assert blocked.json()["error"] == {"code": "gone", "message": "This short link has reached its click limit."}

    after = client.get(f"/api/links/{link['id']}", headers=auth).json()
    assert after["click_count"] == 2  # the blocked visit isn't counted
    assert after["active"] is False and after["inactive_reason"] == "click_limit"


def test_expired_link_is_410_and_not_counted(client, auth, admin_conn):
    link = make_link(client, auth, expires_at=in_future(hours=1))
    admin_conn.execute("update shortener_links set created_at = now() - interval '2 hours', "
                       "expires_at = now() - interval '1 minute' where id = %s", (link["id"],))
    res = client.get("/r/sale", follow_redirects=False)
    assert res.status_code == 410 and res.json()["error"]["message"] == "This short link has expired."
    after = client.get(f"/api/links/{link['id']}", headers=auth).json()
    assert after["click_count"] == 0 and after["inactive_reason"] == "expired"


def test_browsers_get_a_readable_page(client, auth):
    make_link(client, auth, max_clicks=1)
    client.get("/r/sale", follow_redirects=False)
    page = client.get("/r/sale", follow_redirects=False, headers={"Accept": "text/html,application/xhtml+xml"})
    assert page.status_code == 410
    assert page.headers["content-type"].startswith("text/html")
    assert "reached its click limit" in page.text and "/r/sale" in page.text

    missing = client.get("/r/nope123", follow_redirects=False, headers={"Accept": "text/html"})
    assert missing.status_code == 404 and "doesn&#x27;t exist" in missing.text


@pytest.mark.parametrize("extra", [
    {"max_clicks": 0},
    {"max_clicks": 1_000_001},
    {"expires_at": "2020-01-01T00:00:00Z"},           # in the past
    {"expires_at": "2099-01-01T00:00:00"},            # no timezone
])
def test_invalid_limits_are_rejected(client, auth, extra):
    res = client.post("/api/links", json={"target_url": URL, **extra}, headers=auth)
    assert res.status_code == 422


def test_owner_can_change_and_remove_limits(client, auth):
    link = make_link(client, auth, max_clicks=1)
    client.get("/r/sale", follow_redirects=False)
    assert client.get("/r/sale", follow_redirects=False).status_code == 410

    raised = client.patch(f"/api/links/{link['id']}", json={"max_clicks": 5}, headers=auth).json()
    assert raised["max_clicks"] == 5 and raised["active"] is True
    assert client.get("/r/sale", follow_redirects=False).status_code == 302

    expiry = in_future(days=7)
    both = client.patch(f"/api/links/{link['id']}", json={"expires_at": expiry}, headers=auth).json()
    assert both["max_clicks"] == 5 and both["expires_at"] is not None  # untouched field kept

    cleared = client.patch(f"/api/links/{link['id']}", json={"max_clicks": None, "expires_at": None},
                           headers=auth).json()
    assert cleared["max_clicks"] is None and cleared["expires_at"] is None


def test_patch_rules(client, auth):
    link = make_link(client, auth)
    url = f"/api/links/{link['id']}"
    assert client.patch(url, json={}, headers=auth).status_code == 422
    assert client.patch(url, json={"target_url": "https://evil.example"}, headers=auth).status_code == 422
    other = register_and_login(client, email="other@example.com")
    assert client.patch(url, json={"max_clicks": 3}, headers=other).status_code == 404
    assert client.patch(url, json={"max_clicks": 3}).status_code == 401


def test_last_click_cannot_be_used_twice_at_once(auth, client):
    """Two simultaneous clicks on a link with one click left: exactly one redirects."""
    make_link(client, auth, max_clicks=1)
    results = []
    barrier = threading.Barrier(2)

    def click():
        with TestClient(create_app(make_settings())) as c:
            barrier.wait()
            results.append(c.get("/r/sale", follow_redirects=False).status_code)

    threads = [threading.Thread(target=click) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [302, 410]


def test_qr_code_svg_and_png(client, auth):
    link = make_link(client, auth)
    svg = client.get(f"/api/links/{link['id']}/qr", headers=auth)
    assert svg.status_code == 200 and svg.headers["content-type"].startswith("image/svg+xml")
    assert svg.text.lstrip().startswith("<svg") and 'filename="sale-qr.svg"' in svg.headers["content-disposition"]

    png = client.get(f"/api/links/{link['id']}/qr", params={"format": "png"}, headers=auth)
    assert png.status_code == 200 and png.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_qr_code_is_private_and_validated(client, auth):
    link = make_link(client, auth)
    other = register_and_login(client, email="other@example.com")
    assert client.get(f"/api/links/{link['id']}/qr", headers=other).status_code == 404
    assert client.get(f"/api/links/{link['id']}/qr").status_code == 401
    assert client.get(f"/api/links/{link['id']}/qr", params={"format": "gif"}, headers=auth).status_code == 422


def test_app_role_cannot_change_code_or_target(admin_conn):
    from tests.conftest import TEST_DB
    with psycopg.connect(TEST_DB) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("update shortener_links set target_url = 'https://evil.example'")
