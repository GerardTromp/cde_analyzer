#
# File: actions/strip_phrases/run.py
#
import json
from argparse import ArgumentParser, Namespace
from utils.logger import configure_logging, logging
from pydantic import BaseModel, ValidationError
from logic.phrase_stripper import load_phrase_map, strip_phrases
from utils.diff_utils import print_json_diff

from utils.constants import MODEL_REGISTRY

logger = logging.getLogger(__name__)


def run_action(args: Namespace):
    model_class = MODEL_REGISTRY[args.model]

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    # Parse into model if needed
    # items = [CDEItem.model_validate(obj) for obj in raw]
    try:
        parsed = [model_class.model_validate(obj) for obj in data]  # or other model
    # Some verbose error output. Appropriate for STDERR
    except ValidationError as e:
        for error in e.errors():
            print(f"Error Type: {error['type']}")
            print(f"Message: {error['msg']}")
            print(f"Location: {error['loc']}")
            if "input" in error:
                print(f"Input: {error['input']}")
            if "ctx" in error:
                print(f"Context: {error['ctx']}")
            print("-" * 20)
    else:
        phrase_map = load_phrase_map(args.phrases)
        cleaned = strip_phrases(parsed, phrase_map)

        with open(args.output, "w", encoding="utf-8", newline="") as f:
            cleaned_json = [item.model_dump(mode="json") for item in cleaned]
            f.write(json.dumps(cleaned_json, indent=2))

        if args.diff or args.diff_output or args.summary:
            original_json = [item.model_dump(mode="json") for item in parsed]
            cleaned_json = [item.model_dump(mode="json") for item in cleaned]
            original_json = json.dumps(original_json, indent=2)
            cleaned_json = json.dumps(cleaned_json, indent=2)

            print_json_diff(
                original=original_json,
                cleaned=cleaned_json,
                context=args.context,
                color=args.color,
                summary=args.summary,
                output_file=args.diff_output,
            )
