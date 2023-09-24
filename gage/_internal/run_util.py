# SPDX-License-Identifier: Apache-2.0

from typing import *
from .types import *
from logging import Logger
from os import DirEntry

import json
import logging
import os
import subprocess
import threading
import time
import uuid

from . import config
from . import run_config
from . import run_sourcecode
from . import run_output

from .file_select import copy_files

from .file_util import make_dir, set_readonly
from .file_util import ensure_dir
from .file_util import file_sha256
from .file_util import write_file

from .opref_util import decode_opref
from .opref_util import encode_opref


__all__ = [
    "META_SCHEMA",
    "RunManifest",
    "apply_config",
    "finalize_staged_run",
    "init_run_meta",
    "make_run",
    "meta_opdef",
    "open_run_output",
    "run_attr",
    "run_attrs",
    "run_meta_dir",
    "run_meta_path",
    "run_status",
    "run_timestamp",
    "stage_dependencies",
    "stage_run",
    "stage_runtime",
    "stage_sourcecode",
    "start_run",
    "unique_run_id",
]

META_SCHEMA = "1"

__last_ts = None
__last_ts_lock = threading.Lock()


# =================================================================
# Run attributes
# =================================================================


def run_status(run: Run) -> RunStatus:
    meta_dir = run_meta_dir(run)
    if not os.path.exists(meta_dir):
        return "unknown"
    assert False


def run_meta_dir(run: Run):
    return run.run_dir + ".meta"


def run_meta_path(run: Run, *path: str):
    return os.path.join(run_meta_dir(run), *path)


def run_attrs(run: Run) -> dict[str, Any]:
    attrs_dir = run_meta_path(run, "attrs")
    if not os.path.exists(attrs_dir):
        raise FileNotFoundError(attrs_dir)
    assert False


def run_attr(run: Run, name: str):
    try:
        return getattr(run, name)
    except AttributeError:
        assert False, f"TODO run attr {name} somewhere in {run.run_dir}"


# =================================================================
# Meta API
# =================================================================


def meta_opref(run: Run) -> OpRef:
    with open(run_meta_path(run, "opref")) as f:
        return decode_opref(f.read())


def meta_opdef(run: Run) -> OpDef:
    opref = meta_opref(run)
    with open(run_meta_path(run, "opdef.json")) as f:
        data = json.load(f)
    return OpDef(opref.get_full_name(), data)


def meta_config(run: Run) -> RunConfig:
    with open(run_meta_path(run, "config.json")) as f:
        return json.load(f)


def meta_cmd(run: Run) -> OpCmd:
    meta_dir = run_meta_dir(run)
    cmd_filename = os.path.join(meta_dir, "proc", "cmd")
    env_filename = os.path.join(meta_dir, "proc", "env")
    return OpCmd(_decode_cmd_args(cmd_filename), _decode_cmd_env(env_filename))


def _decode_cmd_args(filename: str):
    with open(filename) as f:
        return [line.rstrip() for line in f.readlines()]


def _decode_cmd_env(filename: str):
    with open(filename) as f:
        return dict([line.rstrip().split("=", 1) for line in f.readlines()])


# =================================================================
# Make run
# =================================================================


def make_run(location: Optional[str] = None):
    run_id = unique_run_id()
    location = location or config.runs_home()
    run_dir = os.path.join(location, run_id)
    make_dir(run_dir)
    return Run(run_id, run_dir, run_name_for_id(run_id))


def unique_run_id():
    return str(uuid.uuid4())


def run_name_for_id(run_id: str) -> str:
    from proquint import uint2quint_str

    return uint2quint_str(_run_id_as_uint(run_id))


def _run_id_as_uint(run_id: str):
    if len(run_id) >= 32:
        # Test for likely hex-encoded UUID
        try:
            return int(run_id[:8], 16)
        except ValueError:
            pass
    from binascii import crc32

    return crc32(run_id.encode())


