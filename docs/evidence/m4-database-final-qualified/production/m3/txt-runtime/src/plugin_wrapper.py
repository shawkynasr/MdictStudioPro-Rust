"""Private child entry point. Protocol uses a dedicated authenticated TCP socket.

stdout/stderr remain ordinary OS streams, including os.write and native libraries.
This executes trusted local Python code; it is not a Python security sandbox.
"""
import inspect
import json
import math
import pathlib
import socket
import sys
import threading
import time
import traceback
import types


def run():
    config = json.loads(sys.stdin.buffer.readline(65537))
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
        exec(compile(pathlib.Path(config["snapshot"]).read_bytes(), module.__file__, "exec"), module.__dict__)
        cls = module.__dict__.get(config["class_name"])
        if not inspect.isclass(cls) or not issubclass(cls, base.BaseConverterPlugin) or cls.__module__ != module.__name__:
            raise ValueError("Select a concrete BaseConverterPlugin class defined in the selected file")
        converter = cls()
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
