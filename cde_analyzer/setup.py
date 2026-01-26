#!/usr/bin/env python
"""
Minimal setup.py for PEP 660 editable install compatibility.

All configuration is in pyproject.toml. This file exists only as a fallback
for build tools that don't fully support PEP 660 (editable installs via
pyproject.toml alone).
"""
from setuptools import setup

if __name__ == "__main__":
    setup()
