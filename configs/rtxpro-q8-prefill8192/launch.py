"""Launch the frozen native configuration; additional arguments go to Strata."""
from pathlib import Path
import argparse
import json
import os


def expand(value):
    if isinstance(value, str):
        return os.path.expandvars(value.replace("$HOME", str(Path.home())))
    if isinstance(value, list):
        return [expand(v) for v in value]
    if isinstance(value, dict):
        return {k: expand(v) for k, v in value.items()}
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.example.json"))
    parser.add_argument("--engine", help="Override the path to an unmodified v0.1.40 engine")
    parser.add_argument("--context", type=int, help="Override the allocated context")
    parser.add_argument("--dry-run", action="store_true")
    options, extra = parser.parse_known_args()
    config = expand(json.loads(options.config.read_text()))
    args = list(config["args"])
    if options.context is not None:
        if options.context <= 0:
            parser.error("context must be positive")
        args[args.index("--max-context") + 1] = str(options.context)
    command = [options.engine or config["exe"], *args, *extra]
    env = {k: v for k, v in os.environ.items() if not k.startswith(("STRATA_", "MULTI_CONCURRENCY"))}
    env.update(config["env"])
    if options.dry_run:
        print(json.dumps({"command": command, "environment": config["env"]}, indent=2))
        return
    os.execvpe(command[0], command, env)


if __name__ == "__main__":
    main()
