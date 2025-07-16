"""Setup script for AI Sales Evaluation Arena."""

from setuptools import setup, find_packages

# Read the README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="ai-sales-eval-arena",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="AI-powered tournament framework for evaluating sales pitch performances",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-repo/ai-sales-eval-arena",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "flake8>=6.1.0",
            "mypy>=1.7.0",
            "pre-commit>=3.5.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "arena=ai_sales_eval_arena.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "ai_sales_eval_arena": ["templates/*.html", "static/*"],
    },
) 