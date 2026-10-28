"""Reviewed teaching pattern for fixture, raw request and cleanup."""
from harness import ScenarioCase


class ExistingExample(ScenarioCase):
    def test_success(self):
        sku = self.api.create_item(stock=5)
        self.addCleanup(self.api.delete_item, sku)
        self.assertEqual(self.api.stock(sku), 5)
        result = self.api.reserve(sku, 2, self.request_id('first'))
        self.assertEqual(result['code'], 'OK')
        self.assertIsInstance(result['reservation_id'], str)
        self.assertEqual(self.api.stock(sku), 3)
        self.assertEqual(self.api.reservation_count(sku), 1)
