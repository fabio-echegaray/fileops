# Common Operations Involving Microscopy Data
This package makes easy to replicate figures and movies from microscopy data from configuration files.
It unifies loading image files of the data, with the option of locally caching the image retrieval, and it exports the data into several file formats.
It currently supports image loading using different frameworks (see formats currently supported).
It can also export image stacks of data as volumetric scalars using the OpenVDB format or VTK format for use in data manipulation and visualization software such as Paraview or Blender.
The package is currently under active writing.

## Table of contents
* [Documentation](#documentation)
* [Setup](#setup)
* [Features](#features)
* [Status](#status)
* [Contact](#contact)
* [License](#license)


## Documentation
See documentation [here](docs/main.md)

## Setup
The package has been tested with versions of Python 3.9 and greater. 
The installation script will complain if either Numpy of Wheels is not installed
Thus, make sure you have those dependencies installed first, or alternatively run: `pip install wheels numpy && pip install imgfileops`
    
### Main libraries used
* [BioIO](https://github.com/bioio-devs/bioio) (we use it for OME files in general)
* [Pycromanager](https://github.com/micro-manager/pycro-manager) (for images saved with Micro-Manager)
* [Tifffile](https://github.com/cgohlke/tifffile) (for generic tiff files, for image series when they are stored as individual files in a folder)

The package also uses other libraries.
For a complete list, check the dependencies variable of the pyproject.toml file.

## Features
### Ability to write configuration files for volume export and movie rendering
This feature helps to programmatically render different versions of the data.
For example, it is possible to export the data in volumetric formats using either OpenVDB or the VTK library. 
Similarly, it can render the data in a movie format using each channel separately, or in a composite image.
For more details, see the project that consumes these configuration files: https://github.com/fabio-echegaray/movie-render.
I'm currently working on the declarative grammar of this feature to make it consistent.

### Formats currently supported
* ImageJ BiggTiff files using Pycromanager.
* MicroManager files .
  - Single stacks smaller than 4GBi using the Tifffile library.
  - Single stacks bigger than 4GBi using Pycromanager.
* Micro-Magellan files using the Tifffile library.
* Tiff files conforming to the OME-XML files using the BioIO library.
* Volocity files using the BioIO library.

### To-do list for development in the future:
* Keep writting test functions (maybe generate a repository of image files to test against?).
* Write examples of file export.
* Improve exporting volumetric files and the related syntax in the configuration files.

## Status
Project is active writing and _in progress_.

## Contact
Created by [@fabioechegaray](https://twitter.com/fabioechegaray)
* [fabio.echegaray@gmail.com](mailto:fabio.echegaray@gmail.com)
* [GitHub](https://github.com/fabio-echegaray)
Feel free to contact me!

## License
    ImgFileOps
    Copyright (C) 2021-2025  Fabio Echegaray

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
