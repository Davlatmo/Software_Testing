#!/bin/sh

# .git/hooks/post-commit

#Theoretical part for self understanding since teh git hook is the core idea of 
# agentic test automation:
#The post-commit-hook.sh acts as an automation trigger. After every Git commit, 
#it starts the AI testing pipeline automatically. Within that pipeline, the 
#Validation Agent acts as pre commit quality gate by 
#verifying that requirements meet predefined criteria before test generation begins. 
#If the requirements are valid, the workflow proceeds to test generation, execution, 
#and integration testing.
#Thinking of it as:
# Git commit
#    |
# Post-commit hook
#    |
# Validation Agent -> quality check
#    |
# Test Generator
#    |
# Test Execution
                             
# Understanding of git coomit hook:
# A git hook is a script that git runs automatically at specific moments.
# This is a post commit hook, git runs it immediately after every
# successful "git commit" in this repository.
# We never call this script directly, git do it for us.

# How our git hook works:
# 1) Developer runs the command: git commit -m "add product search feature"
# 2) Git saves the commit
# 3) Git automatically runs this script
# 4) This script starts the agentic testing pipeline

#
# The file located in:
# Our project/.git/hooks/post-commit
# (the .git folder is hidden and is inside our project root)
#
# How to install it:
# Run the install_hook.py script we provide, or manually:
# cp post-commit-hook.sh .git/hooks/post-commit
# chmod +x .git/hooks/post-commit  -> makes it executable
#
#For windows:
# Git for Windows runs shell scripts through Git Bash.

echo ""
echo " Post commit hook triggered"
echo " Starting agentic testing pipeline....."
echo ""

#Finding python
if command -v python3 > /dev/null 2>&1; then
    PYTHON="python3"
elif command -v python > /dev/null 2>&1; then
    PYTHON="python"
else
    echo "ERROR: Python not found in path"
    echo "Make sure that Python is installed and added to path"
    exit 1
fi
 
echo "Using Python: $($PYTHON --version)"

#Finding our project root -> where our coordinator_agent.py lives
PROJECT_ROOT=$(git rev-parse --show-toplevel)
COORDINATOR="$PROJECT_ROOT/agent_coordinator.py"
REQUIREMENTS="$PROJECT_ROOT/requirements.md"
 
# Checking if the coordinator script exists
if [ ! -f "$COORDINATOR" ]; then
    echo "WARNING: agent_coordinator.py not found at $COORDINATOR"
    echo "Skipping agentic pipeline."
    exit 0
fi
 
# Checking if requirements file exists
if [ ! -f "$REQUIREMENTS" ]; then
    echo "WARNING: requirements.md not found at $REQUIREMENTS"
    echo "Create a requirements.md file to enable the pipeline."
    echo "Skipping agentic pipeline."
    exit 0
fi
 
# Running the pipeline
# We run it in the background so the commit doesn't block the
# developer waiting for the full pipeline to finish.
# The developer can continue working while tests run in the background.
# Output goes to pipeline.log so it doesn't occupy the terminal.
# Developer can check pipeline.log or wait for the summary.

cd "$PROJECT_ROOT"
 
LOG_FILE="$PROJECT_ROOT/pipeline.log" # the output of the git hook is going to this file
 
echo "Pipeline running in background, output: $LOG_FILE"
echo "Check pipeline.log or wait for the summary....."
echo ""
 
# Run pipeline in background, capture all output to log
$PYTHON "$COORDINATOR" \
    --requirements "$REQUIREMENTS" \
    --past-tests "tests/test_api.py" \
    --docs "README.md" \
    --template "tests/unit_test_template.py" \
    > "$LOG_FILE" 2>&1 &
 
PIPELINE_PID=$!
echo "Pipeline PID: $PIPELINE_PID"

# if we want the "commit" to "wait" for the pipeline then we uncomment these lines
# and vise versa if we want to wait for completion and show the summary we comment these lines
# echo ""
# echo "Pipeline finished. Last 20 lines of output:"
# tail -20 "$LOG_FILE"
 
exit 0
 