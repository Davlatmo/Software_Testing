"""
agents.py: The four phase agents

 Each agent here maps exactly to one phase from our pseudocode:
    validation_agent  ->  AgentPhase1  (requirements validation)
    unit_test_generator_agent -> AgentPhase2  (unit test generation)
    executor_agent  -> AgentPhase3  (unit test execution + report)
    integration_test_generator_agent  -> AgentPhase4  (integration test generation + report)
 
FROM OUR PSEUDOCODE:
    agent_phase1(arg: requirements_path):
        instructions = "the instructions given to phase1 agent"
        tool = [read_file, git_diff]
 
Each agent class exactly defines:
     instructions -> (the system prompt, what the agent should do)
     tools -> (which tool names from TOOL_REGISTRY the agent can use)
     run -> (the entry point the coordinator calls)
  
                    
"""
import json
import re
from Tools import write_file, write_report, run_tests, read_file
from base_agent import BaseAgent
 
 #Phase1: Validation agent
class AgentPhase1(BaseAgent):
    """
    Checks whether the committed code matches the feature requirements.
 
    FROM OUR PSEUDOCODE:
        agent_phase1(arg: requirements_path):
            instructions = "..."
            tool = [read_file, git_diff]
 
    Tools this agent uses:
        read_file  -> reads the requirements document
        git_diff   -> sees what the developer actually committed
    """
 
    def __init__(self, client, deployment):
        super().__init__(client, deployment)
 
        self.instructions = """
        You are a requirements validation agent.
 
        Your job is to check whether the code a developer committed
        actually implements what the feature requirements describe.
 
        You have two tools:
          * read_file: use this to read the requirements document
          * git_diff: use this to see exactly what the developer changed
 
        Validation process:
         1) Call read_file with the requirements_path to read the requirements
         2) Call git_diff to see what was committed by developer
         3) Compare them carefully and check if the comitted code does what was asked
         4) Respond with a JSON object:
           {
             "compliant": true or false,
             "summary": "overall assessment",
             "missing": ["list of requirements that are missed"],
             "errors": ["specific problems found in the code"],
             "suggestions": ["concrete fix for each problem"],
             "quality_notes": ["observations about code quality"]
           }
 
        Be specific. Specify actual function names, file names, and
        line numbers from the diff when describing problems.
        If compliant is true then missing and errors should be empty lists.
        """
 
        # Tools this agent is allowed to call
        self.tools = ["read_file", "git_diff"]

     #Entry point that is called by our coordinator
    def run(self, requirements_path: str) -> dict:
        """
        Entry point called by the coordinator.
 
        Args:
            requirements_path: path to the requirements .md file
 
        Returns:
            dictionary with keys: compliant, summary, missing, errors,
                            suggestions, quality_notes
        """
        print("\n[Phase1] Starting requirements validation...")
 
        result_str = self.run_with_tools(
            f"Check validaty. Requirements file: {requirements_path}"
        )
 
        # Analyzing the JSON data returned by the AI.
        try:
            result = json.loads(result_str)
        except json.JSONDecodeError:
            #If the AI ​​has added additional text to the text, try extracting the JSON block.
            match = re.search(r'\{.*\}', result_str, re.DOTALL)
            if match:
                result = json.loads(match.group())
            else:
                #treat non-compliant with the raw text as error
                result = {
                    "compliant":     False,
                    "summary":       "Failed to process agent response.",
                    "missing":       [],
                    "errors":        [result_str],
                    "suggestions":   [],
                    "quality_notes": [],
                }
 
        # Save a report regardless of outcome
        report_lines = [
            "# Phase 1 — Requirements Compliance Report\n",
            f"## Result: {'COMPLIANT' if result.get('compliant') else 'NON-COMPLIANT'}\n",
            f"### Summary\n{result.get('summary', '')}\n",
        ]
 
        if result.get("missing"):
            report_lines.append("### Missing requirements\n")
            report_lines.extend(f"- {m}\n" for m in result["missing"])
 
        if result.get("errors"):
            report_lines.append("### Errors found\n")
            report_lines.extend(f"- {e}\n" for e in result["errors"])
 
        if result.get("suggestions"):
            report_lines.append("### Suggestions\n")
            report_lines.extend(f"- {s}\n" for s in result["suggestions"])
 
        if result.get("quality_notes"):
            report_lines.append("### Quality notes\n")
            report_lines.extend(f"- {q}\n" for q in result["quality_notes"])
 
        write_report("".join(report_lines), phase="1")
 
        print(f"[Phase 1] Result: {'COMPLIANT' if result.get('compliant') else 'NON-COMPLIANT'}")
        return result

 
