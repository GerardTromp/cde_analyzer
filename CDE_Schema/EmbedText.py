#
# File: CDE_Schema/EmbedText.py
#
# Simplified model for embedding text extraction workflows
#

from typing import Optional
from pydantic import BaseModel


class EmbedText(BaseModel):
    """
    Simplified model for embedding text extraction.

    Used by the subset command to filter and validate records
    with a minimal field set suitable for text embedding workflows.

    Mandatory fields: tinyId, Name
    Optional fields: Question, Definition, PermissibleValues
    """
    tinyId: str
    Name: str
    Question: Optional[str] = None
    Definition: Optional[str] = None
    PermissibleValues: Optional[str] = None
