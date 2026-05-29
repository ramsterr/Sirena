"""CLI for MicroRank RCA pipeline."""
import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(prog="microrank")
    sub = parser.add_subparsers(dest="command", required=True)

    _add_score_cmd(sub)
    _add_rank_cmd(sub)
    _add_analyze_cmd(sub)
    _add_compare_cmd(sub)

    args = parser.parse_args()

    if args.command == "score":
        _run_score(args)
    elif args.command == "rank":
        _run_rank(args)
    elif args.command == "analyze":
        _run_analyze(args)
    elif args.command == "compare":
        _run_compare(args)


def _add_score_cmd(sub):
    cmd = sub.add_parser("score", help="Score executions from a JSON file")
    cmd.add_argument("--input", "-i", required=True, help="Input JSON file")
    cmd.add_argument("--formula", "-f", default="ochiai",
                     choices=["ochiai", "tarantula", "jaccard", "dstar"],
                     help="Scoring formula (default: ochiai)")
    cmd.add_argument("--temporal-half-life", type=float, default=None,
                     help="Half-life in seconds for temporal weighting "
                          "(earlier failures weighted higher)")
    cmd.add_argument("--output", "-o", default=None,
                     help="Write output to file instead of stdout")
    cmd.add_argument("--output-format", default="text",
                     choices=["text", "json", "csv"],
                     help="Output format (default: text)")


def _add_rank_cmd(sub):
    cmd = sub.add_parser("rank", help="Rank from graph and anomaly scores")
    cmd.add_argument("--graph", "-g", required=True, help="Graph JSON file")
    cmd.add_argument("--scores", "-s", required=True,
                     help="Anomaly scores JSON file")
    cmd.add_argument("--algorithm", "-a", default="propagation",
                     choices=["propagation", "pagerank", "standard_pagerank",
                              "betweenness", "anomaly_only"],
                     help="Ranking algorithm (default: propagation)")
    cmd.add_argument("--alpha", type=float, default=0.30,
                     help="Damping factor for PageRank (default: 0.30)")
    cmd.add_argument("--edge-semantics", default="depends-on",
                     choices=["depends-on", "calls"],
                     help="Edge semantics (default: depends-on)")
    cmd.add_argument("--output", "-o", default=None,
                     help="Write output to file")


def _add_analyze_cmd(sub):
    cmd = sub.add_parser(
        "analyze", help="Full analysis: score + rank in one step")
    cmd.add_argument("--graph", "-g", required=True,
                     help="Graph JSON file")
    cmd.add_argument("--executions", "-e", required=True,
                     help="Executions JSON file")
    cmd.add_argument("--formula", "-f", default="ochiai",
                     choices=["ochiai", "tarantula", "jaccard", "dstar"],
                     help="Scoring formula (default: ochiai)")
    cmd.add_argument("--algorithm", "-a", default="propagation",
                     choices=["propagation", "pagerank", "anomaly_only"],
                     help="Ranking algorithm (default: propagation)")
    cmd.add_argument("--alpha", type=float, default=0.30,
                     help="Damping factor for PageRank (default: 0.30)")
    cmd.add_argument("--edge-semantics", default="depends-on",
                     choices=["depends-on", "calls"],
                     help="Edge semantics (default: depends-on)")
    cmd.add_argument("--iterative", action="store_true",
                     help="Enable iterative root cause removal "
                          "for multi-cause scenarios")
    cmd.add_argument("--max-candidates", type=int, default=3,
                     help="Max candidates for iterative mode (default: 3)")
    cmd.add_argument("--score-threshold", type=float, default=0.0,
                     help="Score threshold for iterative mode (default: 0.0)")
    cmd.add_argument("--temporal-half-life", type=float, default=None,
                     help="Half-life in seconds for temporal weighting "
                          "(earlier failures weighted higher)")
    cmd.add_argument("--output", "-o", default=None,
                     help="Write output to file")


def _add_compare_cmd(sub):
    cmd = sub.add_parser(
        "compare", help="Compare all formula x algorithm combinations")
    cmd.add_argument("--graph", "-g", required=True,
                     help="Graph JSON file")
    cmd.add_argument("--executions", "-e", required=True,
                     help="Executions JSON file")
    cmd.add_argument("--alpha", type=float, default=0.30,
                     help="Damping factor for PageRank (default: 0.30)")
    cmd.add_argument("--edge-semantics", default="depends-on",
                     choices=["depends-on", "calls"],
                     help="Edge semantics (default: depends-on)")
    cmd.add_argument("--temporal-half-life", type=float, default=None,
                     help="Half-life in seconds for temporal weighting")


