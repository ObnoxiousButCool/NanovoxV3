"""Shared locations. Everything is derived from this file's position in the repo,
so the pipeline runs from any working directory."""
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
PROTOTYPE = TOOLS.parent
REPO = PROTOTYPE.parent
DOCUMENTS = REPO / "Documents"
BUILD = TOOLS / "build"

# The two source documents. Both are re-issued periodically and the suffix
# changes when they are -- see README.md before pointing these at a new pair.
WORKBOOK = DOCUMENTS / "nanovox_corpus_v9_build_bible_2.xlsx"
TRANSCRIPTS = DOCUMENTS / "nanovox_v9_transcripts_batch1_001-100_1.pdf"

# Intermediates (git-ignored) and the one published output.
WORKBOOK_JSON = BUILD / "workbook.json"
TRANSCRIPTS_TXT = BUILD / "transcripts.txt"
DATASET_JSON = BUILD / "dataset.json"
APP_DATA_JS = PROTOTYPE / "data.js"


def require(path, stage):
    if not path.exists():
        raise SystemExit(
            "Missing %s\n  needed by: %s\n"
            "  If the corpus was re-issued, the filename suffix will have changed --\n"
            "  update WORKBOOK / TRANSCRIPTS in tools/paths.py, and keep the pair matched\n"
            "  (a tracker from one revision with transcripts from another misattributes\n"
            "  every call, silently)." % (path, stage))
    return path


def ensure_build():
    BUILD.mkdir(parents=True, exist_ok=True)
    return BUILD
