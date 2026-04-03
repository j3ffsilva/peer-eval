"""
CLI entry point for peer-eval tool.

Usage:
    peer-eval --since 2026-03-16 --until 2026-03-27 --deadline 2026-03-27T23:59:00Z
    peer-eval --fixture fixtures/scenario.json --deadline 2026-03-27T23:59:00Z
"""

import sys
from peer_eval.main import main


def cli():
    """Entry point for the peer-eval CLI command."""
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
