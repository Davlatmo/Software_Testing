import unittest
import copy
from techshop_testing import Server as server

class TestIntegrationUserJourneys(unittest.TestCase):
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

    def test_registered_user_full_purchase_flow(self):
        """
        Complete flow:
         - Register a new user
         - Add items to cart
         - Inspect cart (items + total)
         - Checkout with shipping
         - Verify stock reduced and cart emptied
        Verifies state consistency across auth, cart and checkout.
        """
        # Register a fresh user
        register_payload = {"email": "integ_user@example.com", "password": "secret123", "name": "Integ User"}
        resp = self.client.post("/api/register", json=register_payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertIn("user", data)
        user = data["user"]
        self.assertEqual(user["email"], register_payload["email"])

        # Add product id=3 (USB-C Hub, price 49.99) quantity 2
        add_resp = self.client.post("/api/cart", json={"productId": 3, "quantity": 2})
        self.assertEqual(add_resp.status_code, 200)
        add_data = add_resp.get_json()
        self.assertIn("cart", add_data)
        self.assertTrue(any(item["productId"] == 3 and item["quantity"] == 2 for item in add_data["cart"]))

        # Get cart and verify total
        cart_resp = self.client.get("/api/cart")
        self.assertEqual(cart_resp.status_code, 200)
        cart_data = cart_resp.get_json()
        self.assertEqual(len(cart_data["items"]), 1)
        # Total should be price * quantity
        expected_total = 49.99 * 2
        self.assertEqual(cart_data["total"], f"{expected_total:.2f}")

        # Checkout with shipping info
        shipping = {"address": "123 Test St", "city": "Testville", "zip": "12345"}
        checkout_resp = self.client.post("/api/checkout", json={"shipping": shipping})
        self.assertEqual(checkout_resp.status_code, 200)
        checkout_data = checkout_resp.get_json()
        self.assertIn("order", checkout_data)
        order = checkout_data["order"]
        self.assertEqual(order["shipping"], shipping)
        self.assertEqual(order["items"][0]["productId"], 3)

        # Verify that product stock decreased by 2
        product_after = next((p for p in server.PRODUCTS if p["id"] == 3), None)
        self.assertIsNotNone(product_after)
        # original stock:
        orig_product = next((p for p in self._original_products if p["id"] == 3), None)
        self.assertIsNotNone(orig_product)
        self.assertEqual(product_after["stock"], orig_product["stock"] - 2)

        # Cart should now be empty
        post_cart_resp = self.client.get("/api/cart")
        self.assertEqual(post_cart_resp.status_code, 200)
        post_cart_data = post_cart_resp.get_json()
        self.assertEqual(post_cart_data["items"], [])
        self.assertEqual(post_cart_data["total"], "0.00")

    def test_guest_cart_persists_through_login_and_allows_checkout(self):
        """
        Flow:
         - As a guest (no login), add item to cart
         - Confirm not logged in via /api/user
         - Login using existing user credentials while retaining session cookie
         - Ensure cart still contains the previously added item after login
         - Checkout successfully and verify cart cleared and user remains logged in
        This verifies session cookie behavior across auth boundaries.
        """
        # Add product id=6 (Mouse Pad XL, price 24.99) quantity 3 as guest
        add_resp = self.client.post("/api/cart", json={"productId": 6, "quantity": 3})
        self.assertEqual(add_resp.status_code, 200)
        add_data = add_resp.get_json()
        self.assertTrue(any(item["productId"] == 6 and item["quantity"] == 3 for item in add_data["cart"]))

        # GET /api/user should return 401 (not logged in)
        user_resp = self.client.get("/api/user")
        self.assertEqual(user_resp.status_code, 401)

        # Login with existing seeded user (from server.USERS)
        existing_user = self._original_users[0]
        login_payload = {"email": existing_user["email"], "password": existing_user["password"]}
        login_resp = self.client.post("/api/login", json=login_payload)
        self.assertEqual(login_resp.status_code, 200)
        login_data = login_resp.get_json()
        self.assertIn("user", login_data)
        self.assertEqual(login_data["user"]["email"], existing_user["email"])

        # After login, the cart should still contain the guest-added item (session persisted)
        cart_resp = self.client.get("/api/cart")
        self.assertEqual(cart_resp.status_code, 200)
        cart_data = cart_resp.get_json()
        self.assertTrue(any(item["productId"] == 6 and item["quantity"] == 3 for item in cart_data["items"]))
        expected_total = 24.99 * 3
        self.assertEqual(cart_data["total"], f"{expected_total:.2f}")

        # Checkout with shipping info should succeed
        shipping = {"address": "456 Buyer Rd", "city": "Buyertown", "zip": "67890"}
        checkout_resp = self.client.post("/api/checkout", json={"shipping": shipping})
        self.assertEqual(checkout_resp.status_code, 200)
        checkout_data = checkout_resp.get_json()
        self.assertIn("order", checkout_data)

        # After checkout, user endpoint should still show the logged-in user
        post_user_resp = self.client.get("/api/user")
        self.assertEqual(post_user_resp.status_code, 200)
        post_user_data = post_user_resp.get_json()
        self.assertEqual(post_user_data["email"], existing_user["email"])

        # Cart should be empty now
        post_cart_resp = self.client.get("/api/cart")
        self.assertEqual(post_cart_resp.status_code, 200)
        post_cart_data = post_cart_resp.get_json()
        self.assertEqual(post_cart_data["items"], [])
        self.assertEqual(post_cart_data["total"], "0.00")

    def test_update_cart_then_checkout_should_not_allow_exceeding_stock(self):
        """
        Integration scenario demonstrating a potential cross-component validation gap:
         - Add an item to cart (valid quantity)
         - Update the cart to a quantity exceeding current product stock
         - Attempt to checkout
        Expected correct behavior: checkout should fail with 400 and an error about insufficient stock.
        This verifies that stock validation is enforced at checkout time, preventing negative stock.
        (Note: If the implementation lacks this check, this test will fail and highlight the integration bug.)
        """
        # Choose a product to test with
        prod = next((p for p in server.PRODUCTS if p["id"] == 2), None)
        self.assertIsNotNone(prod)
        original_stock = prod["stock"]

        # Add the product with quantity 1 (should succeed)
        add_resp = self.client.post("/api/cart", json={"productId": 2, "quantity": 1})
        self.assertEqual(add_resp.status_code, 200)

        # Now update the cart to exceed stock (original_stock + 5)
        excessive_qty = original_stock + 5
        update_resp = self.client.put("/api/cart/2", json={"quantity": excessive_qty})
        # update_cart currently does not validate stock; it should still accept the update (200),
        # but the critical check should happen at checkout. We accept either 200 or 204 here for the update.
        self.assertIn(update_resp.status_code, (200, 201, 204))

        # Attempt checkout: the expected correct behavior is to reject due to insufficient stock.
        checkout_resp = self.client.post("/api/checkout", json={"shipping": {"address": "1 Infinity Loop", "city": "Nowhere", "zip": "00000"}})

        # Assert expected safe behavior: checkout should fail with 400 and appropriate error.
        # If the implementation does not perform this validation, this assertion will fail and surface the bug.
        self.assertEqual(checkout_resp.status_code, 400, "Checkout should reject orders that exceed available stock")

        body = checkout_resp.get_json() or {}
        self.assertIn("error", body)
        self.assertTrue("stock" in body["error"].lower() or "insufficient" in body["error"].lower())

if __name__ == "__main__":
    unittest.main()