"""Organiser match runner adapter and integration test launcher.

Official Specification (Protocol Specification Section 12):
- "The bot has been tested against the starter kit's local match runner
  for a full 400-hand match inside the time bank."
- The authoritative match engine and local simulation runner are provided
  directly by the competition organisers in the official starter kit.

Scope Note:
- We DO NOT build a custom poker game engine here. This module serves strictly
  as an adapter to execute and verify the bot against the official organiser-provided
  runner script once available.

Dependencies:
- Standard Library: subprocess, sys, typing
"""

import subprocess
import sys


def run_organiser_runner(
    runner_script_path: str,
    bot1_cmd: str = "python bot.py",
    bot2_cmd: str = "python bot.py",
    extra_args: list[str] | None = None,
) -> int:
    """Executes the official organiser-provided local match runner as a subprocess.

    Args:
        runner_script_path: Path to the official starter kit runner script.
        bot1_cmd: Command line to invoke bot 1.
        bot2_cmd: Command line to invoke bot 2.
        extra_args: Optional additional flags supported by the organiser's runner.

    Returns:
        int: Process return code (0 for success).

    TODO:
        - When the official starter kit runner is downloaded, invoke it via subprocess.run:
          cmd = [sys.executable, runner_script_path, ...]
        - Check return code and report stdout/stderr integrity.
    """
    raise NotImplementedError("run_organiser_runner adapter is not yet implemented.")


def main() -> None:
    """CLI entry point for the organiser runner adapter."""
    print("Organiser runner adapter stub. Awaiting official starter kit runner.", file=sys.stderr)


if __name__ == "__main__":
    main()
