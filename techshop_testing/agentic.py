"""
Agentic Testing 
-------------------------
WHAT IS AGENTIC TESTING?
-------------------------
Traditional testing requires hardcoded steps:
    page.locator("#email").fill("demo@techshop.io")
    page.locator('button[type="submit"]').click()

Agentic testing gives plain English to an AI agent which decides HOW
to perform the steps, just like a human tester would:
    "Log in with demo@techshop.io / demo123 and verify success"

------------------------
HOW OUR AGENTIC AI WORKS
------------------------
1. Flask server starts once for all tests
2. For each scenario: take screenshot → ask Claude → execute action → repeat
3. Claude reads the page visually and responds with the next action
4. Loop until Claude says PASS or FAIL

"""

import unittest
import threading
import time
import sys
import os
import base64
import json

from openai import OpenAI
from playwright.sync_api import sync_playwright

_this_dir = os.path.dirname(os.path.abspath(__file__))
_app_dir  = os.path.normpath(os.path.join(_this_dir, "..", "app"))
for _p in [_this_dir, _app_dir]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from Server import app

BASE_URL = "http://localhost:3003"

# ---------------------------------------------------------------------------
# Azure OpenAI configuration
# ---------------------------------------------------------------------------

AZURE_ENDPOINT   = "https://gaeta-mj8ipx75-swedencentral.services.ai.azure.com/openai/v1"
AZURE_DEPLOYMENT = "gpt-4.1"
AZURE_API_KEY    = "Ek1fK3UKcU6RHLC1P73IctVlEFi5K4GKkZgtPcAyeUcRPBH2Q0fRJQQJ99BLACfhMk5XJ3w3AAAAACOGVr8d"

# Creating the OpenAI client pointed at our Azure endpoint
azure_client = OpenAI(
    base_url=AZURE_ENDPOINT,
    api_key=AZURE_API_KEY,
)

MAX_STEPS = 10

# ---------------------------------------------------------------------------
# Module-level server that is started ONCE and shared by all test classes
# ---------------------------------------------------------------------------
_server_started = False

def _ensure_server():
    global _server_started
    if not _server_started:
        t = threading.Thread(
            target=lambda: app.run(
                host="127.0.0.1", port=3003,
                debug=False, use_reloader=False
            ),
            daemon=True,
        )
        t.start()
        time.sleep(1.0)
        _server_started = True

# ---------------------------------------------------------------------------
# Module-level browser that is started ONCE, shared by all test classes
# ---------------------------------------------------------------------------
_pw  = None
_browser = None

def _ensure_browser():
    global _pw, _browser
    if _pw is None:
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(
            headless=False,
            args=["--window-size=1280,800"],
        )

# ---------------------------------------------------------------------------
# Agent helpers
# ---------------------------------------------------------------------------

def take_screenshot(page) -> str:
    """Captures current page as base64 PNG — Claude 'sees' this."""
    return base64.standard_b64encode(page.screenshot()).decode("utf-8")


