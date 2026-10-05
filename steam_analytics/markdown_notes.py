"""Markdown rendering and task updates for saved notes."""

import re

import mistune
from bs4 import BeautifulSoup


def parser():
    return mistune.create_markdown(escape=True, plugins=["table", "task_lists", "strikethrough", "url"])


def render_markdown(value):
    soup = BeautifulSoup(parser()(str(value or "")), "html.parser")
    for index, checkbox in enumerate(soup.select("input.task-list-item-checkbox")):
        checkbox.attrs.pop("disabled", None)
        checkbox["data-note-task"] = str(index)
        checkbox["aria-label"] = checkbox.parent.get_text(" ", strip=True)
    for link in soup.select("a"):
        link["rel"] = "noopener noreferrer"
        link["target"] = "_blank"
    return str(soup)


def update_markdown_task(body, index, checked):
    """Use the parser to locate a task, including nested/quoted lists, excluding code."""
    lines = body.splitlines(keepends=True)
    original = BeautifulSoup(parser()(body), "html.parser").select("input.task-list-item-checkbox")
    if index < 0 or index >= len(original):
        raise ValueError("Item de Markdown não encontrado.")
    for line_index, line in enumerate(lines):
        match = re.match(r"^(\s*(?:>\s*)*(?:[-+*]|\d+[.)])\s+\[)([ xX])(\].*)$", line.rstrip("\r\n"))
        if not match:
            continue
        candidate = lines.copy()
        candidate[line_index] = line[:match.start(2)] + (" " if match[2].lower() == "x" else "x") + line[match.end(2):]
        tasks = BeautifulSoup(parser()("".join(candidate)), "html.parser").select("input.task-list-item-checkbox")
        if len(tasks) == len(original) and (tasks[index].has_attr("checked") != original[index].has_attr("checked")):
            lines[line_index] = line[:match.start(2)] + ("x" if checked else " ") + line[match.end(2):]
            return "".join(lines)
    raise ValueError("Item de Markdown não encontrado.")
