# Data Models

CDE Analyzer uses Pydantic models to represent the NLM CDE API data structures.

## Overview

The CDE repository data structure is implemented as a set of Pydantic models that mirror the [NLM CDE API](https://cde.nlm.nih.gov/api) schema.

```
CDE_Schema/
├── CDE_Item.py      # CDEItem - Individual data elements
├── CDE_Form.py      # CDEForm - Form structures
└── classes.py       # 50+ supporting models
```

## Primary Models

### CDEItem

Represents an individual Common Data Element.

```python
from CDE_Schema.CDE_Item import CDEItem

# Load from JSON
import json
with open("cde_data.json") as f:
    data = json.load(f)

# Parse into Pydantic model
items = [CDEItem.model_validate(item) for item in data]
```

**Key Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `tinyId` | `str` | Unique identifier |
| `designations` | `List[Designation]` | Human-readable names |
| `definitions` | `List[Definition]` | Detailed descriptions |
| `valueDomain` | `ValueDomain` | Permissible values |
| `properties` | `List[Property]` | Additional properties |
| `stewardOrg` | `StewardOrg` | Owning organization |

### CDEForm

Represents a form structure containing multiple CDEs.

```python
from CDE_Schema.CDE_Form import CDEForm
```

## Supporting Models

Located in `CDE_Schema/classes.py`:

### Text Content

| Model | Description |
|-------|-------------|
| `Designation` | Human-readable name with language tag |
| `Definition` | Detailed description with language tag |
| `Instruction` | Usage instructions |

### Value Domain

| Model | Description |
|-------|-------------|
| `ValueDomain` | Container for permissible values |
| `PermissibleValue` | Single allowed value |
| `ValueMeaning` | Semantic meaning of a value |
| `DataType` | Data type specification |

### Organization

| Model | Description |
|-------|-------------|
| `StewardOrg` | Stewarding organization |
| `RegistrationStatus` | Registration state |
| `Classification` | Categorization |

## Design Patterns

### All Fields Optional

All fields are marked as `Optional` to handle sparse API responses:

```python
class CDEItem(BaseModel):
    tinyId: Optional[str] = None
    designations: Optional[List[Designation]] = None
    definitions: Optional[List[Definition]] = None
    # ...
```

**Rationale**: The CDE API returns varying levels of detail. Some records have all fields populated, others have minimal data.

### Field Aliases

MongoDB/API field names are mapped to Python-safe names:

```python
class CDEItem(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    # Allows both item.id and item._id access
```

**Common Aliases**:

| API Name | Python Name |
|----------|-------------|
| `_id` | `id` |
| `_class` | `class_` |

### Self-Referential Nesting

Some models can contain nested instances of themselves:

```python
class FormElement(BaseModel):
    elements: Optional[List["FormElement"]] = None
```

## Validation

Pydantic provides automatic validation:

```python
# Invalid data raises ValidationError
try:
    item = CDEItem.model_validate({"tinyId": 123})  # Should be string
except ValidationError as e:
    print(e.errors())
```

## Serialization

### To JSON

```python
# Single item
json_str = item.model_dump_json()

# With exclusion of null fields
json_str = item.model_dump_json(exclude_none=True)
```

### To Dict

```python
# Full dict
data = item.model_dump()

# By alias (for API compatibility)
data = item.model_dump(by_alias=True)
```

## Usage in Actions

### phrase_miner

```python
from CDE_Schema.CDE_Item import CDEItem

def extract_field_texts(item: CDEItem, field_names: List[str]) -> List[Tuple[str, str]]:
    """Extract text from specified fields."""
    results = []

    if "designation" in field_names and item.designations:
        for i, des in enumerate(item.designations):
            if des.designation:
                results.append((f"designations[{i}].designation", des.designation))

    if "definition" in field_names and item.definitions:
        for i, defn in enumerate(item.definitions):
            if defn.definition:
                results.append((f"definitions[{i}].definition", defn.definition))

    return results
```

### count

```python
from core.recursor import recursive_descent

def count_visitor(value, path, context, depth):
    """Count field occurrences."""
    if path in context["target_fields"]:
        context["counts"][path] += 1
```

## Extending Models

### Adding New Fields

```python
class CDEItem(BaseModel):
    # Existing fields...

    # Add new field
    custom_field: Optional[str] = None
```

### Creating Custom Models

```python
from pydantic import BaseModel
from typing import Optional, List

class CustomAnalysis(BaseModel):
    """Custom model for analysis results."""
    item_id: str
    phrases: List[str]
    scores: Optional[List[float]] = None
```

## API Integration

The models are designed to work with the NLM CDE API:

```python
import requests

# Fetch from API
response = requests.get("https://cde.nlm.nih.gov/api/de/search", params={...})
data = response.json()

# Parse response
items = [CDEItem.model_validate(item) for item in data["elements"]]
```

## Related Documentation

- [Architecture](architecture.md)
- [NLM CDE API Documentation](https://cde.nlm.nih.gov/api)
