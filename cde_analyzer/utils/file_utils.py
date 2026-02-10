# File: utils/file_utils.py
"""
File validation utilities for graceful error handling.

Provides consistent error messages when files specified by users don't exist.
Also provides interrupt handling for graceful Ctrl-C handling.
"""

import sys
from functools import wraps
from pathlib import Path
from typing import Union, Callable, TypeVar

# Type variable for decorated function return type
F = TypeVar('F', bound=Callable)


def graceful_interrupt(func: F) -> F:
    """
    Decorator to handle KeyboardInterrupt gracefully in action run functions.

    Wraps the function to catch Ctrl-C and exit cleanly without stack traces.
    Use this on run_action functions in action modules.

    Example:
        @graceful_interrupt
        def run_action(args: Namespace):
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            print("\nInterrupted.", file=sys.stderr)
            sys.exit(130)  # Standard exit code for SIGINT
    return wrapper  # type: ignore


class FileNotFoundError(Exception):
    """Custom exception for file not found with user-friendly message."""
    pass


def require_file(path: Union[str, Path], description: str = "Input file") -> Path:
    """
    Validate that a file exists and return it as a Path object.

    Raises FileNotFoundError with a clear message including the exact path
    as specified by the user.

    Args:
        path: File path as string or Path object
        description: Description of what the file is for (used in error message)

    Returns:
        Path object for the validated file

    Raises:
        FileNotFoundError: If the file does not exist
    """
    p = Path(path) if isinstance(path, str) else path
    if not p.exists():
        raise FileNotFoundError(f"{description} does not exist: {path}")
    if not p.is_file():
        raise FileNotFoundError(f"{description} is not a file: {path}")
    return p


def require_directory(path: Union[str, Path], description: str = "Input directory") -> Path:
    """
    Validate that a directory exists and return it as a Path object.

    Args:
        path: Directory path as string or Path object
        description: Description of what the directory is for (used in error message)

    Returns:
        Path object for the validated directory

    Raises:
        FileNotFoundError: If the directory does not exist
    """
    p = Path(path) if isinstance(path, str) else path
    if not p.exists():
        raise FileNotFoundError(f"{description} does not exist: {path}")
    if not p.is_dir():
        raise FileNotFoundError(f"{description} is not a directory: {path}")
    return p


def check_file_exists(path: Union[str, Path], description: str = "File") -> bool:
    """
    Check if a file exists, printing an error message if not.

    Use this for quick validation at entry points where you want to
    exit immediately on failure.

    Args:
        path: File path to check
        description: Description for error message

    Returns:
        True if file exists, False otherwise (also prints error to stderr)
    """
    p = Path(path) if isinstance(path, str) else path
    if not p.exists():
        print(f"error: {description} does not exist: {path}", file=sys.stderr)
        return False
    if not p.is_file():
        print(f"error: {description} is not a file: {path}", file=sys.stderr)
        return False
    return True


def exit_if_missing(path: Union[str, Path], description: str = "Input file", exit_code: int = 2) -> Path:
    """
    Validate file exists or exit with error message.

    Convenience function for CLI entry points that should exit immediately
    on missing files.

    Args:
        path: File path to check
        description: Description for error message
        exit_code: Exit code to use (default 2 for CLI argument errors)

    Returns:
        Path object if file exists

    Note:
        Calls sys.exit() if file does not exist - does not return in that case.
    """
    p = Path(path) if isinstance(path, str) else path
    if not p.exists():
        print(f"error: {description} does not exist: {path}", file=sys.stderr)
        sys.exit(exit_code)
    if not p.is_file():
        print(f"error: {description} is not a file: {path}", file=sys.stderr)
        sys.exit(exit_code)
    return p
