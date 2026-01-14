#
# File: actions/strip_html/run.py
#
from argparse import Namespace
from pathlib import Path
from logic.html_stripper import process_file
from utils.logger import log_if_verbose
from utils.constants import MODEL_REGISTRY

def run_action(args: Namespace):
    model_class = MODEL_REGISTRY[args.model]
    outdir = Path(args.outdir)

    for filename in args.input:
        filepath = Path(filename)
        if not filepath.is_file():
            log_if_verbose(f"Skipping: {filename} is not a valid file.", level=0)
            continue
        process_file(
            filepath,
            outdir,
            model_class,
            args.output_format,
            args.dry_run,
            args.set_keys,
            args.pretty,
            args.tables,
            args.colnames,
        )