def ask_claude(scenario: str, history: list, screenshot_b64: str) -> dict:
    """
    Sends screenshot + history to Azure OpenAI (gpt-4.1), gets back the
    next action as JSON.

    Azure OpenAI uses the OpenAI message format:
      - Images go inside a "content" list as { "type": "image_url", ... }
      - The system prompt goes as the first message with role "system"
      - The API endpoint includes the deployment name in the URL

    Responds with one of:
      { "action": "navigate",  "target": "/path" }
      { "action": "click",     "target": "CSS selector or text" }
      { "action": "fill",      "target": "#id", "value": "text" }
      { "action": "select",    "target": "#id", "value": "option" }
      { "action": "wait",      "ms": 500 }
      { "action": "assert",    "target": "#id or page", "value": "expected text" }
      { "action": "pass",      "reason": "..." }
      { "action": "fail",      "reason": "..." }
    """
    system_prompt = (
        "You are a web testing agent for TechShop, an e-commerce site.\n"
        "You receive a screenshot of the current browser page and must decide the next action.\n\n"
        "Respond ONLY with a single JSON object — no markdown, no explanation.\n\n"
        "Available actions:\n"
        '  { "action": "navigate",  "target": "/path" }\n'
        '  { "action": "click",     "target": "CSS_SELECTOR or visible text" }\n'
        '  { "action": "fill",      "target": "CSS_SELECTOR", "value": "text" }\n'
        '  { "action": "select",    "target": "CSS_SELECTOR", "value": "option value" }\n'
        '  { "action": "wait",      "ms": 500 }\n'
        '  { "action": "assert",    "target": "CSS_SELECTOR or page", "value": "expected text" }\n'
        '  { "action": "pass",      "reason": "why it passed" }\n'
        '  { "action": "fail",      "reason": "why it failed" }\n\n'
        "Rules:\n"
        "- Prefer CSS selectors (#id, .class) when visible.\n"
        "- Use visible text in 'click' target if no selector is obvious.\n"
        "- After submitting a form always 'wait' before asserting.\n"
        "- Only output 'pass' or 'fail' when you are certain.\n"
        f"- Base URL: {BASE_URL}\n"
        "- Demo login: demo@techshop.io / demo123"
    )

    messages = [{"role": "system", "content": system_prompt}]

    
    for h in history:
        messages.append(h)

   
    messages.append({
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{screenshot_b64}",
                    "detail": "high",   # high = full resolution analysis
                },
            },
            {
                "type": "text",
                "text": f"Scenario: {scenario}\n\nWhat is the next action?",
            },
        ],
    })

    # Calling Azure via the openai Python client 
    # The client handles auth, headers and endpoint routing automatically.
    completion = azure_client.chat.completions.create(
        model=AZURE_DEPLOYMENT, 
        max_tokens=256,
        messages=messages,
    )

    raw = completion.choices[0].message.content.strip()

   
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        action = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Model returned non-JSON:\n{raw[:300]}"
        ) from e

    # Save assistant reply to history
    history.append({"role": "assistant", "content": raw})
    return action



def execute_action(page, action: dict) -> str:
    """Runs Claude's chosen action in the browser via Playwright."""
    act = action.get("action")
    tgt = action.get("target", "")
    val = action.get("value", "")

    if act == "navigate":
        url = tgt if tgt.startswith("http") else f"{BASE_URL}{tgt}"
        page.goto(url)
        return f"Navigated to {tgt}"

    elif act == "click":
        try:
            page.locator(tgt).first.click(timeout=5000)
        except Exception:
            page.get_by_text(tgt, exact=False).first.click(timeout=5000)
        return f"Clicked '{tgt}'"

    elif act == "fill":
        page.locator(tgt).first.fill(val)
        return f"Filled '{tgt}' with '{val}'"

    elif act == "select":
        page.locator(tgt).select_option(val)
        return f"Selected '{val}' in '{tgt}'"

    elif act == "wait":
        ms = int(action.get("ms", 500))
        page.wait_for_timeout(ms)
        return f"Waited {ms}ms"

    elif act == "assert":
        if tgt in ("page", "title"):
            content = page.title()
        else:
            try:
                content = page.locator(tgt).first.text_content(timeout=5000) or ""
            except Exception:
                content = page.inner_text("body")
        assert val.lower() in content.lower(), \
            f"Expected '{val}' inside '{content[:100]}'"
        return f"Asserted '{val}' in '{tgt}' ✓"

    elif act in ("pass", "fail"):
        return f"Agent verdict: {act.upper()} — {action.get('reason', '')}"

    return f"Unknown action: {act}"


def run_scenario(page, scenario_name: str, instructions: str):
    """
    Main agent loop:
      screenshot → ask Claude → execute → repeat until pass/fail or MAX_STEPS
    Returns (passed: bool, steps_log: list[str])
    """
    history = []
    steps   = []
    full    = f"{scenario_name}\n\n{instructions}"

    for step_num in range(1, MAX_STEPS + 1):
        screenshot = take_screenshot(page)
        try:
            action = ask_claude(full, history, screenshot)
        except Exception as e:
            # API call itself failed — print full error and stop immediately
            steps.append(f"API ERROR: {e}")
            print(f"\n{'!'*60}")
            print(f"API ERROR in step {step_num}:")
            print(str(e))
            print('!'*60)
            return False, steps
        act = action.get("action")

        entry = f"Step {step_num}: [{act.upper()}] " + json.dumps(
            {k: v for k, v in action.items() if k != "action"}
        )
        steps.append(entry)

        if act == "pass":
            steps.append(f"PASSED: {action.get('reason', '')}")
            return True, steps

        if act == "fail":
            steps.append(f"FAILED: {action.get('reason', '')}")
            return False, steps

        try:
            result = execute_action(page, action)
            steps.append(f"       → {result}")
        except AssertionError as e:
            steps.append(f"       → Assertion failed: {e}")
            history.append({"role": "user", "content": f"Assertion failed: {e}"})
        except Exception as e:
            steps.append(f"       → Error: {e}")

    steps.append(f"FAILED: Exceeded {MAX_STEPS} steps without verdict")
    return False, steps


