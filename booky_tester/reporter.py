"""Results collection and reporting."""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class TurnResult:
    persona: str
    flow: str
    turn: int
    label: str
    message: str
    reply: str
    passed: bool
    expect: str
    button_clicked: Optional[str]
    elapsed_s: float
    reason: str = ""


@dataclass
class Report:
    started_at: float = field(default_factory=time.time)
    turns: list[TurnResult] = field(default_factory=list)

    def add(self, result: TurnResult) -> None:
        self.turns.append(result)
        status = "PASS" if result.passed else "FAIL"
        btn = f" [clicked: {result.button_clicked}]" if result.button_clicked else ""
        print(
            f"  [{status}] {result.persona}/{result.flow} T{result.turn} "
            f"({result.elapsed_s:.1f}s){btn} — {result.label}"
        )
        if not result.passed and result.reason:
            print(f"         ✗ {result.reason}")

    def summary(self) -> None:
        total = len(self.turns)
        passed = sum(1 for t in self.turns if t.passed)
        failed = total - passed
        duration = time.time() - self.started_at

        print("\n" + "=" * 70)
        print(f"RESULTS: {passed}/{total} turns passed ({passed/total*100:.1f}%)")
        print(f"Duration: {duration:.0f}s ({duration/60:.1f} min)")
        if failed:
            print(f"\nFailed turns:")
            for t in self.turns:
                if not t.passed:
                    print(f"  {t.persona}/{t.flow} T{t.turn}: {t.label}")
                    print(f"    Expected: {t.expect!r}")
                    print(f"    Got: {t.reply[:120]!r}")
        print("=" * 70)

    def save(self, path: str = "results.json") -> None:
        data = {
            "started_at": self.started_at,
            "duration_s": time.time() - self.started_at,
            "turns": [asdict(t) for t in self.turns],
        }
        Path(path).write_text(json.dumps(data, indent=2))
        print(f"\nResults saved to {path}")
