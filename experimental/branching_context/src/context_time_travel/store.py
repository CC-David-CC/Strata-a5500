"""Tiny POSIX, stdlib reference for *logical* branching-context persistence.

This module deliberately does NOT implement model evaluation, sampler advancement,
KV storage, numerical checkpoint materialization or zero-copy sharing.
It provides one authoritative immutable snapshot DAG plus atomic movable heads.

Durability model: local POSIX filesystem with atomic same-directory rename,
fsync(file), fsync(directory), and POSIX flock. Not validated on network FS,
Windows, untrusted multiuser paths, or power-failure simulators.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional
from contextlib import contextmanager
from collections.abc import Mapping
import copy
import fcntl
import hashlib
import json
import os
import re
import tempfile
import threading


class StoreError(Exception):
    """Base store error."""


class Conflict(StoreError):
    """CAS conflict or duplicate branch identity."""


class IntegrityError(StoreError):
    """Object or metadata was missing, corrupted, or invalid."""


class InvalidOperation(StoreError):
    """Invalid API arguments, lineage, or operation-id reuse."""


class NotFound(StoreError):
    """Unknown snapshot or branch."""


@dataclass(frozen=True)
class BranchHead:
    name: str
    revision: int
    tip: str
    root: str


_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_MAX_TOKEN = 2**32 - 1


def _pairs_unique(pairs: list[tuple[str, Any]]) -> dict:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise IntegrityError(f"Duplicate JSON key: {k}")
        out[k] = v
    return out


def _json_bytes(obj: Any) -> bytes:
    # Reject NaN/Infinity and non-JSON data. Deterministic canonical byte layout
    # for our strictly constrained schema; this is NOT a general JSON canonicalization RFC.
    try:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii") + b"\n"
    except (TypeError, ValueError, OverflowError) as exc:
        raise InvalidOperation(f"Unserializable store data: {exc}") from exc


def _decode(raw: bytes) -> dict:
    try:
        obj = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs_unique,
                         parse_constant=lambda c: (_ for _ in ()).throw(IntegrityError(f"Forbidden value: {c}")))
    except (UnicodeError, ValueError, TypeError) as exc:
        raise IntegrityError(f"Invalid metadata JSON: {exc}") from exc
    try:
        canonical = _json_bytes(obj)
    except InvalidOperation as exc:
        raise IntegrityError("Invalid parsed metadata value") from exc
    if not isinstance(obj, dict) or canonical != raw:
        raise IntegrityError("Object is not canonical JSON")
    return obj


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _tokens(values: tuple[int, ...] | list[int]) -> list[int]:
    if not isinstance(values, (tuple, list)):
        raise InvalidOperation("Token delta must be a tuple/list of exact integers")
    if any(type(x) is not int or x < 0 or x > _MAX_TOKEN for x in values):
        raise InvalidOperation("Token IDs must be nonnegative int32-range Python ints")
    return list(values)


def _controller(value: Mapping[str, Any]) -> dict:
    if not isinstance(value, Mapping):
        raise InvalidOperation("Controller state must be a JSON-compatible mapping")
    clone = _decode(_json_bytes(dict(value)))
    # Freeze semantics by serializing now; callers' mutable dicts cannot alter the record.
    return clone


def _id(value: str) -> str:
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        raise InvalidOperation("Expected lowercase 64-digit content identifier")
    return value


def _name(value: str) -> str:
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise InvalidOperation("Expected 1..64 character ASCII branch/operation ID")
    return value


def _sync_dir(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _stage(directory: Path, data: bytes) -> Path:
    fd, name = tempfile.mkstemp(prefix=".stage-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise
    return Path(name)


class Store:
    """Authoritative snapshots + transactional named branch heads.

    Exposes a private failpoint only for fault-injection tests. Production code
    must treat a transaction that faults after rename as having *uncertain*
    outcome, then retry the same operation ID and inspect the receipt.
    """

    def __init__(self, directory: str | os.PathLike[str],
                 fault_hook: Optional[Callable[[str], None]] = None):
        self._work_lock = threading.Lock()
        self._work = dict(snapshot_read_bytes=0, snapshot_reads=0, snapshot_written_bytes=0,
                         reference_read_bytes=0, reference_reads=0, reference_written_bytes=0,
                         reference_publications=0, reference_entries_scanned=0,
                         root_index_read_bytes=0, root_index_written_bytes=0, root_index_repairs=0,
                         ancestry_nodes_visited=0)
        self.root = Path(directory)
        self.objects = self.root / "objects"
        self.root_index = self.root / "root-index"
        self.refs_path = self.root / "refs.json"
        self.lock_path = self.root / "refs.lock"
        self.order_path = self.root / "ref-order.json"
        self.fault_hook = fault_hook
        self.root.mkdir(parents=True, exist_ok=True)
        self.objects.mkdir(exist_ok=True)
        self.root_index.mkdir(exist_ok=True)
        self.lock_path.touch(exist_ok=True)
        with self._locked():
            if not self.refs_path.exists():
                self.references = self.root / 'references'
                self.references.mkdir(exist_ok=True)
                _sync_dir(self.root)
                self._write_order(0)
                self._publish_format(self.references.name)
            else:
                marker = self._read_reference_json(self.refs_path)
                if marker.get('schema') == 1:
                    self._migrate_references(marker)
                else:
                    self._set_reference_directory(marker)

    def _count(self, **values: int) -> None:
        with self._work_lock:
            for key, value in values.items():
                self._work[key] += value

    def work_counters(self) -> dict[str, int]:
        """Completed application-byte I/O and actual traversals, not disk traffic.

        Reads include cached filesystem reads; writes count staged/fsynced bytes.
        reference_publications counts branch-record renames, before directory
        fsync; reference byte counters also include the format and audit ordinal.
        These counters neither infer device traffic nor establish power-loss durability.
        """
        with self._work_lock:
            return dict(self._work)

    @staticmethod
    def _empty_refs() -> dict:
        return {"schema": 1, "branches": {}, "receipts": {}, "events": []}

    def _fault(self, step: str) -> None:
        if self.fault_hook is not None:
            self.fault_hook(step)

    @contextmanager
    def _locked(self):
        with open(self.lock_path, "r+b") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def _read_reference_json(self, path: Path) -> dict:
        try:
            raw = path.read_bytes()
        except FileNotFoundError as exc:
            raise IntegrityError("Missing reference metadata") from exc
        self._count(reference_reads=1, reference_read_bytes=len(raw))
        return _decode(raw)

    def _publish_reference_json(self, path: Path, value: dict, *, branch: bool = False) -> None:
        raw = _json_bytes(value)
        stage = _stage(path.parent, raw)
        self._count(reference_written_bytes=len(raw))
        try:
            if branch:
                self._fault("after_refs_stage_fsync")
            os.replace(stage, path)
            if branch:
                self._count(reference_publications=1)
                self._fault("after_refs_rename_before_dir_fsync")
            _sync_dir(path.parent)
        finally:
            stage.unlink(missing_ok=True)

    def _publish_format(self, directory: str) -> None:
        self._publish_reference_json(self.refs_path, dict(schema=2, directory=directory))

    def _set_reference_directory(self, marker: dict) -> None:
        directory = marker.get('directory')
        if set(marker) != {'schema', 'directory'} or marker['schema'] != 2 or not isinstance(directory, str):
            raise IntegrityError('Invalid reference directory schema')
        if directory != 'references' and not re.fullmatch(r'references-[0-9a-f]{64}', directory):
            raise IntegrityError('Invalid reference directory name')
        self.references = self.root / directory
        if not self.references.is_dir():
            raise IntegrityError('Missing reference directory')

    def _check_reference_format(self) -> None:
        self._set_reference_directory(self._read_reference_json(self.refs_path))

    def _write_order(self, next_order: int) -> None:
        self._publish_reference_json(self.order_path, dict(schema=1, next=next_order))

    def _reserve_order(self) -> int:
        # Reserve a fixed-size audit ordinal before publishing a branch. A
        # failed transaction may leave a gap; it never creates an audit event
        # or changes a branch. The global file lock serializes reservations.
        value = self._read_reference_json(self.order_path)
        if set(value) != {'schema', 'next'} or value['schema'] != 1 or type(value['next']) is not int or not 0 <= value['next'] < 2**64 - 1:
            raise IntegrityError('Invalid or exhausted reference order counter')
        self._write_order(value['next'] + 1)
        return value['next']

    def _read_branch(self, name: str) -> dict:
        path = self.references / (name + '.json')
        if not path.exists():
            raise NotFound(f'Unknown branch: {name}')
        value = self._read_reference_json(path)
        if set(value) != {'schema', 'name', 'head', 'receipts', 'events', 'orders'} or value['schema'] != 1 or value['name'] != name:
            raise IntegrityError('Invalid branch record')
        head = value['head']
        if not isinstance(head, dict) or set(head) != {'revision', 'tip', 'root'} or type(head['revision']) is not int or head['revision'] < 0:
            raise IntegrityError('Invalid branch head')
        try:
            _id(head['tip']); _id(head['root'])
        except InvalidOperation as error:
            raise IntegrityError('Invalid branch snapshot identity') from error
        if not isinstance(value['receipts'], dict) or not isinstance(value['events'], list) or not isinstance(value['orders'], list):
            raise IntegrityError('Invalid branch receipt/event containers')
        if len(value['events']) != len(value['orders']) or any(type(x) is not int or x < 0 for x in value['orders']):
            raise IntegrityError('Invalid branch event order')
        return value

    def _read_refs(self) -> dict:
        # Full reference enumeration is for receipts/events, never fork. Move
        # still scans committed receipts to keep operation IDs store-global.
        self._check_reference_format()
        result = self._empty_refs()
        events = []
        for path in sorted(self.references.glob('*.json')):
            name = _name(path.stem)
            record = self._read_branch(name)
            self._count(reference_entries_scanned=1 + len(record['receipts']) + len(record['events']))
            result['branches'][name] = record['head']
            for operation, receipt in record['receipts'].items():
                if operation in result['receipts']:
                    raise IntegrityError('Duplicate committed operation ID')
                result['receipts'][operation] = receipt
            events.extend(zip(record['orders'], record['events']))
        orders = [order for order, _ in events]
        if len(orders) != len(set(orders)):
            raise IntegrityError('Duplicate committed audit ordinal')
        result['events'] = [event for _, event in sorted(events, key=lambda row: row[0])]
        return result

    def _migrate_references(self, old: dict) -> None:
        if set(old) != {'schema', 'branches', 'receipts', 'events'} or not isinstance(old['branches'], dict) or not isinstance(old['receipts'], dict) or not isinstance(old['events'], list):
            raise IntegrityError('Invalid legacy reference index')
        # Snapshot objects keep their exact bytes/IDs. Only the reference index
        # changes layout. Until the final marker rename, the old index is the
        # authority; a restart can repeat the same deterministic migration.
        directory = self.root / ('references-' + _hash(_json_bytes(old)))
        directory.mkdir(exist_ok=True)
        records = {}
        for name, head in old['branches'].items():
            _name(name)
            records[name] = dict(schema=1, name=name, head=head, receipts={}, events=[], orders=[])
        for operation, receipt in old['receipts'].items():
            _name(operation)
            try:
                records[receipt['result']['name']]['receipts'][operation] = receipt
            except (KeyError, TypeError) as error:
                raise IntegrityError('Invalid legacy retry receipt') from error
        for order, event in enumerate(old['events']):
            try:
                record = records[event['branch']]
            except (KeyError, TypeError) as error:
                raise IntegrityError('Invalid legacy audit event') from error
            record['events'].append(event)
            record['orders'].append(order)
        self.references = directory
        for name, record in records.items():
            self._publish_reference_json(directory / (name + '.json'), record)
            self._read_branch(name)
        _sync_dir(directory)
        _sync_dir(self.root)
        self._write_order(len(old['events']))
        self._publish_format(directory.name)

    def _publish_root_index(self, identity: str, root: str) -> None:
        value = dict(schema=1, snapshot=identity, root=root)
        raw = _json_bytes(dict(value=value, checksum=_hash(_json_bytes(value))))
        path = self.root_index / (identity + '.json')
        if path.exists():
            if self._read_root_index(identity) != root:
                raise IntegrityError('Conflicting snapshot root lookup')
            return
        stage = _stage(self.root_index, raw)
        self._count(root_index_written_bytes=len(raw))
        try:
            try:
                os.link(stage, path)
            except FileExistsError:
                if self._read_root_index(identity) != root:
                    raise IntegrityError('Conflicting snapshot root lookup')
            else:
                _sync_dir(self.root_index)
        finally:
            stage.unlink(missing_ok=True)

    def _read_root_index(self, identity: str) -> str:
        path = self.root_index / (identity + '.json')
        raw = path.read_bytes()
        self._count(root_index_read_bytes=len(raw))
        envelope = _decode(raw)
        value = envelope.get('value')
        if not isinstance(value, dict) or set(envelope) != {'value', 'checksum'} or envelope['checksum'] != _hash(_json_bytes(value)):
            raise IntegrityError('Corrupt snapshot root lookup')
        if set(value) != {'schema', 'snapshot', 'root'} or value['schema'] != 1 or value['snapshot'] != identity:
            raise IntegrityError('Incompatible snapshot root lookup')
        try:
            return _id(value['root'])
        except InvalidOperation as error:
            raise IntegrityError('Invalid root lookup identity') from error

    def _root_for(self, identity: str) -> str:
        # This derived lookup copies no inputs/controller. Canonical reads and
        # materialization still hash/validate every actual history object.
        try:
            root = self._read_root_index(identity)
        except FileNotFoundError:
            root, _ = self.lineage(identity)
            self._publish_root_index(identity, root)
            self._count(root_index_repairs=1)
        for retained in (identity, root):
            if not (self.objects / (retained + '.json')).is_file():
                raise NotFound(f'Missing retained snapshot: {retained}')
        return root

    def _put_object(self, record: dict, root: str | None = None) -> str:
        raw = _json_bytes(record)
        digest = _hash(raw)
        destination = self.objects / (digest + ".json")
        if destination.exists():
            self._verify_object_file(destination, digest)
            self._publish_root_index(digest, root or digest)
            return digest
        stage = _stage(self.objects, raw)
        self._count(snapshot_written_bytes=len(raw))
        try:
            self._fault("before_snapshot_publish")
            # link is atomic, and unlike replace will never overwrite an
            # existing immutable object (even in a concurrent writer race).
            try:
                os.link(stage, destination)
            except FileExistsError:
                self._verify_object_file(destination, digest)
            else:
                _sync_dir(self.objects)
        finally:
            stage.unlink(missing_ok=True)
        self._publish_root_index(digest, root or digest)
        return digest

    def _verify_object_file(self, path: Path, expected: str) -> dict:
        try:
            raw = path.read_bytes()
        except FileNotFoundError as exc:
            raise NotFound(f"Missing object: {expected}") from exc
        self._count(snapshot_reads=1, snapshot_read_bytes=len(raw))
        if _hash(raw) != expected:
            raise IntegrityError(f"SHA-256 mismatch in object {expected}")
        return _decode(raw)

    def get_snapshot(self, snapshot_id: str) -> dict:
        identity = _id(snapshot_id)
        record = self._verify_object_file(self.objects / (identity + ".json"), identity)
        if set(record) != {"kind", "schema", "model_contract_id", "parent", "inputs", "controller"}:
            raise IntegrityError("Unrecognized snapshot schema")
        if record["kind"] != "snapshot" or record["schema"] != 1:
            raise IntegrityError("Unsupported snapshot kind/version")
        if not isinstance(record["model_contract_id"], str) or not record["model_contract_id"]:
            raise IntegrityError("Invalid model contract identity")
        if record["parent"] is not None:
            try:
                _id(record["parent"])
            except InvalidOperation as exc:
                raise IntegrityError("Invalid parent reference") from exc
        try:
            _tokens(record["inputs"])
            _controller(record["controller"])
        except InvalidOperation as exc:
            raise IntegrityError("Invalid stored snapshot fields") from exc
        return record

    def create_root(self, model_contract_id: str,
                    inputs: tuple[int, ...] | list[int],
                    controller: Mapping[str, Any]) -> str:
        if not isinstance(model_contract_id, str) or not model_contract_id:
            raise InvalidOperation("Model contract identity must be nonempty")
        return self._put_object({"kind": "snapshot", "schema": 1,
                                 "model_contract_id": model_contract_id,
                                 "parent": None,
                                 "inputs": _tokens(inputs),
                                 "controller": _controller(controller)})

    def append(self, parent_id: str, inputs: tuple[int, ...] | list[int],
               controller: Mapping[str, Any]) -> str:
        parent = self.get_snapshot(parent_id)
        root = self._root_for(_id(parent_id))
        return self._put_object({"kind": "snapshot", "schema": 1,
                                 "model_contract_id": parent["model_contract_id"],
                                 "parent": _id(parent_id),
                                 "inputs": _tokens(inputs),
                                 "controller": _controller(controller)}, root)

    def lineage(self, snapshot_id: str) -> tuple[str, list[int]]:
        """Return (root_id, exact inputs); validate every ancestor and contract."""
        cursor = _id(snapshot_id)
        seen: set[str] = set()
        chunks: list[list[int]] = []
        contract = None
        while True:
            self._count(ancestry_nodes_visited=1)
            if cursor in seen:
                raise IntegrityError("Cycle in snapshot ancestry")
            seen.add(cursor)
            record = self.get_snapshot(cursor)
            if contract is None:
                contract = record["model_contract_id"]
            elif contract != record["model_contract_id"]:
                raise IntegrityError("Cross-contract parent reference")
            chunks.append(record["inputs"])
            if record["parent"] is None:
                return cursor, [token for chunk in reversed(chunks) for token in chunk]
            cursor = record["parent"]

    def fork(self, name: str, snapshot_id: str) -> BranchHead:
        name = _name(name)
        identity = _id(snapshot_id)
        root = self._root_for(identity)
        with self._locked():
            self._check_reference_format()
            path = self.references / (name + '.json')
            if path.exists():
                raise Conflict(f"Branch exists: {name}")
            record = dict(schema=1, name=name, head=dict(revision=0, tip=identity, root=root),
                          receipts={}, events=[dict(type='fork', branch=name, tip=identity)],
                          orders=[self._reserve_order()])
            self._publish_reference_json(path, record, branch=True)
        return BranchHead(name, 0, identity, root)

    def head(self, name: str) -> BranchHead:
        name = _name(name)
        with self._locked():
            self._check_reference_format()
            entry = self._read_branch(name)['head']
        self.get_snapshot(entry["tip"])
        return BranchHead(name, entry["revision"], entry["tip"], entry["root"])

    def move(self, name: str, expected_revision: int,
             target_snapshot_id: str, operation_id: str) -> BranchHead:
        name = _name(name)
        op_id = _name(operation_id)
        identity = _id(target_snapshot_id)
        if type(expected_revision) is not int or expected_revision < 0:
            raise InvalidOperation("Expected revision must be a nonnegative integer")
        request = {"type": "move", "name": name, "expected_revision": expected_revision,
                   "target": identity}
        request_digest = _hash(_json_bytes(request))
        with self._locked():
            refs = self._read_refs()
            receipt = refs["receipts"].get(op_id)
            if receipt is not None:
                if receipt["digest"] != request_digest:
                    raise InvalidOperation("Operation ID reused for different request")
                record = receipt["result"]
                return BranchHead(record["name"], record["revision"],
                                  record["tip"], record["root"])
            if name not in refs["branches"]:
                raise NotFound(f"Unknown branch: {name}")
            # Validate the ancestry only on a new operation. Retries must be
            # answered from their committed receipt even after later rewinds.
            root, _ = self.lineage(identity)
            entry = refs["branches"][name]
            if entry["root"] != root:
                raise InvalidOperation("Cannot move branch between unrelated snapshot roots")
            if entry["revision"] != expected_revision:
                raise Conflict(f"CAS revision mismatch: expected {expected_revision}, got {entry['revision']}")
            old_tip = entry["tip"]
            result = BranchHead(name, expected_revision + 1, identity, root)
            record = self._read_branch(name)
            record['head'] = {"revision": result.revision, "tip": identity, "root": root}
            record["receipts"][op_id] = {"digest": request_digest,
                                       "result": {"name": name,
                                                  "revision": result.revision,
                                                  "tip": identity, "root": root}}
            record["events"].append({"type": "move", "branch": name,
                                   "operation_id": op_id, "from": old_tip, "to": identity,
                                   "from_revision": expected_revision, "to_revision": result.revision})
            self._fault("before_refs_stage")
            record['orders'].append(self._reserve_order())
            self._publish_reference_json(self.references / (name + '.json'), record, branch=True)
            return result

    def events(self) -> list[dict]:
        with self._locked():
            return copy.deepcopy(self._read_refs()["events"])
