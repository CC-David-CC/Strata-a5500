"""Read-only PE checks for the two Windows release executables."""
import argparse
import hashlib
import json
from pathlib import Path
import re

import pefile


def inspect(path):
    data = path.read_bytes()
    pe = pefile.PE(data=data, fast_load=True)
    try:
        pe.parse_data_directories(directories=[
            pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
        imports = {
            entry.dll.decode(errors='replace'): [
                item.name.decode(errors='replace') if item.name else '#' + str(item.ordinal)
                for item in entry.imports]
            for entry in getattr(pe, 'DIRECTORY_ENTRY_IMPORT', [])}
        markers = [b'powershell', b'cmd.exe', b'WinHttp', b'WinInet',
                   b'URLDownloadToFile', b'WSAStartup', b'ws2_32',
                   b'nvcuda', b'LoadLibrary']
        return {
            'name': path.name,
            'sha256': hashlib.sha256(data).hexdigest(),
            'size': len(data),
            'machine': hex(pe.FILE_HEADER.Machine),
            'imports': imports,
            'urls': sorted(set(match.group().decode(errors='replace') for match in
                               re.finditer(rb'https?://[a-zA-Z0-9./_?=&%+#:-]{5,180}', data))),
            'raw_string_counts': {marker.decode(): data.count(marker) for marker in markers},
            'authenticode_directory_bytes': pe.OPTIONAL_HEADER.DATA_DIRECTORY[4].Size,
        }
    finally:
        pe.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    results = [inspect(args.artifact_dir / name)
               for name in ('strata.exe', 'strata-vision.exe')]
    args.output.write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
