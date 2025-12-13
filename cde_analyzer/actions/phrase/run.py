#
# File: actions/phrase/run.py
#
import json
import logging
from argparse import Namespace
from logic.phrase_extractor import collect_all_phrase_occurrences
from utils.output_writer import phrase_write_output

# This needs to change to import the MODEL_REGISTRY 
# The run_action needs to be updated to a conditional based on the mode choice
# from pydantic import parse_file_as
from CDE_Schema import CDEItem  # type: ignore 


help_text = "Extract common phrases from CDEs (Forms not implemented yet)."
description_text = "Extract frequent phrases, verbatim or lemmatized, from designatted fields in CDE model classes"

logger = logging.getLogger(__name__)

def run_action(args: Namespace):
    # verbosity = get_verbosity()
    raw = json.load(open(args.input))
    items = [CDEItem.model_validate(obj) for obj in raw]

    logger.info(f"arguments: {args}")

    results = collect_all_phrase_occurrences(
        items=items,
        field_names=args.fields,
        min_words=args.min_words,
        remove_stopwords=args.remove_stopwords,
        min_ids=args.min_ids,
        # verbosity=verbosity,
        prune=args.prune,
        lemmatize=args.lemmatize,
        verbatim=args.verbatim,
    )

    phrase_write_output(results, format=args.output_format, out_path=args.output)
