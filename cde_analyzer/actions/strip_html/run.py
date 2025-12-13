#
# File: actions/strip_html/run.py
#
from argparse import Namespace
from pathlib import Path
from logic.html_stripper import process_file
from utils.logger import logging
from utils.constants import MODEL_REGISTRY

def run_action(args: Namespace):
    model_class = MODEL_REGISTRY[args.model]
    outdir = Path(args.outdir)

    for filename in args.input:
        filepath = Path(filename)
        if not filepath.is_file():
            logging.warning(f"Skipping: {filename} is not a valid file.")
            continue
        process_file(
            filepath,
            outdir,
            model_class,
            args.format,
            args.dry_run,
            args.set_keys,
            args.pretty,
            args.tables,
            args.colnames,
        )