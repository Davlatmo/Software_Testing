"""
unit_test_template.py — Template for generated unit tests

Phase2 agent reads this file and follows this exact structure
when generating new tests. Every generated test file must look like this.
We need this template for structure and also for generating a good test.
"""
import unittest
import sys
import os
import threading
import time
import requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from techshop_testing.Server import app

# Add the app to the path so we can import Server
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

class TestExampleFeature(UnitTestBase):
    """
    Template test class — one class per feature being tested.
    Replace 'ExampleFeature' with the actual feature name.
    """

    def test_example_happy_path_returns_200(self):
        r = self.session.get(f'{BASE_URL}/api/products')
        self.assertEqual(r.status_code, 200)

    def test_example_missing_required_field_returns_400(self):
        r = self.session.post(f'{BASE_URL}/api/login', json={})
        self.assertEqual(r.status_code, 400)

    def test_example_nonexistent_resource_returns_404(self):
        r = self.session.get(f'{BASE_URL}/api/products/99999')
        self.assertEqual(r.status_code, 404)

   
if __name__ == "__main__":
    unittest.main(verbosity=2)

