"""CLI tools: python3 -m app.cli <command>

Commands:
  serve        Run the API with uvicorn
  seed         Initialize DB and seed demo data
  assess FILE  Run a preliminary assessment from a JSON parameters file
  rules        List the draft rule set
  resources    Show the regulatory resource catalog summary
  candidates   Generate rule candidates from the catalog
  readiness    Print production readiness checks
"""

import argparse
import json
import sys


def _print(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="alarrab", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the API server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)

    sub.add_parser("seed", help="initialize DB and seed demo data")

    assess = sub.add_parser("assess", help="assess parameters from a JSON file")
    assess.add_argument("file", help="path to JSON file with project parameters")

    sub.add_parser("rules", help="list draft rules")
    sub.add_parser("resources", help="regulatory catalog summary")
    sub.add_parser("candidates", help="generate rule candidates")
    sub.add_parser("readiness", help="production readiness checks")

    args = parser.parse_args(argv)

    if args.command == "serve":
        import uvicorn

        uvicorn.run("app.main:app", host=args.host, port=args.port)
        return 0

    if args.command == "seed":
        from app.db.seed import seed

        _print(seed())
        return 0

    if args.command == "assess":
        from app.engine.assessment import evaluate

        with open(args.file, encoding="utf-8") as fh:
            params = json.load(fh)
        _print(evaluate(params))
        return 0

    if args.command == "rules":
        from app.engine.rules_store import list_rules

        _print(list_rules())
        return 0

    if args.command == "resources":
        from app.governance.catalog import summary

        _print(summary())
        return 0

    if args.command == "candidates":
        from app.governance.rule_candidates import generate_candidates

        _print(generate_candidates())
        return 0

    if args.command == "readiness":
        from app.api.readiness import production_readiness

        _print(production_readiness())
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