# PHASE2: Unit test generation agen
class AgentPhase2(BaseAgent):
    """
    Generates unit tests for the committed code.
 
    FROM YOUR PSEUDOCODE:
        "Phase2" --> description. Input parameters:
            requirements_path, committed_code, past_tests,
            project_docs, template_to_follow
 
    Tools this agent uses:
        read_file  → reads requirements, past tests, docs, template
    """
 
    def __init__(self, client, deployment):
        super().__init__(client, deployment)
 
        self.instructions = """
        You are a unit test generation agent.
 
        Your job is to write thorough Python unittest test cases for
        newly committed code.
 
        You have read_file available to read any files you need.
 
        Tetst generation process:
        1) Read the requirements file to understand what was built
        2) Read the committed code diff to see the implementation
        3) Read past tests to understand the project's test style
        4) Read the project docs to understand the domain
        5) Read the test template to know the exact format to follow
 
        RULES FOR GENERATING TESTS:
        * Follow the template structure exactly
        * Cover every happy path described in requirements
        * Cover edge cases: empty input, null values, max values, invalid types
        * Cover every error scenario: what happens when things go wrong
        * Do not duplicate any test already in the past tests
        * Test names must be descriptive: test_what_when_expected
          Example: test_add_product_when_price_is_negative_returns_400
 
        Return only valid Python code. No explanation, no markdown.
        The output will be written directly to a python (xxxxxx.py) file and executed.
        """
 
        self.tools = ["read_file"]
 
    def run(
        self,
        requirements_path: str,
        committed_code: str,
        past_tests: str,
        project_docs: str,
        template_to_follow: str,
        output_path: str = "generated_unit_tests.py",
    ) -> str:
        """
        Entry point called by the coordinator.
 
        Args:
            requirements_path:  path to requirements .md file
            committed_code:     the git diff string (already extracted by Phase1)
            past_tests:         path to existing test file to learn structure from
            project_docs:       path to project documentation file
            template_to_follow: path to the unit test template file
            output_path:        where to save the generated tests
 
        Returns:
            path to the generated test file
        """
        print("\n[Phase 2] Generating unit tests...")
 
        generated = self.run_with_tools(
            f"""Generate unit tests using these files:
            * Requirements: {requirements_path}
            * Past tests to match style of: {past_tests}
            * Project docs: {project_docs}
            * Template to follow: {template_to_follow}
 
            The committed code that needs testing (git diff):
            {committed_code}
            """
        )
 
        # Remove any accidental markdown 
        if generated.startswith("```"):
            generated = generated.split("```")[1]
            if generated.startswith("python"):
                generated = generated[6:]
            generated = generated.strip()
 
        # Save the generated tests to disk
        result = write_file(output_path, generated)
        print(f"[Phase 2] {result}")
 
        return output_path
 
 

