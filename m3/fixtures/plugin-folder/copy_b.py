from pathlib import Path
from base_plugin import BaseConverterPlugin

class CopyPlugin(BaseConverterPlugin):
    name = 'Repeated copy converter'
    description = 'Same display name and class in two files; both must remain selectable.'

    def convert(self, input_file, output_file, encoding, progress_callback, log_callback):
        Path(output_file).write_bytes(Path(input_file).read_bytes())
        return 'Folder copy fixture completed'
