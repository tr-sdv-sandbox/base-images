from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="sdv-state-machine",
    version="0.1.0",
    author="SDV Team",
    description="State machine library with dual observability for SDV applications",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourorg/sdv-state-machine",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "prometheus-client>=0.16.0",
        "pyyaml>=6.0",
        "typing-extensions>=4.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0",
            "black>=23.0",
            "mypy>=1.0",
            "ruff>=0.0.270",
        ],
        "kuksa": [
            "kuksa-client>=0.4.0",
        ],
        "redis": [
            "redis>=4.5.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "sm-tool=sdv_state_machine.cli:main",
        ],
    },
)