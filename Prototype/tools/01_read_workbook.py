"""Stage 1 -- read the build bible into JSON.

Parses the xlsx container directly (zipfile + ElementTree) rather than through
openpyxl, so the pipeline needs nothing but the standard library here.

One thing to know about the source: the workbook is written by openpyxl, which
stores formulas without computing them. Around 1,500 cells therefore hold a
formula and no cached value, and read as empty -- including participation, fee
band, COBRA regime, annual premium and calls per 100 lives. Stage 3 derives all
of them, from eligible headcount, rule P-33, and -- for premium -- the per-life
lever in Distribution Targets, which it parses rather than hardcodes. See
premium_per_life() in stage 3 for why a flat lever limits what premium can say.
"""
import json
import re
import zipfile
from xml.etree import ElementTree as ET

from paths import WORKBOOK, WORKBOOK_JSON, ensure_build, require

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def column_index(ref):
    letters = re.match(r"([A-Z]+)", ref or "A").group(1)
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - 64)
    return idx


def main():
    require(WORKBOOK, "stage 1, reading the workbook")
    ensure_build()
    z = zipfile.ZipFile(WORKBOOK)

    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(NS + "si"):
            shared.append("".join(t.text or "" for t in si.iter(NS + "t")))

    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = {r.get("Id"): r.get("Target") for r in rels}
    sheets = []
    for sh in wb.find(NS + "sheets"):
        t = target[sh.get(REL + "id")]
        sheets.append((sh.get("name"), "xl/" + t.lstrip("/").replace("xl/", "", 1)))

    def cell_text(c):
        kind = c.get("t")
        v = c.find(NS + "v")
        if kind == "s" and v is not None:
            return shared[int(v.text)]
        inline = c.find(NS + "is")
        if inline is not None:
            return "".join(x.text or "" for x in inline.iter(NS + "t"))
        return v.text if v is not None else ""

    out = {}
    for name, path in sheets:
        root = ET.fromstring(z.read(path))
        rows = []
        for row in root.iter(NS + "row"):
            vals = []
            for c in row.findall(NS + "c"):
                idx = column_index(c.get("r"))
                while len(vals) < idx - 1:
                    vals.append("")
                vals.append(cell_text(c))
            rows.append(vals)
        out[name] = rows

    WORKBOOK_JSON.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("stage 1: %d sheets -> %s" % (len(out), WORKBOOK_JSON.name))
    for name, rows in out.items():
        width = max((len(r) for r in rows), default=0)
        print("   %-28s %4d rows  %3d cols" % (name[:28], len(rows), width))


if __name__ == "__main__":
    main()
