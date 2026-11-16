import argparse
import json
import os
import sys
from pathlib import Path

from catalog import build_system_prompt
from llm import call_llm
from llm.call import get_provider, load_environment


def load_config(config_path: str = "config.json") -> dict:
    """Load configuration from JSON file."""
    if not os.path.exists(config_path):
        return {
            "provider": "mock",
            "system-prompt": "You are Nomo, an engineering AI assistant that generates CAD models.",
            "output-file": "output/response.text",
        }
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def save_response(text: str, output_path: str) -> None:
    """Save response text to the designated output file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"\n[Saved response to: {path}]")


def main():
    parser = argparse.ArgumentParser(description="Nomo CLI - Design Description to LLM")
    parser.add_argument(
        "prompt", nargs="?", help="User prompt / description (optional)"
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to config.json (default: config.json)",
    )
    parser.add_argument(
        "--env-file",
        help="Extra .env file, e.g. .env.codex (wins over .env)",
    )
    args = parser.parse_args()
    try:
        load_environment(args.config, args.env_file)
    except FileNotFoundError as error:
        parser.error(str(error))

    config = load_config(args.config)
    system_prompt = config.get("system-prompt") or config.get(
        "system_prompt", "You are Nomo CAD assistant."
    )
    output_file = config.get("output-file") or config.get(
        "output_file", "output/response.text"
    )

    # 1. User can enter a prompt in the CLI (via argument or interactively)
    prompt = args.prompt
    if not prompt:
        print("=== Nomo CAD CLI ===")
        active_provider = os.getenv("NOMO_PROVIDER") or config.get("provider")
        print(f"Active Provider: {active_provider}")
        try:
            prompt = input("\nEnter your user prompt: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(0)

    if not prompt:
        print("Error: No prompt provided. Exiting.")
        sys.exit(1)

    # 2. Implement LLM call (pass system prompt and user prompt)
    print("\nCalling LLM...")
    try:
        # The env files were loaded once above, so call_llm gets the provider
        provider = get_provider(config)
        response_text = call_llm(
            system_prompt=build_system_prompt(system_prompt),
            user_prompt=prompt,
            provider=provider,
        )
    except (RuntimeError, ValueError, OSError) as error:
        # A missing or failing AI (not installed, not signed in, timeout, unknown
        # provider, missing key): its message is enough, a traceback only hides it
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)

    # 3. User receives a text response from the LLM
    print("\n--- LLM Response ---")
    print(response_text)
    print("--------------------")

    # 4. Write response to file
    if output_file:
        save_response(response_text, output_file)


if __name__ == "__main__":
    main()
