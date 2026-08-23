from __future__ import annotations

import ast
from pathlib import Path


BANNED_IMPORT_ROOTS = {
    "Agent",
    "simulation",
    "trader",
    "util",
    "marketlens.agents",
    "marketlens.market",
    "marketlens.persistence",
}


def test_phase11_stimulus_package_has_no_agent_market_forum_or_persistence_dependency():
    package = Path(__file__).resolve().parents[3] / "marketlens" / "stimulus"
    violations: list[str] = []
    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if any(name == root or name.startswith(root + ".") for root in BANNED_IMPORT_ROOTS):
                    violations.append(f"{path.name}: {name}")
    assert violations == []
