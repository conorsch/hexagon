"""Enable `python -m hexagon`, mirroring the installed `hexagon` console script.

Useful for running the CLI from a source checkout (e.g. the integration tests)
without installing the package.
"""

from hexagon.cli import main

if __name__ == "__main__":
    main()
