"""Chat JSON formats with logprobs: native schema masks plus mandatory final validation.

No object-only fallback for a missing schema validator; no rewriting streamed text.
The legacy unscored Chat adapter stays independent.
"""
from dataclasses import dataclass
import copy
import json

from serve.grammar import GrammarConstraint


@dataclass
class JsonOutput:
    schema: dict
    validator: object

    def constraint(self, thinking, tools, budget):
        source = json.dumps(native_schema(self.schema), ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        return GrammarConstraint(source, bool(thinking), bool(tools), json_schema=True,
                                 reasoning_tokens=min(budget or 0, 8192) if thinking else 0)

    def instruction(self):
        return ("When producing the final assistant answer, return exactly one JSON value matching this schema. "
                "Do not add Markdown fences or text outside the JSON. Function calls may precede the answer. "
                "Schema: " + json.dumps(self.schema, ensure_ascii=False, allow_nan=False))

    def validate(self, text):
        # Duplicate keys, non-finite numbers and invalid Unicode never pass.
        value = strict_json(text)
        error = next(self.validator.iter_errors(value), None)
        if error is not None:
            path = "/" + "/".join(str(part) for part in error.absolute_path)
            raise ValueError("JSON output failed schema validation at " + path + ": " + error.message)


def schema_nodes(schema):
    """Yield schemas, never property names, annotation values or const data."""
    pending = [schema]
    while pending:
        node = pending.pop()
        if not isinstance(node, dict):
            continue
        yield node
        for key in ("properties", "patternProperties", "$defs", "definitions", "dependentSchemas"):
            if isinstance(node.get(key), dict):
                pending.extend(node[key].values())
        for key in ("allOf", "anyOf", "oneOf", "prefixItems"):
            if isinstance(node.get(key), list):
                pending.extend(node[key])
        for key in ("additionalProperties", "items", "contains", "propertyNames", "if", "then", "else", "not",
                    "unevaluatedProperties", "unevaluatedItems", "contentSchema"):
            if key in node:
                pending.append(node[key])


def native_schema(schema):
    """Equivalent simplification for a native compiler's optional-false limitation."""
    result = copy.deepcopy(schema)
    for node in schema_nodes(result):
        if node.get("additionalProperties") is False:
            # A forbidden, non-required property in a closed object is exactly
            # equivalent to omitting it. Required false schemas stay impossible.
            props = node.get("properties", {})
            if isinstance(props, dict):
                for name in list(props):
                    if props[name] is False and name not in node.get("required", []):
                        del props[name]
    return result




def prepare_json_output(fmt):
    kind = fmt.get("type") if isinstance(fmt, dict) else None
    if kind == "text":
        fields(fmt, "type", "response_format")
        return None
    if kind == "json_object":
        fields(fmt, "type", "response_format")
        schema = {"type": "object"}
    elif kind == "json_schema":
        fields(fmt, "type name description schema strict", "response_format")
        name = string(fmt.get("name"), "response_format.name", False)
        import re
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
            raise RequestError("expected 1-64 letters/digits/underscores/dashes", "response_format.name")
        if "description" in fmt:
            string(fmt["description"], "response_format.description")
        if fmt.get("strict") is not None and type(fmt["strict"]) is not bool:
            raise RequestError("strict must be boolean or null", "response_format.strict")
        schema = fmt.get("schema")
        if not isinstance(schema, dict):
            raise RequestError("schema must be a JSON Schema object", "response_format.schema")
    else:
        unsupported("supported response_format types: text, json_object, json_schema", "response_format")

    # Bound admission and prohibit external references before model loading.
    raw = json.dumps(schema, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    if len(raw.encode("utf-8")) > 8192:
        raise RequestError("JSON schema exceeds 8192 UTF-8 bytes", "response_format.schema")
    pending = [(schema, 0)]
    while pending:
        node, depth = pending.pop()
        if depth > 32:
            raise RequestError("JSON schema nesting exceeds 32", "response_format.schema")
        if isinstance(node, dict):
            pending.extend((value, depth + 1) for value in node.values())
        elif isinstance(node, list):
            pending.extend((value, depth + 1) for value in node)
    try:
        from jsonschema import Draft202012Validator, FormatChecker
        from jsonschema.exceptions import SchemaError
        from referencing import Registry
        from referencing.exceptions import NoSuchResource
    except ImportError as exc:
        raise RequestError("JSON output requires requirements-json.txt; no weaker validation is used",
                           "response_format", "unsupported_parameter") from exc
    if schema.get("$schema", "https://json-schema.org/draft/2020-12/schema") not in (
            "https://json-schema.org/draft/2020-12/schema", "https://json-schema.org/draft/2020-12/schema#"):
        raise RequestError("JSON output uses JSON Schema draft 2020-12", "response_format.schema")

    # Walk schemas, not arbitrary object values. A property named "$ref" or
    # JSON data inside const/default must not be mistaken for a reference.
    annotations = set("$schema $id $anchor $dynamicAnchor $defs definitions then else minContains maxContains title description default examples "
                      "deprecated readOnly writeOnly $comment contentEncoding contentMediaType contentSchema".split())
    for node in schema_nodes(schema):
        unknown = set(node) - set(Draft202012Validator.VALIDATORS) - annotations
        if unknown:
            raise RequestError("unknown JSON Schema keyword: " + sorted(unknown)[0], "response_format.schema")
        for key in ("$ref", "$dynamicRef"):
            if key in node and (not isinstance(node[key], str) or not node[key].startswith("#")):
                raise RequestError("only local schema references are supported", "response_format.schema")

    def no_remote(uri):
        raise NoSuchResource(ref=uri)

    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, registry=Registry(retrieve=no_remote), format_checker=FormatChecker())
    except SchemaError as exc:
        raise RequestError("invalid JSON schema: " + exc.message, "response_format.schema") from exc
    return JsonOutput(schema, validator)


class RequestError(ValueError):
    def __init__(self, message, param=None, code=None):
        super().__init__((param + ": " if param else "") + message)


def fields(value, allowed, param):
    if not isinstance(value, dict) or set(value) - set(allowed.split()):
        raise RequestError("unsupported fields", param)


def string(value, param, empty=True):
    if not isinstance(value, str) or (not empty and not value):
        raise RequestError("expected a string", param)
    value.encode("utf-8")
    return value


def unsupported(message, param):
    raise RequestError(message, param)


def strict_json(raw):
    def pairs(entries):
        out = {}
        for key, value in entries:
            if key in out:
                raise ValueError("duplicate JSON key: " + key)
            out[key] = value
        return out
    def constant(value):
        raise ValueError("invalid JSON constant: " + value)
    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("invalid JSON: " + str(exc)) from exc


def prepare_chat_json(fmt):
    if fmt is None:
        return None
    if not isinstance(fmt, dict):
        raise ValueError("response_format must be an object")
    if fmt.get("type") == "json_schema":
        fields(fmt, "type json_schema", "response_format")
        spec = fmt.get("json_schema")
        if not isinstance(spec, dict):
            raise ValueError("response_format.json_schema must be an object")
        fields(spec, "name description schema strict", "response_format.json_schema")
        return prepare_json_output({"type": "json_schema", **spec})
    return prepare_json_output(fmt)


def json_chunks(chunks, output):
    """Validate the exact delivered bytes; never canonicalize or repair a scored answer."""
    from serve.structured import StructuredOutputError
    parts = []
    try:
        for chunk in chunks:
            if chunk is not None:
                choice = chunk["choices"][0]
                parts.append(choice["delta"].get("content") or "")
                finish = choice["finish_reason"]
                if finish is not None and finish != "tool_calls":
                    if finish != "stop":
                        raise StructuredOutputError("native JSON output is incomplete; increase the output budget")
                    try:
                        output.validate("".join(parts))
                    except Exception as exc:
                        raise StructuredOutputError(str(exc)) from exc
            yield chunk
    finally:
        chunks.close()
