"""
Browser Tests using Playwright 
=========================================================
"""
import unittest
import threading
import time
import sys
import os

from playwright.sync_api import sync_playwright, expect
_this_dir = os.path.dirname(os.path.abspath(__file__))
_app_dir  = os.path.normpath(os.path.join(_this_dir, "..", "app"))
for _p in [_this_dir, _app_dir]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from Server import app, PRODUCTS, SESSIONS, USERS

BASE_URL = "http://localhost:3002"   # Different port from API tests


def start_test_server():
    app.run(host="127.0.0.1", port=3002, debug=False, use_reloader=False)


class BrowserTestBase(unittest.TestCase):
    """
    Base class for all browser tests.
    - Starts Flask server once per class
    - Launches a browser once per class
    - Creates a fresh browser context (≈ new incognito window) per test
    """

    playwright = None
    browser    = None

    @classmethod
    def setUpClass(cls):
        # Start Flask server
        t = threading.Thread(target=start_test_server, daemon=True)
        t.start()
        time.sleep(0.8)

        # Launch Playwright and open a browser
        cls.playwright = sync_playwright().start()
        cls.browser    = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        """Cleanup after all tests in the class — equivalent to afterAll."""
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        """
        Before each test:
        - new_context() ≈ a fresh browser profile (own cookie jar, own localStorage)
        - new_page() ≈ opening a new browser tab
        """
        self.context = self.browser.new_context(base_url=BASE_URL)
        self.page    = self.context.new_page()

        # Clear cart via API before each test
        self.context.request.delete(f"{BASE_URL}/api/cart")

    def tearDown(self):
        """After each test — close the page and context."""
        self.context.close()


# ===========================================================================
# HOMEPAGE TESTS    
# ===========================================================================

class TestHomepage(BrowserTestBase):

    def setUp(self):
        super().setUp()
        self.page.goto("/")   # Navigate to the homepage before each test

    def test_page_title(self):
        """JS: test('should display the page title', ...)"""
        import re
       
        expect(self.page).to_have_title(re.compile("TechShop"))

    def test_logo_visible(self):
        """JS: test('should display the logo in the navbar', ...)"""
        import re
        logo = self.page.locator(".logo")
        expect(logo).to_be_visible()
        expect(logo).to_have_text(re.compile("TechShop"))

    def test_hero_section(self):
        """JS: test('should display the hero section', ...)"""
        expect(self.page.locator(".hero h1")).to_have_text("Forge Your Setup")
        expect(self.page.locator(".hero p")).to_contain_text("finest tech gear, forged for you")

    def test_product_cards_displayed(self):
        """JS: test('should display product cards', ...)"""
        product_grid = self.page.locator("#productGrid")
        expect(product_grid).to_be_visible()

        cards = self.page.locator(".product-card")
        expect(cards).to_have_count(6)

    def test_product_information(self):
        """JS: test('should display product information correctly', ...)"""
        first = self.page.locator(".product-card").first

        expect(first.locator(".product-info h3")).to_be_visible()
        expect(first.locator(".product-price")).to_be_visible()
        expect(first.locator(".product-stock")).to_be_visible()
        expect(first.locator(".add-to-cart-btn")).to_be_visible()

    def test_search_bar_works(self):
        """JS: test('should have a working search bar', ...)"""
        search_input = self.page.locator("#searchInput")
        search_btn   = self.page.locator("#searchBtn")

        expect(search_input).to_be_visible()
        expect(search_btn).to_be_visible()

        search_input.fill("Keyboard")
        search_btn.click()
        self.page.wait_for_timeout(500)

        # Only the keyboard product should remain
        expect(self.page.locator(".product-card")).to_have_count(1)

    def test_category_filter(self):
        """JS: test('should filter products by category', ...)"""
        self.page.locator("#categoryFilter").select_option("electronics")
        self.page.wait_for_timeout(500)

        count = self.page.locator(".product-card").count()
        self.assertGreater(count, 0)
        self.assertLess(count, 6)

    def test_cart_count_in_navbar(self):
        """JS: test('should display cart count in navbar', ...)"""
        cart_count = self.page.locator("#cartCount")
        expect(cart_count).to_be_visible()
        expect(cart_count).to_have_text("0")

    def test_login_signup_buttons(self):
        """JS: test('should have login and signup buttons', ...)"""
        auth_area = self.page.locator("#authArea")
        expect(auth_area.get_by_text("Login")).to_be_visible()
        expect(auth_area.get_by_text("Sign Up")).to_be_visible()


