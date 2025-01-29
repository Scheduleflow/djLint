import regex as re
import jsbeautifier

from djlint.settings import Config
from jsbeautifier.javascript.options import BeautifierOptions


JSHTML_USE_TAG_ARG_FORMAT = re.compile(r'^("[^"]*")\s+(.*)$')


def format_jshtml_vars(
        indent: str,
        indent_level: int,
        config: Config,
        match: re.Match
) -> str:

    lead = match.group(1)

    js = match.group(3)

    if not js:
        return match.group()

    opts = BeautifierOptions({
        "indent_size": len(indent),
        "indent_level": 0,
        "preserve_newlines": False,
        "wrap_line_length": config.max_line_length,
    })
    lines = jsbeautifier.beautify(js, opts).splitlines()
    return lead + "{{ " + ('\n' + ' ' * len(lead)).join(lines) + " }}"


def format_jshtml_tags(
        indent: str,
        indent_level: int,
        config: Config,
        match: re.Match
) -> str:

    lead = match.group(1)

    tag_content = match.group(3)

    if not tag_content:
        return match.group()

    if len(tag_content) + 6 + len(lead) > config.max_line_length:
        lines = _split_jshtml_tag_lines(tag_content)
        inner_indent = len(lead) + config.indent_size * 2
        return lead + "{% " + ('\n' + ' ' * inner_indent).join(lines) + " %}"

    return lead + "{% " + tag_content + " %}"


def _split_jshtml_tag_lines(tag_content: str) -> str:

    parts = tag_content.split(maxsplit=1)

    if len(parts) != 2:
        return parts

    tag_name = parts[0]

    if tag_name == "use" or tag_name == "load":
        tag_args = JSHTML_USE_TAG_ARG_FORMAT.match(parts[1])
        if not tag_args:
            return [tag_content]
        try:
            return [tag_name, tag_args[1]] + _parse_attr_expr(tag_args[2])
        except _InvalidJSHTML:
            return [tag_content]

    return [tag_content]


def _parse_attr_expr(s):
    pos = 0
    attrs = []
    while True:
        attr, pos = _parse_next_attr_pair(s, pos)
        if attr is None:
            break
        attrs.append(attr)
    return attrs


def _consume_space(s, pos):
    while pos < len(s) and s[pos].isspace():
        pos += 1
    return pos


def _parse_next_attr_pair(s, pos):
    name_start = _consume_space(s, pos)
    if name_start == len(s):
        return None, -1
    name, value_start = _parse_attr_name(s, name_start)
    value, value_end = _parse_attr_value(s, value_start)
    return f"{name}={value}", value_end


def _parse_attr_name(s, pos):
    name = ""
    new_pos = pos
    while new_pos < len(s):
        next_char = s[new_pos]
        if next_char == "=":
            new_pos += 1
            break
        if not re.match(r"[\w-]", next_char):
            raise _InvalidJSHTML("Invalid key-value expression: Only a-z, A-Z, 0-9, - and _ characters are allowed in the key name.")
        name += next_char
        new_pos += 1
    if not name:
        raise _InvalidJSHTML("Invalid key-value expression: A key must have at least one character.")
    if new_pos > len(s) or s[new_pos - 1] != "=":
        raise _InvalidJSHTML("Invalid key-value expression: All keys must be followed up with the equals sign (=).")
    return name, new_pos


def _parse_attr_value(s, pos):
    if pos >= len(s):
        raise _InvalidJSHTML("Invalid key-value expression: Missing value after key.")

    opening_char = s[pos]
    if opening_char == '"':
        closing_char = '"'
    elif opening_char == "(":
        closing_char = ")"
    else:
        raise _InvalidJSHTML(f"Invalid key-value expression: All values must start from either \" or ( symbol, but '{opening_char}' found.")

    value = opening_char
    new_pos = pos + 1
    open_char_count = 1

    while open_char_count > 0 and new_pos < len(s):
        next_char = s[new_pos]
        value += next_char
        if next_char == closing_char:
            open_char_count -= 1
        elif next_char == opening_char:
            open_char_count += 1
        new_pos += 1

    if open_char_count != 0:
        raise _InvalidJSHTML("Invalid key-value expression: An unclosed value expression encountered.")

    return value, new_pos


class _InvalidJSHTML(Exception):
    pass