# PHASE3: Unit test execution and review
class AgentPhase3(BaseAgent):
    """
    Runs the generated unit tests and produces a developer report.
 
    Important note:
        Python executes the tests via run_tests tool in 
        Agent using LLM reads the results and writes the report
        Our agent does NOT run tests, it only analyses the test results
 
    Tools this agent uses:
        run_tests -> executes the .py test file
        write_report -> saves the final developer report
    """
 
    def __init__(self, client, deployment):
        super().__init__(client, deployment)
 
        self.instructions = """
        You are a unit test results reviewer.
 
        Your job is to run the generated unit tests and then write a
        clear, actionable report for the developer.
 
        PROCESS:
        1) Call run_tests with the test file path
        2) Read the results carefully
        3) Write a developer report covering:
           * Summary: n passed, n failed, n errored out of N total
           * For each FAILED test: what failed, why, and how to fix it
           * For each ERROR: what caused the crash (not an assertion failure,
             but the code threw an exception before even asserting)
           * What is working correctly, do not suggest changing these
           * Priority order: which failures are most critical to fix first
           * Estimated effort: which fixes are quick vs complex
 
        Write the report in clear markdown that a developer can act on immediately.
        Be specific, indicate exact test names, line numbers, and values.
        """
 
        self.tools = ["run_tests"]
 
    def run(self, unit_test_file: str, requirements_path: str) -> dict:
        """
        Entry point called by the coordinator.
 
        Args:
            test_file:          path to the generated unit test file
            requirements_path:  path to requirements (for context in report)
 
        Returns:
            dict with keys: test_results (raw), report (markdown string), success (bool)
        """
        print("\n[Phase 3] Running unit tests...")
 
        # Step 1: Python runs the tests and AI here is not involved yet
        raw_results = run_tests(unit_test_file)
 
        print(
            f"[Phase 3] Results: "
            f"{raw_results['passed']} passed, "
            f"{raw_results['failed']} failed, "
            f"{raw_results['errors']} errors"
        )
 
        # Step 2: AI reads the output results and makes the report
        requirements_text = ""
        try:
            
            requirements_text = read_file(requirements_path)
        except Exception:
            requirements_text = "(requirements file not available)"
 
        report = self.call_ai(
            f"""Write a developer report for these unit test results.
 
            TEST RESULTS SUMMARY:
            * Total tests: {raw_results['total']}
            * Passed:  {raw_results['passed']}
            * Failed:  {raw_results['failed']}
            * Errors:  {raw_results['errors']}
 
            FULL TEST OUTPUT:
            {raw_results['output']}
 
            FAILURE DETAILS:
            {chr(10).join(raw_results['tracebacks']) or 'None'}
 
            ORIGINAL REQUIREMENTS (for context):
            {requirements_text}
            """
        )
 
        write_report(report, phase="3_unit")
        print("[Phase 3] Report written.")
 
        return {
            "test_results": raw_results,
            "report":       report,
            "success":      raw_results["success"],
        }
 
 

