"""
main.py
=======
Entry point. Questions are NOT hardcoded here — they are typed in by
whoever runs this script (input()), one at a time. Each run produces
its own numbered report file under output/.

Usage:
    python main.py
"""

import os
import shutil

from crew import build_crew

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def run_one_question(question: str, run_number: int) -> str:
    print(f"\n{'='*70}\nRUN #{run_number} — Question: {question}\n{'='*70}\n")

    crew = build_crew(question)
    result = crew.kickoff()

    default_path = os.path.join(OUTPUT_DIR, "report.md")
    final_path = os.path.join(OUTPUT_DIR, f"report_{run_number}.md")
    if os.path.exists(default_path):
        shutil.move(default_path, final_path)

    print(f"\n>>> Report saved to: {final_path}\n")
    return final_path


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("RAG-Powered Document Analyst Crew")
    print("Type a question about Nimbus Cloud Solutions (or 'quit' to stop).\n")

    run_number = 1
    while True:
        question = input(f"[{run_number}] Your question: ").strip()
        if not question or question.lower() in ("quit", "exit"):
            break

        try:
            run_one_question(question, run_number)
        except Exception as e:
            print(f"\n⚠️  Run #{run_number} failed with error:\n{e}\n")
            print("Continuing to the next question...\n")

        run_number += 1

    print("\nDone. Reports are in the output/ folder.")


if __name__ == "__main__":
    main()
