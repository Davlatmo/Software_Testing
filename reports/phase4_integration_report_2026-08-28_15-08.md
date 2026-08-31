Integration Test Results Report
==============================

Summary
-------
- Integration tests run: 0
- Passed: 0
- Failed: 0
- Errors: 0

Full output (as provided)
-------------------------
Ran 0 tests in 0.000s

NO TESTS RAN

Unit test context (for comparison)
----------------------------------
- Unit tests: 7 passed, 0 failed

High-level conclusion
---------------------
No integration tests executed. Because of that, there are no integration failures to report from runtime behavior — but that absence is itself a significant problem: integration-level issues (cross-component problems) remain unexercised and therefore undetected. Since unit tests passed, components appear correct in isolation, but we cannot assume that components integrate correctly.

Immediate observations and likely root causes for "NO TESTS RAN"
----------------------------------------------------------------
These are the most probable reasons why no integration tests ran. Follow the checks in order.

1. Test discovery / naming problems
   - Test file(s) or test class/method names do not follow the test runner conventions (e.g., files not prefixed with test_, TestCase not subclassing unittest.TestCase, or methods not starting with test_).
   - How to confirm: run the test runner in verbose/discovery mode (python -m unittest discover -v or pytest -q) and watch discovery logs.

2. Test module import errors or syntax errors
   - If importing a test module raises, unittest may skip it silently in some configs or show no tests.
   - How to confirm: run python -m pyflakes/.pylint or import the module manually (python -c "import test_module") to see exceptions.

3. Tests being skipped or marked
   - Tests may be decorated with skip or conditionally skipped due to environment variables or missing dependencies.
   - How to confirm: check for @unittest.skip or pytest.skip; run with -q/--verbose to surface skips.

4. Misconfigured test runner or environment
   - Running the wrong command, wrong working dir, or using a test runner that looks in other places.
   - How to confirm: print current working dir and list files; explicitly run a known test file.

5. setUpClass/server startup problems causing immediate abort
   - If setUpClass contains errors or blocks indefinitely, tests may not run; but the provided output shows immediate exit with no tests discovered rather than blocked runs. Still confirm the required server-start snippet is present in each integration test file.
   - How to confirm: run the setUpClass snippet manually in a dedicated script to detect failures, port conflicts, or import errors.

6. Test file(s) simply absent
   - There may be no integration test files committed or saved.
   - How to confirm: inspect repository for tests/ or integration_tests/ files.

Cross-component failure modes that unit tests likely missed
----------------------------------------------------------
Even though we cannot point to a specific failure (no integrations executed), here are concrete integration-level issues that unit tests commonly miss for the product search/filtering feature (REQ-01–REQ-05). These items should be prioritized when adding integration tests.

1. Search case-insensitivity mismatch
   - Unit tests might have validated a helper function that lowercases strings, but the real query layer (ORM/DB) may perform case-sensitive matching depending on collation or SQL used (ILIKE vs LIKE).
   - Symptoms: API returns no matches for term that unit tests said should match.

2. Combined filters and query composition bugs
   - Problems occur when search, category and price filters are combined: wrong SQL WHERE conjunctions, parameters overriding each other, or prematurely short-circuiting filters.
   - Symptoms: Valid combined query returns either too many results (filters not applied) or too few/no results (filter clobbered).

3. Validation and error response inconsistency
   - Category validation or minPrice/maxPrice logic might be implemented in a helper (tested in unit tests) but not applied at the API layer, or vice versa, leading to inconsistent response codes (e.g., 200 vs 400) and different JSON shapes.
   - Symptoms: Unit tests that check only the helper succeed, but API returns plain HTML error or 500 on invalid input.

4. JSON/non-JSON error responses
   - On exceptions the server might return an HTML error page (Flask default) instead of JSON {error: ...}, breaking clients expecting JSON.
   - Symptoms: Tests or clients trying to parse JSON fail with decode errors.

5. Endpoint routing vs service layer disagreements
   - The endpoint signature/parameter parsing may differ from the service method signature unit tested; e.g., endpoint uses "category" parameter but service expects "cat", so tests on service pass but request returns wrong results.
   - Symptoms: API returns full product list when filtering should apply.

6. Single product endpoint inconsistencies
   - Unit tests may validate product retrieval logic with fixtures but not exercise the 404 path in the live API (e.g., different id types, path parameter parsing).
   - Symptoms: GET /api/products/<id> returns 500 or 200 with null body instead of 404 + JSON error.

7. Concurrency / server startup race issues
   - Integration tests that start the server must ensure it's ready before making requests. If the server isn't ready or bound to a different interface/port, tests will fail or hang.
   - Symptoms: connection refused or intermittent failures only in integration runs.

