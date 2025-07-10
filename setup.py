from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ticketmaster-resale-notify",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Monitor Ticketmaster for resale tickets and get notified when available",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/ticketmaster-resale-notify",
    packages=find_packages(),
    package_data={
        "ticketmaster_resale_notify": ["*.pyi", "py.typed"],
    },
    install_requires=[
        "playwright>=1.32.0",
        "httpx>=0.24.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.20.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "mypy>=1.0.0",
            "types-requests>=2.28.0",
            "types-python-dateutil>=2.8.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "ticketmonitor=ticketmaster_resale_notify.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Utilities",
    ],
    python_requires=">=3.8",
)
