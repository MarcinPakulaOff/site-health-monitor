import http.server
import threading

import pytest

from site_monitor import state
from site_monitor.checks import Result, check_http, check_sitemap


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        routes = {
            "/": (200, b"<h1>Hello Example</h1>"),
            "/sitemap.xml": (200, b"<urlset>" + b"<url><loc>x</loc></url>" * 5 + b"</urlset>"),
        }
        code, body = routes.get(self.path, (404, b"nope"))
        self.send_response(code)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def base():
    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_http_ok_and_contains(base):
    assert check_http("home", base + "/", contains="Example").ok
    r = check_http("home", base + "/", contains="Missing")
    assert not r.ok and "missing" in r.detail


def test_http_status_and_expected_codes(base):
    assert check_http("x", base + "/gone").detail == "HTTP 404"
    assert check_http("x", base + "/gone", expect=[404]).ok


def test_http_connection_refused():
    assert not check_http("x", "http://127.0.0.1:9/").ok


def test_sitemap_threshold(base):
    assert check_sitemap(base + "/sitemap.xml", 5).ok
    r = check_sitemap(base + "/sitemap.xml", 6)
    assert not r.ok and "5 URLs" in r.detail


def fail(name="site"):
    return Result(name, False, "HTTP 502")


def ok(name="site"):
    return Result(name, True, "HTTP 200")


def test_single_failure_is_not_an_alert():
    alerts, st = state.evaluate([fail()], {}, now=0)
    assert alerts == [] and st["site"]["fails"] == 1


def test_second_failure_alerts_once_then_recovery():
    _, st = state.evaluate([fail()], {}, now=0)
    alerts, st = state.evaluate([fail()], st, now=60)
    assert len(alerts) == 1 and "HTTP 502" in alerts[0]
    alerts, st = state.evaluate([fail()], st, now=120)
    assert alerts == []                       # no spam while still down
    alerts, st = state.evaluate([ok()], st, now=180)
    assert len(alerts) == 1 and "back" in alerts[0]


def test_long_outage_is_repeated():
    _, st = state.evaluate([fail()], {}, now=0)
    _, st = state.evaluate([fail()], st, now=60)
    alerts, _ = state.evaluate([fail()], st, now=60 + 13 * 3600, repeat_hours=12)
    assert len(alerts) == 1


def test_history_summary(tmp_path):
    h = tmp_path / "h.jsonl"
    state.append_history(h, [Result("a", True, "", 100), Result("a", False, "", None)], now=1000)
    assert state.summary(h, now=1000) == [("a", 50.0, 100)]
