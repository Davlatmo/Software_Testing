# Final Pipeline Report — product search & filtering
**Commit:** Implement product search and filtering endpoints (/api/products, /api/products/<id>)  
**Date:** 2026-08-26  
**Overall verdict:** PASSED WITH WARNINGS

## Summary table
| Phase | Description | Result | Tests |
|-------|-------------|--------|-------|
| 1 | Requirements check | PASSED | — |
| 2 | Test generation | DONE | 13 tests generated (generated_unit_tests.py) |
| 3 | Unit tests | PASSED | 13/13 passed |
| 4 | Integration tests | FAILED | 0/0 passed (no tests ran) |

## What was verified
- REQ-01 (Search by name): PASSED
- REQ-02 (Category filter): PASSED
- REQ-03 (Price range filter): PASSED
- REQ-04 (Combined filters): PASSED
- REQ-05 (Single product endpoint and 404): PASSED

## Bugs found
- **Severity:** High  
  **Found by:** Integration test run (Phase 4)  
  **Description:** No integration tests executed ("Ran 0 tests"). This leaves end-to-end behavior (routing, HTTP layer, DB interaction, error mapping) unverified.  
  **Status:** Still open

- **Severity:** Medium  
  **Found by:** Requirements check / code review (Phase 1) + unit test evidence (Phase 3)  
  **Description:** NaN and Infinity are currently parsed without raising ValueError: float('NaN') or float('inf') will be accepted and treated in code-paths (unit test test_minPrice_nan_and_inf_do_not_raise_400_and_result_in_no_matches asserts current behavior). If the API should reject NaN/Infinity inputs (recommended), get_products in techshop_testing/Server.py must reintroduce math.isnan()/math.isinf() checks when parsing min_price_raw and max_price_raw.  
  **Status:** Still open

- **Severity:** Low/Medium  
  **Found by:** Requirements check (Phase 1)  
  **Description:** Special category value 'all' is currently treated as "no filter" (get_products category normalization). Requirements did not mention 'all'. Decide whether to accept, document, or disallow 'all' and adjust logic/tests accordingly.  
  **Status:** Still open

- **Severity:** Low  
  **Found by:** Requirements check (Phase 1)  
  **Description:** There are two @app.after_request functions: set_session_cookie and add_cors_headers in techshop_testing/Server.py. Flask supports multiple after_request handlers, but ordering may be ambiguous to readers and could cause subtle ordering bugs. Consider consolidating to a single after_request handler or add explicit comments about ordering.  
  **Status:** Still open

## What is working correctly
- /api/products implements case-insensitive search and treats whitespace-only or empty search as "return all" (REQ-01).
- Category validation enforces allowed categories (case-insensitive); invalid category returns 400 with the expected error body (REQ-02).
- minPrice/maxPrice parsing returns clear 400 errors for non-numeric inputs and enforces minPrice <= maxPrice (REQ-03).
- Combined filters (search + category + price) are applied together and return expected items (REQ-04).
- /api/products/<id> returns product when found and 404 with the required JSON error body when not found (REQ-05).
- All present unit tests (generated_unit_tests.py) pass: 13/13 green. Relevant passing tests: test_get_products_search_returns_matching_case_insensitive, test_get_products_category_filter_valid_and_case_insensitive, test_get_products_minPrice_and_maxPrice_filters, test_get_products_combined_filters_search_category_price, test_get_product_by_id_successful, test_get_product_not_found_returns_404, plus validation/edge-case unit tests listed in the unit report.

Do NOT change these behaviors without updating the unit tests listed above.

## Action items
Ordered by priority.

1) Re-enable/repair integration test discovery and run basic end-to-end tests (critical to release)
- What to fix: Make integration tests discoverable and runnable so they actually execute (currently "Ran 0 tests"). Verify test filenames, test method names, test runner invocation, and presence of the required setUpClass server startup snippet.
- Which file(s) to change: tests/integration/* (rename/add files to match discovery), CI/test-runner invocation (e.g., .github/workflows/test.yml or the test runner script if it filters test discovery). Add a new integration test file: tests/integration/test_products_integration.py.
- Tests to add/run first (implementation-ready names):
  - test_search_by_name_end_to_end
  - test_search_whitespace_returns_all_end_to_end
  - test_category_filter_valid_and_invalid_end_to_end
  - test_price_range_filters_and_min_greater_than_max_end_to_end
  - test_combined_filters_end_to_end
  - test_get_product_by_id_integration
- Estimated effort: 1–2 hours to fix discovery + 2–4 hours to add/run the initial set of integration tests.

2) Decide and fix NaN/Infinity handling for minPrice/maxPrice (consistency / input validation)
- What to fix: If API should reject NaN/Infinity, add explicit checks after float parsing using math.isnan(value) or math.isinf(value) and return 400 with a clear JSON error (consistent with other 4xx responses). If current behavior is desired, document it and add integration tests that assert current behavior.
- Which file to change: techshop_testing/Server.py — function get_products (explicitly where min_price_raw and max_price_raw are parsed).
- Tests to add/update: unit test test_minPrice_nan_and_inf_do_not_raise_400_and_result_in_no_matches (update expectation) or add a new test test_minPrice_nan_or_inf_returns_400 to enforce rejecting.
- Estimated effort: 30–90 minutes.

3) Decide policy for special category value 'all' and update code/tests/docs
- What to fix: Either treat 'all' as invalid (return 400) or document that 'all' means no filtering; update get_products category normalization accordingly and add tests that assert the chosen behavior.
- Which file to change: techshop_testing/Server.py — get_products category normalization and validation; docs: techshop_testing/requirements.md or API docs.
- Tests to add/update: unit/integration tests for category 'all' (e.g., test_get_products_category_all_behavior).
- Estimated effort: 15–60 minutes.

4) Standardize error response schema and Content-Type for 4xx/404
- What to fix: Ensure all 4xx and 404 responses consistently return JSON with the agreed schema (e.g., {"error": "message"}). Add assertion checks in tests.
- Which file(s) to change: techshop_testing/Server.py (error handlers, early return points in get_products and get_product), possibly app-wide error handler configuration.
- Tests to add: test_error_responses_all_have_content_type_json (integration); unit tests that check Content-Type on 400/404 responses.
- Estimated effort: 30–90 minutes.

5) (Optional) Consolidate after_request hooks to avoid ordering surprises
- What to fix: Merge set_session_cookie and add_cors_headers into a single after_request function or add comments documenting ordering and intent.
- Which file to change: techshop_testing/Server.py (the two @app.after_request functions).
- Estimated effort: 15–30 minutes.

6) Add integration tests for state consistency (create→search visibility) and decimal precision edge cases
- What to fix: Add tests that create a product and immediately search for it, and tests that validate decimal inclusivity (e.g., price 19.999 vs maxPrice=20.0).
- Which files: tests/integration/test_products_integration.py; update generated_unit_tests.py or add unit tests as needed.
- Estimated effort: 1–3 hours.

## Quality verdict
The commit implements the required search and filtering functionality cleanly and idiomatically (techshop_testing/Server.py: get_products and get_product), and the generated unit test suite (generated_unit_tests.py) confirms the core acceptance criteria (13/13 passing). However, the missing integration test execution is the primary gap: unit tests alone cannot guarantee the HTTP/DB wiring and error mapping are correct in a running service. Immediately enable integration test discovery/run (tests/integration/test_products_integration.py and CI test settings), then address explicit input-validation decisions for NaN/Infinity and the special 'all' category in techshop_testing/Server.py (get_products). The code is well-structured—keep current JSON error shapes and the test names listed above when you change behavior so the test suite can be updated deterministically.