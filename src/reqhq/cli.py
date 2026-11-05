import argparse

from reqhq import __version__


def main() -> None:
    parser = argparse.ArgumentParser(prog="reqhq", description="Agentic specification refinement")
    parser.add_argument("--version", action="version", version=f"reqhq {__version__}")
    parser.parse_args()
    parser.print_help()


if __name__ == "__main__":
    main()
