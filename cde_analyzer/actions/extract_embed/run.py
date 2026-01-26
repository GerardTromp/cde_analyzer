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
    elif args.id_list:
        idlist = args.id_list
    else:
        idlist = []

    input_path = exit_if_missing(args.input, "Input file")
    raw = json.load(open(input_path))
    # ModelType = TypeVar(MODEL_REGISTRY[args.model], bound=BaseModel)
    model_class = MODEL_REGISTRY[args.model]

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
    )
