"""
QuantTrade - ML tabanlı kantitatif alım-satım sistemi
Setup script
"""

from setuptools import setup, find_packages

setup(
    name="quanttrade",
    version="0.1.0",
    description="ML tabanlı kantitatif alım-satım sistemi - BIST100",
    author="QuantTrade Team",
    author_email="",
    url="https://github.com/aleynatasdemir/QuantTrade",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.11",
    install_requires=[
        "evds",
        "pandas",
        "python-dotenv",
        "toml",
        "numpy",
        "requests",
    ],
    extras_require={
        "dev": [
            "jupyter",
            "matplotlib",
            "pytest",
            "black",
            "flake8",
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
