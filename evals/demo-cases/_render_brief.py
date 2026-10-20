#!/usr/bin/env python3
"""Render <case>/input/project-brief.md -> .html -> .pdf, stamped EXAMPLE DATA."""
import sys, subprocess, pathlib, markdown
STAMP = ('<div class="stamp">EXAMPLE DATA &mdash; FICTIONAL DEMO CASE FOR BATATIS &mdash; '
         'NOT A REAL PROJECT, PRODUCT, PERSON, TEST OR APPROVAL</div>')
CSS = """body{font-family:'DejaVu Sans',sans-serif;font-size:10pt;line-height:1.35;margin:18px}
.stamp{border:2px solid #b00;color:#b00;font-weight:bold;text-align:center;padding:5px;margin:0 0 10px}
.foot{margin-top:14px;color:#b00;font-size:8pt;text-align:center}
h1{font-size:15pt;margin:6px 0} h2{font-size:12pt;margin:12px 0 4px;border-bottom:1px solid #999}
table{border-collapse:collapse;width:100%;font-size:9pt} td,th{border:1px solid #999;padding:3px;vertical-align:top}
th{background:#eee} code{font-size:9pt}"""
for md in sys.argv[1:]:
    p = pathlib.Path(md)
    body = markdown.markdown(p.read_text(), extensions=['tables'])
    html = f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{STAMP}{body}<div class='foot'>{STAMP}</div></body></html>"
    h = p.with_suffix('.html'); h.write_text(html)
    subprocess.run(['soffice','--headless','--convert-to','pdf:writer_web_pdf_Export','--outdir',str(p.parent),str(h)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print('rendered', p.with_suffix('.pdf'))
