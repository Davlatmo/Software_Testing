"""
API Tests 
===========================================================

WHAT OUR FILE DOES:
Tests every REST endpoint of the TechShop server using plain HTTP calls.

"""

import unittest
import threading
import time
import sys
import os
import requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
# Import the Flask app object that we'll run it in a background thread
from techshop_testing.Server import app
_this_dir = os.path.dirname(os.path.abspath(__file__))
_app_dir  = os.path.normpath(os.path.join(_this_dir, "..", "app"))
for _p in [_this_dir, _app_dir]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


BASE_URL = "http://localhost:3001"   # here we use 3001 to not clash with a running server


def start_test_server():
    """Start the Flask server in a daemon thread so tests can call it."""
    # use_reloader=False is critical, otherwise Flask spawns a second process
    app.run(host="127.0.0.1", port=3001, debug=False, use_reloader=False)


class TestBase(unittest.TestCase):
    """
    Base class that all test classes inherit from.
    Starts the server once before all tests (setUpClass) and creates a fresh
    requests.Session for each test (setUp).
    """

    @classmethod
    def setUpClass(cls):
        # Start Flask in a background daemon thread
        t = threading.Thread(target=start_test_server, daemon=True)
        t.start()
        
        time.sleep(0.5)

    def setUp(self):
        """
        Runs before EACH test — equivalent to test.beforeEach in Playwright.
        Creates a new session so each test gets its own cookie jar (fresh state).
        """
        # requests.Session ≈ Playwright's request fixture
        self.session = requests.Session()


# ===========================================================================
# PRODUCTS API TESTS   (test.describe('Products API'))
# ===========================================================================

class TestProductsAPI(TestBase):

    def test_get_all_products_returns_200_and_6_items(self):
        """
        JS: test('GET /api/products should return all products', ...)

        Steps:
          1. Send GET to /api/products
          2. Check response is 200 OK
          3. Check we get exactly 6 products back
        """
        r = self.session.get(f"{BASE_URL}/api/products")

        # .ok is True when status code is 2xx  ← same as response.ok() in Playwright
        self.assertTrue(r.ok)
        self.assertEqual(r.status_code, 200)

        data = r.json()                         # parses JSON body just like response.json()
        self.assertIsInstance(data, list)        # assertIsInstance is equivalent to expect(Array.isArray())
        self.assertEqual(len(data), 6)

    def test_filter_by_category(self):
        """JS: test('GET /api/products should filter by category', ...)"""
        r = self.session.get(f"{BASE_URL}/api/products", params={"category": "electronics"})
        # params={"category": "electronics"} adds ?category=electronics to the URL

        self.assertTrue(r.ok)
        data = r.json()

        self.assertGreater(len(data), 0)
        for product in data:
            self.assertEqual(product["category"], "electronics")

    def test_filter_by_search_term(self):
        """JS: test('GET /api/products should filter by search term', ...)"""
        r = self.session.get(f"{BASE_URL}/api/products", params={"search": "keyboard"})

        self.assertTrue(r.ok)
        data = r.json()

        self.assertEqual(len(data), 1)
        self.assertIn("keyboard", data[0]["name"].lower())

    def test_get_single_product(self):
        """JS: test('GET /api/products/:id should return single product', ...)"""
        r = self.session.get(f"{BASE_URL}/api/products/1")

        self.assertTrue(r.ok)
        data = r.json()

        self.assertEqual(data["id"], 1)
        self.assertIn("name", data)    # assertIn checks key exists just like toBeDefined()
        self.assertIn("price", data)

    def test_get_nonexistent_product_returns_404(self):
        """JS: test('GET /api/products/:id should return 404 for non-existent product', ...)"""
        r = self.session.get(f"{BASE_URL}/api/products/999")

        self.assertEqual(r.status_code, 404)

        data = r.json()
        self.assertEqual(data["error"], "Product not found")


# ===========================================================================
# CART API TESTS   (test.describe('Cart API'))
# ===========================================================================

