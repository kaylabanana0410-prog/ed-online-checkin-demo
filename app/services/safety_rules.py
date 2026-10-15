"""Configurable warning-sign rules engine. Safety never depends on the AI: this runs on its own."""
import json, re
from dataclasses import dataclass, field
from pathlib import Path

GENERAL = "Some of what you described can be a warning sign. Call 911 or tell staff now. Do not wait to finish this form."
DEGRADED = "We could not check for warning signs. If you may be having an emergency, call 911 or tell staff now."

@dataclass(frozen=True)
class Rule:
    id: str
    patterns: tuple
    message: str | None = None

@dataclass
class Evaluation:
    emergency: bool = False
    degraded: bool = False
    matched: list = field(default_factory=list)
    messages: list = field(default_factory=list)

class RulesEngine:
    def __init__(self, rules, degraded: bool = False):
        self.degraded = degraded
        self.rules = [(r, [re.compile(p, re.I) for p in r.patterns]) for r in rules]

    @classmethod
    def from_file(cls, path):
        try:
            data = json.loads(Path(path).read_text())
            rules = [Rule(r["id"], tuple(r["patterns"]), r.get("message")) for r in data["rules"]]
            if not rules:
                raise ValueError("no rules")
            return cls(rules)
        except Exception:  # missing or invalid file: fail visibly, never silently "all clear"
            return cls([], degraded=True)

    def evaluate(self, answers: list[str]) -> Evaluation:
        if self.degraded:
            return Evaluation(degraded=True, messages=[DEGRADED])
        text = " ".join(answers).replace("\u2019", "'").replace("\u2018", "'")
        hits = [r for r, pats in self.rules if any(p.search(text) for p in pats)]
        if not hits:
            return Evaluation()
        return Evaluation(True, False, [r.id for r in hits], [GENERAL] + [r.message for r in hits if r.message])
