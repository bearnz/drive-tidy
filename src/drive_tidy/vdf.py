"""Minimal reader for Valve's KeyValues text format (.vdf, .acf).

Keys are lower-cased, since Steam is not consistent about case ("Valve" vs
"valve"). Conditionals ([$WIN32]) and #include lines are not supported.
"""
import re

TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])|//[^\n]*|\s+')


def loads(text):
    root = {}
    stack = [root]
    key = None
    for m in TOKEN.finditer(text):
        s, brace = m.group(1), m.group(2)
        if brace == "{":
            child = {}
            stack[-1][(key or "").lower()] = child
            stack.append(child)
            key = None
        elif brace == "}":
            if len(stack) > 1:
                stack.pop()
            key = None
        elif s is not None:
            s = s.replace("\\\\", "\\").replace('\\"', '"')
            if key is None:
                key = s
            else:
                stack[-1][key.lower()] = s
                key = None
    return root


def load(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return loads(fh.read())


def get(d, *keys):
    """Walk nested keys; None if any is missing."""
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k.lower())
    return d
