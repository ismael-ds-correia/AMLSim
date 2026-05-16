import argparse
import json
import logging
import os
import sys
import yaml
from pydantic import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from amlsim_config import AMLSimConfig

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate AMLSim YAML configuration with Pydantic.")
    parser.add_argument(
        "config",
        nargs="?",
        default="config.yaml",
        help="Path to the YAML configuration file (default: config.yaml)",
    )
    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    if not os.path.isfile(config_path):
        logging.error("Configuration file not found: %s", config_path)
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as file_handle:
        config_data = yaml.safe_load(file_handle)

    if not isinstance(config_data, dict):
        logging.error("Invalid YAML root: expected a mapping at %s", config_path)
        sys.exit(1)

    try:
        validated = AMLSimConfig.model_validate(config_data)
    except ValidationError as exc:
        logging.error("YAML validation failed for %s:\n%s", config_path, exc)
        sys.exit(1)

    logging.info("YAML validation succeeded: %s", config_path)
    logging.info("Validated configuration:\n%s", json.dumps(validated.model_dump(mode="json"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
