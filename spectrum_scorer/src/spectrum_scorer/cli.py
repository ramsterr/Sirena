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
    score_cmd.add_argument("--temporal-half-life", type=float, default=None,
                          help="Half-life in seconds for temporal weighting "
                               "(earlier failures weighted higher)")
    score_cmd.add_argument("--output-format", "-o", default="text",
                          choices=["text", "json", "csv"],
                          help="Output format (default: text)")
    score_cmd.add_argument("--output", default=None,
                          help="Write output to file instead of stdout")

    compare_cmd = sub.add_parser("compare", help="Compare all formulas on a JSON file")
    compare_cmd.add_argument("--input", "-i", required=True, help="Input JSON file")
    compare_cmd.add_argument("--temporal-half-life", type=float, default=None,
                             help="Half-life in seconds for temporal weighting")

    args = parser.parse_args()

    if args.command == "score":
        run_score(args)
    elif args.command == "compare":
        run_compare(args)


def run_score(args):
    data = json.loads(Path(args.input).read_text())
    executions = [Execution(**e) for e in data["executions"]]
    scorer = SpectrumScorer(
        formula=args.formula,
        temporal_half_life=args.temporal_half_life,
    )
    result = scorer.score(executions)
    ranked = list(result.scores.items())

    out_lines = _format_output(ranked, args.output_format)

    if args.output:
        Path(args.output).write_text("\n".join(out_lines) + "\n")
    else:
        for line in out_lines:
            print(line)


def run_compare(args):
    data = json.loads(Path(args.input).read_text())
    executions = [Execution(**e) for e in data["executions"]]

    for formula in ["ochiai", "tarantula", "jaccard", "dstar"]:
        scorer = SpectrumScorer(
            formula=formula,
            temporal_half_life=args.temporal_half_life,
        )
        result = scorer.score(executions)
        ranked = list(result.scores.items())
        print(f"=== {formula} ===")
        for comp, score in ranked:
            print(f"  {score:.4f}  {comp}")


def _format_output(ranked, output_format):
    if output_format == "json":
        return [json.dumps(
            [{"component": c, "score": s} for c, s in ranked], indent=2)]
    elif output_format == "csv":
        return ["component,score"] + [f"{c},{s}" for c, s in ranked]
    else:
        return [f"{score:.4f}  {comp}" for comp, score in ranked]


if __name__ == "__main__":
    main()
