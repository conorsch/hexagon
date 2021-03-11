import setuptools


exclude = ["tests"]


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

version = "0.1.0"


if __name__ == "__main__":
    setuptools.setup(
        name="hexagon",
        author="Conor Schaefer",
        version=version,
        author_email="conor@freedom.press",
        description="Experimental CLI for managing Qubes OS VMs",
        long_description=long_description,
        long_description_content_type="text/markdown",
        license="GPLv3+",
        packages=setuptools.find_packages(exclude=exclude),
        python_requires=">=3.5",
        url="https://github.com/conorsch/hexagon",
        classifiers=[
            "Development Status :: 3 - Alpha",
            "Programming Language :: Python :: 3",
            "Topic :: Software Development :: Libraries :: Python Modules",
            "License :: OSI Approved :: " "GNU General Public License v3 or later (GPLv3+)",
            "Intended Audience :: Developers",
            "Operating System :: OS Independent",
        ],
        scripts=["bin/hexagon"],
    )
