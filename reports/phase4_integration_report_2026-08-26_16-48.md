# Integration Test Results Report

## Summary
- Total integration tests run: 3  
- Passed: 2  
- Failed: 1  
- Errors: 0

Failing test:
- test_concurrent_sessions_can_overcommit_stock_showing_cross_component_issue (generated_integration_tests.TestIntegrationUserJourneys.test_concurrent_sessions_can_overcommit_stock_showing_cross_component_issue)

Unit tests: passed 6, failed 0.

This failure exposes a cross-component concurrency/consistency bug that unit tests did not catch.

---

## Failure details (from test output)
- Assertion failure:
  - Assertion: self.assertGreaterEqual(updated_product["stock"], 0)
  - Observed value: -1
  - Message: "Stock became negative after concurrent checkouts — indicates overcommit bug"
- Trace shows the assertion raised in generated_integration_tests.py line 203.
- Deprecation warnings about datetime usage are present but not functionally related to the failure.

Test log excerpt:
- "FAIL: test_concurrent_sessions_can_overcommit_stock_showing_cross_component_issue"
- Final assertion failure: -1 not greater than or equal to 0 : Stock became negative after concurrent checkouts — indicates overcommit bug

---

## What happened (high level)
The integration test simulated concurrent checkout operations from two sessions against the same product. After the two concurrent checkouts completed, product stock ended up as -1, i.e. stock went negative. This indicates that two parallel flows both observed sufficient stock and both decremented it, leading to an overcommit.

This is a cross-component problem because it requires multiple pieces working together:
- The checkout API (orders creation/validation)
- Inventory/storefront product data (stock read/write)
- The persistence layer (database) and its transaction/isolation behavior
- Session/cart handling (how quantities are calculated/held)

Unit tests (which passed) did not reveal this because they likely exercised components in isolation or did not simulate concurrency/race conditions.

---

## Likely root cause(s)
Primary cause (most probable):
- Inventory decrement is not atomic or protected by a transaction/isolation mechanism that prevents concurrent modifications leading to negative stock.
  - Example: checkout code reads product.stock, checks that stock >= qty, and then writes product.stock - qty without a DB-level check/lock. With two concurrent requests both reading the same initial value, both write resulting in negative stock.

Secondary/related causes:
- No DB constraint preventing negative stock (e.g., CHECK (stock >= 0)). Without such constraint, an accidental over-decrement can persist.
- No optimistic locking/versioning on product rows (so last-writer wins without detecting conflicts).
- No reservation/hold mechanism: cart/checkout expects stock availability at commit time but doesn't reserve inventory early or re-check/lock at commit.
- Checkout endpoint may not run in a transaction that spans the validation -> decrement -> order create steps, so partial updates can interleave.
- Potential missing idempotency or unique order token handling, so retries cause additional decrements.

Which component is at fault?
- Not a single component bug exclusively; rather it's a coordination bug between Checkout (orders) and Inventory persistence components. The checkout flow assumes read-then-write without concurrency protection. The DB/persistence layer lacks constraints/locking to enforce correctness under concurrency.

---

## Why unit tests missed it
- Unit tests typically exercise logic paths individually (e.g., “if stock < qty reject”, “decrement stock on success”) but do not run concurrent threads/processes against the real persistence store.
- If unit tests mock the inventory or the DB layer, locks and race conditions are not exercised.
- There were no integration/concurrency tests covering simultaneous checkouts or verifying that stock never becomes negative under concurrent load.

---

## Reproduction steps (how to reproduce deterministically)
1. Create a product with stock = 1 (or any small integer).
2. Create two distinct sessions/carts, each with quantity = 1 of that product.
3. Simultaneously issue two checkout POST requests (one per session) to the checkout endpoint (use threads or parallel processes so they overlap).
4. Observe responses — both may succeed.
5. Query GET /api/products/<id> (or product listing) and observe stock == -1 (or negative).

The failing integration test performed this kind of scenario and asserted final stock >= 0, which failed.

---

