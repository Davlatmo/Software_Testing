import unittest
import copy
from techshop_testing import Server as server
from flask import json

class TestServerProducts(unittest.TestCase):
    def setUp(self):
        # Preserve original mutable globals and reset session store
        self._original_products = copy.deepcopy(server.PRODUCTS)
        self._original_users = copy.deepcopy(server.USERS)
        server.SESSIONS.clear()

        self.client = server.app.test_client()

    def tearDown(self):
        # Restore globals to avoid cross-test contamination
        server.PRODUCTS.clear()
        server.PRODUCTS.extend(copy.deepcopy(self._original_products))

        server.USERS.clear()
        server.USERS.extend(copy.deepcopy(self._original_users))

        server.SESSIONS.clear()

    def test_get_products_search_case_insensitive_returns_matches(self):
        # search for "headphones" in different case
        resp = self.client.get("/api/products?search=HEADphones")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsInstance(data, list)
        # Expect at least one matching product and that it contains the term (case-insensitive)
        self.assertTrue(any("Headphones".lower() in p["name"].lower() for p in data))

    def test_get_products_search_whitespace_returns_all_products(self):
        # whitespace-only search should return all products
        resp = self.client.get("/api/products?search=   ")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(len(data), len(self._original_products))

    def test_get_products_category_case_insensitive_filters(self):
        # category "Electronics" should match electronics products only
        resp = self.client.get("/api/products?category=Electronics")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(all(p["category"] == "electronics" for p in data))
        # there should be at least one electronics product
        self.assertGreater(len(data), 0)

    def test_get_products_category_all_returns_all_products(self):
        resp = self.client.get("/api/products?category=all")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(len(data), len(self._original_products))

    def test_get_products_invalid_category_returns_400(self):
        resp = self.client.get("/api/products?category=toys")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data.get("error"), "Invalid category")

    def test_get_products_price_range_filters_and_inclusive_boundaries(self):
        # minPrice and maxPrice inclusive: choose a range that should include product id 6 (24.99)
        resp = self.client.get("/api/products?minPrice=24.99&maxPrice=25")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        prices = [p["price"] for p in data]
        self.assertIn(24.99, prices)

        # Another range: expect products priced between 50 and 90
        resp2 = self.client.get("/api/products?minPrice=50&maxPrice=90")
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.get_json()
        for p in data2:
            self.assertGreaterEqual(p["price"], 50)
            self.assertLessEqual(p["price"], 90)

    def test_get_products_invalid_min_price_non_number_returns_400(self):
        resp = self.client.get("/api/products?minPrice=abc")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data.get("error"), "minPrice must be a number")

    def test_get_products_invalid_max_price_non_number_returns_400(self):
        resp = self.client.get("/api/products?maxPrice=notanumber")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data.get("error"), "maxPrice must be a number")

    def test_get_products_empty_min_price_param_returns_400(self):
        # empty string as minPrice should be treated as invalid number
        resp = self.client.get("/api/products?minPrice=")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data.get("error"), "minPrice must be a number")

    def test_min_price_greater_than_max_price_returns_400(self):
        resp = self.client.get("/api/products?minPrice=150&maxPrice=50")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data.get("error"), "minPrice cannot be greater than maxPrice")

    def test_combined_filters_search_category_price_returns_expected(self):
        # This should match the Mechanical Keyboard (id 2): electronics, name contains keyboard, price 129.99 <= 150
        resp = self.client.get("/api/products?search=keyboard&category=electronics&maxPrice=150")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(any(p["id"] == 2 for p in data))
        # Ensure all returned items meet all filters
        for p in data:
            self.assertIn("keyboard", p["name"].lower())
            self.assertEqual(p["category"], "electronics")
            self.assertLessEqual(p["price"], 150)

    def test_get_single_product_exists_returns_product(self):
        resp = self.client.get("/api/products/1")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["id"], 1)
        self.assertIn("name", data)

    def test_get_single_product_not_found_returns_404(self):
        resp = self.client.get("/api/products/9999")
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertEqual(data.get("error"), "Product not found")

if __name__ == "__main__":
    unittest.main()