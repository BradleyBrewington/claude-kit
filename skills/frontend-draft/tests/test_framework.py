import http.client
import json
import re
import socket
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from framework_server import create_server
from studio import build_draft, detect


class Upstream(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def do_GET(self):
        if self.headers.get('Upgrade') == 'websocket':
            self.send_response(101)
            self.send_header('Upgrade', 'websocket')
            self.send_header('Connection', 'Upgrade')
            self.end_headers()
            self.wfile.write(self.rfile.read(4))
            return
        body = b'<html><body><h1>Original</h1></body></html>'
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class FrameworkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
        self.server = create_server(self.root, 0, self.upstream.server_port)
        for server in (self.upstream, self.server):
            threading.Thread(target=server.serve_forever, daemon=True).start()
        self.host = '127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        for server in (self.server, self.upstream):
            server.shutdown(); server.server_close()
        self.tmp.cleanup()

    def request(self, method, path, data=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        connection.request(method, path, json.dumps(data) if data is not None else None, headers or {})
        response = connection.getresponse()
        result = response.status, response.read()
        connection.close()
        return result

    def test_html_and_websocket_forwarding(self):
        status, body = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(b'<h1>Original</h1>', body)
        self.assertIn(b'/__draft_studio/editor.js', body)
        with socket.create_connection(('127.0.0.1', self.server.server_port)) as sock:
            sock.settimeout(3)
            sock.sendall(f'GET /hmr HTTP/1.1\r\nHost: {self.host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n'.encode())
            header = b''
            while not header.endswith(b'\r\n\r\n'): header += sock.recv(1)
            self.assertIn(b'101', header)
            sock.sendall(b'ping')
            self.assertEqual(sock.recv(4), b'ping')

    def test_save_persists_without_touching_source_and_rejects_conflicts(self):
        source = self.root / 'App.tsx'; source.write_text('<h1>Original</h1>')
        _, script = self.request('GET', '/__draft_studio/editor.js')
        token = re.search(rb'const token = "([^"]+)"', script).group(1).decode()
        payload = {'revision': 0, 'changes': [{'id':'one','kind':'text','route':'/','selector':'h1','tag':'h1','before':'Original','after':'Edited'}]}
        headers = {'X-Draft-Token':token, 'Origin':'http://' + self.host, 'Content-Type':'application/json'}
        self.assertEqual(self.request('POST', '/__draft_studio/changes', payload)[0], 403)
        self.assertEqual(self.request('POST', '/__draft_studio/changes', payload, {**headers,'Origin':'https://evil.example'})[0], 403)
        self.assertEqual(self.request('GET', '/', headers={'Host':'evil.example'})[0], 403)
        status, body = self.request('POST', '/__draft_studio/changes', payload, headers)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['revision'], 1)
        self.assertEqual(source.read_text(), '<h1>Original</h1>')
        self.assertEqual(json.loads((self.root / '.draft-studio/changes.json').read_text())['changes'][0]['after'], 'Edited')
        self.assertEqual(self.request('POST', '/__draft_studio/changes', payload, headers)[0], 409)
        payload['revision'] = 1; payload['changes'][0]['kind'] = 'write-file'
        self.assertEqual(self.request('POST', '/__draft_studio/changes', payload, headers)[0], 400)

    def test_framework_copy_excludes_builds_and_keeps_original(self):
        source = self.root / 'source'; source.mkdir()
        (source / 'package.json').write_text(json.dumps({'scripts':{'dev':'next dev'},'dependencies':{'next':'16.4.3'}}))
        (source / '.next').mkdir(); (source / '.next/stale').write_text('build')
        (source / 'App.tsx').write_text('<p>Keep me</p>')
        mode, servable, meta = detect(source)
        self.assertEqual((mode, meta['flavor']), ('framework', 'next'))
        draft = self.root / 'project/draft'
        build_draft(mode, servable, source, draft, False)
        self.assertFalse((draft / '.next').exists())
        (draft / 'App.tsx').write_text('<p>Changed</p>')
        self.assertEqual((source / 'App.tsx').read_text(), '<p>Keep me</p>')


if __name__ == '__main__': unittest.main()