# PHASE4: Integration test generation and review
class AgentPhase4(BaseAgent):
    """
    Generates integration tests and produces a final report.
 
    Tools this agent uses:
        read_file  -> reads requirements, unit tests, docs
        run_tests  -> executes the integration test file
    """
 
    def __init__(self, client, deployment):
        super().__init__(client, deployment)
 
        self.instructions = """
        You are an integration test generation and review agent.
 
        You have two responsibilities:
        
        First part:  Generate integration tests:
        Integration tests verify that multiple components work together.
        Each test must call multiple API endpoints in sequence and verify
        that state changes correctly across all of them.
 
        Example: adding to cart -> checking out -> verifying stock reduced ->
                 verifying cart is empty. One test, four endpoint calls.
 
        When generating:
        * Read requirements to find all multistep user flows
        * Read existing unit tests, do not duplicate what they test
        * Read project docs for domain knowledge
        * Focus on: complete user journeys, data flowing between components,
        * state consistency after multistep operations
 
        Second part: Review results:
        After tests run, write a report focusing specifically on:
        * Cross component failures (things that only break when connected)
        * Compare with unit test results (unit passed but integration failed?)
        * Root cause analysis: is the bug in component A, B, or when these components
        are workong together?
 
        Return only valid Python code when generating tests.
        Return clear markdown when writing reports.

        Critical: Every generated test file must include this exact server startup
        in setUpClass, don't use an external server:

    @classmethod
    def setUpClass(cls):
        import threading, time, sys, os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from techshop_testing.Server import app
        t = threading.Thread(
            target=lambda: app.run(host='127.0.0.1', port=3000,
                                   debug=False, use_reloader=False),
            daemon=True
        )
        t.start()
        time.sleep(1.0)
        """
 
        self.tools = ["read_file", "run_tests"]
 
    def run(
        self,
        requirements_path: str,
        unit_test_results: dict,
        project_docs: str,
        output_path: str = "generated_integration_tests.py",
    ) -> dict:
        """
        Entry point called by the coordinator.
 
        Args:
            requirements_path:  path to requirements file
            unit_test_results:  results dict from Phase 3 (for context)
            project_docs:       path to project docs
            output_path:        where to save the integration tests
 
        Returns:
            dict with keys: test_results, report, success
        """
        print("\n[Phase 4] Generating integration tests...")
 
        #Generating integration tests
        generated = self.run_with_tools(
            f"""Generate integration tests.
 
            Requirements file to read: {requirements_path}
            Project docs to read: {project_docs}
 
            Context from unit tests already written:
            Unit test summary — passed: {unit_test_results.get('passed', 'N/A')},
            failed: {unit_test_results.get('failed', 'N/A')}
 
            Generate integration tests that cover complete user journeys.
            Each test calls multièle endpoints in sequence.
            Do not test individual endpoints in isolation, unit tests already do that.
            Return only valid Python code.
            """
        )
 
        # Removing markdown 
        if generated.startswith("```"):
            generated = generated.split("```")[1]
            if generated.startswith("python"):
                generated = generated[6:]
            generated = generated.strip()
 
        # Saving the integration tests
        write_file(output_path, generated)
        print(f"[Phase 4] Integration tests written to {output_path}")
 
        #Python runs the integration tests
        print("[Phase 4] Running integration tests...")
        raw_results = run_tests(output_path)
 
        print(
            f"[Phase 4] Results: "
            f"{raw_results['passed']} passed, "
            f"{raw_results['failed']} failed, "
            f"{raw_results['errors']} errors"
        )
 
        # Our Agent reviews the results
        requirements_text = ""
        try:
            requirements_text = read_file(requirements_path)
        except Exception:
            requirements_text = "(requirements not available)"
 
        report = self.call_ai(
            f"""Write an integration test results report.
 
            INTEGRATION TEST RESULTS:
            * Total: {raw_results['total']}
            * Passed: {raw_results['passed']}
            * Failed: {raw_results['failed']}
            * Errors: {raw_results['errors']}
 
            FULL OUTPUT:
            {raw_results['output']}
 
            FAILURES:
            {chr(10).join(raw_results['tracebacks']) or 'None'}
 
            UNIT TEST CONTEXT (for comparison):
            Unit tests passed: {unit_test_results.get('passed')},
            failed: {unit_test_results.get('failed')}
 
            REQUIREMENTS:
            {requirements_text}
 
            Focus on cross component failures, bugs that unit tests missed
            because they only tested components in isolation.
            """
        )
 
        write_report(report, phase="4_integration")
        print("[Phase 4] Report written.")
 
        return {
            "test_results": raw_results,
            "report":       report,
            "success":      raw_results["success"],
        }

