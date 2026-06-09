#
# File: actions/extract_embed/run.py
#
import json
import sys
import logging
from utils.tinyid_utils import load_tinyids
from utils.constants import MODEL_REGISTRY
from utils.file_utils import exit_if_missing, graceful_interrupt
from logic.extract_embed import extract_path

logger = logging.getLogger(__name__)


models_str = ", ".join(MODEL_REGISTRY.keys())


def _run_batch(args):
    """Batch mode: extract embed TSV + CSV for each stripped variant."""
    import glob
    import os

    import pathlib
    batch_dir = args.batch_dir
    if not pathlib.Path(batch_dir).is_dir():
        print(f"error: Batch directory does not exist: {batch_dir}", file=sys.stderr)
        sys.exit(2)
    model_class = MODEL_REGISTRY[args.model]
    path_file = args.path_file
    embed_sep = getattr(args, "embed_separator", " :--: ")

    # Find stripped_*.json files
    pattern = os.path.join(batch_dir, "stripped_*.json")
    json_files = sorted(glob.glob(pattern))

    if not json_files:
        print(f"No stripped_*.json files found in {batch_dir}", file=sys.stderr)
        sys.exit(1)

    # Filter by requested variants
    requested = None
    if args.batch_variants:
        requested = set(args.batch_variants.split(","))

    extracted = 0
    for json_path in json_files:
        basename = os.path.basename(json_path)
        # stripped_MTSFPT.json → MTSFPT
        variant = basename.replace("stripped_", "").replace(".json", "")

        if requested and variant not in requested:
            continue

        print(f"  [{variant}] Loading {basename}...")
        raw = json.load(open(json_path))

        # TSV: concatenated embed_text (2 columns: tinyId + embed_text)
        tsv_out = os.path.join(batch_dir, f"embed_{variant}.tsv")
        extract_path(
            model_class, raw, [], tsv_out, "tsv",
            path_file, True, True, True,
            concatenate=embed_sep,
        )

        # CSV: separate columns (tinyId, Name, Question, Definition, ...)
        csv_out = os.path.join(batch_dir, f"embed_{variant}.csv")
        extract_path(
            model_class, raw, [], csv_out, "csv",
            path_file, True, True, True,
            concatenate=None,
        )

        print(f"  [{variant}] → {os.path.basename(tsv_out)}, {os.path.basename(csv_out)}")
        extracted += 1

    if extracted == 0:
        if requested:
            print(f"No matching variants found for: {', '.join(sorted(requested))}", file=sys.stderr)
        sys.exit(1)

    print(f"\nBatch complete: {extracted} variant(s), {extracted * 2} files written")
    return 0


@graceful_interrupt
def run_action(args):
    # Batch mode
    if getattr(args, "batch_dir", None):
        return _run_batch(args)

    # Single-file mode requires --input
    if not args.input:
        print("error: --input is required (or use --batch-dir for batch mode)",
              file=sys.stderr)
        sys.exit(2)

    if (args.id_list or args.id_file) and args.id_type is None:
        print(
            "error:--id_type is required when --id-list or --id-file is used.",
            file=sys.stderr,
        )
        sys.exit(2)

    if (args.id_list or args.id_file) and args.exclude is None:
        print(
            "error:--exclude / --no-exclude is required when --id-list or --id-file is used.",
            file=sys.stderr,
        )
        sys.exit(2)

    # paths = load_path_schema(args.path_file)
    if args.id_file:
        idlist = load_tinyids(args.id_file)
    elif args.id_list:
        idlist = args.id_list
    else:
        idlist = []

    input_path = exit_if_missing(args.input, "Input file")
    raw = json.load(open(input_path))
    # ModelType = TypeVar(MODEL_REGISTRY[args.model], bound=BaseModel)
    model_class = MODEL_REGISTRY[args.model]

    concatenate = getattr(args, 'concatenate', None)

    if concatenate and args.output_format == "json":
        logger.info("--concatenate requires csv or tsv output; switching to tsv")
        args.output_format = "tsv"

    extract_path(
        model_class,
        raw,
        idlist,
        args.output,
        args.output_format,
        args.path_file,
        args.exclude,
        args.collapse,
        args.simplify_permissible,
        concatenate=concatenate,
    )
    return 0
