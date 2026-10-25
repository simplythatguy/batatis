#!/usr/bin/env python3
"""Refresh geographic navigation without discarding curated use/rights guidance."""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

from corpus import BASE, write_indexes


def write_navigation(base, index):
    city = [row for row in index if row['priority_tier'] == 1]
    lines = ['# Calgary and Edmonton', '',
             'Primary local attachment exercises. Use the named cases below or browse [all locations](GEOGRAPHY_INDEX.md). Province-wide records and other Alberta localities remain separate.', '',
             '| Case | Record | Source type | Code edition |', '| --- | --- | --- | --- |']
    for row in city:
        target = quote(row['folder'] + '/prompt.txt')
        title = row['title'].replace('|', '/')
        edition = str(row['code_edition']).replace('|', '/')
        lines.append(f"| [{row['case_id']}]({target}) | {title} | {row['case_type']} | {edition} |")
    (base / 'CITY_CASES.md').write_text('\n'.join(lines) + '\n')
    locations = defaultdict(list)
    for row in index:
        locations[(row['country'], row['province_or_state'], row['city_or_town'])].append(row)
    lines = ['# Locations', '',
             'Country → Province/State → City/Town → Prompts → named case. Scope labels preserve national, province-wide, multi-location and undisclosed records without inventing a project city.', '',
             '| Country | Province / State | City / Town or scope | Cases |', '| --- | --- | --- | ---: |']
    keys = sorted(locations, key=lambda key: (min(row['priority_tier'] for row in locations[key]), key))
    for country, region, locality in keys:
        rows = locations[(country, region, locality)]
        target = quote(str(Path(rows[0]['folder']).parent))
        lines.append(f'| {country} | {region} | [{locality}]({target}) | {len(rows)} |')
    (base / 'GEOGRAPHY_INDEX.md').write_text('\n'.join(lines) + '\n')
    readme = base / 'README.md'
    if readme.exists():
        text = readme.read_text()
        text = re.sub(r'\d+ (?:numbered )?source-backed attachment exercises',
                      f'{len(index)} source-backed attachment exercises', text, count=1)
        groups = len({row['source_group'] for row in index})
        text = re.sub(r'There are \d+ groups of shared original input sources',
                      f'There are {groups} groups of shared original input sources', text)
        readme.write_text(text)


def main():
    index = json.loads((BASE / 'index.json').read_text())
    write_indexes(BASE, index)
    write_navigation(BASE, index)
    print(json.dumps({'cases': len(index), 'countries': dict(Counter(row['country'] for row in index))}))


if __name__ == '__main__':
    main()
