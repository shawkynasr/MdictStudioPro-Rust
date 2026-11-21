"""Original bridge fixture: prints must not interfere with callback messages."""
import os
import sys
from pathlib import Path
from base_plugin import BaseConverterPlugin

print("Plugin import: ordinary stdout")
os.write(1, b"Native stdout write: not protocol JSON\n")


class NoisyPlugin(BaseConverterPlugin):
    name = "Bridge qualification fixture"

    def convert(self, input_file, output_file, encoding, progress_callback, log_callback):
        print("Conversion debug print")
        print("Fixture stderr warning", file=sys.stderr)
        log_callback("Structured callback: English · 中文 · العربية")
        progress_callback(25)
        Path(output_file).write_bytes(Path(input_file).read_bytes())
        Path(input_file + "_log.txt").write_text("Sidecar retained in result bundle\n", encoding="utf-8")
        progress_callback(100)
        return "Fixture conversion completed"


class FailingPlugin(BaseConverterPlugin):
    def convert(self, input_file, output_file, encoding, progress_callback, log_callback):
        Path(output_file).write_text("partial", encoding="utf-8")
        raise RuntimeError("Intentional fixture failure")


class SlowPlugin(BaseConverterPlugin):
    def convert(self, input_file, output_file, encoding, progress_callback, log_callback):
        import time
        log_callback("Waiting for cancellation")
        progress_callback(1)
        while True:
            time.sleep(0.05)


class OptionsPlugin(BaseConverterPlugin):
    """scalar-map-v1 fixture; options are available before convert()."""
    name = 'Options demo'
    description = 'Prefix a new entry and optionally uppercase the source entries.'
    options_schema = [
        {'key': 'prefix', 'type': 'string', 'label': 'Prefix · 字 · العربية', 'default': 'Options default'},
        {'key': 'uppercase', 'type': 'boolean', 'label': 'Uppercase source', 'default': False},
    ]

    def convert(self, input_file, output_file, encoding, progress_callback, log_callback):
        options = getattr(self, 'options', {})
        body = Path(input_file).read_text(encoding='utf-8')
        if options.get('uppercase', False):
            body = body.upper()
        # Prefix a complete canonical dictionary entry, keeping the source rows.
        prefix = options.get('prefix', 'Options default')
        if not isinstance(prefix, str) or '\n' in prefix or '\r' in prefix:
            raise ValueError('prefix must be a single line')
        Path(output_file).write_text('plugin-options\n' + prefix + '\n</>\n' + body, encoding='utf-8')
        return 'Options fixture completed'
