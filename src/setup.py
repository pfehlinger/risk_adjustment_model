from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(packages=find_packages(),
    name="risk_adjustment_model",
    version="0.1.0",
    description="risk_adjustment_model is a Python implementation of healthcare risk adjustment models",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Phil Fehlinger",
    author_email="pjfehlinger@gmail.com",
    url="https://github.com/pfehlinger/risk_adjustment_model",
    license="MIT", 
    install_requires = [],
    include_package_data=True,
    package_dirc={"": "src"},
    package_data={"reference_data": ["*.yaml", "*.csv", "*.json", '*.txt']},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT Software License",
        "Operating System :: OS Independent"
    ])