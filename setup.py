"""
Setup script for peer-eval package.

Usage:
    pip install -e .           # Install in development mode
    pip install .              # Install from source
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = (
    requirements_file.read_text(encoding="utf-8").strip().split("\n")
    if requirements_file.exists()
    else []
)
# Filter out comments and empty lines
requirements = [
    line.strip()
    for line in requirements
    if line.strip() and not line.startswith("#")
]

setup(
    name="peer-eval",
    version="3.0.0",
    description="Contribution Factor Model v3.0 — Evaluate student contributions in collaborative projects",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Jefferson Silva",
    author_email="silva.o.jefferson@gmail.com",
    license="MIT",
    url="https://github.com/inteli-perf-eng/peer-eval",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "peer-eval=peer_eval.cli:cli",
        ],
    },
    keywords=[
        "contribution",
        "evaluation",
        "gitlab",
        "metrics",
        "collaboration",
        "student",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Education",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
)