def run_timestamp():
    """Returns an integer use for run timestamps.

    Ensures that subsequent calls return increasing values.
    """
    ts = time.time_ns() // 1000
    with __last_ts_lock:
        if __last_ts is not None and __last_ts >= ts:
            ts = __last_ts + 1
        globals()["__last_ts"] = ts
    return ts


# =================================================================
# Meta init
# =================================================================


def init_run_meta(
    run: Run,
    opref: OpRef,
    opdef: OpDef,
    config: RunConfig,
    cmd: OpCmd,
    user_attrs: Optional[dict[str, Any]] = None,
    system_attrs: Optional[dict[str, Any]] = None,
):
    if opref.op_name != opdef.name:
        raise ValueError(
            f"mismatched names in opref ('{opref.op_name}') and opdef ('{opdef.name}')"
        )
    meta_dir = _ensure_run_meta_dir(run)
    _write_schema_file(meta_dir)
    _ensure_meta_log_dir(meta_dir)
    log = _runner_log(run)
    _write_run_id(run, meta_dir, log)
    _write_opdef(opdef, meta_dir, log)
    _write_config(config, meta_dir, log)
    _write_cmd_args(cmd, meta_dir, log)
    _write_cmd_env(cmd, meta_dir, log)
    if user_attrs:
        _write_user_attrs(user_attrs, meta_dir, log)
    if system_attrs:
        _write_system_attrs(system_attrs, meta_dir, log)
    # opref marks run as discoverable in lists - should appear last
    _write_opref(opref, meta_dir, log)
    _write_initialized_timestamp(meta_dir, log)


def _ensure_run_meta_dir(run: Run):
    meta_dir = run_meta_dir(run)
    ensure_dir(meta_dir)
    return meta_dir


def _write_schema_file(meta_dir: str):
    filename = os.path.join(meta_dir, "__schema__")
    write_file(filename, str(META_SCHEMA), readonly=True)


def _ensure_meta_log_dir(meta_dir: str):
    ensure_dir(os.path.join(meta_dir, "log"))


def _write_run_id(run: Run, meta_dir: str, log: Logger):
    log.info("Writing meta id")
    filename = os.path.join(meta_dir, "id")
    write_file(filename, run.id, readonly=True)


def _write_opdef(opdef: OpDef, meta_dir: str, log: Logger):
    log.info("Writing meta opdef.json")
    filename = os.path.join(meta_dir, "opdef.json")
    write_file(filename, _encode_json(opdef), readonly=True)


def _encode_json(val: Any):
    try:
        val = val.as_json()
    except AttributeError:
        pass
    return json.dumps(val, indent=2, sort_keys=True)


def _write_config(config: RunConfig, meta_dir: str, log: Logger):
    log.info("Writing meta config.json")
    filename = os.path.join(meta_dir, "config.json")
    write_file(filename, _encode_json(config), readonly=True)


def _write_cmd_args(cmd: OpCmd, meta_dir: str, log: Logger):
    log.info("Writing meta proc/cmd")
    ensure_dir(os.path.join(meta_dir, "proc"))
    filename = os.path.join(meta_dir, "proc", "cmd")
    write_file(filename, _encode_cmd_args(cmd.args), readonly=True)


def _encode_cmd_args(args: list[str]):
    return "".join([arg + "\n" for arg in args])


def _write_cmd_env(cmd: OpCmd, meta_dir: str, log: Logger):
    log.info("Writing meta proc/env")
    ensure_dir(os.path.join(meta_dir, "proc"))
    filename = os.path.join(meta_dir, "proc", "env")
    write_file(filename, _encode_cmd_env(cmd.env), readonly=True)


def _encode_cmd_env(env: dict[str, str]):
    return "".join([f"{name}={val}\n" for name, val in sorted(env.items())])


def _write_user_attrs(attrs: dict[str, Any], meta_dir: str, log: Logger):
    _gen_write_attrs("user", attrs, meta_dir, log)