# ---------------------------------------------------------------------------
# Base test class
# ---------------------------------------------------------------------------

class AgenticTestBase(unittest.TestCase):
    """
    All agentic test classes inherit from this.

    KEY FIX: server and browser are started at module level (_ensure_server /
    _ensure_browser) so they are created ONCE no matter how many subclasses
    exist. The old pattern (setUpClass per subclass) caused:
      - "Address already in use" on port 3003 for every class after the first
      - Playwright crash in Python 3.14 on Windows when stopping per-class
    """

    @classmethod
    def setUpClass(cls):
        _ensure_server()
        _ensure_browser()


    def setUp(self):
        """Fresh browser context (= clean cookies) before every test."""
        self.context = _browser.new_context(
            base_url=BASE_URL,
            viewport={"width": 1280, "height": 800},
        )
        self.page = self.context.new_page()
        # Clear cart state before each test
        self.context.request.delete(f"{BASE_URL}/api/cart")

    def tearDown(self):
        """Close the context (not the whole browser) after every test."""
        self.context.close()

    def run_agentic_scenario(self, name: str, instructions: str):
        """Runs the scenario and asserts it passed."""
        print(f"\n{'='*60}")
        print(f"AGENTIC SCENARIO: {name}")
        print(f"{'='*60}")

        passed, steps = run_scenario(self.page, name, instructions)

        for step in steps:
            print(step)

        self.assertTrue(
            passed,
            f"Scenario '{name}' FAILED\n" + "\n".join(steps),
        )


# ===========================================================================
# OUR TEST SCENARIOS  
# ===========================================================================

class TestAgenticHomepage(AgenticTestBase):
    """Scenario 1 — Homepage Verification"""

    def test_homepage_loads_correctly(self):
        self.page.goto("/")
        self.run_agentic_scenario(
            name="Homepage Verification",
            instructions="""
            You are on the TechShop homepage.
            1. Assert the page title contains "TechShop"
            2. Assert the hero heading "Forge Your Setup" is visible
            3. Assert the logo "TechShop" is in the header
            4. Assert 6 product cards are visible in the product grid
            5. Assert at least one "Add to Cart" button is visible
            If all 5 checks pass → PASS. Otherwise → FAIL.
            """,
        )


class TestAgenticSearch(AgenticTestBase):
    """Scenario 2 — Product Search"""

    def test_search_for_products(self):
        self.page.goto("/")
        self.run_agentic_scenario(
            name="Product Search",
            instructions="""
            You are on the TechShop homepage showing 6 products.
            1. Find the search input and type "Keyboard"
            2. Click the search button
            3. Wait 1 second
            4. Assert only 1 product card is displayed
            5. Assert "Mechanical Keyboard" is visible
            If all checks pass → PASS. Otherwise → FAIL.
            """,
        )


class TestAgenticCart(AgenticTestBase):
    """Scenario 4: Add Item to Cart"""

    def test_add_product_to_cart(self):
        self.page.goto("/")
        self.run_agentic_scenario(
            name="Add Product to Shopping Cart",
            instructions="""
            You are on the TechShop homepage.
            1. Click the "Add to Cart" button on the first product card
            2. Wait 1 second
            3. Assert a toast notification containing "Added to cart" appeared
            4. Assert the cart count badge in the navbar now shows "1"
            If all checks pass → PASS. Otherwise → FAIL.
            """,
        )


