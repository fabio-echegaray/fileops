# Common Operations Involving Movie File IO
This is a package that tries to unify loading image files of microscopy data, 
with the option of locally caching the image retrieval.
It currently supports image loading using different frameworks (see libraries supported).
It can also export image stacks of data as volumetric scalars for software that uses VTK libraries for data manipulation such as Paraview.
The package is currently under active writing.

## Table of contents
* [Technologies](#technologies)
* [Setup](#setup)
* [Features](#features)
* [Status](#status)
* [Contact](#contact)
* [License](#license)

## Technologies
Has been tested with versions of Python 3.6 or greater. 
There are also some packages that this library depends on. 
For specifics, see requirements.txt.

## Setup
`git clone https://github.com/fabio-echegaray/fileops.git`
Then, on the working folder run: `pip install -r requirements.txt`
    

## Features
### Ability to write configuration files for volume export and movie rendering
The movie rendering feature works using another library that I have written (https://github.com/fabio-echegaray/movie-render).
It helps to programatically render different versions of the data.
See export.py for an example.
I'm currently working on the declarative grammar of this feature so to make it consistent .

### Libraries used
* Bioformats (OME files in general)
* Pycromanager (for images saved with Micro-Manager)
* Tifffile (for generic tiff files, for image series when they are stored as individual files in a folder)

### Formats currently supported
* ImageJ BiggTiff files using Pycromanager.
* MicroManager files .
  - Single stacks smaller than 4GBi using the Tifffile library.
  - Single stacks bigger than 4GBi using Pycromanager.
* Micro-Magellan files using the Tifffile library.
* Tiff files conforming to the OME-XML files using the Bioformats library.
* Volocity files using the Bioformats library.

### To-do list for development in the future:
* Create a function that decides wich library to use based on the format of the input file.
* Write test functions (maybe generate a repository of image files to test against?).
* Improve the egg-associated info for the installation of the package.

## Status
Project is active writing and _in progress_.

## Contact
Created by [@fabioechegaray](https://twitter.com/fabioechegaray)
* [fabio.echegaray@gmail.com](mailto:fabio.echegaray@gmail.com)
* [github](https://github.com/fabio-echegaray)
Feel free to contact me!

## License
    FileOps
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
