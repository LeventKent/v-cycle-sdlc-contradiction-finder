"""Lambda target exposing V-cycle documents through AgentCore Gateway."""

from __future__ import annotations

from pathlib import Path, PurePath

DELIMITER = "___"
ROOT = Path(__file__).resolve().parent
DOCUMENTS = ROOT / "documents"
GUIDELINES = ROOT / "guidelines"


def _tool_name(event, context) -> str:
    try:
        extended = context.client_context.custom["bedrockAgentCoreToolName"]
        return extended.split(DELIMITER, 1)[1]
    except (AttributeError, KeyError, IndexError):
        return event.pop("tool_name", "")


def _safe_name(value: object) -> str:
    if not isinstance(value, str) or PurePath(value).name != value:
        raise ValueError("document_name must be a plain filename")
    return value


def _read(path: Path) -> dict:
    if not path.is_file():
        available = sorted(item.name for item in path.parent.glob("*.md"))
        return {"error": f"Unknown document: {path.name}", "available": available}
    lines = path.read_text(encoding="utf-8").splitlines()
    content = "\n".join(
        f"[{path.name}:{number}] {line}"
        for number, line in enumerate(lines, start=1)
    )
    return {"document_name": path.name, "content": content}


def get_document(document_name: str) -> dict:
    return _read(DOCUMENTS / _safe_name(document_name))


def get_guideline(document_name: str) -> dict:
    name = _safe_name(document_name)
    guideline_name = f"{Path(name).stem}-Guideline.md"
    return _read(GUIDELINES / guideline_name)


def lambda_handler(event, context):
    tool_name = _tool_name(event, context)
    if tool_name == "get_document":
        return get_document(event.get("document_name"))
    if tool_name == "get_guideline":
        return get_guideline(event.get("document_name"))
    return {"error": f"Unknown tool: {tool_name}"}
