""""
Our main coordinator that orchastrates all four agents work
------------------------------------------------------------------------------
Our pseudocode:

agent_coordinator(arg:requirements_path):
agent_coordinator_instructions = "You are the coordinator agent that controls the overall process flow of a project. Your task is to ensure that all phases of the project are executed in the correct order and all necessary requirements are met before moving forward to the next phase".

"Phase1" -->description of the phase. Input parameters (requirements_path)

"Phase2" --> description of the phase. Input parameters ( requirements_path, committed_code, 
past_tests, project_docs, template_to_follow )

"Phase3" --> description of the phase.

"Phase4" --> description of the phase

WHAT OUR  COORDINATOR AGENT ACTUALLY DOES:
-------------------------------------------------------------------------------
The coordinator is the only thing that we call from outside. 
  It:
   *Knows about all phases and  in which order they should run 
   *Calls each phase agent in sequence
   *Passes the output of one phase as input to the next
   *Stops the pipeline if in phase1 we encounter an error
   *Prints a final summary of everything that happened
 
 Without our agent coordinator we would run manually  every phase 
 and then check the results and then run the next phase and again check
 the results. But our coordinator does it automatically. It runs all four
 scripts in the right order.
   
"""
import os
import sys
import json
import argparse
from openai import OpenAI
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
from agents import AgentPhase1, AgentPhase2, AgentPhase3, AgentPhase4
from Tools import git_diff

#Azure openai configueation
load_dotenv()
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
AZURE_DEPLOYMENT = "gpt-5-mini"
AZURE_API_KEY= os.getenv("AZURE_API_KEY")
print("api key =", os.getenv("AZURE_API_KEY"))
print(" azure endpoint =", os.getenv("AZURE_ENDPOINT"))
print("Current directory:", os.getcwd())
print("api key before loading env:", os.getenv("AZURE_API_KEY"))
print("the api key before creating a client:", os.getenv("AZURE_API_KEY"))

# Creating the OpenAI client pointed at our Azure endpoint
azure_client = OpenAI(
    base_url=AZURE_ENDPOINT,
    api_key=AZURE_API_KEY,
)

#Our Coordinator Agent
"""
    FROM OUR PSEUDOCODE:
    agent_coordinator(arg: requirements_path):
    * Orchestrates all four phases in order.
    * Stops at Phase1 if requirements are not met.
    * Passes outputs between our phases automatically.
  
    Input parameters:
        requirements_path:  path to the feature requirements file
        past_tests:         path to existing tests, guides for our phase2
        project_docs:       path to project README or docs that serves as a context for phase2
        template_to_follow: path to unit test template for structure
"""

def agent_coordinator(
    requirements_path: str   = "requirements.md",
    past_tests: str          = "tests/test_api.py",
    project_docs: str        = "README.md",
    template_to_follow: str  = "tests/unit_test_template.py",
):
    
    coordinator_instructions = (
        "You are the coordinator agent that controls the overall process "
        "flow of a project. Your task is to ensure that all phases of the "
        "project are executed in the correct order and all necessary "
        "requirements are met before moving forward to the next phase."
    )

    print("=" * 60)
    print("AGENTIC TESTING PIPELINE, STARTING")
    print("=" * 60)
    print(f"Requirements: {requirements_path}")
    print(f"Past tests:   {past_tests}")
    print(f"Docs:         {project_docs}")
    print(f"Template:     {template_to_follow}")
    print()
 
    # Storing the results from each phase to pass forward
    results = {}

  # PHASE 1: Requirements Validation Agent
    #
    # FROM OUR PSEUDOCODE:
    # Phase1 --> instructions = " ". 
    # Input parameters (requirements_path)
    # tools = [read_file, etc...]
    print(" Phase1: Checking if the requirements are met...")
 
    Validation_Agent = AgentPhase1(azure_client, AZURE_DEPLOYMENT)
 
    # FROM OUR PSEUDOCODE:
    # tools = [consult_agent_phase1, 
    # counsult_agent_phase2, consut_agent_phase3, 
    # consult_agent_phase4] -->as an exmaple to understand the logic
    phase1_result = Validation_Agent.run(requirements_path=requirements_path)
    results["phase1"] = phase1_result
 
    # Decision that is taken by the validation agent
    #  stop if the requirements are not met
    if not phase1_result.get("compliant", False):
        print("\n" + "!" * 60)
        print("The pipline is stoped since requirements are not met")
        print("!" * 60)
        print(f"\nSummary: {phase1_result.get('summary', '')}")

    #if there are missing requirements
        if phase1_result.get("missing"):
            print("\nthere are missing requirements:")
            for m in phase1_result["missing"]:
                print(f"  X {m}")

    #if errors are found
        if phase1_result.get("errors"):
            print("\nErrors found:")
            for e in phase1_result["errors"]:
                print(f"  X {e}")
    
        if phase1_result.get("suggestions"):
            print("\nSuggestions:")
            for s in phase1_result["suggestions"]:
                print(f"  -> {s}")
 
        print("\nFull report saved to: reports/phase1_report_*.md")
        print("\nFix the issues and commit again to restart the pipeline.")
        return  results
 
    print("Phase1 passed, the requirements are met!")
 
    # Get the committed code from Phase1  git_diff call
    # Phase2 needs it as context for generating good tests
    committed_code = git_diff()

