import argparse
import json
import os
import sys
from pathlib import Path
from llm import call_llm, get_provider


def load_config(config_path: str = "config.json") -> dict:
    """Load configuration from JSON file."""
    if not os.path.exists(config_path):
        return {
            "provider": "claude",
            "system-prompt": "You are Nomo, an engineering AI assistant that generates CAD models.",
            "output-file": "output/response.text"
        }
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_response(text: str, output_path: str) -> None:
    """Save response text to the designated output file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"\n[Saved response to: {path}]")


def main():
    parser = argparse.ArgumentParser(description="Nomo CLI - Design Description to LLM")
    parser.add_argument("prompt", nargs="?", help="User prompt / description (optional)")
    parser.add_argument("--config", default="config.json", help="Path to config.json (default: config.json)")
    args = parser.parse_args()

    config = load_config(args.config)
    system_prompt = config.get("system-prompt") or config.get("system_prompt", "You are Nomo CAD assistant.")
    output_file = config.get("output-file") or config.get("output_file", "output/response.text")

    # 1. User can enter a prompt in the CLI (via argument or interactively)
    prompt = args.prompt
    if not prompt:
        print("=== Nomo CAD CLI ===")
        print(f"Active Provider: {config.get('provider')}")
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
    response_text = call_llm(
        system_prompt=system_prompt,
        user_prompt=prompt,
        config_path=args.config
    )

    # 3. User receives a text response from the LLM
    print("\n--- LLM Response ---")
    print(response_text)
    print("--------------------")

    # 4. Write response to file
    if output_file:
        save_response(response_text, output_file)


if __name__ == "__main__":
    main()
