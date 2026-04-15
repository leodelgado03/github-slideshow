from setuptools import setup, find_packages

setup(
    name="credit-analysis",
    version="1.0.0",
    description="Sistema de Análise de Emissores de Crédito Privado",
    packages=find_packages(),
    install_requires=[
        "yfinance>=0.2.36",
        "sqlalchemy>=2.0.0",
        "rich>=13.7.0",
        "requests>=2.31.0",
        "pandas>=2.1.0",
        "python-dateutil>=2.8.2",
        "feedparser>=6.0.11",
        "click>=8.1.7",
        "tabulate>=0.9.0",
    ],
    entry_points={
        "console_scripts": [
            "credit-analysis=credit_analysis.main:main",
        ],
    },
    python_requires=">=3.10",
    package_data={
        "credit_analysis": ["data/*.json"],
    },
)
