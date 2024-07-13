# Common Operations Involving Movie File IO
This package unifies loading image files of microscopy data, 
with the option of locally caching the image retrieval.
It currently supports image loading using different frameworks (see formats currently supported).
It can also export image stacks of data as volumetric scalars using the OpenVDB format or VTK format for use in data manipulation and visualization software such as Paraview or Blender.
The package is currently under active writing.

## Table of contents
* [Setup](#setup)
* [Features](#features)
* [Status](#status)
* [Contact](#contact)
* [License](#license)


## Setup
The package has been tested with versions of Python 3.6 or greater. 
The installation script will complain if either Numpy of Wheels is not installed
Thus, make sure you have those dependencies installed first, or alternatively run: `pip install wheels numpy && pip install imgfileops`
    
### Libraries used
* Bioformats (OME files in general)
* Pycromanager (for images saved with Micro-Manager)
* Tifffile (for generic tiff files, for image series when they are stored as individual files in a folder)

## Features
### Ability to write configuration files for volume export and movie rendering
This feature helps to programmatically render different versions of the data.
For example, it is possible to render each channel separately, or in a composite image;
for more details, see the project that consumes these configuration files: https://github.com/fabio-echegaray/movie-render.
I'm currently working on the declarative grammar of this feature to make it consistent.

### Formats currently supported
* ImageJ BiggTiff files using Pycromanager.
* MicroManager files .
  - Single stacks smaller than 4GBi using the Tifffile library.
  - Single stacks bigger than 4GBi using Pycromanager.
* Micro-Magellan files using the Tifffile library.
* Tiff files conforming to the OME-XML files using the Bioformats library.
* Volocity files using the Bioformats library.

### To-do list for development in the future:
* Create a function that decides wichh library to use based on the format of the input file.
* Write test functions (maybe generate a repository of image files to test against?).
* Avoid the legacy library `java-bioformats`.
* Write examples of file export.

## Status
Project is active writing and _in progress_.

## Contact
Created by [@fabioechegaray](https://twitter.com/fabioechegaray)
* [fabio.echegaray@gmail.com](mailto:fabio.echegaray@gmail.com)
* [github](https://github.com/fabio-echegaray)
Feel free to contact me!

## License
    ImgFileOps
    Copyright (C) 2021-2023  Fabio Echegaray

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
