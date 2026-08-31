# Integration Test Results — Report

Summary
- Total integration tests run: 3  
- Passed: 0, Failed: 0, Errors: 3  
- All three tests errored during test setup while attempting to contact the API at http://localhost:3000/api/health. The error in each case is a ConnectionRefused (WinError 10061), meaning the test process could not establish a TCP connection to the target host:port.

Key log evidence
- Repeated stack traces show requests.exceptions.ConnectionError:  
  "HTTPConnectionPool(host='localhost', port=3000): Max retries exceeded with url: /api/health (Caused by NewConnectionError(...): [WinError 10061] No connection could be made because the target machine actively refused it))"
- Failures occur in setUp() when the tests call api_get(self.session, "api/health"), i.e. before exercising any multi-endpoint flows.

Comparison with unit tests
- Unit tests: 15 passed, 0 failed.
- Interpretation: unit tests exercised components in isolation and reported no logic errors. The integration run never reached the multi-component behavior checks because of an environment/connectivity problem. This indicates the immediate integration failures are infrastructure/runner related, not necessarily business-logic bugs that unit tests would catch.

Root cause analysis
1. Primary cause (most likely)
   - No server process listening on localhost:3000. The tests attempted to hit /api/health and the connection was actively refused. This is consistent with the API not being started, started on a different port, or not bound to localhost.

2. Possible alternate/environmental causes
   - BASE_URL in the test harness is incorrect (wrong host, wrong port, missing scheme). Tests assume localhost:3000 but the service may be running at a different address/port.
   - The test runner assumed an external dev server instance would be available but that server was not started as part of the test run.
   - Docker/container port mapping not configured (container runs the service but host port 3000 is not mapped to the container).
   - Firewall or Windows configuration blocking local connections on the port (less likely because error is "actively refused" not "timed out", which normally indicates no process listening).
   - The health endpoint path differs or has authentication, causing the health check to fail (but that normally returns 4xx/401/404, not connection refused).
   - A race condition where server startup is still in progress when tests begin (test didn't wait for readiness).

Is the bug in component A, B, or integration glue?
- The error indicates an environment/connectivity problem — not a component logic bug. The likely problem is in the integration glue / test environment (server not started or wrong configuration). Components themselves (as shown by passing unit tests) are likely correct, but we cannot confirm cross-component interactions until the service is reachable.

Immediate remediation steps (high-priority)
1. Confirm server process:
   - On the test machine run: netstat -ano | findstr :3000 (or equivalent) to confirm whether any process is listening on port 3000.
   - Try: curl -v http://localhost:3000/api/health (or use a browser) to reproduce outside the test harness.
2. If no process is listening:
   - Start the API server (in dev/test mode) that binds to localhost and listens on port 3000. Ensure any required environment variables (DB URL, config) are set.
   - If the server is containerized, ensure docker run / docker-compose maps port 3000 to the host.
3. If server is running on another port:
   - Update the tests' BASE_URL or the test environment to point to the correct host/port.
4. If server should be started by test setup:
   - Modify the test harness to launch the server before tests and wait for readiness (see "Improvements" below).
5. Collect server logs when reproducing the problem to observe startup errors or binding problems.

Suggested test-harness and CI improvements (prevent recurrence)
- Add a robust readiness check/waiter used by tests:
  - Implement a wait_for_http(BASE_URL + /api/health, timeout=30s, backoff=0.5s) that gives the service time to start and clearly fails with a descriptive message if unreachable.
- Make starting the service part of the integration-test fixture:
  - Either start the application process (subprocess) or start required Docker containers in setUpClass/CI job, and shut them down in tearDownClass.
  - Ensure database migrations and seeds run inside the fixture before tests proceed.
- Fail fast and provide better diagnostics:
  - If the health check fails, fail the test suite with a clear error: "Backend unreachable at $BASE_URL – ensure server is running and reachable."
  - Capture and attach container/service logs to CI failure artifacts.
- Environment configuration:
  - Read BASE_URL from a single configuration source (env var). Validate it at test startup and log it.
  - Provide a local test script (e.g., make test-integration) that starts dependencies so developers run tests reliably.
- CI steps:
  - Add a job step to bring up the service(s) (docker-compose up -d) and run migrations, then wait for the health endpoint before running tests.
  - Ensure ports are exposed and firewall rules permit local connections in CI.

Potential integration-only issues to watch for (once connectivity is fixed)
- Session isolation and cart behavior
  - Race conditions where session cookies are mis-handled by a reverse proxy or where the session store is shared incorrectly across users.
  - Tests will need to assert that session identifiers are distinct and that checkout in one session decrements stock and does not remove items from another session's cart.
- Stock consistency under concurrent modifications
  - Concurrent checkouts might cause stock to go negative if no transactional locking is present; add tests that run parallel checkouts to verify proper optimistic/pessimistic locking or validation.
- Filter and validation behavior across layers
  - Units may validate inputs, but an integration failure could occur if routing or middleware swallows errors or transforms responses (e.g., an invalid category returns HTML error page instead of JSON).
  - Confirm 4xx error responses still return the required JSON error bodies (per requirements).
- Health endpoint semantics
  - Make sure /api/health returns 200 and JSON and does not require auth; tests rely on a simple, unauthenticated health endpoint.

Next verification checklist (what to run after fixing environment)
1. Start server/service and confirm health endpoint:
   - curl http://localhost:3000/api/health -> expect 200 + JSON
2. Re-run the three integration tests. Expect them to exercise:
   - Combined filters -> product selection -> add to cart -> checkout -> stock decrement and invalid filter handling.
   - Session isolation where two sessions' carts do not interfere and stock effects are visible across sessions.
   - Full search/add/update/checkout journey.
3. If any of those tests now fail (non-Connection errors), collect full request/response logs and server logs and re-run failing tests with increased logging to determine whether the issue is in the API logic or cross-component interactions.

Actionable items for the team
- Short-term: Verify the API process is running and reachable on the expected host/port. Re-run integration tests.
- Medium-term: Add process startup in test fixtures and a robust wait-for-health step so tests do not fail due to timing/infra issues.
- Long-term: Add CI integration job that brings up the full stack (app + DB), runs migrations/seed, waits for readiness, executes integration suite, and archives logs/artifacts on failure.

Conclusion
- Current integration failures are caused by the test harness being unable to reach the API (connection refused). This is an infrastructure/runner issue rather than a component-level logic bug (unit tests passed). Fix the test environment (start server / correct BASE_URL / map ports / include waiter) and re-run the integration tests. After connectivity is restored, re-evaluate any remaining failures — those will be true cross-component bugs that unit tests could have missed (session handling, stock races, error formatting, etc.).