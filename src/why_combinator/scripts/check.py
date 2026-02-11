
import subprocess
import sys

def main():
    """Run mypy and pytest."""
    try:
        print("Running type checks (mypy)...")
        subprocess.check_call([sys.executable, "-m", "mypy", "src/why_combinator"])
        
        print("Running tests (pytest)...")
        subprocess.check_call([sys.executable, "-m", "pytest", "tests"])
        
        print("All checks passed!")
    except subprocess.CalledProcessError as e:
        print(f"Check failed with exit code {e.returncode}")
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