# ===========================================================================
# AUTHENTICATION TESTS    
# ===========================================================================

class TestAuthLogin(BrowserTestBase):

    def setUp(self):
        super().setUp()
        self.page.goto("/login.html")

    def test_login_form_visible(self):
        """JS: test('should display login form', ...)"""
        expect(self.page.locator("h1")).to_have_text("Welcome back")
        expect(self.page.locator("#email")).to_be_visible()
        expect(self.page.locator("#password")).to_be_visible()
        expect(self.page.locator('button[type="submit"]')).to_be_visible()

    def test_invalid_credentials_shows_error(self):
        """JS: test('should show error for invalid credentials', ...)"""
        self.page.locator("#email").fill("wrong@email.com")
        self.page.locator("#password").fill("wrongpassword")
        self.page.locator('button[type="submit"]').click()

        error_msg = self.page.locator("#errorMessage")
        expect(error_msg).to_be_visible()
        expect(error_msg).to_contain_text("Invalid credentials")

    def test_valid_login_redirects_home(self):
        """JS: test('should login successfully with valid credentials', ...)"""
        self.page.locator("#email").fill("demo@techshop.io")
        self.page.locator("#password").fill("demo123")
        self.page.locator('button[type="submit"]').click()

        toast = self.page.locator("#toast")
        expect(toast).to_contain_text("Login successful")

        # wait_for_url waits until the URL matches — like await page.waitForURL('/')
        self.page.wait_for_url("/")

    def test_empty_form_fails_html_validation(self):
        """JS: test('should show validation for empty fields', ...)"""
        self.page.locator('button[type="submit"]').click()

        # .evaluate() runs JavaScript in the browser — same as in JS
        email_input = self.page.locator("#email")
        is_invalid  = email_input.evaluate("el => !el.checkValidity()")
        self.assertTrue(is_invalid)

    def test_signup_link_navigates(self):
        """JS: test('should have link to registration page', ...)"""
        self.page.get_by_text("Sign up here").click()
        expect(self.page).to_have_url(f"{BASE_URL}/register.html")

    def test_demo_credentials_displayed(self):
        """JS: test('should display demo credentials', ...)"""
        demo_section = self.page.locator(".demo-credentials")
        expect(demo_section).to_be_visible()
        expect(demo_section).to_contain_text("demo@techshop.io")
        expect(demo_section).to_contain_text("demo123")


class TestAuthRegistration(BrowserTestBase):

    def setUp(self):
        super().setUp()
        self.page.goto("/register.html")

    def test_registration_form_visible(self):
        """JS: test('should display registration form', ...)"""
        expect(self.page.locator("h1")).to_have_text("Create Your Account")
        expect(self.page.locator("#name")).to_be_visible()
        expect(self.page.locator("#email")).to_be_visible()
        expect(self.page.locator("#password")).to_be_visible()
        expect(self.page.locator("#confirmPassword")).to_be_visible()

    def test_mismatched_passwords_shows_error(self):
        """JS: test('should show error for mismatched passwords', ...)"""
        self.page.locator("#name").fill("Test User")
        self.page.locator("#email").fill("test@example.com")
        self.page.locator("#password").fill("password123")
        self.page.locator("#confirmPassword").fill("different123")
        self.page.locator('button[type="submit"]').click()

        error_msg = self.page.locator("#errorMessage")
        expect(error_msg).to_be_visible()
        expect(error_msg).to_contain_text("Passwords do not match")

    def test_successful_registration_redirects_home(self):
        """JS: test('should register new user successfully', ...)"""
        unique_email = f"test_{int(time.time())}@example.com"

        self.page.locator("#name").fill("New User")
        self.page.locator("#email").fill(unique_email)
        self.page.locator("#password").fill("password123")
        self.page.locator("#confirmPassword").fill("password123")
        self.page.locator('button[type="submit"]').click()

        expect(self.page.locator("#toast")).to_contain_text("Account created")
        self.page.wait_for_url("/")

    def test_login_link_navigates(self):
        """JS: test('should have link to login page', ...)"""
        self.page.get_by_text("Login here").click()
        expect(self.page).to_have_url(f"{BASE_URL}/login.html")


