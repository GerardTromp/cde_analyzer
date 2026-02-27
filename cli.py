"""
CDE Analyzer CLI - Command Line Interface entry point.

This module serves as the pip-installable entry point for the cde-analyzer command.
It delegates to the main() function in cde_analyzer.py.
"""

import sys


def main():
    """
    Main entry point for the cde-analyzer CLI command.

    This function is called when users run:
        cde-analyzer <action> [arguments]

    After pip install, this becomes available as a console script.
    """
    try:
        # Import the actual main function from cde_analyzer.py
        # Using late import to ensure proper module loading
        from cde_analyzer import main as cde_main

        # Call the main function and return its exit code
        result = cde_main()

        # Return exit code if provided, otherwise 0 for success
        if result is not None:
            sys.exit(result)
        sys.exit(0)

    except KeyboardInterrupt:
        # Graceful exit on Ctrl-C without stack trace
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)  # Standard exit code for SIGINT
    except SystemExit:
        # Re-raise SystemExit (from argparse errors, etc.)
        raise
    except Exception as e:
        # Catch unexpected errors and show a cleaner message
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
