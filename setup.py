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
    # license="MIT", 
    install_requires = [],
    include_package_data=True,
    # packages=find_packages(include=['risk_adjustment_model', 'risk_adjustment_model.*']),
    # package_dirc={"": "risk_adjustment_model"},
    # package_data={"risk_adjustment_model/reference_data": ["*.yaml", "*.csv", "*.json", '*.txt']},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT Software License",
        "Operating System :: OS Independent"
    ])


# setup(
#     name = "an_example_pypi_project",
#     version = "0.0.4",
#     author = "Andrew Carter",
#     author_email = "andrewjcarter@gmail.com",
#     description = ("An demonstration of how to create, document, and publish "
#                                    "to the cheese shop a5 pypi.org."),
#     license = "BSD",
#     keywords = "example documentation tutorial",
#     url = "http://packages.python.org/an_example_pypi_project",
#     packages=['an_example_pypi_project', 'tests'],
#     long_description=read('README'),
#     classifiers=[
#         "Development Status :: 3 - Alpha",
#         "Topic :: Utilities",
#         "License :: OSI Approved :: BSD License",
#     ],
# )