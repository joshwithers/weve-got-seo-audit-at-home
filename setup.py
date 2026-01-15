"""
Setup script for SEO Audit Engine.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="seo-audit-engine",
    version="0.2.0",
    author="Your Name",
    description="Local-first SEO website audit tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/seo-audit-engine",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Internet :: WWW/HTTP :: Site Management",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.11",
    install_requires=[
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
        "click>=8.1.0",
        "urllib3>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "audit=audit_engine.cli:cli",
        ],
    },
)