class TestAuthLogout(BrowserTestBase):

    def test_logout_success(self):
        """JS: test('should logout successfully', ...)"""
        # Login first
        self.page.goto("/login.html")
        self.page.locator("#email").fill("demo@techshop.io")
        self.page.locator("#password").fill("demo123")
        self.page.locator('button[type="submit"]').click()
        self.page.wait_for_url("/")
        self.page.wait_for_timeout(500)

        # Check logged-in state
        expect(self.page.locator("#authArea")).to_contain_text("Hi, Demo User")

        # Logout
        self.page.locator("#logoutBtn").click()

        # Check logged-out state
        expect(self.page.locator("#authArea")).to_contain_text("Login")


# ===========================================================================
# SHOPPING CART TESTS   
# ===========================================================================

class TestShoppingCart(BrowserTestBase):

    def setUp(self):
        """Clear cart and go to homepage before each test."""
        super().setUp()
        self.page.goto("/")

    def test_add_item_to_cart(self):
        """JS: test('should add item to cart', ...)"""
        self.page.locator(".add-to-cart-btn").first.click()

        expect(self.page.locator("#toast")).to_contain_text("Added to cart")
        expect(self.page.locator("#cartCount").first).to_have_text("1")

    def test_navigate_to_cart_page(self):
        """JS: test('should navigate to cart page', ...)"""
        self.page.locator(".add-to-cart-btn").first.click()
        self.page.wait_for_timeout(500)

        self.page.locator(".cart-link").first.click()

        expect(self.page).to_have_url(f"{BASE_URL}/cart.html")
        expect(self.page.locator("h1")).to_have_text("Your Shopping Cart")

    def test_display_cart_items(self):
        """JS: test('should display cart items correctly', ...)"""
        self.context.request.post(
            f"{BASE_URL}/api/cart",
            data={"productId": 1, "quantity": 2},
        )

        self.page.goto("/cart.html")

        expect(self.page.locator(".cart-item")).to_have_count(1)
        expect(self.page.locator(".qty-value")).to_have_text("2")

    def test_update_item_quantity(self):
        """JS: test('should update item quantity', ...)"""
        self.context.request.post(
            f"{BASE_URL}/api/cart", data={"productId": 1, "quantity": 1}
        )
        self.page.goto("/cart.html")

        # Second qty-btn is the "+" button
        self.page.locator(".qty-btn").nth(1).click()
        self.page.wait_for_timeout(500)

        expect(self.page.locator(".qty-value")).to_have_text("2")

    def test_remove_item_from_cart(self):
        """JS: test('should remove item from cart', ...)"""
        self.context.request.post(
            f"{BASE_URL}/api/cart", data={"productId": 1, "quantity": 1}
        )
        self.page.goto("/cart.html")

        self.page.locator(".remove-btn").click()
        self.page.wait_for_timeout(500)

        expect(self.page.locator("#emptyCart")).to_be_visible()

    def test_clear_entire_cart(self):
        """JS: test('should clear entire cart', ...)"""
        self.context.request.post(f"{BASE_URL}/api/cart", data={"productId": 1, "quantity": 1})
        self.context.request.post(f"{BASE_URL}/api/cart", data={"productId": 2, "quantity": 1})

        self.page.goto("/cart.html")
        self.page.locator("#clearCartBtn").click()
        self.page.wait_for_timeout(500)

        expect(self.page.locator("#emptyCart")).to_be_visible()

    def test_correct_totals(self):
        """JS: test('should calculate correct totals', ...)"""
        # 2 × $79.99 = $159.98
        self.context.request.post(f"{BASE_URL}/api/cart", data={"productId": 1, "quantity": 2})
        self.page.goto("/cart.html")

        expect(self.page.locator("#total")).to_contain_text("159.98")

    def test_empty_cart_message(self):
        """JS: test('should show empty cart message when cart is empty', ...)"""
        self.page.goto("/cart.html")

        empty_cart = self.page.locator("#emptyCart")
        expect(empty_cart).to_be_visible()
        expect(empty_cart).to_contain_text("Your cart is empty")
        expect(empty_cart.get_by_text("Start Shopping")).to_be_visible()


