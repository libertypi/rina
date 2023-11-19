from setuptools import setup, find_packages

setup(
    name="rina",
    version="0.1",
    description="The Ultimate AV Helper",
    url="https://github.com/libertypi/avinfo",
    author="David Pi",
    author_email="libertypi@gmail.com",
    license="MIT",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Everyone",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
    keywords="jav, scraper",
    install_requires=["requests", "lxml"],
    python_requires=">=3.6",
    packages=find_packages(include=["avinfo"]),
    package_data={"rina": ["*.txt", "*.json"]},
    entry_points={"console_scripts": ["rina=rina.__main__:main"]},
)
