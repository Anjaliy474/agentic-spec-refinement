"""Command line: ``reqhq run PRD.md``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from reqhq import __version__
from reqhq.critics.prompted import ROLES, PromptedCritic
from reqhq.gating.gate import MODES
from reqhq.humans import InteractiveHuman, NoHuman, OracleHuman
from reqhq.llm import make_llm
from reqhq.pipeline import run_pipeline
from reqhq.prd import load_prd
from reqhq.trace.render import render_markdown


def _run(args: argparse.Namespace) -> None:
    cfg = yaml.safe_load(Path(args.config).read_text())
    prd = load_prd(args.prd)
    orchestrator = make_llm(cfg["orchestrator"])

    names = args.critics.split(",") if args.critics else list(cfg["critics"])
    critics = [PromptedCritic(ROLES[n], make_llm(cfg["critics"][n])) for n in names]

    if args.human == "ask":
        human = InteractiveHuman()
    elif args.human == "oracle":
        if not args.reference:
            raise SystemExit("--human oracle needs --reference REFERENCE_SPEC")
        human = OracleHuman(make_llm(cfg["oracle"]), Path(args.reference).read_text())
    else:
        human = NoHuman()
    mode = "none" if args.human == "none" and args.mode == "targeted" else args.mode

    result = run_pipeline(prd, orchestrator, critics, human, mode=mode)

    out = Path(args.out) / prd.id
    out.mkdir(parents=True, exist_ok=True)
    (out / "spec.md").write_text(render_markdown(result.spec, prd))
    (out / "spec.json").write_text(result.spec.model_dump_json(indent=2))
    (out / "findings.json").write_text(
        json.dumps([f.model_dump() for f in result.findings], indent=2)
    )
    (out / "usage.json").write_text(json.dumps(result.usage, indent=2))

    n_fr = sum(r.is_functional for r in result.spec.requirements)
    n_open = sum(r.open_issue for r in result.spec.requirements)
    print(f"PRD {prd.id}: {len(prd.sentences)} sentences")
    print(f"  {n_fr} functional, {len(result.spec.requirements) - n_fr} non-functional "
          f"({n_open} open), {len(result.findings)} findings, {len(result.conflicts)} conflicts, "
          f"{len(result.spec.questions_asked)} questions")
    print(f"  usage: {json.dumps(result.usage)}")
    for w in result.warnings:
        print(f"  warning: {w}")
    print(f"  wrote {out}/spec.md")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="reqhq", description="Agentic specification refinement")
    parser.add_argument("--version", action="version", version=f"reqhq {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="turn a PRD into a traced specification")
    run.add_argument("prd", help="PRD file (Markdown or plain text)")
    run.add_argument("--config", default="configs/default.yaml")
    run.add_argument("--critics", help="comma-separated subset, e.g. security,performance")
    run.add_argument("--human", choices=["none", "ask", "oracle"], default="ask")
    run.add_argument("--reference", help="reference spec for --human oracle")
    run.add_argument("--mode", choices=MODES, default="targeted",
                     help="which findings become questions")
    run.add_argument("--out", default="experiments/runs")
    run.set_defaults(func=_run)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
