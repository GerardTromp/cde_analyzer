# Action file for utility that builds repeated phrases.
#   These phrases need to be examined for inclusion in list of phrases for
#   replacement in the embedding and clustering data
# Long phrases unlikely to cause problems, but short phrases need to be
#   curated to avoid change in semantic intent of the remaining text

import json
import sys
import time
from argparse import Namespace
from datetime import datetime

from utils.logger import logging


logger = logging.getLogger(__name__)

def run_action(args: Namespace):
    # Lazy imports - heavy dependencies loaded only when action runs
    import pandas as pd  # type: ignore
    from pydantic import ValidationError
    from utils.constants import MODEL_REGISTRY
    from utils.phrase_builder import rename_embed
    from logic.phrase_builder import gen_kmer_counts, gen_kmers, tokenizer
    from utils.plot_kmer_counts import plot_kmer_counts

    fields_wanted = ["Name", "Question", "Definition"] # This should come from args.
    k_list = [3,4,5,6,7,8,9,10,11,12,13,14,15,16,17]
    model_class = MODEL_REGISTRY[args.model]

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)
    
    ## 
    # Need to have argument to determine which element of parent list to
    # use. 
    if isinstance(data, dict) and "lemmatized" in data.keys(): 
        data = data["lemmatized"]
    elif not isinstance(data, list):    
        sys.exit("Input is neither list nor dict. Something wrong.")
    data = rename_embed(data)

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
        start_time = time.perf_counter()
        kmer_list = gen_kmers(parsed, fields_wanted, tokenizer, k_list) # type: ignore
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        print(f"Function execution time: {elapsed_time:.4f} seconds")
    
    kmer_counts = gen_kmer_counts(kmer_list)
    # Note to self. if flat ensures return of populated dataframe. else returns empty dataframe.
    if kmer_list:
        df_kmers = pd.DataFrame(kmer_list) 
    
    # Need to get the limits from the data OR from cmdline arguments or a config file
    fig, ax = plot_kmer_counts(kmer_counts, k_list, [0,250,0,.1], mincount=15)
    
    now = datetime.now()
    formatted_date_time = now.strftime("%Y%m%d-%H%M%S")
    filename = f"{args.output}_{formatted_date_time}.csv"
    df_kmers.to_csv(filename)