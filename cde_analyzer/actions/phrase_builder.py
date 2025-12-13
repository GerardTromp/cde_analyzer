# Action file for utility that builds repeated phrases.
#   These phrases need to be examined for inclusion in list of phrases for
#   replacement in the embedding and clustering data
# Long phrases unlikely to cause problems, but short phrases need to be
#   curated to avoid change in semantic intent of the remaining text

import os
import json
import base64
import struct
import sys
import time
import json
import hashlib
import networkx as nx
import numpy as np
import pandas as pd # type: ignore -- vs does not have access to WSL modules
import matplotlib.pyplot as plt  # type: ignore -- vs does not have access to WSL modules
from argparse import ArgumentParser, Namespace
from utils.logger import logging
from utils.constants import MODEL_REGISTRY
from utils.phrase_builder import rename_embed
from typing import Tuple, Dict, Any, List
from collections import defaultdict
from pydantic import BaseModel, ValidationError
from nltk.tokenize import RegexpTokenizer
from logic.phrase_builder import df_kmers, gen_kmer_counts, gen_kmers, tokenizer
from datetime import datetime
from utils.plot_kmer_counts import plot_kmer_counts


logger = logging.getLogger(__name__)

def register_subparser(subparser: ArgumentParser):
    # parser = subparsers.add_parser(
    #     "strip_phrases",
    #     help="Remove curated phrases from specific paths in a JSON document.",
    # )
    subparser.add_argument(
        "-i", "--input", required=True, help="Path to input JSON file."
    )
    subparser.add_argument(
        "-m",
        "--model",
        choices=MODEL_REGISTRY.keys(),
        required=True,
        help="Top-level Pydantic model name for parsing the input JSON.",
    )
    subparser.add_argument(
        "-o", "--output", required=True, help="Path to output JSON file."
    )
    subparser.set_defaults(func=run_action)


def run_action(args: Namespace):
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