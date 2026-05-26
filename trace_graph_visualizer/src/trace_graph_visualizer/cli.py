"""CLI interface for trace graph fetching and rendering."""
import argparse
import json
import sys
from pathlib import Path
from .fetcher import JaegerFetcher
from .graph_builder import DependencyGraphBuilder


def main():
    parser = argparse.ArgumentParser(prog="trace-graph")
    sub = parser.add_subparsers(dest="command", required=True)

    render_cmd = sub.add_parser("render", help="Fetch traces and render the graph")
    render_cmd.add_argument("--jaeger-url", default="http://localhost:16686")
    render_cmd.add_argument("--service")
    render_cmd.add_argument("--lookback", default="1h")
    render_cmd.add_argument("--limit", type=int, default=100)

    export_cmd = sub.add_parser("export", help="Export dependency graph as JSON")
    export_cmd.add_argument("--jaeger-url", default="http://localhost:16686")
    export_cmd.add_argument("--service")
    export_cmd.add_argument("--lookback", default="1h")
    export_cmd.add_argument("--limit", type=int, default=100)
    export_cmd.add_argument("--output", "-o", default="graph.json")

    lag_cmd = sub.add_parser(
        "lag-windows", help="Compute per-edge lag windows from traces"
    )
    lag_cmd.add_argument("--jaeger-url", default="http://localhost:16686")
    lag_cmd.add_argument("--service")
    lag_cmd.add_argument("--lookback", default="1h")
    lag_cmd.add_argument("--limit", type=int, default=100)
    lag_cmd.add_argument("--output", "-o", default="lag_windows.json")

    args = parser.parse_args()

    if args.command in ("render", "export", "lag-windows"):
        run_fetch_and_export(args)


def run_fetch_and_export(args):
    fetcher = JaegerFetcher(args.jaeger_url)
    print(f"Fetching traces from {args.jaeger_url}...", file=sys.stderr)
    traces = fetcher.fetch_traces(
        service=args.service, lookback=args.lookback, limit=args.limit
    )
    print(f"Fetched {len(traces)} traces", file=sys.stderr)

    if not traces:
        print("No traces found.", file=sys.stderr)
        return

    builder = DependencyGraphBuilder()
    graph = builder.build(traces)

    if args.command == "render":
        nodes = list(graph.nodes())
        edges = [(u, v, d["weight"]) for u, v, d in graph.edges(data=True)]
        print(f"Services ({len(nodes)}): {nodes}")
        print(f"Edges ({len(edges)}):")
        for u, v, w in sorted(edges):
            print(f"  {u} → {v} (weight={w})")

    elif args.command == "export":
        output = {
            "nodes": list(graph.nodes()),
            "edges": [
                {"source": u, "target": v, "weight": d["weight"]}
                for u, v, d in graph.edges(data=True)
            ],
        }
        Path(args.output).write_text(json.dumps(output, indent=2))
        print(f"Graph exported to {args.output}")

    elif args.command == "lag-windows":
        result = builder.build_with_lag_windows(graph)
        Path(args.output).write_text(json.dumps(result, indent=2))
        print(f"Lag windows exported to {args.output}")


if __name__ == "__main__":
    main()