def _run_score(args):
    from spectrum_scorer.models import Execution
    from spectrum_scorer.scorer import SpectrumScorer

    data = json.loads(Path(args.input).read_text())
    executions = [Execution(**e) for e in data["executions"]]
    scorer = SpectrumScorer(
        formula=args.formula,
        temporal_half_life=args.temporal_half_life,
    )
    result = scorer.score(executions)
    ranked = list(result.scores.items())

    out_lines = _format_ranked_output(ranked, args.output_format)

    if args.output:
        Path(args.output).write_text("\n".join(out_lines) + "\n")
    else:
        for line in out_lines:
            print(line)


def _run_rank(args):
    import networkx as nx
    from microrank.ranker import RootCauseRanker

    graph = _load_graph(args.graph)
    scores = _load_scores_dict(args.scores)
    ranker = RootCauseRanker(
        alpha=args.alpha,
        edge_semantics=args.edge_semantics,
    )
    ranked = ranker.rank(graph, scores, algorithm=args.algorithm)

    out_lines = _format_ranked_output(ranked, "text")

    if args.output:
        Path(args.output).write_text("\n".join(out_lines) + "\n")
    else:
        for line in out_lines:
            print(line)


def _run_analyze(args):
    import networkx as nx
    from spectrum_scorer.models import Execution
    from microrank.pipeline import analyze, iterative_analyze

    graph = _load_graph(args.graph)
    data = json.loads(Path(args.executions).read_text())
    executions = [Execution(**e) for e in data["executions"]]

    if args.iterative:
        results = iterative_analyze(
            graph=graph,
            executions=executions,
            formula=args.formula,
            algorithm=args.algorithm,
            max_candidates=args.max_candidates,
            score_threshold=args.score_threshold,
            alpha=args.alpha,
            edge_semantics=args.edge_semantics,
            temporal_half_life=args.temporal_half_life,
        )
        for i, r in enumerate(results):
            print(f"\n=== Root Cause #{i + 1}: {r.ranked[0][0]} "
                  f"(score={r.ranked[0][1]:.4f}) ===")
            for comp, score in r.ranked[:10]:
                print(f"  {score:.4f}  {comp}")
    else:
        result = analyze(
            graph=graph,
            executions=executions,
            formula=args.formula,
            algorithm=args.algorithm,
            alpha=args.alpha,
            edge_semantics=args.edge_semantics,
            temporal_half_life=args.temporal_half_life,
        )
        _print_analysis_result(result)


def _run_compare(args):
    import networkx as nx
    from spectrum_scorer.models import Execution
    from microrank.pipeline import compare_all

    graph = _load_graph(args.graph)
    data = json.loads(Path(args.executions).read_text())
    executions = [Execution(**e) for e in data["executions"]]

    results = compare_all(
        graph=graph,
        executions=executions,
        alpha=args.alpha,
        edge_semantics=args.edge_semantics,
        temporal_half_life=args.temporal_half_life,
    )

    for label, ranked in results.items():
        print(f"\n=== {label} ===")
        for comp, score in ranked[:5]:
            print(f"  {score:.4f}  {comp}")


def _print_analysis_result(result):
    from microrank.pipeline import AnalysisResult
    print(f"Formula: {result.formula_used}")
    print(f"Algorithm: {result.algorithm_used}")
    print(f"n_f={result.n_f:.1f}  n_p={result.n_p:.1f}")
    print()
    for comp, score in result.ranked:
        print(f"  {score:.4f}  {comp}")


def _load_graph(path):
    import networkx as nx
    data = json.loads(Path(path).read_text())
    g = nx.DiGraph()
    g.add_nodes_from(data.get("nodes", []))
    for edge in data.get("edges", []):
        g.add_edge(edge["source"], edge["target"],
                   weight=edge.get("weight", 1.0))
    return g


def _load_scores_dict(path):
    data = json.loads(Path(path).read_text())
    if isinstance(data, list):
        return {item["component"]: item["score"] for item in data}
    return data


def _format_ranked_output(ranked, output_format):
    if output_format == "json":
        return [json.dumps(
            [{"component": c, "score": s} for c, s in ranked], indent=2)]
    elif output_format == "csv":
        return ["component,score"] + [f"{c},{s}" for c, s in ranked]
    else:
        return [f"{score:.4f}  {comp}" for comp, score in ranked]


if __name__ == "__main__":
    main()