# ===========================================================================
# CHECKOUT TESTS    
# ===========================================================================

class TestCheckout(BrowserTestBase):

    def setUp(self):
        """Clear cart, add one product, then each test runs."""
        super().setUp()
        self.context.request.delete(f"{BASE_URL}/api/cart")
        self.context.request.post(f"{BASE_URL}/api/cart", data={"productId": 1, "quantity": 1})

    def _fill_shipping(self):
        """Helper to fill in the shipping form — used by multiple tests."""
        self.page.locator("#firstName").fill("John")
        self.page.locator("#lastName").fill("Doe")
        self.page.locator("#address").fill("123 Main Street")
        self.page.locator("#city").fill("Grand Rapids")
        self.page.locator("#state").select_option("MI")
        self.page.locator("#zip").fill("49501")
        self.page.locator("#phone").fill("555-123-4567")

    def _fill_payment(self):
        """Helper to fill in the payment form."""
        self.page.locator("#cardName").fill("John Doe")
        self.page.locator("#cardNumber").fill("4111111111111111")
        self.page.locator("#expiry").fill("12/25")
        self.page.locator("#cvv").fill("123")

    def test_redirect_if_cart_empty(self):
        """JS: test('should redirect to cart if cart is empty', ...)"""
        self.context.request.delete(f"{BASE_URL}/api/cart")
        self.page.goto("/checkout.html")
        self.page.wait_for_url(f"{BASE_URL}/cart.html", timeout=5000)

    def test_checkout_form_visible(self):
        """JS: test('should display checkout form', ...)"""
        self.page.goto("/checkout.html")

        for field in ["#firstName", "#lastName", "#address", "#city",
                      "#state", "#zip", "#phone", "#cardName",
                      "#cardNumber", "#expiry", "#cvv"]:
            expect(self.page.locator(field)).to_be_visible()

    def test_order_summary_visible(self):
        """JS: test('should display order summary', ...)"""
        self.page.goto("/checkout.html")

        order_summary = self.page.locator(".order-summary-sidebar")
        expect(order_summary).to_be_visible()
        expect(order_summary.locator(".order-item")).to_have_count(1)
        expect(self.page.locator("#subtotal")).to_be_visible()
        expect(self.page.locator("#tax")).to_be_visible()
        expect(self.page.locator("#total")).to_be_visible()

    def test_tax_calculation(self):
        """JS: test('should calculate tax correctly', ...)  — $79.99 × 8% = $6.40"""
        self.page.goto("/checkout.html")
        expect(self.page.locator("#tax")).to_contain_text("6.40")

    def test_card_number_formatting(self):
        """JS: test('should format card number with spaces', ...)"""
        self.page.goto("/checkout.html")

        card_number = self.page.locator("#cardNumber")
        card_number.fill("1234567890123456")

        expect(card_number).to_have_value("1234 5678 9012 3456")

    def test_expiry_formatting(self):
        """JS: test('should format expiry date correctly', ...)"""
        self.page.goto("/checkout.html")

        expiry = self.page.locator("#expiry")
        expiry.fill("1225")
        expect(expiry).to_have_value("12/25")

    def test_complete_checkout(self):
        """JS: test('should complete checkout successfully', ...)"""
        self.page.goto("/checkout.html")
        self._fill_shipping()
        self._fill_payment()

        self.page.locator("#placeOrderBtn").click()

        confirmation_modal = self.page.locator("#orderConfirmation")
        expect(confirmation_modal).to_be_visible()
        expect(confirmation_modal).to_contain_text("Order Confirmed")
        expect(self.page.locator("#orderId")).not_to_be_empty()

    def test_required_fields_validation(self):
        """JS: test('should validate required fields', ...)"""
        self.page.goto("/checkout.html")
        self.page.locator("#placeOrderBtn").click()

        is_invalid = self.page.locator("#firstName").evaluate("el => !el.checkValidity()")
        self.assertTrue(is_invalid)

    def test_zip_code_validation(self):
        """JS: test('should validate ZIP code format', ...)"""
        self.page.goto("/checkout.html")
        self._fill_shipping()
        self.page.locator("#zip").fill("abc")   # invalid ZIP
        self.page.locator("#placeOrderBtn").click()

        is_invalid = self.page.locator("#zip").evaluate("el => !el.checkValidity()")
        self.assertTrue(is_invalid)