Root cause attribution guidance
-------------------------------
With zero integration tests executed we cannot conclusively identify component-level faults. However, common places to inspect when integration failures appear are:

- Routing/Controller layer (API): parameter parsing, response formatting (JSON), status codes — likely culprit if unit-tested service functions pass but API responses are wrong.
- Validation layer / request parsing: category/value validation and error generation — common source of inconsistent 4xx responses.
- Persistence / query layer (ORM/SQL): search matching logic (case sensitivity, LIKE vs ILIKE), combined WHERE clause composition — likely culprit when filters are combined incorrectly.
- Server bootstrap/infra (Flask app): error handlers and content-type enforcement — likely culprit when errors return non-JSON or HTML.

Actionable next steps (priority order)
-------------------------------------

1. Get tests to run (blocker)
   - Verify there are integration test files present and named appropriately (file names starting with test_).
   - Ensure TestCase classes subclass unittest.TestCase and methods are named test_*.
   - Run discovery with verbose output:
     - python -m unittest discover -v
     - or pytest -q
   - If discovery still shows no tests, try importing a test module directly to reveal import errors.

2. Ensure the required server startup snippet is present and correct
   - Each integration test file must include the exact setUpClass snippet provided (server runs on 127.0.0.1:3000). If missing, add it.
   - Check for port conflicts (another process on 3000). If conflict exists, stop conflicting process or modify tests to use an available port and update snippet accordingly.
   - Manually run the setUpClass snippet in REPL to watch for exceptions.

3. Add/enable the following integration tests (high priority)
   - Test A: Search flow + details:
     - GET /api/products?search=Term -> assert 200, JSON list, each product name contains Term (case-insensitive).
     - Take one returned id -> GET /api/products/<id> -> assert 200 and product fields match.
   - Test B: Category filtering:
     - GET /api/products?category=electronics -> assert 200 and all products have category electronics.
     - GET /api/products?category=invalid -> assert 400 and JSON { "error": "Invalid category" }.
   - Test C: Price range validation and filtering:
     - GET /api/products?minPrice=50&maxPrice=100 -> assert 200 and all products have price between 50 and 100 inclusive.
     - GET /api/products?minPrice=200&maxPrice=100 -> assert 400 and JSON { "error": "minPrice cannot be greater than maxPrice" }.
   - Test D: Combined filters:
     - GET /api/products?search=keyboard&category=electronics&maxPrice=150 -> assert 200 and returned set respects all filters.
   - Test E: Single product not found:
     - GET /api/products/999999 -> assert 404 and JSON { "error": "Product not found" }.
   - For each test, assert Content-Type: application/json and that responses are valid JSON.

   Note: Even though these are read-only flows, make tests multi-step by chaining endpoints (list -> pick id -> get details) to validate data consistency across layers.

4. Add logging/diagnostics in app for integration runs
   - Ensure Flask error handlers return JSON for 4xx/5xx.
   - Enable request logging to capture incoming query parameters and SQL/ORM queries (or enable debug logging for the database layer) during test runs.

5. Re-run integration tests and compare with unit tests
   - If integration tests fail while unit tests pass, target the layer separating them:
     - If service unit tests pass but API returns wrong response, inspect controller and validation code.
     - If combined filter cases fail, inspect query composition/ORM layer and the exact SQL generated.

6. Capture and attach artifacts if failures occur
   - Full server logs (stdout/stderr)
   - HTTP request/response bodies (including headers)
   - Stack traces for any exceptions
   - SQL/ORM logs for queries executed during failing tests

Quick debugging checklist for common issues
------------------------------------------
- Are integration tests present and named correctly?
- Does each test file include the required setUpClass server startup snippet?
- Is Flask app importable from techshop_testing.Server (path mismatch)?
- Is port 3000 available and not blocked by firewall?
- Do endpoints consistently return application/json, including errors?
- Are validation error messages and status codes exactly as required by REQs?
- Is search implemented using case-insensitive comparison (ILIKE or lower() comparisons)?
- Are all three filters combined in a single query (not applying them in separate steps that overwrite results)?

Recommendations for preventing similar gaps
------------------------------------------
- Add CI step that runs integration tests separately from unit tests; fail the build if integration tests are missing or zero.
- Include a test-discovery smoke test that asserts at least one integration test executes.
- Add health-check endpoint (e.g., /__health) called by tests after server startup to ensure readiness before running requests.
- Include a standardized error-handling middleware that ensures JSON responses for errors.

Closing note
------------
Right now the principal problem is test execution — no integration coverage. Fixing test discovery and ensuring the server startup code from the project instructions is present in each test file is the immediate priority. Once integration tests run, re-run them and collect logs; then a focused root-cause analysis can be done for any failing integration test to determine whether the issue lies in the API layer, service/validation layer, or persistence/query layer.