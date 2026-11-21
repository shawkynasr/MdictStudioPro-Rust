from pathlib import Path
from base_plugin import BaseConverterPlugin

class OptionsPlugin(BaseConverterPlugin):
    name = 'Folder options demo'
    description = 'Prefix a new entry and optionally uppercase the source entries.'
    options_schema = [
        {'key': 'prefix', 'type': 'string', 'label': 'Prefix · 字 · العربية', 'default': 'Folder default'},
        {'key': 'uppercase', 'type': 'boolean', 'label': 'Uppercase source', 'default': False},
    ]

    def convert(self, input_file, output_file, encoding, progress_callback, log_callback):
        options = getattr(self, 'options', {})
        body = Path(input_file).read_text(encoding='utf-8')
        if options.get('uppercase', False):
            body = body.upper()
        prefix = options.get('prefix', 'Folder default')
        if not isinstance(prefix, str) or '\n' in prefix or '\r' in prefix:
            raise ValueError('prefix must be a single line')
        Path(output_file).write_text('plugin-options\n' + prefix + '\n</>\n' + body, encoding='utf-8')
        return 'Folder options fixture completed'
