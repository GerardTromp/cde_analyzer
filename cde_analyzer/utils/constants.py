# repository for constants to avoid repetition

from CDE_Schema import CDEItem, CDEForm
from pydantic import BaseModel, ValidationError
from typing import Type, Any, List, Optional, Dict, Union

#  NB *****
# This data model only valid after using utils.phrase_builder rename_embed
class EmbedItem(BaseModel):
    tinyId: str
    Name: str
    Question: str
    Definition: str
    Pv1: str
    Pv2: str


class EmbedText(BaseModel):
    """
    Simplified model for embedding text extraction.

    Mandatory fields: tinyId, Name
    Optional fields: Question, Definition, PermissibleValues
    """
    tinyId: str
    Name: str
    Question: Optional[str] = None
    Definition: Optional[str] = None
    PermissibleValues: Optional[str] = None


MODEL_REGISTRY: dict[str, Type[BaseModel]] = {
    "CDE": CDEItem,
    "Form": CDEForm,
    "Embed": EmbedItem,
    "EmbedText": EmbedText,
}

