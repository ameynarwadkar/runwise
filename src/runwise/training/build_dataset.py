"""
Generates, validates, and exports the candidate SFT dataset.
"""

from __future__ import annotations

import json
from pathlib import Path

from runwise.training.dataset_generator import generate_candidate_dataset
from runwise.training.validator import SFTDatasetValidator

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "sft" / "candidate_40_examples.jsonl"


def build_and_validate_dataset(output_path: Path | None = None) -> dict[str, Any]:
    """
    Builds the 40 candidate SFT examples, executes strict validation,
    and writes to disk.
    """
    out_file = output_path or DEFAULT_OUTPUT_PATH
    out_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"Generating candidate SFT dataset across 10 curriculum domains...")
    examples = generate_candidate_dataset()
    print(f"Generated {len(examples)} examples.")

    print("Running strict validation (schema, tool arguments, sequential auth, quarantine)...")
    validator = SFTDatasetValidator()
    metrics = validator.validate_dataset(examples)
    print(f"Validation successful: {metrics}")

    with out_file.open("w", encoding="utf-8") as f:
        for ex in examples:
            f.write(ex.model_dump_json() + "\n")

    print(f"Exported {len(examples)} validated examples to: {out_file}")
    return metrics


if __name__ == "__main__":
    build_and_validate_dataset()
