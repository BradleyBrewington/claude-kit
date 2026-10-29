"""Loopback dev proxy and durable visual change requests (no JSX rewriting)."""
import argparse
import gzip
import http.client
import json
import os
import secrets
import select
import socket
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
PREFIX = '/__draft_studio/'
HOP = {'connection', 'keep-alive', 'transfer-encoding', 'upgrade',
       'proxy-connection', 'te', 'trailer'}
STYLE_KEYS = {'color', 'background-color', 'font-size', 'font-weight',
              'padding', 'margin', 'gap', 'border-radius', 'width',
              'max-width', 'text-align', 'display'}


class ChangeStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.path = self.root / '.draft-studio' / 'changes.json'
        self.lock = threading.Lock()

    @contextmanager
    def file_lock(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.parent.resolve().is_relative_to(self.root):
            raise ValueError('Change directory must stay inside the draft')
        lock_path = self.path.parent / '.lock'
        if lock_path.is_symlink():
            raise ValueError('Invalid lock file')
        with lock_path.open('a+b') as lock:
            lock.seek(0, 2)
            if lock.tell() == 0:
                lock.write(b'0'); lock.flush()
            lock.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                lock.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock, fcntl.LOCK_UN)

    def read(self):
        if not self.path.exists():
            return {'version': 1, 'revision': 0, 'changes': []}
        if not self.path.resolve().is_relative_to(self.root):
            raise ValueError('Change file must stay inside the draft')
        return json.loads(self.path.read_text(encoding='utf-8'))

    def write(self, payload):
        changes = payload.get('changes')
        if not isinstance(changes, list) or len(changes) > 200:
            raise ValueError('Expected at most 200 changes')
        ids = set()
        for c in changes:
            if not isinstance(c, dict) or c.get('kind') not in ('text', 'style', 'hide'):
                raise ValueError('Unsupported change kind')
            for field in ('id', 'route', 'selector', 'before', 'after'):
                if not isinstance(c.get(field), str) or len(c[field]) > 20000:
                    raise ValueError('Invalid ' + field)
            if not c['route'].startswith('/') or c['route'].startswith('//'):
                raise ValueError('Expected a relative route')
            if c['id'] in ids:
                raise ValueError('Duplicate change id')
            ids.add(c['id'])
            if c['kind'] == 'style' and c.get('property') not in STYLE_KEYS:
                raise ValueError('Unsupported style property')
        with self.lock, self.file_lock():
            current = self.read()
            if payload.get('revision') != current['revision']:
                return None
            doc = {'version': 1, 'revision': current['revision'] + 1,
                   'updated_at': datetime.now(timezone.utc).isoformat(),
                   'changes': changes}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.parent.resolve().is_relative_to(self.root):
                raise ValueError('Change directory must stay inside the draft')
            temp = self.path.with_suffix('.tmp')
            if temp.is_symlink():
                raise ValueError('Invalid temporary file')
            temp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            os.replace(temp, self.path)
            return doc


