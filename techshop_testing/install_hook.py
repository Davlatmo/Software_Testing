"""
install_hook.py installs the post commit git hook

 what it does:
 Copies post-commit-hook.sh to the .git/hooks/post-commit folder (that is hidden) 
 inside our project and makes it executable so git runs it after every commit.
 
How to run it:
    python install_hook.py
 
we run it once" from project root. After that, every
"git commit" automatically triggers the agentic pipeline.
 
We need this script because:
* The .git folder is hidden and managed by git.
* We cannot by ourselves commit files inside .git (git ignores it).
* So we provide this installer that copies the hook into into our folder.
* Every developer on the team runs this once after cloning.
"""
import os
import sys
import shutil
import stat

def install_hook():
# Step1: Finding the .git/hooks directory
# Walk up from current directory to find the .git folder
    current = os.path.abspath(".")
    git_dir = None

    for _ in range(10):  
        candidate = os.path.join(current, ".git")
        if os.path.isdir(candidate):
            git_dir = candidate
            break
        parent = os.path.dirname(current)
        if parent == current: 
            break
        current = parent
 
    if not git_dir:
        print("Error: Couldn't find a .git directory.")
        print("Make sure you are inside a git repository.")
        print("Run: git init (if you haven't initialised git yet)")
        sys.exit(1)
 
    hooks_dir = os.path.join(git_dir, "hooks")
    os.makedirs(hooks_dir, exist_ok=True)
 
    print(f"Found .git directory: {git_dir}")
    print(f"Hooks directory: {hooks_dir}")

    # Step2: Finding post-commit-hook.sh
    #The hook source file lives next to this install script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    source = os.path.join(script_dir, "post-commit-hook.sh")
 
    if not os.path.exists(source):
        print(f"ERROR: post-commit-hook.sh not found at: {source}")
        sys.exit(1)

    # Step3: Checking if a hook already exists
    destination = os.path.join(hooks_dir, "post-commit")
 
    if os.path.exists(destination):
        print(f"\nA post-commit hook already exists at:\n  {destination}")
        answer = input("Overwrite it? (y/n): ").strip().lower()
        if answer != "y":
            print("Installation cancelled.")
            sys.exit(0)

    #Step4: Copy the hook
    shutil.copy2(source, destination)
    print(f"\nHook installed: {destination}")

    # Step5: Make it executable (required on Mac or Linux)
    # On Windows this has no effect but doesn't hurt
    current_mode = os.stat(destination).st_mode
    os.chmod(destination, current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print("Permissions set: executable")  

    # Step6: Verifying the pipeline files exist
    required_files = [
        "agent_coordinator.py",
        "agents.py",
        "base_agent.py",
        "Tools.py",
        "requirements.md",
        "README.md",
        "tests/unit_test_template.py",
    ]
 
    print("\nChecking required pipeline files......")
    all_ok = True
 
    for f in required_files:
        path = os.path.join(script_dir, f)
        if os.path.exists(path):
            print(f"All required files exist {f}")
        else:
            print(f"Some required files doesn't exist{f} -> MISSING")
            all_ok = False

    #Installation is done
    print()
    if all_ok:
        print("=" * 50)
        print("Installation complete!")
        print("=" * 50)
        print()
        print("What happens now:")
        print("1) We make changes to our code")
        print("2) We run:  git add  and then  git commit -m '...'")
        print("3) The pipeline starts automatically in the background")
        print("4) Reports appear in the reports/ folder")
        print("5) We can watch progress in: pipeline.log")
        print()
        print("To watch the pipeline live:")
        print("Windows: Get-Content pipeline.log -Wait")
        print("Mac/Linux: tail -f pipeline.log")
    else:
        print("=" * 50)
        print("Installation complete with warnings.")
        print("=" * 50)
        print()
        print("Some required files are missing (which we mentioned above).")
        print("The hook is installed but the pipeline may fail.")
        print("Create the missing files before making a commit.")
 
 
if __name__ == "__main__":
    install_hook()
 