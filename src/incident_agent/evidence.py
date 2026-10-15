"""The evidence ledger: every tool result gets a stable ID that agents must cite.

This is what makes the final report checkable. A claim citing E4 can be verified against the exact
tool output stored under E4; a citation to an ID that does not exist is a hallucination.
"""

import json
from dataclasses import dataclass


@dataclass
class Evidence:
    id: str
    agent: str
    tool: str
    args: dict
    output: str
    is_error: bool = False

    def label(self) -> str:
        args = ", ".join(f"{k}={v}" for k, v in self.args.items())
        return f"{self.tool}({args})"


class EvidenceLedger:
    def __init__(self):
        self._items: dict[str, Evidence] = {}
        self._by_call: dict[str, str] = {}

    def add(self, agent: str, tool: str, args: dict, output: str, is_error: bool = False) -> str:
        """Record a tool result. Identical calls (same tool and args) reuse the existing ID."""
        key = tool + json.dumps(args, sort_keys=True)
        if key in self._by_call:
            return self._by_call[key]
        eid = f"E{len(self._items) + 1}"
        self._items[eid] = Evidence(eid, agent, tool, args, output, is_error)
        self._by_call[key] = eid
        return eid

    def find(self, tool: str, args: dict) -> str | None:
        return self._by_call.get(tool + json.dumps(args, sort_keys=True))

    def get(self, eid: str) -> Evidence | None:
        return self._items.get(eid)

    def __contains__(self, eid: str) -> bool:
        return eid in self._items

    def __iter__(self):
        return iter(self._items.values())

    def __len__(self) -> int:
        return len(self._items)

    def index(self) -> str:
        """One line per item, for prompts that need to know what evidence exists."""
        return "\n".join(
            f"{e.id} [{e.agent}] {e.label()}{' (error)' if e.is_error else ''}" for e in self
        )

    def to_dict(self) -> list[dict]:
        return [e.__dict__ for e in self]
