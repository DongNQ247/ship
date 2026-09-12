from setuptools import setup, find_packages

setup(
    name="ship-cli",
    version="0.1.0",
    description="Git-like secure file deployment CLI over SSH and rsync",
    packages=find_packages(),
    py_modules=["main"],
    entry_points={
        "console_scripts": [
            "ship = main:cli",
        ],
    },
)
