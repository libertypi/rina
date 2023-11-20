from setuptools import setup, find_packages

setup(
    name="rina",
    version="0.1",
    description="All-in-One Japanese AV Toolbox",
    url="https://github.com/libertypi/rina",
    author="David Pi",
    author_email="libertypi@gmail.com",
    license="GPLv3",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Everyone",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    keywords="jav, scraper",
    install_requires=["requests", "lxml"],
    python_requires=">=3.6",
    packages=find_packages(include=["rina"]),
    package_data={"rina": ["*.json"]},
    entry_points={"console_scripts": ["rina=rina.__main__:main"]},
)