# PHASE2: Unit test generation
    #
    # FROM OUR PSEUDOCODE:
    # Phase2 --> "instructions ". 
    # Input parameters:
    #     requirements_path, committed_code, past_tests,
    #     project_docs, template_to_follow
    # tools = [ tools that will be used by agent in phase2]

    print("\nPhase2: Generating unit tests...")
 
    tests_generator_agent = AgentPhase2(azure_client, AZURE_DEPLOYMENT)
 
    # FROM OUR PSEUDOCODE: unit_test_generator_agent_phase2
    unit_test_file = tests_generator_agent.run(
        requirements_path  = requirements_path,
        committed_code     = committed_code,
        past_tests         = past_tests,
        project_docs       = project_docs,
        template_to_follow = template_to_follow,
    )
    results["phase2"] = {"generated_file": unit_test_file}
    print(f"Phase2 completed and tests are saved to: {unit_test_file}")

    # PHASE3: Unit test execution and report
    print("Phase3: Running unit tests...")
 
    executor_agent = AgentPhase3(azure_client, AZURE_DEPLOYMENT)
 
    phase3_result = executor_agent.run(
        unit_test_file = unit_test_file,
        requirements_path  = requirements_path,
    )
    results["phase3"] = phase3_result
 
    unit_status = "all passed" if phase3_result["success"] else "some failed"
    print(f"  {unit_status}, check the reports or phase3_unit_report_*.md")

    # PHASE4: Integration tests
    # FROM OUR PSEUDOCODE:
    #   Phase4 --> instructions = " ".
    #   tools = [tools used by agent in phase4]
    # -------------------------------------------------------------------
    print("\nPhase4,running integration tests...")
 
    integration_test_executor_agent = AgentPhase4(azure_client, AZURE_DEPLOYMENT)
 
    phase4_result = integration_test_executor_agent.run(
        requirements_path  = requirements_path,
        unit_test_results  = phase3_result["test_results"],
        project_docs       = project_docs,
    )
    results["phase4"] = phase4_result
 
    integration_status = "all the tests passed" if phase4_result["success"] else "some failed"
    print(f"  {integration_status} check the phase4 integration test report")

    # Summary
    p3 = phase3_result["test_results"]
    p4 = phase4_result["test_results"]
 
    print("\n" + "=" * 60)
    print("Pipline is completed, the final summary")
    print("=" * 60)
    print(f"Phase 1  Requirements validation:    PASSED")
    print(f"Phase 2  Tests generation:       {unit_test_file}")
    print(f"Phase 3  Unit tests execution:            {p3['passed']}/{p3['total']} passed")
    print(f"Phase 4  Integration tests execution:     {p4['passed']}/{p4['total']} passed")
    print()
    print("Reports written to: reports/")
    print("=" * 60)
 
    return results
 
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Agentic testing pipeline — triggered by a local git commit"
    )
    parser.add_argument(
        "requirements",
        default="requirements.md",
        help="Path to the feature requirements file (default: requirements.md)",
    )
    parser.add_argument(
        "--past-tests",
        default="tests/test_api.py",
        help="Path to existing tests for structure and better tests generation ",
    )
    parser.add_argument(
        "--docs",
        default="README.md",
        help="Path to project documentation",
    )
    parser.add_argument(
        "--template",
        default="tests/unit_test_template.py",
        help="Path to unit test template",
    )
 
    args = parser.parse_args()
 
    agent_coordinator(
        requirements_path  = args.requirements,
        past_tests         = args.past_tests,
        project_docs       = args.docs,
        template_to_follow = args.template,
    )
 