class TestCartAPI(TestBase):

    def setUp(self):
        """
        Runs before each cart test.
        Clears the cart via DELETE /api/cart — same as the JS beforeEach block.
        """
        super().setUp()                               # call parent setUp
        self.session.delete(f"{BASE_URL}/api/cart")  # clear cart

    def test_empty_cart_initially(self):
        """JS: test('GET /api/cart should return empty cart initially', ...)"""
        r = self.session.get(f"{BASE_URL}/api/cart")

        self.assertTrue(r.ok)
        data = r.json()

        self.assertEqual(data["items"], [])
        self.assertEqual(data["total"], "0.00")

    def test_add_item_to_cart(self):
        """JS: test('POST /api/cart should add item to cart', ...)"""
        # json= sends the body as JSON just like data: { productId: 1, quantity: 2 }
        r = self.session.post(f"{BASE_URL}/api/cart", json={"productId": 1, "quantity": 2})

        self.assertTrue(r.ok)
        data = r.json()

        self.assertEqual(data["message"], "Added to cart")
        self.assertEqual(len(data["cart"]), 1)
        self.assertEqual(data["cart"][0]["productId"], 1)
        self.assertEqual(data["cart"][0]["quantity"], 2)

    def test_add_nonexistent_product_returns_404(self):
        """JS: test('POST /api/cart should return 404 for non-existent product', ...)"""
        r = self.session.post(f"{BASE_URL}/api/cart", json={"productId": 999, "quantity": 1})

        self.assertEqual(r.status_code, 404)
        data = r.json()
        self.assertEqual(data["error"], "Product not found")

    def test_update_cart_quantity(self):
        """JS: test('PUT /api/cart/:productId should update quantity', ...)"""
        # First add an item
        self.session.post(f"{BASE_URL}/api/cart", json={"productId": 1, "quantity": 1})

        # Then update it
        r = self.session.put(f"{BASE_URL}/api/cart/1", json={"quantity": 5})

        self.assertTrue(r.ok)
        data = r.json()
        self.assertEqual(data["cart"][0]["quantity"], 5)

    def test_delete_cart_item(self):
        """JS: test('DELETE /api/cart/:productId should remove item', ...)"""
        self.session.post(f"{BASE_URL}/api/cart", json={"productId": 1, "quantity": 1})

        r = self.session.delete(f"{BASE_URL}/api/cart/1")
        self.assertTrue(r.ok)

        # Verify cart is now empty
        cart_r = self.session.get(f"{BASE_URL}/api/cart")
        self.assertEqual(len(cart_r.json()["items"]), 0)

    def test_clear_entire_cart(self):
        """JS: test('DELETE /api/cart should clear entire cart', ...)"""
        self.session.post(f"{BASE_URL}/api/cart", json={"productId": 1, "quantity": 1})
        self.session.post(f"{BASE_URL}/api/cart", json={"productId": 2, "quantity": 1})

        r = self.session.delete(f"{BASE_URL}/api/cart")
        self.assertTrue(r.ok)

        cart_r = self.session.get(f"{BASE_URL}/api/cart")
        self.assertEqual(len(cart_r.json()["items"]), 0)


# ===========================================================================
# AUTH API TESTS   (test.describe('Auth API'))
# ===========================================================================

class TestAuthAPI(TestBase):

    def test_login_with_valid_credentials(self):
        """JS: test('POST /api/login should succeed with valid credentials', ...)"""
        r = self.session.post(
            f"{BASE_URL}/api/login",
            json={"email": "dasha@techshop.com", "password": "dasha123"},
        )

        self.assertTrue(r.ok)
        data = r.json()

        self.assertEqual(data["message"], "Login successful")
        self.assertEqual(data["user"]["email"], "dasha@techshop.com")

    def test_login_with_invalid_credentials(self):
        """JS: test('POST /api/login should fail with invalid credentials', ...)"""
        r = self.session.post(
            f"{BASE_URL}/api/login",
            json={"email": "wrong@email.com", "password": "wrongpassword"},
        )

        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["error"], "Invalid credentials")

    def test_login_requires_email_and_password(self):
        """JS: test('POST /api/login should require email and password', ...)"""
        r = self.session.post(f"{BASE_URL}/api/login", json={})

        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "Email and password required")

    def test_register_new_user(self):
        """JS: test('POST /api/register should create new user', ...)"""
        unique_email = f"test_{time.time():.0f}@example.com"  # like 'test${Date.now()}@example.com'

        r = self.session.post(
            f"{BASE_URL}/api/register",
            json={"name": "Test User", "email": unique_email, "password": "password123"},
        )

        self.assertEqual(r.status_code, 201)
        data = r.json()
        self.assertEqual(data["message"], "Registration successful")
        self.assertEqual(data["user"]["email"], unique_email)


# ===========================================================================
# HEALTH API TESTS   (test.describe('Health API'))
# ===========================================================================

class TestHealthAPI(TestBase):

    def test_health_returns_healthy(self):
        """JS: test('GET /api/health should return healthy status', ...)"""
        r = self.session.get(f"{BASE_URL}/api/health")

        self.assertTrue(r.ok)
        data = r.json()

        self.assertEqual(data["status"], "healthy")
        self.assertIn("timestamp", data)


# ---------------------------------------------------------------------------
# Run the tests
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # unittest.main() discovers and runs all TestCase subclasses
    # verbosity=2 prints each test name — similar to Playwright's test output
    unittest.main(verbosity=2)