class AgentPhase5(BaseAgent):
    """
    Reads all four phases reports and creates one single developer facing
    summary document saved to reports/final_*.md
 
    This phase exist beacuse:
        After phases 1-4, the developer has four separate report files.
        In the fifth stage, they are combined into one document that provides the answers:
          * What was committed and does it meet requirements?
          * How many tests passed and failed across all levels?
          * What bugs were found, how severe are they, and what to fix first  according to priority?
          * What is working correctly and should not be changed?
          * What is the overall quality rating of this commit?
 
    Tools this agent uses:
        read_file   -> reads all four phase reports
        write_file  -> saves the final consolidated report
    """
 
    def __init__(self, client, deployment):
        super().__init__(client, deployment)
 
        self.instructions = """
        You are a senior engineering lead writing a final consolidated
        test report for a developer after an automated pipeline ran.
 
        You will be given the results from all four pipeline phases.
        Write a single, clear, well structured  report that a
        developer can read in few minutes and know exactly what to do next.
 
        Report structure -> follow this exactly:
 
        # Final Pipeline Report — <feature name>
        **Commit:** <short description of what was committed>
        **Date:** <today's date>
        **Overall verdict:** PASSED / PASSED WITH WARNINGS / FAILED
 
        ## Summary table
        | Phase | Description | Result | Tests |
        |-------|-------------|--------|-------|
        | 1 | Requirements check | PASSED/FAILED | — |
        | 2 | Test generation | DONE | N tests generated |
        | 3 | Unit tests | PASSED/FAILED | X/Y passed |
        | 4 | Integration tests | PASSED/FAILED | X/Y passed |
 
        ## What was verified
        List every requirement (REQ-01 etc.) and whether it passed.
 
        ## Bugs found
        For each bug found across all phases:
        - **Severity**: Critical / High / Medium / Low
        - **Found by**: Unit test / Integration test / Requirements check
        - **Description**: What went wrong
        - **Status**: Fixed / Still open
 
        ## What is working correctly
        List what passed and should NOT be changed.
 
        ## Action items
        Numbered list ordered by priority. Each item has:
        - What to fix
        - Which file to change
        - Estimated effort (minutes/hours)
 
        ## Quality verdict
        One paragraph: overall assessment of the commit quality,
        what the developer did well, and what to improve next time.
 
        TONE: Direct, specific, constructive. Reference exact test names,
        file names, and line numbers. No generic advice.
        """
 
        self.tools = ["read_file"]
 
    def run(
        self,
        phase1_result: dict,
        phase3_result: dict,
        phase4_result: dict,
        requirements_path: str,
        generated_test_file: str,
    ) -> str:
        """
        Entry point called by the coordinator.
 
        Builds a rich context from all phase results and calls the AI
        to combine them into one consolidated report.
 
        Args:
            phase1_result -> compliance dictionary from Phase 1
            phase3_result -> results dictionary from Phase 3
            phase4_result -> results dictionary from Phase 4
            requirements_path ->path to requirements file
            generated_test_file ->path to the generated test file
 
        Returns:
            path to the saved final report
        """
        print("\n[Phase 5] Generating consolidated report.....")
 
        p3 = phase3_result["test_results"]
        p4 = phase4_result["test_results"]
 
        # Determine overall verdict
        if not phase1_result.get("compliant"):
            verdict = "FAILED"
        elif not p3["success"] or not p4["success"]:
            verdict = "Passed with warnings"
        else:
            verdict = "PASSED"
 
        # Build the full context to send to the AI
        context = f"""
PHASE1: Requirements Compliance
Result: {"COMPLIANT" if phase1_result.get("compliant") else "NON-COMPLIANT"}
Summary: {phase1_result.get("summary", "")}
Missing: {phase1_result.get("missing", [])}
Errors: {phase1_result.get("errors", [])}
Suggestions: {phase1_result.get("suggestions", [])}
Quality notes: {phase1_result.get("quality_notes", [])}
 
PHASE2: Tests Generation
Generated file: {generated_test_file}
 
PHASE3: Unit Tests Execution
Total: {p3["total"]}
Passed: {p3["passed"]}
Failed: {p3["failed"]}
Errors: {p3["errors"]}
All passed: {p3["success"]}
Unit test report:
{phase3_result.get("report", "(not available)")}
 
PHASE4: Itegration Tests
Total: {p4["total"]}
Passed: {p4["passed"]}
Failed: {p4["failed"]}
Errors: {p4["errors"]}
All passed: {p4["success"]}
Integration test report:
{phase4_result.get("report", "(not available)")}
 
Overall Assessment: {verdict}
        """
 
        final_report = self.call_ai(
            f"""Write the final consolidated pipeline report.
 
            Use all the information below to produce one clear 
            document a developer can act on immediately.
 
            {context}
            """
        )
 
        # Save to reports/final_*.md
        result = write_report(final_report, phase="5_final")
        print(f"[Phase 5] {result}")
 
        return result