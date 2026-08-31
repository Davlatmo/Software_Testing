import unittest
import sys
import os
import threading
import time
import requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from techshop_testing.Server import app

BASE_URL = "http://localhost:3000"

def start_server():
    app.run(host="127.0.0.1", port=3000, debug=False, use_reloader=False)

class UnitTestBase(unittest.TestCase):
    """
    Base class for all generated unit tests.
    Starts the server once, creates a fresh session per test.
    """

    @classmethod
    def setUpClass(cls):
        t = threading.Thread(target=start_server, daemon=True)
        t.start()
        time.sleep(0.5)

    def setUp(self):
        """Fresh session before each test — clean cookie state."""
        self.session = requests.Session()
        self.session.delete(f"{BASE_URL}/api/cart")


class TestProductsFeature(UnitTestBase):
    """
    Tests for product search and filtering (REQ-01 through REQ-04).
    """

    def test_search_whitespace_returns_all_products(self):
        """If the search term is only whitespace, return all products (200)."""
        r = self.session.get(f"{BASE_URL}/api/products", params={"search": "   "})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 6)

    def test_invalid_category_returns_400(self):
        """Providing an invalid category should return 400 with error message."""
        r = self.session.get(f"{BASE_URL}/api/products", params={"category": "toys"})
        self.assertEqual(r.status_code, 400)
        data = r.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"], "Invalid category")

    def test_category_case_insensitive_and_all_keyword(self):
        """Category filtering should be case-insensitive and 'all' returns everything."""
        r1 = self.session.get(f"{BASE_URL}/api/products", params={"category": "Electronics"})
        self.assertEqual(r1.status_code, 200)
        data1 = r1.json()
        self.assertGreater(len(data1), 0)
        for p in data1:
            self.assertEqual(p["category"], "electronics")

        r2 = self.session.get(f"{BASE_URL}/api/products", params={"category": "all"})
        self.assertEqual(r2.status_code, 200)
        data2 = r2.json()
        self.assertEqual(len(data2), 6)

    def test_minPrice_invalid_string_returns_400(self):
        """Non-numeric minPrice should return 400 with an explanatory error."""
        r = self.session.get(f"{BASE_URL}/api/products", params={"minPrice": "not-a-number"})
        self.assertEqual(r.status_code, 400)
        data = r.json()
        self.assertEqual(data.get("error"), "minPrice must be a number")

    def test_maxPrice_invalid_string_returns_400(self):
        """Non-numeric maxPrice should return 400 with an explanatory error."""
        r = self.session.get(f"{BASE_URL}/api/products", params={"maxPrice": "NaNValue"})
        self.assertEqual(r.status_code, 400)
        data = r.json()
        self.assertEqual(data.get("error"), "maxPrice must be a number")

    def test_minPrice_greater_than_maxPrice_returns_400(self):
        """If minPrice > maxPrice, return 400 with specific error message."""
        r = self.session.get(f"{BASE_URL}/api/products", params={"minPrice": "200", "maxPrice": "100"})
        self.assertEqual(r.status_code, 400)
        data = r.json()
        self.assertEqual(data.get("error"), "minPrice cannot be greater than maxPrice")

    def test_price_range_filters_inclusive(self):
        """Price filtering should include products whose price is within [minPrice, maxPrice]."""
        r = self.session.get(f"{BASE_URL}/api/products", params={"minPrice": "50", "maxPrice": "90"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        # Expected product ids with prices between 50 and 90 inclusive: 1 (79.99), 4 (89.99), 5 (69.99)
        ids = {p["id"] for p in data}
        self.assertEqual(ids, {1, 4, 5})
        self.assertEqual(len(data), 3)

    def test_combined_filters_search_category_maxPrice(self):
        """Combined filters should work together (search + category + maxPrice)."""
        params = {"search": "keyboard", "category": "electronics", "maxPrice": "150"}
        r = self.session.get(f"{BASE_URL}/api/products", params=params)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data), 1)
        product = data[0]
        self.assertEqual(product["id"], 2)
        self.assertEqual(product["category"], "electronics")
        self.assertIn("keyboard", product["name"].lower())

    def test_minPrice_nan_is_rejected(self):
        """
        According to requirements, NaN/Infinity should not be accepted as valid numbers.
        Sending 'nan' as minPrice should result in a 400 response.
        """
        r = self.session.get(f"{BASE_URL}/api/products", params={"minPrice": "nan"})
        # Expecting a 400 error per requirements for invalid numeric input
        self.assertEqual(r.status_code, 400)
        data = r.json()
        # Accept either minPrice-specific message or generic numeric error
        self.assertIn("error", data)
        self.assertEqual(data["error"], "minPrice must be a number")


if __name__ == "__main__":
    unittest.main(verbosity=2)