## Short-term mitigations (quick fixes to stop data corruption)
1. Add a DB-level constraint to prevent negative stock (CHECK stock >= 0). This stops negative values from persisting and surface an immediate failure instead of silent corruption.
2. On checkout, after attempting to decrement stock, verify the updated stock >= 0; if the DB update would go negative, rollback and return 409/400 (out of stock).
3. Return a clear 409 Conflict / 400 error when checkout cannot be fulfilled due to insufficient stock (so client can surface the failure).

These mitigate damage quickly but may produce more user-visible errors if concurrency remains unhandled.

---

## Long-term/robust fixes (recommended)
1. Use database transactions + row-level locking:
   - Wrap checkout in a transaction.
   - Use SELECT ... FOR UPDATE (or equivalent) to lock product rows that will be decremented so concurrent checkouts serialize.
2. Implement optimistic locking:
   - Add a version or updated_at field; updates must include expected version and fail if changed, then retry the operation.
3. Implement reservation/hold model:
   - When adding to cart or at intent-to-checkout, create a reservation that reduces "available" stock but not committed until successful payment/checkout.
   - Release reservations on timeout or explicit cancel.
4. Enforce idempotency for checkout endpoints:
   - Protect against retries performing duplicate decrements.
5. Add integration tests that simulate high concurrency across checkout and cart operations.
6. Consider adding metrics and alerts for negative or near-zero stock anomalies.

---

## Suggested changes to code & schema
- Schema: add CHECK constraint on products.stock >= 0 and/or make stock UNSIGNED (if DB supports).
- Checkout code:
  - Begin DB transaction.
  - For each item: SELECT stock FROM products WHERE id = ? FOR UPDATE.
  - If stock < qty: rollback and return 409 (insufficient stock).
  - Else update stock = stock - qty.
  - Create order, commit transaction.
- Alternative: use UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ? and then check affected rows; if affected rows = 0, treat as insufficient stock. This is a single atomic update that avoids separate read-then-write.

---

## Tests to add (integration and regression)
High priority (must add now):
- Concurrent checkout test(s):
  - N parallel sessions each attempting to checkout items that in total exceed available stock; assert:
    - No final product.stock < 0.
    - At most available_qty units are sold (sum of successful order quantities ≤ original stock).
    - Requests that fail return a clear out-of-stock status (409/400).
  - Repeat with many concurrent requests (stress test).
- Atomic update test:
  - Issue concurrent UPDATE-based decrements and assert DB state consistent and no negative stock.

Medium priority:
- Reservation flow tests:
  - Reserve stock on add-to-cart, then two parallel reservations: ensure available stock is not over-reserved.
- Idempotency tests:
  - Ensure repeating the same checkout request (same idempotency key) does not create duplicate orders or double-decrement stock.

Low priority:
- Verify DB constraint kicks in: create negative decrement scenario and verify transaction rolls back.

Also update unit tests:
- Add tests for “UPDATE ... WHERE stock >= qty” code path to ensure it correctly rejects when stock insufficient.
- Add tests for retry/optimistic lock handling.

---

## Verification plan (post-fix)
- Run integration concurrency tests (the failing test plus stress tests) repeatedly in CI, ideally against the same DB engine used in production.
- Add a CI job that runs the concurrency test with varied timing to catch race windows.
- Monitor in staging for order failures / stock inconsistencies after deployment.

---

## Priority & impact
- Priority: High. This bug allows data corruption (negative stock) and overselling, directly impacting user experience and business integrity.
- Impact: Orders may be accepted for items not actually available. Financial and customer support risk.

---

## Actionable next steps (ordered)
1. Immediately add DB constraint preventing negative stock and return/retry logic in checkout to prevent silent corruption.
2. Implement atomic update pattern (single UPDATE ... WHERE stock >= qty) or SELECT FOR UPDATE inside a transaction.
3. Add/enable the concurrent integration test that failed (and the additional concurrent tests above) in CI so this class of bug is blocked from regressions.
4. Add logging/metrics around checkout failures and stock adjustments.
5. After fixes, re-run the integration suite and the failing test to verify the issue is resolved.

---

If you want, I can:
- Propose exact SQL patterns (UPDATE with WHERE) and pseudo-code for transactional checkout.
- Draft the new integration tests (python) to add to the suite that will assert invariants and stress concurrency.
- Identify which endpoints to instrument for more detailed logs to help root-cause verification.