import regex as re
import jsbeautifier

from djlint.settings import Config
from jsbeautifier.javascript.options import BeautifierOptions


JSHTML_USE_TAG_ARG_FORMAT = re.compile(r'^("[^"]*")\s+(.*)$')


def format_jshtml_vars(indent, indent_level, config, match):

    lead = match.group(1)

    js = match.group(3)

    if not js:
        return match.group()

    opts = _build_js_beautifier_options(len(indent), config.max_line_length)
    lines = _beautify_js(js, opts)
    return lead + "{{ " + ('\n' + ' ' * len(lead)).join(lines) + " }}"


def format_jshtml_tags(indent, indent_level, config, match):

    lead = match.group(1)

    tag_content = match.group(3)

    if not tag_content:
        return match.group()

    if len(tag_content) + 6 + len(lead) > config.max_line_length:
        inner_indent = len(lead) + config.indent_size * 2
        js_options = _build_js_beautifier_options(
            config.indent_size,
            max(20, config.max_line_length - inner_indent),
        )
        lines = _split_jshtml_tag_lines(tag_content, js_options)
        return lead + "{% " + ('\n' + ' ' * inner_indent).join(lines) + " %}"

    return lead + "{% " + tag_content + " %}"


def _split_jshtml_tag_lines(tag_content, js_options):

    parts = tag_content.split(maxsplit=1)

    if len(parts) != 2:
        return parts

    tag_name = parts[0]

    if tag_name == "use" or tag_name == "load":
        tag_args = JSHTML_USE_TAG_ARG_FORMAT.match(parts[1])
        if not tag_args:
            return [tag_content]
        try:
            attrs = _parse_attr_expr(tag_args[2])
            formatted_attrs = _format_attrs(attrs, js_options)
            return [tag_name, tag_args[1]] + formatted_attrs
        except _InvalidJSHTML:
            return [tag_content]

    return [tag_content]


def _format_attrs(attrs, js_options):

    result = []
    indent = " " * js_options.indent_size

    for attr_name, attr_value in attrs:

        attr_len = len(attr_name) + 1 + len(attr_value)
        if (attr_len > js_options.wrap_line_length and attr_value[0] == "("):
            # A special formatting rule for long js expressions
            lines = _beautify_js(attr_value[1:-1].strip(), js_options)
            lines = [
                "(",
                *(indent + line for line in lines),
                ")",
            ]
        else:
            lines = _beautify_js(attr_value, js_options)

        for line_index, line in enumerate(lines):
            if line_index == 0:
                result.append(f"{attr_name}={line}")
            else:
                result.append(line)

    return result


def _parse_attr_expr(s):
    pos = 0
    attrs = []
    while True:
        attr_name, attr_value, pos = _parse_next_attr_pair(s, pos)
        if attr_name is None:
            break
        attrs.append((attr_name, attr_value))
    return attrs


def _consume_space(s, pos):
    while pos < len(s) and s[pos].isspace():
        pos += 1
    return pos


def _parse_next_attr_pair(s, pos):
    name_start = _consume_space(s, pos)
    if name_start == len(s):
        return None, None, -1
    name, value_start = _parse_attr_name(s, name_start)
    value, value_end = _parse_attr_value(s, value_start)
    return name, value, value_end


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


def _build_js_beautifier_options(indent_size, max_line_length):
    return BeautifierOptions({
        "indent_size": indent_size,
        "indent_level": 0,
        "preserve_newlines": False,
        "wrap_line_length": max_line_length,
    })


def _beautify_js(js_str, options):
    return jsbeautifier.beautify(js_str, options).splitlines()