# ===========================================================================
# EDGE CASES TESTS    
# ===========================================================================

class TestEdgeCases(BrowserTestBase):

    def setUp(self):
        super().setUp()
        self.page.goto("/")

    def test_empty_search_shows_all_products(self):
        """JS: test('should handle empty search gracefully', ...)"""
        self.page.locator("#searchBtn").click()
        self.page.wait_for_timeout(500)

        expect(self.page.locator(".product-card")).to_have_count(6)

    def test_no_results_for_nonsense_search(self):
        """JS: test('should show no results for nonsense search', ...)"""
        self.page.locator("#searchInput").fill("xyznonexistent123")
        self.page.locator("#searchBtn").click()
        self.page.wait_for_timeout(500)

        expect(self.page.locator(".product-card")).to_have_count(0)

    def test_special_characters_in_search(self):
        """JS: test('should handle special characters in search', ...)"""
        self.page.locator("#searchInput").fill('<script>alert("xss")</script>')
        self.page.locator("#searchBtn").click()
        self.page.wait_for_timeout(500)

        expect(self.page.locator(".product-card")).to_have_count(0)
        expect(self.page.locator(".logo")).to_be_visible()    # page didn't crash

    def test_whitespace_search(self):
        """JS: test('should handle search with only whitespace', ...)"""
        self.page.locator("#searchInput").fill("   ")
        self.page.locator("#searchBtn").click()
        self.page.wait_for_timeout(500)

        count = self.page.locator(".product-card").count()
        self.assertGreaterEqual(count, 0)
        expect(self.page.locator(".logo")).to_be_visible()

    def test_add_same_product_multiple_times(self):
        """JS: test('should handle adding same product multiple times', ...)"""
        add_btn = self.page.locator(".add-to-cart-btn").first

        for _ in range(3):
            add_btn.click()
            self.page.wait_for_timeout(300)

        expect(self.page.locator("#cartCount").first).to_have_text("3")

    def test_cannot_checkout_with_empty_cart(self):
        """JS: test('should not allow checkout with empty cart', ...)"""
        self.page.goto("/checkout.html")
        self.page.wait_for_url(f"{BASE_URL}/cart.html", timeout=5000)
        expect(self.page.locator(".logo")).to_be_visible()

    def test_require_all_registration_fields(self):
        """JS: test('should require all fields for registration', ...)"""
        self.page.goto("/register.html")
        self.page.locator("#email").fill("test@example.com")
        self.page.locator('button[type="submit"]').click()
        self.page.wait_for_timeout(300)

        current_url = self.page.url
        self.assertIn("register", current_url)

    def test_reject_duplicate_email(self):
        """JS: test('should reject duplicate email registration', ...)"""
        self.page.goto("/register.html")
        self.page.locator("#name").fill("Another User")
        self.page.locator("#email").fill("demo@techshop.io")  # already registered
        self.page.locator("#password").fill("password123")
        self.page.locator("#confirmPassword").fill("password123")
        self.page.locator('button[type="submit"]').click()
        self.page.wait_for_timeout(500)

        import re
        error_msg = self.page.locator("#errorMessage")
        expect(error_msg).to_be_visible()
        expect(error_msg).to_contain_text(re.compile("already registered|exists", re.IGNORECASE))

    def test_direct_url_access_to_cart(self):
        """JS: test('should handle direct URL access to cart page', ...)"""
        self.page.goto("/cart.html")
        expect(self.page.locator(".logo")).to_be_visible()

    def test_cart_preserved_across_navigation(self):
        """JS: test('should preserve cart across page navigation', ...)"""
        self.page.locator(".add-to-cart-btn").first.click()
        self.page.wait_for_timeout(500)

        self.page.goto("/login.html")
        self.page.goto("/")

        expect(self.page.locator("#cartCount").first).to_have_text("1")


