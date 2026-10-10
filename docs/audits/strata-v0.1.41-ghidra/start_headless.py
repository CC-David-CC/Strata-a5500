"""Launch the reviewed GhidraMCP headless loader on loopback."""
import argparse
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ghidra-home', type=Path, required=True)
    parser.add_argument('--java', type=Path, required=True)
    parser.add_argument('--plugin-jar', type=Path, required=True)
    parser.add_argument('--artifact', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8089)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    for path in (args.ghidra_home, args.java, args.plugin_jar, args.artifact):
        if not path.exists():
            parser.error('Path does not exist: ' + str(path))
    ghidra = args.ghidra_home.resolve()
    jars = [args.plugin_jar.resolve()]
    for group in ('Framework', 'Features', 'Processors'):
        jars.extend(sorted((ghidra / 'Ghidra' / group).glob('*/lib/*.jar')))
    command = [
        str(args.java.resolve()), '-Xmx2g', '-Djava.awt.headless=true',
        '-Dghidra.home=' + str(ghidra), '-Dapplication.name=GhidraMCP',
        '-classpath', os.pathsep.join(map(str, jars)),
        'com.xebyte.headless.GhidraMCPHeadlessServer', '--bind', '127.0.0.1',
        '--port', str(args.port), '--file', str(args.artifact.resolve()),
    ]
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    raise SystemExit(subprocess.call(command, cwd=ghidra, creationflags=flags))


if __name__ == '__main__':
    main()
