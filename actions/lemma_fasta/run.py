#
# File: actions/lemma_fasta/run.py
#
import json
import sys
import logging
from CDE_Schema import CDEItem, CDEForm
from utils.tinyid_utils import load_tinyids
from utils.constants import MODEL_REGISTRY
from utils.file_utils import exit_if_missing, graceful_interrupt
from logic.lemma_fasta import make_pfasta, make_lfasta
from argparse import ArgumentParser, ArgumentError, BooleanOptionalAction

# from actions.count import run_action
logger = logging.getLogger(__name__)


@graceful_interrupt
def run_action(args):
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
    else:
        idlist = args.id_list

    input_path = exit_if_missing(args.input, "Input file")
    raw = json.load(open(input_path))
    # ModelType = TypeVar(MODEL_REGISTRY[args.model], bound=BaseModel)
    model_class = MODEL_REGISTRY[args.model]
    
    collapse =  True
    simplify_permissible = True
    ### 
    # Need a wrapper function here that calls extract path and then processes the data
    # for the pseudo fasta
    if args.output_format == "pfasta":
        make_pfasta(
            model_class,
            raw,
            idlist,
            args.output,
            args.output_format,
            args.path_file,
            args.exclude,
            collapse,
            simplify_permissible,
            args.remove_stopwords,
            args.min_freq,
        )
    
    if args.output_format == "lfasta":    
        make_lfasta(
            model_class,
            raw,
            idlist,
            args.output,
            args.output_format,
            args.path_file,
            args.exclude,
            collapse,
            simplify_permissible,
            args.remove_stopwords,
            args.min_freq,
        )
