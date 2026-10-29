# -*- coding: utf-8 -*-
"""Simple path-based reverse proxy:
  /                 -> Bot Room 3D      (localhost:8099)
  /monitor          -> Usage Monitor    (localhost:3001)
  /monitor/*        -> Usage Monitor    (localhost:3001)
  /api/*            -> Usage Monitor    (localhost:3001)
Serves over HTTP (Tailscale terminate TLS at :443 and forward plain HTTP to this).
"""
import http.server, socketserver, urllib.request, urllib.error, logging
from urllib.parse import urlparse

BACKENDS = {
    # check these FIRST (more specific), then / as catch-all for Bot Room
    "/monitor": ("http://localhost:3001", 3001),
    "/api": ("http://localhost:3001", 3001),
    "/": ("http://localhost:8099", 8099),
}


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    server_version = "BotRoom-Proxy/1.0"

    def log_message(self, format, *args):
        logging.getLogger("proxy").info("%s - %s" % (self.address_string(), format % args))

    def _forward(self, forward_host, forward_port, forward_path):
        try:
            url = 'http://{}:{}/{}'.format(forward_host, forward_port, forward_path.lstrip('/'))
            open(r'C:/Users/PONG/proxy_debug.log', 'a', encoding='utf-8').write("FORWARD {} -> {}  ".format(self.path, url) + "\n")
            req = urllib.request.Request(url, method=self.command)
            for key, value in self.headers.items():
                if key.lower() in ("host", "content-length"):
                    continue
                req.add_header(key, value)
            with urllib.request.urlopen(req, timeout=30) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in ("transfer-encoding",):
                        continue
                    self.send_header(k, v)
                self.end_headers()
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except urllib.error.HTTPError as e:
            self.send_error(e.code, f"Upstream error ({e.code})")
        except Exception as e:
            body = f"Proxy error: {type(e).__name__}: {e}".encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith('/monitor'):
            forward_host, forward_port = '127.0.0.1', 3001
            forward_path = path[len('/monitor'):] or '/'
        elif path.startswith('/api'):
            forward_host, forward_port = '127.0.0.1', 3001
            forward_path = path
        else:
            forward_host, forward_port = '127.0.0.1', 8099
            forward_path = path
        self._forward(forward_host, forward_port, forward_path)
        return

    do_POST = do_GET


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s proxy %(message)s")
    PORT = 80
    with socketserver.TCPServer(("0.0.0.0", PORT), ProxyHandler) as httpd:
        print(f"[proxy] serving on port {PORT}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
