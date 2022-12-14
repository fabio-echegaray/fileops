import setuptools

# with open("README.md", "r") as fh:
#     long_description = fh.read()

setuptools.setup(
    name='fileops',
    version='0.1',
    scripts=[],
    author="Fabio Echegaray",
    author_email="fabio.echegaray@gmail.com",
    description="A package that solves common file operations in biological data; "
                "including cached results, image loading (wrapping the bioformat library),"
                " and movie rendering programmatically from microscope data.",
    # long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/fabio-echegaray/fileops",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        ],
    )
