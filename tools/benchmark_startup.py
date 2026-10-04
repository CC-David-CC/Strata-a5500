"""Fail before a prompt when a benchmark's declared placement did not load."""
from pathlib import Path
import os
import re
import time


class StartupMismatch(RuntimeError):
    pass


def resource_snapshot():
    """Read-only evidence; no reclaim, resource-limit or system-setting changes."""
    result = {}
    for name in ('meminfo', 'self/cgroup', 'self/limits'):
        path = Path('/proc') / name
        if path.exists():
            result[name] = path.read_text()
    if hasattr(os, 'sched_getaffinity'):
        result['cpu_affinity'] = sorted(os.sched_getaffinity(0))
    return result


def start_checked_engine(factory, expected, log_path, patterns, run):
    # Absent configuration preserves existing benchmark behavior. Expectations
    # are caller-supplied facts for a specific comparison, not model defaults.
    if expected is None and not patterns:
        return factory()
    if not isinstance(expected, dict) or not expected:
        raise ValueError('benchmark_expected_engine_info must be a nonempty mapping')
    compiled = [re.compile(pattern, re.MULTILINE) for pattern in patterns]
    report = dict(expected=expected, required_log_patterns=patterns, passed=False,
                  resources_before=resource_snapshot())
    run['startup_precondition'] = report
    engine = None
    start = time.monotonic()
    try:
        engine = factory()
        run['engine_info'] = dict(engine.info)
        report['resources_ready'] = resource_snapshot()
        report['differences'] = {key: dict(expected=value, actual=engine.info.get(key),
                                          present=key in engine.info)
            for key, value in expected.items()
            if key not in engine.info or type(engine.info[key]) is not type(value)
            or engine.info[key] != value}
        log = Path(log_path).read_text(errors='replace') if compiled else ''
        report['missing_log_patterns'] = [pattern.pattern for pattern in compiled
                                           if not pattern.search(log)]
        if report['differences'] or report['missing_log_patterns']:
            raise StartupMismatch('Benchmark startup placement/locking differs: '
                                  + repr((report['differences'], report['missing_log_patterns'])))
        report['passed'] = True
        return engine
    except BaseException:
        if engine is not None:
            engine.close()  # Do not return an engine capable of receiving GEN.
            report['closed_after_rejection'] = True
        raise
    finally:
        report['startup_seconds'] = time.monotonic() - start