def _write_system_attrs(attrs: dict[str, Any], meta_dir: str, log: Logger):
    _gen_write_attrs("sys", attrs, meta_dir, log)


def _gen_write_attrs(dir: str, attrs: dict[str, Any], meta_dir: str, log: Logger):
    ensure_dir(os.path.join(meta_dir, dir))
    for name in attrs:
        log.info("Writing meta %s/%s", dir, name)
        filename = os.path.join(meta_dir, dir, name)
        encoded = json.dumps(attrs[name])
        write_file(filename, encoded, readonly=True)


def _write_opref(opref: OpRef, meta_dir: str, log: Logger):
    log.info("Writing meta opref")
    filename = os.path.join(meta_dir, "opref")
    write_file(filename, encode_opref(opref), readonly=True)


def _write_initialized_timestamp(meta_dir: str, log: Logger):
    log.info("Writing meta initialized")
    filename = os.path.join(meta_dir, "initialized")
    timestamp = run_timestamp()
    write_file(filename, str(timestamp), readonly=True)


# =================================================================
# Stage run
# =================================================================


def stage_run(run: Run, project_dir: str):
    stage_sourcecode(run, project_dir)
    apply_config(run)
    stage_runtime(run, project_dir)
    stage_dependencies(run, project_dir)
    finalize_staged_run(run)


def stage_sourcecode(run: Run, project_dir: str):
    log = _runner_log(run)
    opdef = meta_opdef(run)
    _copy_sourcecode(run, project_dir, opdef, log)
    _stage_sourcecode_hook(run, project_dir, opdef, log)
    _apply_log_files(run, "s")


def _copy_sourcecode(run: Run, project_dir: str, opdef: OpDef, log: Logger):
    sourcecode = run_sourcecode.init(project_dir, opdef)
    log.info(f"Copying source code (see log/files for details): {sourcecode.patterns}")
    copy_files(project_dir, run.run_dir, sourcecode.paths)


def _stage_sourcecode_hook(run: Run, project_dir: str, opdef: OpDef, log: Logger):
    exec = opdef.get_exec().get_stage_sourcecode()
    if exec:
        _run_phase_exec(
            run,
            "stage-sourcecode",
            exec,
            run.run_dir,
            _phase_exec_env(run, project_dir),
            "10_sourcecode",
            log,
        )


def apply_config(run: Run):
    log = _runner_log(run)
    config = meta_config(run)
    opdef = meta_opdef(run)
    log.info("Applying configuration (see log/patched for details)")
    diffs = run_config.apply_config(config, opdef, run.run_dir)
    _log_applied_config(run, diffs)


def stage_runtime(run: Run, project_dir: str):
    log = _runner_log(run)
    opdef = meta_opdef(run)
    _stage_runtime_hook(run, project_dir, opdef, log)
    _apply_log_files(run, "r")


def _stage_runtime_hook(run: Run, project_dir: str, opdef: OpDef, log: Logger):
    exec = opdef.get_exec().get_stage_runtime()
    if exec:
        _run_phase_exec(
            run,
            "stage-runtime",
            exec,
            run.run_dir,
            _phase_exec_env(run, project_dir),
            "20_runtime",
            log,
        )


def stage_dependencies(run: Run, project_dir: str):
    log = _runner_log(run)
    opdef = meta_opdef(run)
    _resolve_dependencies(run, project_dir, opdef, log)
    _stage_dependencies_hook(run, project_dir, opdef, log)
    _apply_log_files(run, "d")


def _resolve_dependencies(run: Run, project_dir: str, opdef: OpDef, log: Logger):
    for dep in opdef.get_dependencies():
        pass

    # TODO
    # dependencies = run_dependencies.init(project_dir, opdef)
    # log.info(f"Copying dependencies (see log/files for details): {dependencies.patterns}")
    # copy_files(project_dir, run.run_dir, dependencies.paths)


