"""Stage 2 -- extract the transcripts PDF to plain text.

Needs pypdf. The backend virtualenv already has it:
  Code/Backend/.venv/Scripts/python.exe

The header format matters downstream and has changed once already. The current
revision reads:

    C-0001 - Claims & EOB
    Mon 06 Jul 2026 09:14 - AHT 6m 20s - Competent and resolved - rules C-12, P-14
    MEMBER - CB-7700205 | RESOLVED | score 91/100 | agent AGT-01|Sarah Whitlock

The previous revision put the caller's name in that third line ("MEMBER
CB-7700001 - Rowan Hollis"). It no longer does; the name appears only as the
dialogue speaker label. Stage 3 takes caller identity from the tracker sheet
rather than the header for exactly that reason.
"""
from paths import TRANSCRIPTS, TRANSCRIPTS_TXT, ensure_build, require


def main():
    require(TRANSCRIPTS, "stage 2, reading the transcripts")
    ensure_build()
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SystemExit(
            "pypdf is not installed for this interpreter.\n"
            "  Run the pipeline with the backend virtualenv, which has it:\n"
            "    Code/Backend/.venv/Scripts/python.exe Prototype/tools/build.py")

    reader = PdfReader(str(TRANSCRIPTS))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    TRANSCRIPTS_TXT.write_text(text, encoding="utf-8")

    calls = text.count("\nC-0")
    print("stage 2: %d pages, %d chars, ~%d call blocks -> %s"
          % (len(reader.pages), len(text), calls, TRANSCRIPTS_TXT.name))


if __name__ == "__main__":
    main()
