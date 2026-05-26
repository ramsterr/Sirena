"""CLI for MicroRank RCA pipeline."""
import argparse
import sys
from .pipeline import MicroRankPipeline


def main():
    parser = argparse.ArgumentParser(prog="micro-rank")
    sub = parser.add_subparsers(dest="command", required=True)

    rank_cmd = sub.add_parser("rank", help="Run root cause ranking for an incident")
    rank_cmd.add_argument("--jaeger-url", default="http://localhost:16686")
    rank_cmd.add_argument("--service")
    rank_cmd.add_argument("--lookback", default="1h")
    rank_cmd.add_argument("--baseline-window", default="30m")
    rank_cmd.add_argument("--incident-window", default="30m")
    rank_cmd.add_argument("--limit", type=int, default=200)
    rank_cmd.add_argument(
        "--algorithm", "-a", default="pagerank",
        choices=["pagerank", "betweenness", "anomaly_only"],
    )
    rank_cmd.add_argument("--formula", "-f", default="ochiai",
                          choices=["ochiai", "tarantula", "jaccard", "dstar"])

    compare_cmd = sub.add_parser("compare", help="Compare all ranking algorithms")
    compare_cmd.add_argument("--jaeger-url", default="http://localhost:16686")
    compare_cmd.add_argument("--service")
    compare_cmd.add_argument("--lookback", default="1h")
    compare_cmd.add_argument("--limit", type=int, default=200)

    args = parser.parse_args()

    if args.command == "rank":
        pipeline = MicroRankPipeline(
            jaeger_url=args.jaeger_url, spectrum_formula=args.formula
        )
        ranked = pipeline.run(
            service=args.service,
            baseline_window=args.baseline_window,
            incident_window=args.incident_window,
            lookback=args.lookback,
            limit=args.limit,
            algorithm=args.algorithm,
        )
        for svc, score in ranked[:10]:
            print(f"{score:.4f}  {svc}")

    elif args.command == "compare":
        from trace_graph_visualizer import JaegerFetcher, DependencyGraphBuilder
        from spectrum_scorer import SpectrumScorer, Execution
        from .trace_classifier import TraceAnomalyClassifier, traces_to_executions
        from .ranker import RootCauseRanker

        fetcher = JaegerFetcher(args.jaeger_url)
        traces = fetcher.fetch_traces(service=args.service, lookback=args.lookback, limit=args.limit)
        classifier_builder = DependencyGraphBuilder()
        graph = classifier_builder.build(traces)

        mid = len(traces) // 2
        baseline_traces = traces[:mid]
        incident_traces = traces[mid:]
        classifier = TraceAnomalyClassifier()
        classifier.learn_baseline(baseline_traces)
        anomalous, normal = classifier.split_anomalous_normal(incident_traces)
        all_traces = baseline_traces + incident_traces

        executions = traces_to_executions(all_traces, anomalous)
        scorer = SpectrumScorer(formula="ochiai")
        scores = scorer.score(executions)

        ranker = RootCauseRanker()
        results = ranker.compare(graph, scores)

        for algo, ranked in results.items():
            print(f"\n=== {algo} ===")
            for svc, score in ranked[:5]:
                print(f"  {score:.4f}  {svc}")


if __name__ == "__main__":
    main()