# ===========================================================================
# MOCKING TESTS    
# ===========================================================================

class TestMocking(BrowserTestBase):
    """
    page.route() intercepts network requests in the browser.

    JS:  await page.route('**/api/products*', route => route.fulfill({ status: 500 }))
    Py:  self.page.route('**/api/products*', lambda route: route.fulfill(status=500))

    Python uses lambda (anonymous function) where JS uses arrow function (=>).
    """

    def test_error_state_when_api_fails(self):
        """JS: test('should display error state when API fails', ...)"""
        self.page.route(
            "**/api/products*",
            lambda route: route.fulfill(
                status=500,
                content_type="application/json",
                body='{"error": "Internal server error"}',
            ),
        )

        self.page.goto("/")
        expect(self.page.locator(".product-card")).to_have_count(0)

    def test_slow_api_response_graceful(self):
        """JS: test('should handle slow API responses gracefully', ...)"""
        def slow_handler(route):
            time.sleep(3)
            route.continue_()

        self.page.route("**/api/products*", slow_handler)
        self.page.goto("/")

        expect(self.page.locator(".logo")).to_be_visible()
        expect(self.page.locator("#searchInput")).to_be_visible()
        expect(self.page.locator(".product-card")).to_have_count(6, timeout=15_000)

    def test_out_of_stock_display(self):
        """JS: test('should display out-of-stock correctly', ...)"""
        import json

        mock_products = [
            {"id": 1, "name": "Wireless Headphones", "price": 79.99,
             "category": "electronics", "image": "headphones.svg", "stock": 0},
            {"id": 2, "name": "Mechanical Keyboard", "price": 129.99,
             "category": "electronics", "image": "keyboard.svg", "stock": 8},
        ]

        self.page.route(
            "**/api/products*",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(mock_products),
            ),
        )

        self.page.goto("/")
        expect(self.page.locator(".product-card")).to_have_count(2)

        headphones_card = self.page.locator(".product-card[data-product-id='1']")
        stock_text = headphones_card.locator(".product-stock").text_content() or ""
        self.assertTrue(
            "0" in stock_text or "out" in stock_text.lower() or "Out of Stock" in
            headphones_card.locator(".add-to-cart-btn").text_content(),
            f"Expected out-of-stock indicator, got stock='{stock_text}'"
        )

    def test_add_to_cart_failure_handled(self):
        """JS: test('should handle add-to-cart failure', ...)"""
        self.page.goto("/")

        def cart_handler(route):
            if route.request.method == "POST":
                route.fulfill(
                    status=400,
                    content_type="application/json",
                    body='{"error": "Insufficient stock"}',
                )
            else:
                route.continue_()

        self.page.route("**/api/cart", cart_handler)
        self.page.locator(".add-to-cart-btn").first.click()

        expect(self.page.locator("#toast")).to_be_visible()

    def test_network_timeout_handled(self):
        """JS: test('should handle network timeout', ...)"""
        self.page.route(
            "**/api/products*",
            lambda route: route.abort("timedout"),
        )

        self.page.goto("/")

        expect(self.page.locator(".logo")).to_be_visible()
        expect(self.page.locator(".product-card")).to_have_count(0)


# ---------------------------------------------------------------------------
# Run all browser tests
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    unittest.main(verbosity=2)
