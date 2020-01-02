def code_to_lines(code):
    return list(map(str.rstrip, code.split('\n')))


def lines_to_code(lines):
    return '\n'.join(lines)


def add_indent(code, indent=' ' * 4):
    if isinstance(indent, int):
        indent = ' ' * (4 * indent)
    lines = code_to_lines(code)
    return lines_to_code((indent + line for line in lines))


def remove_indent(code):
    lines = code_to_lines(code)
    if not lines:
        return ''
    indent = ''.join(itertools.takewhile(str.isspace, lines[0]))
    indent_len = len(indent)
    res = []
    for line in lines:
        if line.startswith(indent):
            res.append(line[indent_len:])
        else:
            res.append(line)
    return lines_to_code(res)


def reindent(code, indent):
    return add_indent(remove_indent(code), indent)
