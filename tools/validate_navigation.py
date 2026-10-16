#!/usr/bin/env python3
"""只读校验指定入口文档的本地链接，不递归扫描仓库或维护模块清单。"""
from __future__ import annotations

import argparse
from pathlib import Path, PureWindowsPath
import re
import sys
import unicodedata
from urllib.parse import unquote, urlsplit

MAX_DOCUMENT_BYTES = 262144
DEFAULT_DOCUMENTS = ("README.md", "MODULE_MAP.md")


def _lines(text, strip_inline=True):
    """忽略示例代码和注释，保留行号用于诊断。"""
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group().count("\n"), text, flags=re.S)
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if marker:
            value = marker.group(1)
            if fence is None:
                fence = value
            elif value[0] == fence[0] and len(value) >= len(fence):
                fence = None
            continue
        if fence is None:
            yield number, re.sub(r"(`+).*?\1", "代码", line) if strip_inline else line


def _links(text):
    """提取单行内联链接和引用式链接；支持带空格的尖括号目标。"""
    lines = list(_lines(text))
    references = {}
    for unused, line in lines:
        match = re.match(r'^ {0,3}\[([^]]+)\]:\s*(<[^>]+>|\S+)', line)
        if match:
            references[match.group(1).strip().casefold()] = match.group(2).strip("<>")
    for number, line in lines:
        if re.match(r"^ {0,3}\[[^]]+\]:", line):
            continue
        for match in re.finditer(r"!?\[([^]\n]+)\]", line):
            rest = line[match.end():]
            if rest.startswith("("):
                value = rest[1:].lstrip()
                if value.startswith("<"):
                    closing = value.find(">")
                    if closing >= 0:
                        yield number, value[1:closing]
                    continue
                depth, end = 0, 0
                for end, character in enumerate(value):
                    if character.isspace() and depth == 0:
                        break
                    if character == "(" and (end == 0 or value[end - 1] != "\\"):
                        depth += 1
                    elif character == ")" and (end == 0 or value[end - 1] != "\\"):
                        if depth == 0:
                            break
                        depth -= 1
                else:
                    continue
                yield number, re.sub(r"\\([()])", r"\1", value[:end])
            else:
                ref = re.match(r"\[([^]]*)\]", rest)
                label = (ref.group(1) or match.group(1)) if ref else match.group(1)
                destination = references.get(label.strip().casefold())
                if destination is not None:
                    yield number, destination


def _headings(text):
    used = set()
    for unused, line in _lines(text, strip_inline=False):
        match = re.match(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        title = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", match.group(1))
        base = "".join(c for c in title.lower()
                       if c in "_- " or unicodedata.category(c)[0] in "LNM").replace(" ", "-")
        slug, suffix = base, 0
        while slug in used:
            suffix += 1
            slug = base + "-" + str(suffix)
        used.add(slug)
    return used


def _inside(root, path):
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError("路径超出项目范围")
    return path


def _read(path):
    if not path.is_file():
        raise ValueError("文档文件不存在")
    if path.stat().st_size > MAX_DOCUMENT_BYTES:
        raise ValueError("文档超过读取上限")
    return path.read_text(encoding="utf-8-sig")


def validate(root, documents=DEFAULT_DOCUMENTS):
    root, errors = Path(root).resolve(), []
    for name in documents:
        try:
            source = _inside(root, root / name)
            text = _read(source)
        except (OSError, UnicodeError, ValueError) as error:
            errors.append("%s: %s" % (name, error))
            continue
        for number, destination in _links(text):
            try:
                target = urlsplit(destination)
                if target.scheme in {"http", "https", "mailto"}:
                    continue  # 不请求网络，也不宣称外部链接有效。
                path = unquote(target.path)
                if (target.scheme or target.netloc or PureWindowsPath(path).drive
                        or path.startswith("/") or "\\" in path or ":" in path
                        or any(ord(c) < 32 for c in path)
                        or any(part.casefold() == ".git" for part in Path(path).parts)):
                    raise ValueError("本地链接路径不安全")
                resolved = _inside(root, source.parent / path) if path else source
                if not resolved.exists():
                    raise ValueError("链接目标不存在")
                if target.fragment:
                    if resolved.suffix.lower() != ".md":
                        raise ValueError("标题锚点需要 Markdown 文件")
                    if unquote(target.fragment) not in _headings(_read(resolved)):
                        raise ValueError("标题锚点不存在")
            except (OSError, UnicodeError, ValueError) as error:
                errors.append("%s:%s: %s [%s]" % (name, number, error, destination))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("documents", nargs="*", help="项目内入口文档；默认 README.md 和 MODULE_MAP.md")
    args = parser.parse_args()
    errors = validate(args.root, args.documents or DEFAULT_DOCUMENTS)
    for error in errors:
        print(error, file=sys.stderr)
    if not errors:
        print("导航链接校验通过；外部链接与语义未验证。")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
