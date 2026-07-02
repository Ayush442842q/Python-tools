#!/usr/bin/env python3
"""
Git Merge Conflict Simulator
An educational CLI tool that generates a real local Git merge conflict in a temporary
directory and guides developers step-by-step through understanding conflict markers
and completing the merge resolution process.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

# Color codes
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"


def run_git(args, cwd):
    """Executes a git command in the specified directory and returns stdout/stderr."""
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return result


def check_git_installed():
    """Checks if git is installed and available in the system path."""
    try:
        subprocess.run(["git", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False


class ConflictSimulator:
    def __init__(self, use_system_temp=True):
        self.use_system_temp = use_system_temp
        self.repo_dir = None
        self.file_name = "project_report.txt"

    def setup_repo(self):
        """Creates a temporary repository and sets up the conflict scenario."""
        if self.use_system_temp:
            self.repo_dir = tempfile.mkdtemp(prefix="git-conflict-sim-")
        else:
            self.repo_dir = os.path.abspath("./git-conflict-sim-temp")
            if os.path.exists(self.repo_dir):
                shutil.rmtree(self.repo_dir)
            os.makedirs(self.repo_dir)

        print(f"\n{CYAN}* Initializing temporary Git repository in:{RESET} {self.repo_dir}")
        
        # git init
        run_git(["init"], self.repo_dir)
        
        # Set dummy user configuration for this repository
        run_git(["config", "user.name", "Simulator Admin"], self.repo_dir)
        run_git(["config", "user.email", "admin@sim.local"], self.repo_dir)
        
        # Create base file
        filepath = os.path.join(self.repo_dir, self.file_name)
        with open(filepath, "w") as f:
            f.write(
                "=========================================\n"
                "ANNUAL PROJECT SURVEY REPORT 2026\n"
                "=========================================\n"
                "\n"
                "Introduction:\n"
                "This document summarizes project survey findings.\n"
                "\n"
                "Key Priority Area:\n"
                "Priority level is set to LOW for all internal systems.\n"
                "\n"
                "Conclusion:\n"
                "Project deliverables are on track.\n"
            )
            
        # First commit on main
        run_git(["add", self.file_name], self.repo_dir)
        # Rename branch to main just in case default is master
        run_git(["checkout", "-b", "main"], self.repo_dir)
        run_git(["commit", "-m", "Initial commit: Add project survey outline"], self.repo_dir)

        # Create and switch to feature branch
        print(f"{CYAN}* Creating feature-branch and modifying key priority area...{RESET}")
        run_git(["checkout", "-b", "feature-branch"], self.repo_dir)
        
        # Modify file on feature branch
        with open(filepath, "w") as f:
            f.write(
                "=========================================\n"
                "ANNUAL PROJECT SURVEY REPORT 2026\n"
                "=========================================\n"
                "\n"
                "Introduction:\n"
                "This document summarizes project survey findings.\n"
                "\n"
                "Key Priority Area:\n"
                "Priority level is set to HIGH for internal security audit and cloud migration.\n"
                "\n"
                "Conclusion:\n"
                "Project deliverables are on track.\n"
            )
        run_git(["add", self.file_name], self.repo_dir)
        run_git(["commit", "-m", "Feature: Upgrade priority area to HIGH for security"], self.repo_dir)

        # Checkout main and modify the same line differently
        print(f"{CYAN}* Returning to main branch and making conflicting modifications...{RESET}")
        run_git(["checkout", "main"], self.repo_dir)
        
        with open(filepath, "w") as f:
            f.write(
                "=========================================\n"
                "ANNUAL PROJECT SURVEY REPORT 2026\n"
                "=========================================\n"
                "\n"
                "Introduction:\n"
                "This document summarizes project survey findings.\n"
                "\n"
                "Key Priority Area:\n"
                "Priority level is set to MEDIUM focusing exclusively on database optimization.\n"
                "\n"
                "Conclusion:\n"
                "Project deliverables are on track.\n"
            )
        run_git(["add", self.file_name], self.repo_dir)
        run_git(["commit", "-m", "Main: Set priority to MEDIUM for databases"], self.repo_dir)

    def print_conflict_file(self):
        """Displays the contents of the conflicted file with highlighted markers."""
        filepath = os.path.join(self.repo_dir, self.file_name)
        if not os.path.exists(filepath):
            print(f"{RED}Error: File {self.file_name} does not exist.{RESET}")
            return
            
        print(f"\n{BOLD}--- Contents of {self.file_name} ---{RESET}")
        with open(filepath, "r") as f:
            for line in f:
                if line.startswith("<<<<<<<"):
                    print(f"{RED}{line.strip()}   <-- Start of changes on current branch (main/ours){RESET}")
                elif line.startswith("======="):
                    print(f"{YELLOW}{line.strip()}   <-- Divider between changes{RESET}")
                elif line.startswith(">>>>>>>"):
                    print(f"{GREEN}{line.strip()}   <-- End of changes on incoming branch (feature-branch/theirs){RESET}")
                else:
                    print(line.strip())
        print(f"{BOLD}----------------------------------{RESET}\n")

    def run_simulation(self):
        """Walks the user through the interactive merge conflict resolution steps."""
        self.setup_repo()
        
        print(f"\n{BOLD}=== STEP 1: Trigger the Merge Conflict ==={RESET}")
        print("We are on branch 'main'. We will attempt to merge 'feature-branch'.")
        print(f"Executing: {CYAN}git merge feature-branch{RESET}...")
        
        merge_res = run_git(["merge", "feature-branch"], self.repo_dir)
        print(merge_res.stdout)
        print(merge_res.stderr)
        
        if merge_res.returncode == 0:
            print(f"{RED}Failed to create conflict! Git merged the files automatically.{RESET}")
            self.cleanup()
            return
            
        print(f"{YELLOW}Conflict triggered successfully!{RESET} Notice the message:")
        print(f"  {RED}CONFLICT (content): Merge conflict in {self.file_name}{RESET}")
        print("  Automatic merge failed; fix conflicts and then commit the result.")

        input(f"\nPress Enter to view the conflict markers in {self.file_name}...")

        print(f"\n{BOLD}=== STEP 2: Understanding Conflict Markers ==={RESET}")
        print("Git has modified the file to show you both versions of the conflicting code.")
        self.print_conflict_file()
        
        print("Legend:")
        print(f"  {RED}<<<<<<< HEAD{RESET} : Start of your local changes (on 'main').")
        print(f"  {YELLOW}======={RESET} : Divider separating local changes from incoming changes.")
        print(f"  {GREEN}>>>>>>> feature-branch{RESET} : End of incoming changes (from 'feature-branch').")

        while True:
            print(f"\n{BOLD}=== STEP 3: Resolve the Conflict ==={RESET}")
            print("Select how you want to resolve this conflict:")
            print(f" 1. {CYAN}Keep Main's version{RESET} (Priority: MEDIUM)")
            print(f" 2. {GREEN}Keep Feature branch's version{RESET} (Priority: HIGH)")
            print(f" 3. {YELLOW}Keep BOTH versions combined{RESET}")
            print(f" 4. {BOLD}Resolve manually{RESET} (I will edit the file myself directly on disk)")
            print(f" 5. View conflict file again")
            
            choice = input("\nEnter choice (1-5): ").strip()
            
            filepath = os.path.join(self.repo_dir, self.file_name)
            
            if choice == "1":
                # Keep Main's version
                resolved_content = (
                    "=========================================\n"
                    "ANNUAL PROJECT SURVEY REPORT 2026\n"
                    "=========================================\n"
                    "\n"
                    "Introduction:\n"
                    "This document summarizes project survey findings.\n"
                    "\n"
                    "Key Priority Area:\n"
                    "Priority level is set to MEDIUM focusing exclusively on database optimization.\n"
                    "\n"
                    "Conclusion:\n"
                    "Project deliverables are on track.\n"
                )
                with open(filepath, "w") as f:
                    f.write(resolved_content)
                print(f"\n{GREEN}File updated to Keep Main's version.{RESET}")
                break
                
            elif choice == "2":
                # Keep Feature's version
                resolved_content = (
                    "=========================================\n"
                    "ANNUAL PROJECT SURVEY REPORT 2026\n"
                    "=========================================\n"
                    "\n"
                    "Introduction:\n"
                    "This document summarizes project survey findings.\n"
                    "\n"
                    "Key Priority Area:\n"
                    "Priority level is set to HIGH for internal security audit and cloud migration.\n"
                    "\n"
                    "Conclusion:\n"
                    "Project deliverables are on track.\n"
                )
                with open(filepath, "w") as f:
                    f.write(resolved_content)
                print(f"\n{GREEN}File updated to Keep Feature's version.{RESET}")
                break
                
            elif choice == "3":
                # Keep Both
                resolved_content = (
                    "=========================================\n"
                    "ANNUAL PROJECT SURVEY REPORT 2026\n"
                    "=========================================\n"
                    "\n"
                    "Introduction:\n"
                    "This document summarizes project survey findings.\n"
                    "\n"
                    "Key Priority Area:\n"
                    "Priority level is set to MEDIUM focusing exclusively on database optimization,\n"
                    "and HIGH for internal security audit and cloud migration.\n"
                    "\n"
                    "Conclusion:\n"
                    "Project deliverables are on track.\n"
                )
                with open(filepath, "w") as f:
                    f.write(resolved_content)
                print(f"\n{GREEN}File updated to combine both priority settings.{RESET}")
                break
                
            elif choice == "4":
                print(f"\n{YELLOW}* Please open the file in your preferred editor:{RESET}")
                print(f"  {filepath}")
                print("  Remove conflict markers and keep the lines you want.")
                input("\nPress Enter here after you have saved and closed the file...")
                # Verify that conflict markers are gone
                with open(filepath, "r") as f:
                    content = f.read()
                if "<<<<<<<" in content or "=======" in content or ">>>>>>>" in content:
                    print(f"{RED}Warning: Conflict markers are still present in the file! Please edit again.{RESET}")
                else:
                    print(f"{GREEN}Confirmed: Conflict markers removed successfully!{RESET}")
                    break
                    
            elif choice == "5":
                self.print_conflict_file()
            else:
                print(f"{RED}Invalid choice. Please enter 1-5.{RESET}")

        print(f"\n{BOLD}=== STEP 4: Staging and Completing the Merge ==={RESET}")
        print("Now that the conflict has been resolved, we must stage the file.")
        print(f"Executing: {CYAN}git add {self.file_name}{RESET}...")
        add_res = run_git(["add", self.file_name], self.repo_dir)
        
        status_res = run_git(["status"], self.repo_dir)
        print(f"\n{BOLD}Git Status Output:{RESET}")
        print(status_res.stdout)

        print("The file is staged. Now we finalize the merge by committing.")
        print(f"Executing: {CYAN}git commit -m \"Merge branch 'feature-branch' into main\"{RESET}...")
        commit_res = run_git(["commit", "-m", "Merge branch 'feature-branch' into main"], self.repo_dir)
        print(commit_res.stdout)
        
        # Verify clean tree
        final_status = run_git(["status"], self.repo_dir)
        if "nothing to commit, working tree clean" in final_status.stdout:
            print(f"\n{GREEN}{BOLD}★ MERGE SUCCESSFUL!{RESET} The repository is now clean and fully merged.")
            # Show log
            log_res = run_git(["log", "--oneline", "-n", "3", "--graph"], self.repo_dir)
            print(f"\n{BOLD}Recent Commit Graph:{RESET}")
            print(log_res.stdout)
        else:
            print(f"\n{RED}Merge not completed properly. Status details:{RESET}")
            print(final_status.stdout)

        input(f"\nPress Enter to clean up and delete the temporary repo...")
        self.cleanup()

    def cleanup(self):
        """Removes the temporary repository folder."""
        if self.repo_dir and os.path.exists(self.repo_dir):
            print(f"{CYAN}* Cleaning up temporary files...{RESET}")
            shutil.rmtree(self.repo_dir)
            print(f"{GREEN}Done!{RESET}")


def main():
    parser = argparse.ArgumentParser(description="Git Merge Conflict Simulator & Interactive Tutorial")
    parser.add_argument("--local", action="store_true", help="Create the temp repository in the current folder instead of system temp")
    args = parser.parse_args()

    if not check_git_installed():
        print(f"{RED}Error: Git is not installed or not found in system PATH. Cannot run simulation.{RESET}")
        sys.exit(1)

    print(f"{BOLD}================================================={RESET}")
    print(f"{BOLD}      GIT MERGE CONFLICT SIMULATOR & TUTORIAL    {RESET}")
    print(f"{BOLD}================================================={RESET}")
    print("This utility simulates a real-life Git merge conflict locally and")
    print("explains conflict markers, file states, and how to successfully merge.")
    
    sim = ConflictSimulator(use_system_temp=not args.local)
    try:
        sim.run_simulation()
    except KeyboardInterrupt:
        print(f"\n{RED}Simulation interrupted. Cleaning up...{RESET}")
        sim.cleanup()
        sys.exit(1)


if __name__ == "__main__":
    main()