def _stage_dependencies_hook(run: Run, project_dir: str, opdef: OpDef, log: Logger):
    exec = opdef.get_exec().get_stage_dependencies()
    if exec:
        _run_phase_exec(
            run,
            "stage-dependencies",
            exec,
            project_dir,
            _phase_exec_env(run, project_dir),
            "30_dependencies",
            log,
        )


def finalize_staged_run(run: Run):
    log = _runner_log(run)
    _finalize_staged_files(run, log)
    _write_staged_timestamp(run_meta_dir(run), log)


def _finalize_staged_files(run: Run, log: Logger):
    log.info("Finalizing staged files (see manifest for details)")
    with RunManifest(run, "w") as m:
        for type, path in _reduce_files_log(run):
            filename = os.path.join(run.run_dir, path)
            set_readonly(filename)
            digest = file_sha256(filename)
            m.add(type, digest, path)


def _write_staged_timestamp(meta_dir: str, log: Logger):
    log.info("Writing meta staged")
    filename = os.path.join(meta_dir, "staged")
    timestamp = run_timestamp()
    write_file(filename, str(timestamp), readonly=True)


def _reduce_files_log(run: Run):
    paths: Dict[str, LoggedFileType] = {}
    for event, type, modified, path in _iter_files_log(run):
        if event == "a":
            paths[path] = type
        elif event == "d":
            paths.pop(path, None)
    for path, type in paths.items():
        yield type, path


# =================================================================
# Run
# =================================================================


