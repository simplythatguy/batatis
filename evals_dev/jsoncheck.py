"""Small JSON Schema checker for the subset these eval scripts write.

Covers type (including a list of types), properties, required, additionalProperties,
items, enum, minLength, minimum, maximum and pattern. It does not implement the whole draft.
"""
from __future__ import annotations

import re


def validate(instance, schema, path='$') -> list[str]:
    """Return a list of error strings. An empty list means the instance fits the schema."""
    errors: list[str] = []
    if schema is True:
        return errors
    if schema is False:
        return [f'{path}: rejected by schema']

    expected = schema.get('type')
    if expected is not None and not _type_ok(instance, expected):
        errors.append(f'{path}: expected {expected}, got {_type_name(instance)}')
        return errors

    if 'enum' in schema and instance not in schema['enum']:
        errors.append(f'{path}: {instance!r} is not one of {schema["enum"]}')

    if isinstance(instance, str):
        if 'minLength' in schema and len(instance) < schema['minLength']:
            errors.append(f'{path}: shorter than {schema["minLength"]}')
        if 'maxLength' in schema and len(instance) > schema['maxLength']:
            errors.append(f'{path}: longer than {schema["maxLength"]}')
        if 'pattern' in schema and re.fullmatch(schema['pattern'], instance) is None:
            errors.append(f'{path}: does not match {schema["pattern"]}')

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if 'minimum' in schema and instance < schema['minimum']:
            errors.append(f'{path}: below {schema["minimum"]}')
        if 'maximum' in schema and instance > schema['maximum']:
            errors.append(f'{path}: above {schema["maximum"]}')

    if isinstance(instance, dict):
        props = schema.get('properties', {})
        required = schema.get('required', [])
        for key in required:
            if key not in instance:
                errors.append(f'{path}: missing {key}')
        additional = schema.get('additionalProperties', True)
        for key, value in instance.items():
            if key in props:
                errors.extend(validate(value, props[key], f'{path}.{key}'))
            elif additional is False:
                errors.append(f'{path}: unexpected {key}')
            elif isinstance(additional, dict):
                errors.extend(validate(value, additional, f'{path}.{key}'))

    if isinstance(instance, list) and 'items' in schema:
        for i, item in enumerate(instance):
            errors.extend(validate(item, schema['items'], f'{path}[{i}]'))

    return errors


def _type_ok(instance, expected) -> bool:
    """Accept an instance matching any of the declared JSON Schema types."""
    names = expected if isinstance(expected, list) else [expected]
    return any(_one(instance, name) for name in names)


def _one(instance, name: str) -> bool:
    """Check one supported JSON type without treating Python booleans as numbers."""
    if name == 'object':
        return isinstance(instance, dict)
    if name == 'array':
        return isinstance(instance, list)
    if name == 'string':
        return isinstance(instance, str)
    if name == 'integer':
        return isinstance(instance, int) and not isinstance(instance, bool)
    if name == 'number':
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if name == 'boolean':
        return isinstance(instance, bool)
    if name == 'null':
        return instance is None
    raise ValueError(f'unsupported schema type {name}')


def _type_name(instance) -> str:
    """Describe a Python value using the supported JSON type vocabulary."""
    if instance is None:
        return 'null'
    if isinstance(instance, bool):
        return 'boolean'
    if isinstance(instance, str):
        return 'string'
    if isinstance(instance, int):
        return 'integer'
    if isinstance(instance, float):
        return 'number'
    if isinstance(instance, list):
        return 'array'
    if isinstance(instance, dict):
        return 'object'
    return type(instance).__name__
