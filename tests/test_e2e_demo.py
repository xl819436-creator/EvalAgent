"""Day 39：验证 scripts/e2e_demo.py 的 _request——request_id 与有界重试（不依赖 docker）。"""

import httpx

from scripts.e2e_demo import _request


def test_request_id_header_sent():
    seen = {}

    def handler(request):
        seen["rid"] = request.headers.get("X-Request-Id")
        return httpx.Response(200, json={"ok": True})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://testserver")
    _request(client, "GET", "/health", "req-test")
    assert seen["rid"] == "req-test"


def test_bounded_retries_on_500():
    calls = {"n": 0}

    def flaky(request):
        calls["n"] += 1
        return httpx.Response(500, json={"detail": "boom"})

    client = httpx.Client(transport=httpx.MockTransport(flaky), base_url="http://testserver")
    try:
        _request(client, "GET", "/health", "req-x")
        raise AssertionError("应当抛 RuntimeError")
    except RuntimeError:
        assert calls["n"] == 3  # 1 次直接 + 2 次重试 = 有界，不无限循环