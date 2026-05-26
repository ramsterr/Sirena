"""CLI interface for spectrum scoring."""
import argparse
import json
import sys
from pathlib import Path
from .models import Execution
from .scorer import SpectrumScorer


def main():
    parser = argparse.ArgumentParser(prog="spectrum-score")
    sub = parser.add_subparsers(dest="command", required=True)

    score_cmd = sub.add_parser("score", help="Score executions from a JSON file")
    score_cmd.add_argument("--input", "-i", required=True, help="Input JSON file")
    score_cmd.add_argument("--formula", "-f", default="ochiai",
                          choices=["ochiai", "tarantula", "jaccard", "dstar"],
                          help="Scoring formula (default: ochiai)")
    score_cmd.add_argument("--output-format", "-o", default="text",
                          choices=["text", "json", "csv"],
                          help="Output format (default: text)")

    compare_cmd = sub.add_parser("compare", help="Compare all formulas on a JSON file")
    compare_cmd.add_argument("--input", "-i", required=True, help="Input JSON file")

    args = parser.parse_args()

    if args.command == "score":
        run_score(args)
    elif args.command == "compare":
        run_compare(args)


def run_score(args):
    data = json.loads(Path(args.input).read_text())
    executions = [Execution(**e) for e in data["executions"]]
    scorer = SpectrumScorer(formula=args.formula)
    ranked = scorer.rank(executions)

    if args.output_format == "json":
        result = [{"component": c, "score": s} for c, s in ranked]
        print(json.dumps(result, indent=2))
    elif args.output_format == "csv":
        print("component,score")
        for c, s in ranked:
            print(f"{c},{s}")
    else:
        for comp, score in ranked:
            print(f"{score:.4f}  {comp}")


def run_compare(args):
    data = json.loads(Path(args.input).read_text())
    executions = [Execution(**e) for e in data["executions"]]

    for formula in ["ochiai", "tarantula", "jaccard", "dstar"]:
        scorer = SpectrumScorer(formula=formula)
        ranked = scorer.rank(executions)
        print(f"=== {formula} ===")
        for comp, score in ranked:
            print(f"  {score:.4f}  {comp}")


if __name__ == "__main__":
    main()