class TestAgenticAuth(AgenticTestBase):
    """Scenario 7: Login with Valid Credentials"""

    def test_login_with_demo_account(self):
        self.page.goto("/login.html")
        self.run_agentic_scenario(
            name="Login with Demo Account",
            instructions="""
            You are on the TechShop login page.
            1. Enter "demo@techshop.io" in the email field (#email)
            2. Enter "demo123" in the password field (#password)
            3. Click the Login / submit button
            4. Wait 2 seconds
            5. Assert a success toast message appeared
            6. Assert "Hi, Demo User" is visible in the navigation
            If all checks pass → PASS. Otherwise → FAIL.
            """,
        )


class TestAgenticAuthFail(AgenticTestBase):
    """Scenario 8: Login Fails with Wrong Password"""

    def test_login_fails_with_wrong_password(self):
        self.page.goto("/login.html")
        self.run_agentic_scenario(
            name="Login Fails with Wrong Password",
            instructions="""
            You are on the TechShop login page.
            1. Enter "wrong@email.com" in the email field (#email)
            2. Enter "wrongpassword" in the password field (#password)
            3. Click the Login / submit button
            4. Wait 1 second
            5. Assert an error message containing "Invalid credentials" is visible
            6. Assert we are still on the login page (URL contains "login")
            If all checks pass → PASS. Otherwise → FAIL.
            """,
        )


class TestAgenticLogout(AgenticTestBase):
    """Scenario 13: Logout After Login"""

    def test_logout_after_login(self):
        self.page.goto("/login.html")
        self.run_agentic_scenario(
            name="Logout After Login",
            instructions="""
            You are on the TechShop login page.
            1. Enter "demo@techshop.io" in the email field
            2. Enter "demo123" in the password field
            3. Click the Login button
            4. Wait 2 seconds for redirect to homepage
            5. Assert "Hi, Demo User" is visible in the nav
            6. Click the Logout button
            7. Wait 1 second
            8. Assert the "Login" link is visible again
            9. Assert "Hi, Demo User" is no longer on the page
            If all checks pass → PASS. Otherwise → FAIL.
            """,
        )


class TestAgenticCheckout(AgenticTestBase):
    """Scenario 11: Full E2E Checkout"""

    def test_full_checkout_flow(self):
        # Pre-add via API so we can focus the test on the checkout UI
        self.context.request.post(
            f"{BASE_URL}/api/cart",
            data={"productId": 1, "quantity": 1}
        )
        self.page.goto("/checkout.html")
        self.run_agentic_scenario(
            name="Full E2E Checkout Process",
            instructions="""
            You are on the TechShop checkout page. Wireless Headphones is in the cart.
            Fill shipping:
            1. Fill #firstName with "John"
            2. Fill #lastName with "Doe"
            3. Fill #address with "123 Main Street"
            4. Fill #city with "Grand Rapids"
            5. Select "MI" in #state
            6. Fill #zip with "49501"
            7. Fill #phone with "555-123-4567"
            Fill payment:
            8. Fill #cardName with "John Doe"
            9. Fill #cardNumber with "4111111111111111"
            10. Fill #expiry with "12/25"
            11. Fill #cvv with "123"
            12. Click #placeOrderBtn
            13. Wait 2 seconds
            14. Assert a confirmation modal is visible containing "Order Confirmed"
            If all steps succeed → PASS. Otherwise → FAIL.
            """,
        )


class TestAgenticRegistration(AgenticTestBase):
    """Scenario 9: Register New Account"""

    def test_register_new_account(self):
        self.page.goto("/register.html")
        unique_email = f"agent_{int(time.time())}@example.com"
        self.run_agentic_scenario(
            name="Register New Account",
            instructions=f"""
            You are on the TechShop registration page.
            1. Fill #name with "Jane Smith"
            2. Fill #email with "{unique_email}"
            3. Fill #password with "securepassword123"
            4. Fill #confirmPassword with "securepassword123"
            5. Click the Create Account / submit button
            6. Wait 2 seconds
            7. Assert a success toast appeared
            8. Assert the page redirected to the homepage (URL ends with "/")
            If all checks pass → PASS. Otherwise → FAIL.
            """,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("TechShop — Agentic Tests (Claude AI-powered)")
    print("=" * 60)
    print()
    print("The AI agent reads the page visually and decides what")
    print("to do next — just like a human tester would.\n")

    unittest.main(verbosity=2)
