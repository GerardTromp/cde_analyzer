
import os
import sys
import re
import pandas as pd # type: ignore # 
from multiprocessing import Pool
from typing import List, Dict, Tuple

from collections import Counter
from typing import Tuple, Dict, Any, List
from nltk.tokenize import RegexpTokenizer
from utils.kmer_extend_phrases1 import extend_phrases_in_bin
from logic.phrase_stripper import strip_phrases

# Define a regular expression to match sequences of word characters (alphanumeric and underscore)
# This will effectively ignore most punctuation, including apostrophes and backticks.
tokenizer = RegexpTokenizer(r"\b\w+(?:'\w+)?\b")

def tokenize(text: str):
    return re.findall(r"\b\w+(?:'\w+)?\b", text.lower())

fields_wanted = ["Name", "Question", "Definition"]
df_kmers = pd.DataFrame(columns=["tinyId","field","k","kmer"])
# df_xwalk = pd.DataFrame(columns=["k_id","doc_id"])
# df_cdeinfo = pd.DataFrame(columns=["doc_id","cde_id","field"])



def compute_kmers(args: Tuple[List[str], int, str, str]) -> List[Dict]:
    """
    Worker: generate kmers for a given (tokens, k, tinyId, field).
    Returns a list of dicts, much lighter than DataFrames.
    """
    tokens, k, cd_id, fld = args
    n = len(tokens) - k + 1
    if n <= 0:
        return []

    return [
        {"kmer": tuple(tokens[i:i+k]), "tinyId": cd_id, "field": fld, "k": k}
        for i in range(n)
    ]


def prepare_kmer_jobs(cde_list: List[Dict], fields_wanted: List[str], tokenizer, k_list: List[int]):
    """
    Prepare all jobs (tokens, k, tinyId, field) across all records.
    """
    jobs = []
    for cde in cde_list:
        cd_id = cde.tinyId # type: ignore
        if not cd_id:
            continue
        for key, val in cde:
            if key == "tinyId" or val == "":
                continue
            if key in fields_wanted:
                tokens = tokenizer.tokenize(val)
                jobs.extend((tokens, k, cd_id, key) for k in k_list)
    return jobs


def gen_kmers(cde_list: List[Dict], fields_wanted: List[str], tokenizer, k_list: List[int]) -> List[Dict]:
    """
    Process all records in parallel with one global pool.
    Workers return dicts; parent builds the final DataFrame.
    """
    jobs = prepare_kmer_jobs(cde_list, fields_wanted, tokenizer, k_list)
    cpucount = os.cpu_count()
    if cpucount is None:
        print("=" * 80)
        print("Can't determine the number of CPUs on machine")
        print("=" * 80)
        sys.exit(f"OS CPU count returned 'None'")
    else:
        # Leave one CPU available for system activity
        cpucount = max(1, cpucount - 1) # type: ignore -- pylance nonsence protected so that there is in int
    with Pool(processes=cpucount) as pool:
        results = pool.map(compute_kmers, jobs)
   # Flatten list of lists
    flat = [item for sublist in results for item in sublist]


    return flat



def build_kmers_lemma(lemma: List[Dict], kmer_list: List[int]) -> pd.DataFrame:
    """Generate a set of kmers from an input JSON of a list of simple dictionaries
    of a converted CDE (designations to Name, Question; definitions to Definition).
    k-mer lengths specified in kmer_list. 

    Args:
        lemma (List[Dict]): List of dictionary with keys: tinyId, Name, Question, Definition, PermVal1, PermVal2
        kmer_list (List[int]): List of integers specifying lengths of kmers to produce

    Returns:
        pd.DataFrame: _description_
    """
# count = 0
    for cde in lemma:
        # count+=1
        # if count >= 10000:
        #     break
        for key, val in cde.items():
            if val == "":
                break
            if key == "tinyId":
                cd_id = val
                # print(f"This is supposed to be the tinyID proper: {cd_id}")
            elif key in fields_wanted:
                fld = key
                tokens = tokenizer.tokenize(val)
                for k in [4, 5, 6, 7, 8, 9,  10, 11, 13, 15, 17]:
                    kmers = []
                    for i in range(len(tokens) - k + 1):
                        kmer = tuple(tokens[i:i+k])
                        # prefix, suffix = kmer[:-1], kmer[1:]
                        kmers.append(kmer)
                    tmp_df = pd.DataFrame({'kmer': kmers})
                    tmp_df = tmp_df.assign(**{'tinyId': cd_id, 'field': fld, 'k': k})
                    # if len(tmp_df) > 0:
                    #     print(tmp_df.head(5))
                    df_kmers=pd.concat([df_kmers,tmp_df], ignore_index=True)
    
    return df_kmers


def gen_kmer_counts(raw_kmers: List[Dict]) -> pd.DataFrame:

    # Summarize just (k, kmer)
    counts = Counter((rec["k"], rec["kmer"]) for rec in raw_kmers)

    # Optional: DataFrame for visualization
    df_counts = pd.DataFrame([
        {"k": k, "kmer": kmer, "count": count}
        for (k, kmer), count in counts.items()
    ])
    
    return df_counts

def extract_phrases(records, kmax=5, min_count=2, margin_threshold=1):
    global_counts = Counter()
    per_record_output = []

    for tinyId, field, text in records:
        tokens = tokenize(text)
        original_text = text
        phrases = []
        margin_cases = []
        seen = set()

        # Work from longer kmers down to 1
        for k in range(kmax, 0, -1):
            kmer_counts = Counter(
                tuple(tokens[i:i+k]) for i in range(len(tokens) - k + 1)
            )

            # Only keep frequent kmers
            for kmer, count in kmer_counts.items():
                if count < min_count or kmer in seen:
                    continue

                phrase_text = " ".join(kmer)

                # greedy extension: here simplified to recording the kmer itself
                phrases.append({"text": phrase_text, "count": count})
                seen.add(kmer)
                global_counts[phrase_text] += count

                # destructive removal from text
                tokens_str = " ".join(tokens)
                tokens_str = re.sub(r"\b" + re.escape(phrase_text) + r"\b", "", tokens_str)
                tokens = tokenize(tokens_str)

                # margin cases (subsets)
                if count <= margin_threshold and k > 1:
                    for sublen in (k-1,):
                        for i in range(len(kmer) - sublen + 1):
                            sub = kmer[i:i+sublen]
                            sub_text = " ".join(sub)
                            margin_cases.append({"text": sub_text, "count": count})

        per_record_output.append({
            "tinyId": tinyId,
            "field": field,
            "original_text": original_text,
            "phrases": phrases,
            "margin_cases": margin_cases
        })

    return per_record_output, dict(global_counts)


# def recursive_extension(text: List[Dict], paths, kmax: int, kmin: int):
#     """_summary_

#     Args:
#         text (List[Dict]): _description_
#         kmax (int): _description_
#         kmin (int): _description_
#     """
#     # filter the fields of interest
#     for k in range(kmax, kmin, -1):
#         kmers = gen_kmers_k(text, k)
#         kmer_count = gen_kmer_counts(kmers)
#         phrases = extend_phrases_in_bin(phrases=kmer_count)
#         text = strip_phrases_simple(text, phrases)
#         phrases_global = phrases_global.extend(phrases) 
        
        
        
        