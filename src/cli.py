"""CLI entry point for AgentOps."""

import asyncio
import sys


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("AgentOps CLI")
        print("Usage:")
        print("  agentops serve    - Start the API server")
        print("  agentops eval     - Run evaluation")
        print("  agentops version  - Show version")
        return

    command = sys.argv[1]

    if command == "serve":
        import uvicorn
        uvicorn.run("src.main:app", host="0.0.0.0", port=8080, reload=True)

    elif command == "eval":
        if len(sys.argv) < 3:
            print("Usage: agentops eval <config.json>")
            return
        from src.eval.runner import run_eval
        asyncio.run(run_eval(sys.argv[2]))

    elif command == "version":
        from src import __version__
        print(f"AgentOps v{__version__}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
