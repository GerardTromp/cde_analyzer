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

MODEL_REGISTRY: dict[str, Type[BaseModel]] = {
    "CDE": CDEItem,
    "Form": CDEForm,
    "Embed": EmbedItem,
}

