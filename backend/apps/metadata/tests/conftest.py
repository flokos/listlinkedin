"""A local web for fetcher tests: HTTP and HTTPS servers on 127.0.0.1, a stub DNS resolver,
and a dial hook that sends connections for the *validated public address* to them.

The fetcher refuses 127.0.0.1, rightly, so tests resolve their host names to a public address
(PUBLIC) and the dial hook, the one seam the fetcher has, connects that address to the local
server instead. Every lookup and every dial is recorded, so tests can show the fetcher
connects only to the address it checked.
"""

import gzip
import ssl
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import trustme

from apps.metadata import fetcher

PUBLIC = "93.184.215.14"  # a global address: what the test names resolve to
HOSTS = ("site.test", "www.site.test", "other.test", "images.test")


@dataclass
class Route:
    status: int = 200
    body: bytes = b""
    headers: dict = field(default_factory=dict)
    delay: float = 0.0  # before answering
    trickle: float = 0.0  # pause between body chunks of 1 KB


@dataclass
class Web:
    routes: dict = field(default_factory=dict)  # (host, path) -> Route
    requests: list = field(default_factory=list)  # (host header, path, headers)
    dns: dict = field(default_factory=dict)  # name -> [addresses]
    lookups: list = field(default_factory=list)
    dialed: list = field(default_factory=list)

    def page(self, url_path: str, html: str, host="site.test", **route):
        headers = {"Content-Type": "text/html; charset=utf-8", **route.pop("headers", {})}
        self.routes[(host, url_path)] = Route(body=html.encode(), headers=headers, **route)

    def add(self, host: str, url_path: str, **route):
        self.routes[(host, url_path)] = Route(**route)

    def redirect(self, host: str, url_path: str, location: str, status=302):
        self.routes[(host, url_path)] = Route(status=status, headers={"Location": location})


def _handler(web: Web):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (the stdlib's name)
            host = self.headers.get("Host", "").split(":")[0]
            web.requests.append((self.headers.get("Host"), self.path, dict(self.headers)))
            route = web.routes.get((host, self.path), Route(status=404, body=b"not found"))
            time.sleep(route.delay)
            self.send_response(route.status)
            headers = {"Content-Length": str(len(route.body)), **route.headers}
            for name, value in headers.items():
                self.send_header(name, value)
            self.end_headers()
            if route.trickle:
                for start in range(0, len(route.body), 1024):
                    self.wfile.write(route.body[start : start + 1024])
                    self.wfile.flush()
                    time.sleep(route.trickle)
            else:
                self.wfile.write(route.body)

        def log_message(self, *args):
            pass

    return Handler


@pytest.fixture(scope="session")
def test_ca():
    return trustme.CA()


@pytest.fixture
def web(monkeypatch, test_ca, tmp_path):
    state = Web(dns={host: [PUBLIC] for host in HOSTS})
    http = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    https = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    test_ca.issue_cert("site.test", "www.site.test", "images.test").configure_cert(context)
    https.socket = context.wrap_socket(https.socket, server_side=True)
    for server in (http, https):
        threading.Thread(target=server.serve_forever, daemon=True).start()

    def resolve(host, port):
        state.lookups.append(host)
        if host not in state.dns:
            raise fetcher.FetchFailed(f"{host} doesn't exist.")
        return list(state.dns[host])

    def dial(address, port):
        state.dialed.append((address, port))
        assert address == PUBLIC, f"dialed {address}: only the validated address may be"
        return ("127.0.0.1", (http if port == 80 else https).server_address[1])

    ca_file = tmp_path / "ca.pem"
    test_ca.cert_pem.write_to_path(str(ca_file))
    monkeypatch.setattr(fetcher, "resolve", resolve)
    monkeypatch.setattr(fetcher, "dial", dial)
    monkeypatch.setattr(fetcher, "ca_certs", str(ca_file))
    monkeypatch.setattr(fetcher, "PER_HOST_INTERVAL", 0.0)
    monkeypatch.setattr(fetcher, "_last_request", {})
    yield state
    for server in (http, https):
        server.shutdown()
        server.server_close()


def gzipped(data: bytes) -> bytes:
    return gzip.compress(data)
