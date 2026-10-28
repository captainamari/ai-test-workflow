"""Isolated teaching HTTP service. Never use as a production inventory server."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from urllib.parse import parse_qs, urlparse
import uuid


class Inventory:
    def __init__(self, fault='none'):
        self.items = {}
        self.reservations = {}
        self.fault = fault
        self.lock = threading.Lock()

    def reserve(self, sku, quantity, request_id):
        with self.lock:
            if sku not in self.items:
                return {'code': 'ITEM_NOT_FOUND', 'reservation_id': None}
            if type(quantity) is not int or quantity <= 0:
                return {'code': 'INVALID_QUANTITY', 'reservation_id': None}
            previous = self.reservations.get(request_id)
            if previous:
                if (previous['sku'], previous['quantity']) != (sku, quantity):
                    return {'code': 'IDEMPOTENCY_CONFLICT', 'reservation_id': None}
                if self.fault != 'double-reserve':
                    return {'code': 'OK', 'reservation_id': previous['id']}
            if self.items[sku] < quantity:
                if self.fault == 'reject-writes':
                    self.items[sku] -= quantity
                return {'code': 'INSUFFICIENT_STOCK', 'reservation_id': None}
            self.items[sku] -= quantity
            reservation_id = str(uuid.uuid4())
            if self.fault != 'missing-record':
                self.reservations[request_id] = {
                    'id': reservation_id, 'sku': sku, 'quantity': quantity}
            return {'code': 'OK', 'reservation_id': reservation_id}


@contextmanager
def serve(fault='none'):
    state = Inventory(fault)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, body, status=200):
            raw = json.dumps(body).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            try:
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path == '/items':
                    if type(body['stock']) is not int or body['stock'] < 0:
                        raise ValueError('invalid stock')
                    sku = str(uuid.uuid4())
                    with state.lock:
                        state.items[sku] = body['stock']
                    self.reply({'sku': sku})
                elif self.path == '/reservations':
                    self.reply(state.reserve(body['sku'], body['quantity'], body['request_id']))
                else:
                    self.reply({'error': 'unknown endpoint'}, 404)
            except (ValueError, KeyError, TypeError):
                self.reply({'error': 'malformed request'}, 400)

        def do_GET(self):
            parsed = urlparse(self.path)
            with state.lock:
                if parsed.path.startswith('/items/'):
                    sku = parsed.path.rsplit('/', 1)[1]
                    if sku in state.items:
                        self.reply({'stock': state.items[sku]})
                    else:
                        self.reply({'error': 'not found'}, 404)
                elif parsed.path == '/reservations':
                    sku = parse_qs(parsed.query).get('sku', [''])[0]
                    count = sum(r['sku'] == sku for r in state.reservations.values())
                    self.reply({'count': count})
                else:
                    self.reply({'error': 'unknown endpoint'}, 404)

        def do_DELETE(self):
            sku = self.path.rsplit('/', 1)[1]
            with state.lock:
                state.items.pop(sku, None)
                state.reservations = {k: v for k, v in state.reservations.items() if v['sku'] != sku}
            self.reply({'deleted': True})

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:{}'.format(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
