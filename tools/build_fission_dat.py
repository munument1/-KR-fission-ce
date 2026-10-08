#!/usr/bin/env python3
"""Materialize and verify the packaged Fallout 2 DAT from tracked resources."""
import argparse
from pathlib import Path
import struct
import zlib


def read_dat(path):
    blob = path.read_bytes()
    tree_size, archive_size = struct.unpack_from('<II', blob, len(blob) - 8)
    if archive_size != len(blob):
        raise ValueError('DAT archive size mismatch')
    cursor = len(blob) - tree_size - 8
    count, = struct.unpack_from('<I', blob, cursor)
    cursor += 4
    files = {}
    for _ in range(count):
        length, = struct.unpack_from('<I', blob, cursor)
        cursor += 4
        name = blob[cursor:cursor + length].decode('ascii')
        cursor += length
        compressed, size, packed_size, offset = struct.unpack_from('<BIII', blob, cursor)
        cursor += 13
        if offset + packed_size > len(blob) - tree_size - 8:
            raise ValueError('DAT entry outside data region: ' + name)
        raw = blob[offset:offset + packed_size]
        raw = zlib.decompress(raw) if compressed else raw
        if len(raw) != size or name.lower() in files:
            raise ValueError('Invalid or duplicate DAT entry: ' + name)
        files[name.lower()] = (name, raw)
    if cursor != len(blob) - 8:
        raise ValueError('DAT tree size mismatch')
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=Path('os/macos/fission.dat'))
    parser.add_argument('--resources', type=Path, default=Path('files/fission'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    files = read_dat(args.base)
    for path in sorted(args.resources.rglob('*')):
        if path.is_file():
            name = str(path.relative_to(args.resources)).replace('/', '\\')
            files[name.lower()] = (name, path.read_bytes())
    data = bytearray()
    tree = bytearray(struct.pack('<I', len(files)))
    for key in sorted(files):
        name, raw = files[key]
        packed = zlib.compress(raw)
        encoded = name.encode('ascii')
        tree += struct.pack('<I', len(encoded)) + encoded
        tree += struct.pack('<BIII', 1, len(raw), len(packed), len(data))
        data += packed
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data + tree + struct.pack('<II', len(tree), len(data) + len(tree) + 8))
    if read_dat(args.output) != files:
        raise ValueError('DAT byte round-trip failed')
    print(f'Verified {len(files)} DAT entries: {args.output}')


if __name__ == '__main__':
    main()
