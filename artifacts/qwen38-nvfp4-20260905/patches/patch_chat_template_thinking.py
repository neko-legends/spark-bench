#!/usr/bin/env python3
"""Flip the Qwen3.8 chat template so a missing `enable_thinking` means OFF.

Stock template (two sites):
    {%- if enable_thinking is undefined or enable_thinking is true %}   # reasoning prelude
    {%- if enable_thinking is defined and enable_thinking is false %}   # empty <think> block

Both treat an unspecified kwarg as thinking ON with reasoning_effort=xhigh. The
2026-09-05 role bench measured that default burning the entire max_tokens budget
on reasoning and returning no content. Patched semantics:

    undefined  -> OFF   (the new default)
    false      -> OFF
    true       -> ON    (per-request opt in via chat_template_kwargs)

Usage: patch_chat_template_thinking.py SRC.jinja DST.jinja
Writes DST only if both sites were rewritten exactly once; exits 1 otherwise so
the launcher fails loudly instead of serving an unpatched template.
"""
import sys

SITES = [
    ("{%- if enable_thinking is undefined or enable_thinking is true %}",
     "{%- if enable_thinking is defined and enable_thinking is true %}"),
    ("{%- if enable_thinking is defined and enable_thinking is false %}",
     "{%- if enable_thinking is undefined or enable_thinking is false %}"),
]


def patch(text: str) -> str:
    for old, new in SITES:
        n = text.count(old)
        if n != 1:
            raise SystemExit(f"expected exactly 1 occurrence of {old!r}, found {n}")
        text = text.replace(old, new)
    return text


def main(argv):
    if len(argv) != 3:
        raise SystemExit(__doc__)
    src, dst = argv[1], argv[2]
    with open(src, encoding="utf-8") as f:
        original = f.read()
    patched = patch(original)
    if patched == original:
        raise SystemExit("no change produced; refusing to write")
    with open(dst, "w", encoding="utf-8") as f:
        f.write(patched)
    print(f"patched {dst}: enable_thinking now defaults OFF")


if __name__ == "__main__":
    main(sys.argv)
