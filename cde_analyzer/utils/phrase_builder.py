import pandas as pd  # type: ignore
from typing import List, Dict, Tuple



def rename_embed(cde_list: List[Dict]) -> List[Dict]:
    """Simple routine to rename dictionary keys. 
    The simplified dictionary from extract_embed unfortunately has some really long
    key names (e.g., PermissibleValues.permissibleValue, PermissibleValues.permissibleValue
    or PermissibleValues.permval and PermissibleValues.minor).
    This routines simplifies this to: Pv1 and Pv2

    Args:
        cde_list (List[Dict]): List of simple unnested dictionaries with keys:
            "tinyId", "Name", "Question", "Definition", "PermissibleValues.permissibleValue", "PermissibleValues.secondary"
        or equivalent

    Returns:
        List[Dict]: List of dictionaries with keys:
        "tinyId", "Name", "Question", "Definition", "Pv1", "Pv2"
    """
    for cde in cde_list:
        if "PermissibleValues.permissibleValue" in cde:
            cde["Pv1"] = cde.pop("PermissibleValues.permissibleValue")
        if "PermissibleValues.secondary" in cde:
            cde["Pv2"] = cde.pop("PermissibleValues.secondary")
        if "PermissibleValues.permVal" in cde:
            cde["Pv1"] = cde.pop("PermissibleValues.permVal")
        if "PermissibleValues.minor" in cde:
            cde["Pv2"] = cde.pop("PermissibleValues.minor")
    
    return cde_list


