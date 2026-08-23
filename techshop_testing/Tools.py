"""
tools.py: All tools that are available to our agents
 
Why we used here the tools:
A tool is a plain function in python that an agent is allowed to call.
The @ decorator is just a simple marker that we use in front of tool(@tool) 
and it registers the function in a tools registry so our coordinator knows 
which tools exist and can pass them to the right agent.
 
Tools only interact with the real world:
  * read_file: touches the filesystem and reads the file
  * git_diffruns: a real shell command
  * run_tests: executes Python test files
  * write_file: saves generated code to disk
 
Tools don't call the llms. This is the job of agent.
Tools don't  make decisions. They just fetch or execute, exactly when function doing its job
 
By separating the tools from agent means:
  * We can test tools individually, so we don't need AI
  * We can modify tools without touching anything agent logic
  * The coordinator can see exactly what each agent is allowed to do
"""
import subprocess
import os
import json
from datetime import datetime

#Tool registry that is populated by the @tool decorator as we mentioned above
# This is a simple dict: { "tool_name": function }
# The coordinator reads this to know which tools exist.
TOOL_REGISTRY: dict = {}

def tool(func):
    """
    @tool decorator.
 
    Usage:
        @tool
        def read_file(file_path: str) -> str:
            ...
 
    Effect:
        - Registers the function in TOOL_REGISTRY under its name
        - Returns the function unchanged (so it still works normally)
 
    This is exactly what our pseudocode had:
     import subprocess
        @tool()
        def read_file(file_path: str) -> str:
        #Reads the contents of a file and returns it as a string
          with open(file_path, 'r') as f:
          return f.read()

        @tool()
       def git_diff():
       #Runs the 'git diff' command and returns the output as a string
         result = subprocess.run(['git', 'diff'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
         if result.returncode != 0:
           raise Exception(f"Errore nell'esecuzione di git diff: {result.stderr}")
         return result.stdout

    """
    TOOL_REGISTRY[func.__name__] = func
    return func

# The first tool: read_file
# This tool is used by Phase1 for reading the requirements and 
# by Phase2 for reading docs, past tests, template
@tool
def read_file(file_path: str) -> str:
    """
    Reads the content of a file and returns it as a string.
 
    FROM OUR PSEUDOCODE:
        @tool()
        def read_file(file_path: str) -> str
            with open(file_path, 'r') as f:
                return f.read()
 
    We added the check that the file actually exists (clear error if not)
    and removing whitespace so the LLM gets clean text
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"read_file: '{file_path}' does not exist.\n"
            f"Current directory: {os.getcwd()}\n"
            f"Files here: {os.listdir('.')}"
        )
 
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()

# Second Tool: git_diff
# Used by validation agent in phase1 to see what changes developer commited
@tool
def git_diff() -> str:
    """
    Runs 'git diff HEAD~1 HEAD' and returns the output as a string.
    This shows exactly what changed in the most recent commit.
 
    FROM OUR PSEUDOCODE:
        @tool()
        def git_diff() -> str
            result = subprocess.run(['git', 'diff'], ...)
            if result.returncode != 0:
                raise Exception(f"Error running git diff: {result.stderr}")
            return result.stdout
 
    We changed ['git', 'diff'] to ['git', 'diff', 'HEAD~1', 'HEAD'] because:
        *git, diff alone shows the changes that are not yet commited
        *git, diff HEAD~1 HEAD shows what was in the last commit
        *Since our  commit is a trigger, we want the committed changes
    """
    result = subprocess.run(
        ["git", "diff", "HEAD~1", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
 
    if result.returncode != 0:
        raise Exception(f"Error running git diff: {result.stderr}")
 
    if not result.stdout.strip():
        # No diff means no changes — return a clear message instead of empty string
        return "No changes found in the last commit."
 
    return result.stdout


 # Third Tool: run_tests
 # This tool is used by unit_test_executor_agent in phase3 and 
 # by integration_test_executor_agent in phase4
@tool
def run_tests(test_file: str) -> dict:
    """
    Runs a Python unittest file and returns structured results.
 
    FROM OUR PSEUDOCODE (Phase3 instructions):
        Execute programmatically the unit tests created.Here we don't involve agent.
        LLM only reviews the passed and failed tests and makes report.
 
    This is the programatical  part which is done by python. Our agent doesn't run
    tests. The AI only reads the dictionary results.
 
    Returns a dictionary with:
        passed: number of tests that passed
        failed: number of tests that failed
        errors: number of tests that errored (crashed before asserting)
        output: full verbose output (test names + ok/FAIL/ERROR)
        tracebacks: just the failure/error details (what the AI focuses on)
        success: True if all tests passed, otherwise fail
    """
    if not os.path.exists(test_file):
        raise FileNotFoundError(f"run_tests: '{test_file}' not found")
 
    result = subprocess.run(
        ["python3", "-m", "unittest", test_file, "-v"],
        capture_output=True,
        text=True,
    )
 
    # unittest writes results to stderr 
    full_output = result.stderr + result.stdout
 
    # Parse the summary line for example "Ran 5 tests in 1.243s"
    ran_line = next(
        (l for l in full_output.splitlines() if l.startswith("Ran ")), ""
    )
    total = int(ran_line.split()[1]) if ran_line else 0
 
    # Counting failures and errors from the summary
    failures = full_output.count("\nFAIL:")
    errors    = full_output.count("\nERROR:")
    passed    = total - failures - errors
 
    # Extracting just the error tracebacks for the LLM to read
    # The full output can be very long so we only needs the errors for our AI
    tracebacks = []
    lines = full_output.splitlines()
    in_traceback = False
    current = []
 
    for line in lines:
        if line.startswith("FAIL:") or line.startswith("ERROR:"):
            in_traceback = True
            current = [line]
        elif in_traceback:
            if line.startswith("-" * 20) or line.startswith("=" * 20):
                if current:
                    tracebacks.append("\n".join(current))
                current = []
                in_traceback = False
            else:
                current.append(line)
 
    if current:
        tracebacks.append("\n".join(current))
 
    return {
        "passed":     passed,
        "failed":     failures,
        "errors":     errors,
        "total":      total,
        "success":    result.returncode == 0,
        "output":     full_output,
        "tracebacks": tracebacks,
    }

# Fourth Tool: write_file
""" This tool is used by test_generator_agent in phase2 to
    save generated unit tests, and by integration_test_generator_agent 
    in phase4 to save integration tests
"""
@tool
def write_file(file_path: str, content: str) -> str:
    """
    Writes content to a file. Creates parent directories if needed.
    Returns the path written to (so agents can confirm where the file went).
    """
    os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
 
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
 
    return f"Written: {file_path} ({len(content)} characters)"

# Fifth tool: write_report
""" This tool is used by validation_agent in phase1 for reports 
    regarding requirements correspondence, in phase3 for unit test report, 
     and in phase4 for integration report"""

@tool
def write_report(report_content: str, phase: str) -> str:
    """
    Saves an AI-generated report to the reports/ folder with a timestamp.
    Each phase gets its own report file so nothing is overwritten.
 
    Example output path:
        reports/phase1_requirements_report_2026-07-21_14-30.md
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename  = f"reports/phase{phase}_report_{timestamp}.md"
 
    os.makedirs("reports", exist_ok=True)
 
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report_content)
 
    return f"Report saved: {filename}"
 