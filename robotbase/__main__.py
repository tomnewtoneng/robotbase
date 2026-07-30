"""Enable `python -m robotbase ...` so callers can invoke the CLI PATH-independently."""
from robotbase.cli import main

if __name__ == "__main__":
    main()
