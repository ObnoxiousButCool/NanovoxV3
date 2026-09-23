"""Run the whole pipeline: two source documents in, data.js out.

    Code/Backend/.venv/Scripts/python.exe Prototype/tools/build.py

Stages run in order and each writes an intermediate into tools/build/, so a
failure can be inspected rather than guessed at. Only stage 2 needs a
third-party package (pypdf); everything else is the standard library.
"""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

STAGES = [
    ("01_read_workbook", "read the build bible"),
    ("02_read_transcripts", "extract the transcripts PDF"),
    ("03_join_corpus", "join calls to employers, brokers and agents"),
    ("04_build_app_data", "compute the analytical layer"),
]


def main():
    for name, what in STAGES:
        print("\n== %s  (%s) ==" % (name, what))
        importlib.import_module(name).main()
    print("\nDone. Reload any open prototype to pick up the new data.js.")


if __name__ == "__main__":
    main()
