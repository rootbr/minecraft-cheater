#!/usr/bin/env python3
"""
Download Minecraft blueprint layer images from GrabCraft.
Downloads all layer images for Y, X, and Z axes.
"""

import os
import re
import sys
from urllib.request import urlopen, Request
from urllib.error import HTTPError


def fetch_page(url: str) -> str:
    """Fetch HTML content from URL."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    request = Request(url, headers=headers)
    with urlopen(request, timeout=30) as response:
        return response.read().decode('utf-8')


def extract_blueprint_id(html: str) -> str | None:
    """Extract blueprint ID from page HTML."""
    # Look for bprints.grabcraft.com URLs with ID
    patterns = [
        r'bprints\.grabcraft\.com/(\d+)/',
        r'blueprint[_-]?id["\s:=]+(\d+)',
        r'/blueprints?/(\d+)',
        r'data-id["\s:=]+["\']?(\d+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def download_image(url: str, output_path: str) -> bool:
    """Download image from URL to file."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        request = Request(url, headers=headers)
        with urlopen(request, timeout=30) as response:
            with open(output_path, 'wb') as f:
                f.write(response.read())
        return True
    except HTTPError as e:
        if e.code == 404:
            return False
        raise


def download_axis_layers(blueprint_id: str, axis: str, output_dir: str) -> int:
    """Download all layers for a given axis. Returns count of downloaded images."""
    axis_dir = os.path.join(output_dir, axis)
    os.makedirs(axis_dir, exist_ok=True)

    layer = 1
    downloaded = 0

    while True:
        url = f'https://bprints.grabcraft.com/{blueprint_id}/{axis}/combined/{layer}.png'
        output_path = os.path.join(axis_dir, f'{layer}.png')

        print(f'  Downloading {axis} layer {layer}...', end=' ')

        if download_image(url, output_path):
            print('OK')
            downloaded += 1
            layer += 1
        else:
            print('not found (end of layers)')
            break

    return downloaded


def main():
    url = 'https://www.grabcraft.com/minecraft/oakshire-wall-tower/military-buildings'
    output_dir = 'blueprints'

    if len(sys.argv) > 1:
        url = sys.argv[1]
    if len(sys.argv) > 2:
        output_dir = sys.argv[2]

    print(f'Fetching: {url}')
    html = fetch_page(url)

    blueprint_id = extract_blueprint_id(html)
    if not blueprint_id:
        print('Error: Could not find blueprint ID in page')
        sys.exit(1)

    print(f'Found blueprint ID: {blueprint_id}')

    # Extract object name for folder
    name_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    if name_match:
        name = re.sub(r'[^\w\s-]', '', name_match.group(1)).strip().replace(' ', '_')
        output_dir = os.path.join(output_dir, f'{blueprint_id}_{name}')
    else:
        output_dir = os.path.join(output_dir, blueprint_id)

    os.makedirs(output_dir, exist_ok=True)
    print(f'Output directory: {output_dir}')

    total = 0
    for axis in ['Y', 'X', 'Z']:
        print(f'\nDownloading {axis} axis layers:')
        count = download_axis_layers(blueprint_id, axis, output_dir)
        total += count
        print(f'  Downloaded {count} layers for {axis} axis')

    print(f'\nTotal: {total} images downloaded to {output_dir}')


if __name__ == '__main__':
    main()
