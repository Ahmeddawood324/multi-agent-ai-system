"""Run the whole multi-agent pipeline:  python run.py   (add --mock to force the offline LLM)"""
import sys

from agent_system.llm import get_llm
from agent_system.orchestrator import Orchestrator


def main():
    llm = get_llm(force_mock=True if "--mock" in sys.argv else None)
    print(f"LLM backend: {llm.name}")
    result = Orchestrator(llm=llm).run()
    meta = result["meta"]
    print("\n=== Pipeline log ===")
    for e in meta["log"]:
        print(f"  {e['stage']:<13} {e['agent']:<24} {e['status']:<6} {e['seconds']}s")
    for w in meta["warnings"]:
        print("  WARNING:", w)
    print(f"\nFact check passed: {meta['validation_ok']} | total time: {meta['seconds']}s")
    print("\n" + result["executive"]["text"])
    print("\nFiles written to the output/ folder:", ", ".join(result["outputs"]["files"]))


if __name__ == "__main__":
    main()
