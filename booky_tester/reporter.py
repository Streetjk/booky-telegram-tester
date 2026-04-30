"""Results collection and reporting."""

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
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

    def _persona_stats(self, persona: str) -> tuple[int, int]:
        rows = [t for t in self.turns if t.persona == persona]
        return sum(1 for t in rows if t.passed), len(rows)

    def add(self, result: TurnResult) -> None:
        self.turns.append(result)
        status = "PASS" if result.passed else "FAIL"
        p_passed, p_total = self._persona_stats(result.persona)
        pct = (p_passed / p_total * 100) if p_total else 0
        btn = f" [clicked: {result.button_clicked}]" if result.button_clicked else ""
        print(
            f"  [{status}] {result.persona}/{result.flow} T{result.turn} "
            f"({result.elapsed_s:.1f}s){btn} — {result.label} "
            f"[persona {p_passed}/{p_total} {pct:.0f}%]"
        )
        if not result.passed and result.reason:
            print(f"         ✗ {result.reason}")

    def summary(self) -> None:
        total = len(self.turns)
        passed = sum(1 for t in self.turns if t.passed)
        failed = total - passed
        duration = time.time() - self.started_at
        pct = (passed / total * 100) if total else 0

        print("\n" + "=" * 70)
        print(f"RESULTS: {passed}/{total} turns passed ({pct:.1f}%)")
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
            "started_at_iso": datetime.fromtimestamp(self.started_at, timezone.utc).isoformat(),
            "duration_s": time.time() - self.started_at,
            "turns": [asdict(t) for t in self.turns],
        }
        latest = Path(path)
        latest.write_text(json.dumps(data, indent=2))

        history_dir = latest.parent / "results"
        history_dir.mkdir(exist_ok=True)
        stamp = datetime.fromtimestamp(self.started_at, timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        history_path = history_dir / f"results-{stamp}.json"
        history_path.write_text(json.dumps(data, indent=2))
        print(f"\nResults saved to {latest} (history: {history_path})")
