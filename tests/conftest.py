import threading

import pytest

from toolsmoke.mock import serve


def _start(**kw):
    srv = serve("127.0.0.1", 0, ttft_ms=5, tps=4000, **kw)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/v1"


@pytest.fixture(scope="session")
def good_server():
    srv, url = _start(mode="good", api_key="sk-test")
    yield url
    srv.shutdown()


@pytest.fixture(scope="session")
def broken_server():
    srv, url = _start(mode="broken")
    yield url
    srv.shutdown()


@pytest.fixture()
def start_mock():
    servers = []

    def _f(**kw):
        srv, url = _start(**kw)
        servers.append(srv)
        return url

    yield _f
    for s in servers:
        s.shutdown()
