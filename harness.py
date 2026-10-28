"""Company migration seam: replace InventoryAPI, preserve observable semantics."""
import json
import unittest
from urllib.request import Request, build_opener, ProxyHandler
from urllib.parse import urlencode
import uuid

BASE_URL = None


class InventoryAPI:
    def __init__(self, base_url):
        self.base_url = base_url
        self.opener = build_opener(ProxyHandler({}))  # loopback demo ignores proxy env

    def call(self, method, path, body=None):
        raw = None if body is None else json.dumps(body).encode('utf-8')
        request = Request(self.base_url + path, data=raw, method=method,
                          headers={'Content-Type': 'application/json'})
        with self.opener.open(request, timeout=5) as response:
            return json.load(response)

    def create_item(self, stock):
        return self.call('POST', '/items', {'stock': stock})['sku']

    def delete_item(self, sku):
        self.call('DELETE', '/items/' + sku)

    def stock(self, sku):
        return self.call('GET', '/items/' + sku)['stock']

    def reserve(self, sku, quantity, request_id):
        # Preserve quantity type/value: negative cases must reach the server.
        return self.call('POST', '/reservations', {
            'sku': sku, 'quantity': quantity, 'request_id': request_id})

    def reservation_count(self, sku):
        return self.call('GET', '/reservations?' + urlencode({'sku': sku}))['count']


class ScenarioCase(unittest.TestCase):
    def setUp(self):
        if not BASE_URL:
            raise RuntimeError('Run generated tests with workflow.py run')
        self.api = InventoryAPI(BASE_URL)
        self.namespace = uuid.uuid4().hex

    def request_id(self, key):
        return self.namespace + ':' + key
