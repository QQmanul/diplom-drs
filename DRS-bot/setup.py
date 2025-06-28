from setuptools import setup, find_packages

setup(
    name="drs-bot",
    version="1.0",
    packages=find_packages(),
    install_requires=[
        "python-telegram-bot",
        "aiohttp",
        "PyJWT",
        "signalrcore"
    ],
    python_requires=">=3.8",
) 