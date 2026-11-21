"""Private child entry point. Protocol uses a dedicated authenticated TCP socket.

stdout/stderr remain ordinary OS streams, including os.write and native libraries.
This executes trusted local Python code; it is not a Python security sandbox.
"""
import inspect
import json
import math
import os
import shutil
import signal
import stat
import pathlib
import socket
import sys
import threading
import time
import traceback
import types


def validate_options(options):
    if type(options) is not dict or len(options) > 64:
        raise ValueError("Plugin options must be an object with at most 64 fields")
    import re
    for key, value in options.items():
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', key):
            raise ValueError("Plugin option keys must be ASCII identifiers <=64 bytes")
        if type(value) is str:
            if len(value.encode('utf-8')) > 2048:
                raise ValueError("Plugin option string exceeds 2048 UTF-8 bytes")
        elif type(value) is bool:
            pass
        elif type(value) in (int, float):
            if not math.isfinite(value) or abs(value) > 9007199254740991:
                raise ValueError("Plugin option number exceeds the finite safe range")
        else:
            raise ValueError("Plugin option values must be strings, booleans or numbers")
    if len(json.dumps(options, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')) > 8192:
        raise ValueError("Plugin options exceed 8 KiB")
    return options


def start_parent_watch(config):
    """Cooperative trusted-bridge cleanup, never a general stale-directory sweep.

    This daemon cannot interrupt native plugin code that holds the Python GIL.
    Detached descendants and malicious trusted plugins remain outside this guard.
    """
    watch = config.get("parent_watch")
    if watch is None:  # direct wrapper harnesses without a native parent
        return
    parent_pid = watch["pid"]
    if type(parent_pid) is not int or parent_pid <= 1:
        raise ValueError("Invalid parent identity")
    root = pathlib.Path(watch["stage"])
    if (not root.is_absolute() or not root.name.startswith(".tmp")
            or root.is_symlink() or pathlib.Path(__file__).resolve() != root / "bridge.py"):
        raise ValueError("Invalid owned bridge stage")
    marker = root / ".studio-parent-watch"
    token = config["token"]
    if marker.is_symlink() or marker.read_text() != token:
        raise ValueError("Invalid bridge stage marker")
    identity = root.stat()
    parent_fd = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY)
    stop = threading.Event()

    def orphaned():
        try:
            while not stop.wait(0.1):
                if os.getppid() == parent_pid:
                    continue
                # Resolve only the original directory entry under the held parent.
                # rmtree's fd traversal does not follow nested symlinks.
                try:
                    current = os.stat(root.name, dir_fd=parent_fd, follow_symlinks=False)
                    if (stat.S_ISDIR(current.st_mode)
                            and (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino)
                            and not marker.is_symlink() and marker.read_text() == token
                            and shutil.rmtree.avoids_symlink_attacks):
                        shutil.rmtree(root.name, dir_fd=parent_fd)
                except OSError:
                    pass  # still stop the bridge; never broaden cleanup on error
                finally:
                    # Native run_child creates a fresh group. Never signal the
                    # inherited group when a non-native harness launches us.
                    if os.getpgrp() == os.getpid():
                        os.killpg(os.getpid(), signal.SIGKILL)
                    os._exit(74)
        finally:
            os.close(parent_fd)

    threading.Thread(target=orphaned, name="studio-parent-watch", daemon=True).start()
    # Keep watching through plugin completion until process exit. The native
    # parent may die after done, before collecting the child.


def run():
    config = json.loads(sys.stdin.buffer.readline(65537))
    start_parent_watch(config)
    connection = socket.create_connection(("127.0.0.1", config["port"]), timeout=10)
    connection.settimeout(10)
    lock = threading.Lock()

    def send(message):
        data = json.dumps(message, ensure_ascii=True, allow_nan=False).encode() + b"\n"
        if len(data) > 8192:
            raise ValueError("Bridge frame exceeds 8 KiB")
        with lock:
            connection.sendall(data)

    send({"type": "hello", "token": config["token"], "version": 1})
    # Install the app's compatible abstract base before importing user code.
    base = types.ModuleType("base_plugin")
    exec(compile(pathlib.Path(config["base"]).read_bytes(), config["base"], "exec"), base.__dict__)
    sys.modules["base_plugin"] = base
    sys.path.insert(0, str(pathlib.Path(config["original_plugin"]).parent))
    module = types.ModuleType("studio_selected_plugin")
    module.__file__ = config["original_plugin"]
    sys.modules[module.__name__] = module
    last_progress = [0.0]
    logs = [0]

    def progress(value):
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("Non-finite progress")
        now = time.monotonic()
        if now - last_progress[0] >= 0.05 or value >= 100:
            last_progress[0] = now
            send({"type": "progress", "value": min(100, max(0, int(value)))})

    def log(value):
        # Callbacks are bounded independently of raw stdout/stderr.
        if logs[0] < 64:
            send({"type": "log", "message": str(value)[:512]})
            logs[0] += 1

    try:
        options = validate_options(config.get("options", {}))
        exec(compile(pathlib.Path(config["snapshot"]).read_bytes(), module.__file__, "exec"), module.__dict__)
        if config.get("mode") == "inspect":
            helper = types.ModuleType("studio_catalog_helper")
            helper_path = pathlib.Path(__file__).with_name("plugin_catalog.py")
            exec(compile(helper_path.read_bytes(), str(helper_path), "exec"), helper.__dict__)
            catalog = helper.inspect_module(module, base.BaseConverterPlugin, validate_options)
            pathlib.Path(config["catalog"]).write_text(json.dumps(catalog, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            send({"type": "done", "message": "Plugin inspection completed"})
            return 0
        cls = module.__dict__.get(config["class_name"])
        if not inspect.isclass(cls) or not issubclass(cls, base.BaseConverterPlugin) or cls.__module__ != module.__name__:
            raise ValueError("Select a concrete BaseConverterPlugin class defined in the selected file")
        converter = cls()
        if options:
            converter.options = options
        summary = converter.convert(config["input"], config["output"], "utf-8", progress, log)
        send({"type": "done", "message": str(summary)[:512]})
    except BaseException as error:
        traceback.print_exc()
        send({"type": "error", "message": (type(error).__name__ + ": " + str(error))[:512]})
        return 1
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
