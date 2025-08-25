.. image:: https://github.com/mapchete/mapchete/blob/main/logo/mapchete_grey.svg

Tile-based geodata processing.

.. image:: https://img.shields.io/pypi/v/mapchete.svg
  :target: https://pypi.org/project/mapchete/

.. image:: https://img.shields.io/conda/v/conda-forge/mapchete
  :target: https://anaconda.org/conda-forge/mapchete

.. image:: https://img.shields.io/pypi/l/mapchete.svg
  :target: https://github.com/mapchete/mapchete/blob/main/LICENSE

.. image:: https://img.shields.io/github/actions/workflow/status/mapchete/mapchete/python-package.yml?label=tests
  :target: https://github.com/mapchete/mapchete/actions

.. image:: https://codecov.io/gh/mapchete/mapchete/branch/main/graph/badge.svg?token=aOracso0OQ
  :target: https://codecov.io/gh/mapchete/mapchete

.. image:: https://img.shields.io/github/repo-size/mapchete/mapchete
  :target: https://github.com/mapchete/mapchete

.. image:: https://readthedocs.org/projects/mapchete/badge/?version=stable
  :target: http://mapchete.readthedocs.io/en/stable/?badge=stable

mapchete is a Python library for processing large geospatial raster and vector datasets. It reads and writes data in a tiled fashion, allowing you to run your algorithms on data that is too large to fit into memory, and it can process your data in parallel.

You define the data inputs, output format, and the geographic extent, and mapchete handles the rest. Your custom Python code is then applied to each tile, enabling complex processing workflows on a massive scale.


Key Features
------------

* 🗺️ **Process Large Datasets**: Work with massive raster and vector data without memory issues using a tile-based, out-of-core approach.
* ⚡ **Parallel Processing**: Automatically run computations on multiple CPU cores to significantly speed up your workflows.
* ⚙️ **Simple Configuration**: Separate your processing logic from your data configuration using easy-to-read ``.mapchete`` files.
* 🐍 **Pythonic API**: Use mapchete directly from the command line or as a library in your own Python applications.
* 🔌 **Flexible & Extensible**: Natively supports common raster and vector formats (e.g., GeoTIFF, GeoPackage). Easily add your own drivers for custom formats.
* 🖥️ **Interactive Inspection**: Instantly visualize your processing inputs and results on a browser map with the built-in ``serve`` command.


Installation
------------

We highly recommend installing mapchete and its dependencies from PyPI using ``pip``:

.. code-block:: bash

    pip install mapchete

Alternatively, it can be installed from the ``conda-forge`` channel using ``conda`` or ``mamba``:

.. code-block:: bash

    mamba install -c conda-forge mapchete


Quickstart: Generate a Hillshade
--------------------------------

A great way to get started with mapchete is to generate a hillshade from a Digital Elevation Model (DEM). A hillshade creates a 3D-like relief effect by modeling how the surface would be illuminated by a light source. This example uses the modern process syntax where inputs and custom parameters are defined as typed function arguments.

You can find free DEM data for your area of interest from many sources, such as the `Copernicus DEM <https://registry.opendata.aws/copernicus-dem/>`_.

**1. Create a mapchete configuration file.**

This file now includes a ``process_parameters`` section to control the hillshade's appearance. These values are passed directly to your Python script. Save this file as ``hillshade.mapchete``:

.. code-block:: yaml

    # The Python file containing the processing algorithm.
    process: create_hillshade.py
    # Note: there is a predefined process available, so you don't need to write your own hillshade process
    # process: mapchete.processes.hillshade

    # The CRS and grid definition for the output.
    pyramid:
      grid: geodetic

    # Define the zoom levels to process.
    zoom_levels:
      min: 7
      max: 12

    # User-defined parameters passed to the 'execute()' function.
    process_parameters:
      azimuth: 315
      altitude: 45
      z_factor: 2.0
      scale: 1.0

    # Define the input data.
    # The key 'dem' will be the name of the variable passed to the execute() function.
    input:
      dem: path/to/your/dem.tif

    # Define the output format and location.
    output:
      path: ./hillshade_output
      format: PNG
      bands: 3
      dtype: uint8  # Hillshade is an 8-bit grayscale image

**2. Create your processing script.**

The ``execute`` function now accepts the hillshade parameters from the config file as arguments. It also uses ``raise Empty``, the recommended way to tell mapchete that a tile has no data and should be skipped. Save this file as ``create_hillshade.py``:

.. code-block:: python

    import numpy as np
    from mapchete import Empty, RasterInput
    # mapchete has a built-in helper for this common task!
    from mapchete.processes.hillshade import hillshade

    def execute(
        dem: RasterInput,
        azimuth: int = 315,
        altitude: int = 45,
        z_factor: float = 1.0,
        scale: float = 1.0,
    ) -> np.ndarray:
        """
        Generate a hillshade from an input DEM tile.
        The function arguments are automatically populated from the .mapchete file.
        """
        # If the input tile is empty, raise an Empty exception to skip it.
        if dem.is_empty():
            raise Empty

        # Read the elevation data and generate the hillshade with the given parameters.
        return hillshade(
            dem.read(),
            azimuth=azimuth,
            altitude=altitude,
            z_factor=z_factor,
            scale=scale
        )

**3. Run the process.**

To run the process, use the ``execute`` subcommand. You can edit the values in ``hillshade.mapchete`` and re-run the process to see how the lighting changes. Make sure to use the ``--overwrite`` flag if you want to overwrite existing output.

.. code-block:: bash

    mapchete execute hillshade.mapchete

**4. View the output.**

Use the ``serve`` command to inspect your results on an interactive map.

.. code-block:: bash

    mapchete serve hillshade.mapchete


Documentation
-------------

For more detailed information, tutorials, and the API reference, please visit our full documentation at:
`mapchete.readthedocs.io <https://mapchete.readthedocs.io/>`_


Contributing
------------

Contributions are welcome! We are happy to receive bug reports, feature requests, or pull requests. Please have a look at our `CONTRIBUTING.rst <CONTRIBUTING.rst>`_ file for guidelines on how to get started.


License
-------

This project is licensed under the `MIT License <LICENSE>`_.
