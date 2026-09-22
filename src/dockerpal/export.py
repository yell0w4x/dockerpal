"""Writing resource details out to files in the current directory."""

import re

from pathlib import Path


def unique_path(stem, suffix):
    """A free path in the current directory, so an export never clobbers."""

    stem = re.sub(r'[^A-Za-z0-9._-]', '_', stem) or 'details'
    path = Path(f'{stem}{suffix}').resolve()
    i = 0
    while path.exists():
        i += 1
        path = Path(f'{stem}-{i}{suffix}').resolve()

    return path


def write(text, stem, suffix):
    """Write text to a free path named after stem; returns the path used."""

    path = unique_path(stem, suffix)
    path.write_text(text)
    return path
