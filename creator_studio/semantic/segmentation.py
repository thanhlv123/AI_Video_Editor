"""Linear LF-only structural scanner, preserving absolute source offsets."""
import re
from ..manifest.semantic import (BlockType, SourceSpan, SemanticBlock,
                                 SemanticDiagnostic, block_id, exact_signature)
from .spans import SemanticError

SEGMENTER_VERSION = "1"
HEADING = re.compile(r"^(#{1,6})[ \t]+\S")
LIST = re.compile(r"^[ \t]{0,3}(?:[-+*]|[0-9]{1,9}[.)])[ \t]+\S")
QUOTE = re.compile(r"^[ \t]{0,3}>[ \t]?.*")
FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})([^\n]*)$")
# Explicit dash followed by a quotation mark, never arbitrary Name: prefixes.
DIALOGUE = re.compile(r'^[ \t]*[—–][ \t]+["“«]\S')


def segment(text, structure, options, control=None):
    if type(options.markdown) is not bool or type(options.long_block_characters) is not int or options.long_block_characters < 1:
        raise SemanticError()
    # split only on LF: U+2028, U+2029 and other Unicode separators are content.
    lines = text.split("\n")
    offsets = []
    offset = 0
    for line in lines:
        offsets.append(offset)
        offset += len(line) + 1
    blocks, diagnostics = [], []
    heading_id = None
    def table_at(i):
        if i + 1 >= len(lines) or "|" not in lines[i]:
            return False
        header = lines[i].strip().strip("|").split("|")
        cells = lines[i + 1].strip().strip("|").split("|")
        return len(header) >= 2 and len(header) == len(cells) and all(re.fullmatch(r"[ \t]*:?-{3,}:?[ \t]*", c) for c in cells)
    def special(i):
        line = lines[i]
        return bool(FENCE.match(line) or HEADING.match(line) or table_at(i)
                    or LIST.match(line) or QUOTE.match(line) or DIALOGUE.match(line))
    i = 0
    while i < len(lines):
        if control is not None:
            control.check()
        if not lines[i].strip():
            i += 1
            continue
        start = i
        kind, level = BlockType.PARAGRAPH, None
        fence = FENCE.match(lines[i]) if options.markdown else None
        heading = HEADING.match(lines[i]) if options.markdown else None
        if fence:
            kind = BlockType.FENCED_CODE
            marker = fence.group(1)
            i += 1
            closed = False
            while i < len(lines):
                if control is not None:
                    control.check()
                if re.fullmatch(r"[ \t]{0,3}" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}[ \t]*", lines[i]):
                    i += 1
                    closed = True
                    break
                i += 1
            if not closed:
                diagnostics.append(SemanticDiagnostic("semantic_unclosed_fence"))
        elif heading:
            kind, level = BlockType.HEADING, len(heading.group(1))
            i += 1
        elif options.markdown and table_at(i):
            kind = BlockType.TABLE
            i += 2
            while i < len(lines) and lines[i].strip() and "|" in lines[i]:
                i += 1
        elif options.markdown and LIST.match(lines[i]):
            kind = BlockType.LIST_ITEM
            marker_end = LIST.match(lines[i]).end() - 1
            i += 1
            while i < len(lines) and lines[i].strip() and not special(i):
                indent = len(lines[i]) - len(lines[i].lstrip(" \t"))
                if indent < marker_end:
                    break
                i += 1
        elif options.markdown and QUOTE.match(lines[i]):
            kind = BlockType.BLOCKQUOTE
            i += 1
            while i < len(lines) and QUOTE.match(lines[i]) and lines[i].strip():
                i += 1
        elif options.markdown and DIALOGUE.match(lines[i]):
            kind = BlockType.DIALOGUE_LIKE
            i += 1
        else:
            i += 1
            while i < len(lines) and lines[i].strip() and not (options.markdown and special(i)):
                i += 1
        span = SourceSpan(offsets[start], offsets[i - 1] + len(lines[i - 1]))
        excerpt = text[span.start:span.end]
        key = block_id(structure, span, kind)
        blocks.append(SemanticBlock(key, len(blocks), span, excerpt, kind, level,
                                    heading_id, exact_signature(excerpt)))
        if kind == BlockType.HEADING:
            heading_id = key
        if len(excerpt) > options.long_block_characters:
            diagnostics.append(SemanticDiagnostic("semantic_long_block"))
    return blocks, diagnostics
