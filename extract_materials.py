#!/usr/bin/env python3
"""
Extract Minecraft object materials from GrabCraft page.
Parses the object_properties table and outputs CSV with material, color, and count.
"""

import csv
import re
import sys
from urllib.request import urlopen, Request
from html.parser import HTMLParser


class MaterialsParser(HTMLParser):
    """Parse GrabCraft HTML to extract materials from object_properties table."""

    def __init__(self):
        super().__init__()
        self.in_object_properties = False
        self.in_materials_section = False
        self.in_row = False
        self.in_parameter_td = False
        self.in_value_td = False
        self.current_material = None
        self.current_count = None
        self.current_color = None
        self.materials = []
        self.td_count = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == 'table' and attrs_dict.get('id') == 'object_properties':
            self.in_object_properties = True

        if not self.in_object_properties:
            return

        if tag == 'tr':
            self.in_row = True
            self.td_count = 0
            self.current_material = None
            self.current_count = None
            self.current_color = None

        if tag == 'td':
            self.td_count += 1
            td_class = attrs_dict.get('class', '')

            if 'parameter' in td_class:
                self.in_parameter_td = True
            elif 'value' in td_class:
                self.in_value_td = True

        if tag == 'div' and 'material-list' in attrs_dict.get('class', ''):
            style = attrs_dict.get('style', '')
            color_match = re.search(r'background:\s*([#\w]+)', style)
            if color_match:
                self.current_color = color_match.group(1)

    def handle_endtag(self, tag):
        if tag == 'table' and self.in_object_properties:
            self.in_object_properties = False

        if tag == 'tr' and self.in_row:
            self.in_row = False
            if self.current_material and self.current_count and self.current_color:
                self.materials.append({
                    'material': self.current_material.strip(),
                    'count': self.current_count.strip(),
                    'color': self.current_color.strip()
                })

        if tag == 'td':
            self.in_parameter_td = False
            self.in_value_td = False

    def handle_data(self, data):
        if not self.in_object_properties:
            return

        data = data.strip()
        if not data:
            return

        if data == 'Object materials':
            self.in_materials_section = True
            return

        if not self.in_materials_section:
            return

        if self.in_parameter_td and self.td_count == 1:
            self.current_material = data

        if self.in_value_td and self.td_count == 2:
            count_match = re.match(r'(\d+)', data)
            if count_match:
                self.current_count = count_match.group(1)


def fetch_page(url: str) -> str:
    """Fetch HTML content from URL."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    request = Request(url, headers=headers)
    with urlopen(request, timeout=30) as response:
        return response.read().decode('utf-8')


def extract_materials(html: str) -> list[dict]:
    """Extract materials from HTML content."""
    parser = MaterialsParser()
    parser.feed(html)
    return parser.materials


def save_csv(materials: list[dict], output_file: str):
    """Save materials to CSV file."""
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['material', 'color', 'count'])
        writer.writeheader()
        writer.writerows(materials)


def main():
    url = 'https://www.grabcraft.com/minecraft/oakshire-wall-tower/military-buildings'
    output_file = 'materials.csv'

    if len(sys.argv) > 1:
        url = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]

    print(f'Fetching: {url}')
    html = fetch_page(url)

    print('Extracting materials...')
    materials = extract_materials(html)

    if not materials:
        print('No materials found!')
        sys.exit(1)

    save_csv(materials, output_file)
    print(f'Saved {len(materials)} materials to {output_file}')

    print('\nMaterials:')
    for m in materials:
        print(f"  {m['material']}: {m['count']} ({m['color']})")


if __name__ == '__main__':
    main()
