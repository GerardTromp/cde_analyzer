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
    # Import the actual main function from cde_analyzer.py
    # Using late import to ensure proper module loading
    from cde_analyzer import main as cde_main

    # Call the main function and return its exit code
    result = cde_main()

    # Return exit code if provided, otherwise 0 for success
    if result is not None:
        sys.exit(result)
    sys.exit(0)


if __name__ == "__main__":
    main()
