"""Bounded metadata for explicitly trusted, selected-file plugin inspection.

No constructor or convert method is invoked. Import itself executes trusted code.
This scalar-fields-v1 schema is additive, not an arbitrary legacy schema claim.
"""
import inspect
import json
import re


def text(value, maximum):
    if type(value) is not str or len(value.encode('utf-8')) > maximum:
        raise ValueError('Metadata string exceeds supported bounds')
    return value


def schema_fields(value, validate_options):
    if type(value) is not list or len(value) > 16:
        raise ValueError('options_schema must contain at most 16 fields')
    fields = []
    keys = set()
    for item in value:
        if type(item) is not dict or set(item) - {'key', 'type', 'label', 'default', 'choices'}:
            raise ValueError('Unsupported option schema fields')
        if not {'key', 'type', 'default'} <= set(item):
            raise ValueError('Option schema requires key, type and default')
        key = item['key']
        if type(key) is not str or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', key) or key in keys:
            raise ValueError('Option keys must be unique ASCII identifiers')
        keys.add(key)
        kind, default = item['type'], item['default']
        if kind not in ('string', 'boolean', 'number', 'choice'):
            raise ValueError('Supported types: string, boolean, number, choice')
        validate_options({key: default})
        if not ((kind in ('string', 'choice') and type(default) is str) or
                (kind == 'boolean' and type(default) is bool) or
                (kind == 'number' and type(default) in (int, float))):
            raise ValueError('Option default does not match its type')
        field = {'key': key, 'type': kind, 'label': text(item.get('label', key), 256), 'default': default, 'choices': []}
        if kind == 'choice':
            choices = item.get('choices')
            if type(choices) is not list or not 1 <= len(choices) <= 16:
                raise ValueError('Choice requires 1..16 strings')
            field['choices'] = [text(c, 256) for c in choices]
            if len(set(choices)) != len(choices) or default not in choices:
                raise ValueError('Choice default must be one of the unique choices')
        elif 'choices' in item:
            raise ValueError('choices only applies to choice fields')
        fields.append(field)
    validate_options({f['key']: f['default'] for f in fields})
    return fields


def inspect_module(module, base, validate_options):
    classes = []
    seen = set()
    for name, cls in sorted(vars(module).items()):
        if not (inspect.isclass(cls) and cls.__module__ == module.__name__ and
                issubclass(cls, base) and cls is not base and not inspect.isabstract(cls)):
            continue
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}', name) or id(cls) in seen:
            continue
        seen.add(id(cls))
        if len(classes) >= 16:
            raise ValueError('Selected plugin defines more than 16 converter classes')
        # Schema errors leave this class selectable through manual JSON options.
        try:
            fields, error = schema_fields(getattr(cls, 'options_schema', []), validate_options), None
        except (ValueError, TypeError, UnicodeError) as exc:
            fields, error = [], str(exc)[:256]
        classes.append({'class_name': name, 'name': text(getattr(cls, 'name', name), 256),
                        'description': text(getattr(cls, 'description', ''), 512),
                        'fields': fields, 'schema_error': error})
    catalog = {'version': 1, 'classes': classes}
    if len(json.dumps(catalog, ensure_ascii=False, allow_nan=False).encode('utf-8')) > 32768:
        raise ValueError('Plugin catalog exceeds 32 KiB')
    return catalog