def create_server(root, port, upstream_port):
    store = ChangeStore(root)
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        # No read-ahead: websocket frames after the handshake belong to the tunnel.
        rbufsize = 0

        def log_message(self, *args):
            pass

        def send_data(self, status, data, content_type='application/json'):
            if isinstance(data, str):
                data = data.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(data)

        def allowed(self):
            hosts = {f'localhost:{self.server.server_port}', f'127.0.0.1:{self.server.server_port}'}
            host = self.headers.get('Host', '')
            origin = self.headers.get('Origin')
            return host in hosts and (not origin or origin == 'http://' + host)

        def dispatch(self):
            if not self.allowed():
                return self.send_data(403, '{"error":"Use the local studio URL"}')
            path = urlsplit(self.path).path
            if path.startswith(PREFIX):
                return self.studio_request(path)
            if self.headers.get('Upgrade', '').lower() == 'websocket':
                return self.websocket()
            return self.proxy()

        def studio_request(self, path):
            try:
                if path == PREFIX + 'editor.js' and self.command == 'GET':
                    script = (HERE / 'framework_editor.js').read_text(encoding='utf-8')
                    script = script.replace('__STUDIO_TOKEN__', json.dumps(token))
                    return self.send_data(200, script, 'text/javascript; charset=utf-8')
                if path != PREFIX + 'changes':
                    return self.send_data(404, '{"error":"Unknown studio endpoint"}')
                if self.command == 'GET':
                    return self.send_data(200, json.dumps(store.read()))
                if self.command != 'POST':
                    return self.send_data(405, '{"error":"Method not allowed"}')
                if self.headers.get('X-Draft-Token') != token:
                    return self.send_data(403, '{"error":"Invalid session token; reload the page"}')
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 1_000_000:
                    return self.send_data(413, '{"error":"Change request exceeds 1 MB"}')
                doc = store.write(json.loads(self.rfile.read(length)))
                if doc is None:
                    return self.send_data(409, '{"error":"Changes were updated elsewhere. Reload before editing."}')
                return self.send_data(200, json.dumps(doc))
            except (ValueError, KeyError, TypeError) as exc:
                return self.send_data(400, json.dumps({'error': str(exc)}))
            except OSError as exc:
                return self.send_data(500, json.dumps({'error': str(exc)}))

        def proxy(self):
            conn = http.client.HTTPConnection('127.0.0.1', upstream_port, timeout=120)
            response_started = False
            try:
                headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
                headers['Accept-Encoding'] = 'identity'
                length = int(self.headers.get('Content-Length', '0'))
                if self.headers.get('Transfer-Encoding') or length > 20_000_000:
                    return self.send_data(413, '{"error":"Unsupported request body"}')
                body = self.rfile.read(length) if length else None
                conn.request(self.command, self.path, body, headers)
                response = conn.getresponse()
                html = 'text/html' in response.getheader('Content-Type', '') and self.command != 'HEAD'
                data = None
                if html:
                    data = response.read()
                    if response.getheader('Content-Encoding') == 'gzip':
                        data = gzip.decompress(data)
                    if response.getheader('Content-Encoding') in (None, 'identity', 'gzip'):
                        markup = b'<script src="/__draft_studio/editor.js" defer data-draft-chrome></script>'
                        lower = data.lower()
                        pos = lower.rfind(b'</body>')
                        data = data[:pos] + markup + data[pos:] if pos >= 0 else data + markup
                    else:
                        html = False
                self.send_response(response.status)
                for key, value in response.getheaders():
                    if key.lower() in HOP or key.lower() in ('content-length', 'connection'):
                        continue
                    if html and key.lower() in ('content-encoding', 'etag', 'content-md5'):
                        continue
                    self.send_header(key, value)
                if data is not None:
                    self.send_header('Content-Length', str(len(data)))
                self.send_header('Connection', 'close')
                self.end_headers()
                response_started = True
                if data is not None:
                    self.wfile.write(data)
                else:
                    while chunk := response.read1(65536):
                        self.wfile.write(chunk)
                        self.wfile.flush()
                self.close_connection = True
            except (OSError, http.client.HTTPException, ValueError) as exc:
                # If upstream is still starting, the user can simply refresh.
                if not response_started and not self.wfile.closed:
                    try:
                        self.send_data(502, json.dumps({'error': 'Dev server unavailable', 'detail': str(exc)}))
                    except OSError:
                        pass
            finally:
                conn.close()

        def websocket(self):
            try:
                with socket.create_connection(('127.0.0.1', upstream_port), timeout=10) as upstream:
                    request = f'{self.command} {self.path} HTTP/1.1\r\n'
                    request += ''.join(f'{k}: {v}\r\n' for k, v in self.headers.items()) + '\r\n'
                    upstream.sendall(request.encode('latin-1'))
                    upstream.settimeout(None)
                    self.connection.settimeout(None)
                    while True:
                        readable, _, _ = select.select([upstream, self.connection], [], [], 1)
                        for source in readable:
                            data = source.recv(65536)
                            if not data:
                                return
                            (self.connection if source is upstream else upstream).sendall(data)
            except OSError:
                pass
            finally:
                self.close_connection = True

        do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = dispatch

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    server.store = store
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', required=True)
    parser.add_argument('--port', type=int, default=8792)
    parser.add_argument('--upstream-port', type=int)
    parser.add_argument('--ack', type=int, metavar='REVISION', help='Clear an implemented batch only if its revision still matches')
    args = parser.parse_args()
    if args.ack is not None:
        result = ChangeStore(args.dir).write({'revision': args.ack, 'changes': []})
        if result is None:
            parser.exit(1, 'Newer edits exist; read changes.json again before acknowledging.\n')
        print('Acknowledged visual requests; revision', result['revision'])
        parser.exit()
    if args.upstream_port is None:
        parser.error('--upstream-port is required when serving')
    server = create_server(args.dir, args.port, args.upstream_port)
    print(f'Visual editor: http://localhost:{server.server_port}/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