def start_run(run: Run):
    cmd = meta_cmd(run)
    p = subprocess.Popen(
        cmd.args,
        env=cmd.env,
        cwd=run.run_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return p


def open_run_output(run: Run, p: subprocess.Popen[bytes]):
    output_filename = run_meta_path(run, "output", "40_run")
    ensure_dir(os.path.dirname(output_filename))
    output = run_output.RunOutput(output_filename)
    output.open(p)
    return output


def finalize_run(run: Run, exit_status: int):
    assert False, "TODO run finalize-run hook, make files readonly, finalize manifest"


# =================================================================
# Utils
# =================================================================

LoggedFileEvent = Literal["a", "d", "m"]
LoggedFileType = Literal["s", "d", "r"]
RunFileType = Literal["s", "d", "r", "g"]


def _runner_log(run: Run):
    filename = _runner_log_filename(run)
    filename_parent = os.path.dirname(filename)
    assert os.path.exists(filename_parent), filename_parent
    log = logging.Logger("runner")
    handler = logging.FileHandler(filename)
    log.addHandler(handler)
    formatter = logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%dT%H:%M:%S%z")
    handler.setFormatter(formatter)
    return log


def _runner_log_filename(run: Run):
    return run_meta_path(run, "log", "runner")


def _run_meta_schema(run: Run):
    with open(run_meta_path(run, "__schema__")) as f:
        return f.read().rstrip()


def _apply_log_files(run: Run, type: LoggedFileType):
    pre_files = _init_pre_files_index(run)
    seen = set()
    with _open_files_log(run) as f:
        for entry in _iter_run_files(run):
            relpath = os.path.relpath(entry.path, run.run_dir)
            seen.add(relpath)
            modified = int(entry.stat().st_mtime * 1_000_000)
            pre_modified = pre_files.get(relpath)
            if modified == pre_modified:
                continue
            event = "a" if pre_modified is None else "m"
            encoded = _encode_logged_file(LoggedFile(event, type, modified, relpath))
            f.write(encoded)
        for path in pre_files:
            if path not in seen:
                encoded = _encode_logged_file(LoggedFile("d", type, None, path))
                f.write(encoded)


def _iter_run_files(run: Run):
    return _scan_files(run.run_dir)


def _scan_files(dir: str) -> Generator[DirEntry[str], Any, None]:
    for entry in os.scandir(dir):
        if entry.is_file():
            yield entry
        elif entry.is_dir():
            for entry in _scan_files(entry.path):
                yield entry


PreFilesIndex = Dict[str, int | None]


def _init_pre_files_index(run: Run) -> PreFilesIndex:
    return {path: modified for event, type, modified, path in _iter_files_log(run)}


class LoggedFile(NamedTuple):
    event: LoggedFileEvent
    type: LoggedFileType
    modified: int | None
    path: str


def _iter_files_log(run: Run):
    schema = _run_meta_schema(run)
    if schema != META_SCHEMA:
        raise TypeError(f"unsupported meta schema: {schema!r}")
    filename = run_meta_path(run, "log", "files")
    try:
        f = open(filename)
    except FileNotFoundError:
        pass
    else:
        lineno = 1
        for line in f:
            try:
                yield _decode_files_log_line(line.rstrip())
            except TypeError:
                raise TypeError(
                    "bad encoding in \"{filename}\", line {lineno}: {line!r}"
                )
            lineno += 1


def _decode_files_log_line(line: str):
    parts = line.split(" ", 3)
    if len(parts) != 4:
        raise TypeError()
    event, type, modified_str, path = parts
    if modified_str == "-":
        modified = None
    else:
        try:
            modified = int(modified_str)
        except ValueError:
            raise TypeError()
    if event not in ("a", "d", "m"):
        raise TypeError()
    if type not in ("s", "d", "r"):
        raise TypeError()
    return LoggedFile(event, type, modified, path)


def _open_files_log(run: Run):
    return open(run_meta_path(run, "log", "files"), "a")


def _encode_logged_file(file: LoggedFile):
    return f"{file.event} {file.type} {file.modified or '-'} {file.path}\n"


class RunManifest:
    def __init__(self, run: Run, mode: Literal["r", "w", "a"] = "r"):
        self._f = open(run_meta_path(run, "manifest"), mode)

    def close(self):
        self._f.close()

    def __enter__(self):
        self._f.__enter__()
        return self

    def __exit__(self, *exc: Any):
        self._f.__exit__(*exc)

    def add(self, type: RunFileType, digest: str, path: str):
        self._f.write(_encode_run_manifest_entry(type, digest, path))


def _encode_run_manifest_entry(type: RunFileType, digest: str, path: str):
    return f"{type} {digest} {path}\n"


def _log_applied_config(run: Run, diffs: list[tuple[str, UnifiedDiff]]):
    with open(run_meta_path(run, "log", "patched"), "a") as f:
        for path, diff in sorted(diffs):
            for line in diff:
                f.write(line)


class RunExecError(Exception):
    pass


def _run_phase_exec(
    run: Run,
    phase_name: str,
    exec_cmd: str | list[str],
    cwd: str,
    env: dict[str, str],
    output_name: str,
    log: Logger,
):
    log.info(f"Running {phase_name} (see output/{output_name} for output): {exec_cmd}")

    proc_args, use_shell = _proc_args(exec_cmd)
    proc_env = {**os.environ, **env}
    p = subprocess.Popen(
        proc_args,
        shell=use_shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
        env=proc_env,
    )
    output_filename = run_meta_path(run, "output", output_name)
    output = run_output.RunOutput(output_filename)
    ensure_dir(os.path.dirname(output_filename))
    output.open(p)
    exit_code = p.wait()
    output.wait_and_close()
    log.info(f"Exit code for {phase_name}: {exit_code}")
    if exit_code != 0:
        raise RunExecError(phase_name, proc_args, exit_code)


def _proc_args(exec_cmd: str | list[str]) -> tuple[str | list[str], bool]:
    if isinstance(exec_cmd, list):
        return exec_cmd, False
    line1, *rest = exec_cmd.splitlines()
    if line1.startswith("#!"):
        return [line1[2:].rstrip(), "-c", "".join(rest)], False
    else:
        return exec_cmd, True


def _phase_exec_env(run: Run, project_dir: str):
    return {
        "run_dir": run.run_dir,
        "project_dir": project_dir,
    }
