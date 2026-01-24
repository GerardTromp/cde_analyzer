# Data Models

## Overview

The CDE Analyzer uses Pydantic BaseModel classes to represent the NLM Common Data Elements API schema. All models are in the `CDE_Schema/` directory and provide type-safe, validated representations of CDE data structures.

**Key Characteristic**: The schema supports **self-referential nesting** - data elements can contain nested instances of the same or related types, requiring recursive traversal for processing.

## Top-Level Models

### CDEItem (CDE_Schema/CDE_Item.py)

Represents an individual Common Data Element.

**Structure**:
```python
class CDEItem(BaseModel):
    # Identity
    x_id: Optional[str] = None              # Internal ID (rarely used)
    tinyId: Optional[str]                    # Short identifier
    elementType: Optional[str]               # Type classification

    # Status
    nihEndorsed: Optional[bool]              # NIH endorsement flag
    archived: Optional[bool]                 # Archive status
    registrationState: Optional[RegistrationState]

    # Metadata
    created: Optional[str] = None            # ISO date string
    createdBy: Optional[CreatedBy]
    updated: Optional[str] = None            # ISO date string
    updatedBy: Optional[UpdatedBy] = None

    # Organization
    stewardOrg: Optional[StewardOrg]
    usedByOrgs: Optional[List[str]] = None
    sources: Optional[List[Source]]

    # Semantic Content
    designations: Optional[List[Designation]]  # Names/labels
    definitions: Optional[List[Definition]]     # Descriptions

    # Value Constraints
    valueDomain: Optional[ValueDomain] = None  # Data type and constraints

    # Classification & Context
    classification: Optional[List[Classification]]
    properties: Optional[List[Property]]
    ids: Optional[List[Identifier]]            # External identifiers

    # Related Items
    formElements: Optional[List[FormElement]] = None
    dataSets: Optional[List[DataSet]] = None
    derivationRules: Optional[List[DerivationRule]] = None

    # Documentation
    referenceDocuments: Optional[List[ReferenceDocument]]
    attachments: Optional[List[Attachment]]
    comments: Optional[List[Comment]] = None

    # History
    history: Optional[List[str]] = None
    lastMigrationScript: Optional[str] = None
    views: Optional[int] = None
    origin: Optional[str] = None
    imported: Optional[str] = None
```

**42 fields total**, mostly Optional to handle varying API responses.

### CDEForm (CDE_Schema/CDE_Form.py)

Represents a form structure containing multiple data elements.

**Structure**:
```python
class CDEForm(BaseModel):
    # Identity (note: uses Field alias for MongoDB _id)
    id: Optional[str] = Field(alias="_id", default=None)
    tinyId: Optional[str]
    elementType: Optional[str]               # Appears twice in original
    version: Optional[str] = None

    # Status
    nihEndorsed: Optional[bool]
    archived: Optional[bool]
    registrationState: Optional[RegistrationState]
    noRenderAllowed: Optional[bool] = None

    # Metadata
    created: Optional[str] = None
    createdBy: Optional[CreatedBy]
    updated: Optional[str] = None
    updatedBy: Optional[UpdatedBy] = None
    changeNote: Optional[str] = None

    # Organization
    stewardOrg: Optional[StewardOrg]
    sources: Optional[List[Source]]

    # Content
    formElements: Optional[List[FormElement]]  # The actual form structure
    designations: Optional[List[Designation]]
    definitions: Optional[List[Definition]]

    # Copyright
    isCopyrighted: Optional[bool] = None
    copyright: Optional[FormCopyright]

    # Classification & Properties
    classification: Optional[List[Classification]] = None
    properties: Optional[List[Property]]
    ids: Optional[List[Identifier]]
    cdeTinyIds: Optional[List[str]]            # References to CDEItems

    # Presentation
    displayProfiles: Optional[List[DisplayProfile]]

    # Documentation
    referenceDocuments: Optional[List[ReferenceDocument]]
    attachments: Optional[List[Attachment]]
    comments: Optional[List[Comment]] = None

    # History
    history: Optional[List[str]] = None
    lastMigrationScript: Optional[str] = None
    origin: Optional[str] = None
    imported: Optional[str] = None
```

**~35 fields**, with nested FormElement lists containing the form structure.

## Shared Model Classes (CDE_Schema/classes.py)

### Identity & Metadata Classes

**Source** - Origin of data
```python
sourceName: str
created, updated: datetime strings
registrationStatus: str
datatype: str
copyright: Optional[Copyright]
```

**CreatedBy, UpdatedBy, UploadedBy** - User references
```python
username: str
```

**StewardOrg** - Organizational steward
```python
name: str
```

**Identifier** - External identification
```python
id: str
source: str
version: Optional[str]
```

### Registration & Status

**RegistrationState** - Lifecycle status
```python
administrativeNote: str
administrativeStatus: str
effectiveDate: datetime string
registrationStatus: str
replacedBy: Optional[ReplacedBy]
mergedTo: Optional[MergedTo]
unresolvedIssue: str
untilDate: datetime string
```

**ReplacedBy, MergedTo** - Succession references
```python
tinyId: str
```

### Semantic Content

**Designation** - Names/labels
```python
designation: str                # The actual name/label
sources: List[str]              # Where this name comes from
tags: List[str]                 # Categorical tags
```

**Definition** - Descriptions
```python
definition: str                 # The definition text
definitionFormat: str           # HTML, text, etc.
sources: List[str]
tags: List[str]
```

### Value Domain - Data Type Specifications

**ValueDomain** - Defines allowed values and data types
```python
datatype: str                   # "Text", "Number", "Date", etc.
name: str
definition: str
uom: str                        # Unit of measure
vsacOid: str                    # VSAC OID for value sets

# Type-specific constraints (only one populated based on datatype)
datatypeText: Optional[DatatypeText]
datatypeNumber: Optional[DatatypeNumber]
datatypeDate: Optional[DatatypeDate]
datatypeTime: Optional[DatatypeTime]
datatypeValueList: Optional[DatatypeValueList]
datatypeDynamicCodeList: Optional[DatatypeDynamicCodeList]
datatypeExternallyDefined: Optional[DatatypeExternallyDefined]

# For enumerated values
permissibleValues: List[PermissibleValue]
identifiers: List[Identifier]
ids: List[Identifier]
```

**DatatypeText** - Text constraints
```python
maxLength: int
minLength: int
regex: str
rule: str
```

**DatatypeNumber** - Numeric constraints
```python
maxValue: Union[float, int]
minValue: Union[float, int]
precision: int
```

**DatatypeDate, DatatypeTime** - Temporal constraints
```python
format: str
```

**DatatypeValueList** - List specification
```python
datatype: str
```

**DatatypeDynamicCodeList** - Code system reference
```python
system: str
```

**DatatypeExternallyDefined** - External reference
```python
description: str
descriptionFormat: str
link: str
```

**PermissibleValue** - Enumerated value
```python
permissibleValue: str           # The actual value
valueMeaningName: str           # Display name
valueMeaningDefinition: str     # Description
valueMeaningCode: str           # Code
conceptId: str                  # Concept identifier
conceptSource: str              # Ontology source
codeSystemName: str
codeSystemVersion: str
```

### Classification & Organization

**Classification** - Hierarchical categorization
```python
elements: List[ElementInner]    # Nested classification elements
stewardOrg: StewardOrg
workingGroup: bool
```

**ElementInner** - Nested classification element
```python
elements: List[dict]            # Recursive nesting!
name: str
```

**Property** - Key-value properties
```python
key: str
value: Union[str, dict]         # Can be nested!
valueFormat: str
source: str
```

### Form-Specific Classes

**FormElement** - Not shown in sampled code but referenced
- Likely contains: question, instruction, CDE reference, skip logic

**DisplayProfile** - Form rendering configuration
```python
displayType: str
name: str
displayInstructions: bool
displayInvisible: bool
displayNumbering: bool
displayValues: bool
numberOfColumns: int
repeatFormat: str
sectionsAsMatrix: bool
```

**Instruction** - User instructions
```python
value: str
valueFormat: str
```

**Form** - Form reference
```python
name: str
tinyID: str
version: str
```

**InForm** - Form membership
```python
form: Form
```

**CDE** - CDE reference (distinct from CDEItem)
```python
ids: List[Identifier]
newCde: Optional[NewCde]
name: str
permissibleValues: List[PermissibleValue]
tinyId: str
version: str
```

### Documentation & Support

**ReferenceDocument** - External documentation
```python
document: str
docType: str
languageCode: str
providerOrg: str
referenceDocumentId: str
source: str
text: str
title: str
uri: str
```

**Attachment** - Uploaded files
```python
comment: str
fileid: str
filename: str
filesize: int
filetype: str
isDefault: bool
pendingApproval: bool
scanned: bool
uploadedBy: UploadedBy
uploadDate: datetime string
```

**Comment** - User comments
```python
created: datetime string
element: Element
linkedTab: str
pendingApproval: bool
replies: List[Reply]
status: str
text: str
user: str
usename: str              # Note: typo in API schema
```

**Reply** - Comment reply
```python
created: datetime string
pendingApproval: bool
status: str
text: str
user: str
usename: str              # Note: typo in API schema
```

**Element** - Element reference
```python
eltId: str
eltType: str
```

### Data Lineage

**DataSet** - Dataset reference
```python
id: str
notes: str
source: str
studyUri: str
```

**DerivationRule** - Derived data calculation
```python
formula: str
inputs: List[str]
name: str
outputs: List[str]
ruleType: str
```

### Other Supporting Classes

**Copyright, FormCopyright** - Copyright information
```python
# Copyright
value: str
valueFormat: str

# FormCopyright
authority: str
valueFormat: str
urls: List[Url]
```

**Url** - URL reference
```python
x_id: str
url: str
valid: bool
```

**Tag** - Simple tag
```python
tag: str
```

**UnitOfMeasure** - Measurement unit
```python
code: str
system: str
```

**ClassificationScheme, Protocol, Context** - Reference types
```python
id: str
name: str / preferredName: str
longName: str (for Scheme/Protocol)
```

## Data Validation Patterns

### Pydantic Features Used
1. **Optional fields** - Nearly all fields are Optional to handle API variability
2. **Field aliases** - `Field(alias="_id")` for MongoDB compatibility
3. **Type unions** - `Union[float, int]`, `Union[str, dict]`
4. **Nested models** - Rich composition of models
5. **List fields** - `List[SomeModel]` for collections

### Date/Time Handling
- All dates stored as **ISO 8601 strings** (not datetime objects)
- Fields: `created`, `updated`, `effectiveDate`, `untilDate`, `uploadDate`
- Format: `"2024-01-15T10:30:00Z"` (typical)

### Null Semantics
Three types of "empty":
1. `None` - Field is null/missing
2. `""` - Empty string (distinct from None)
3. `[]` - Empty list (distinct from None)

The `logic/counter.py` match_condition function explicitly handles these:
```python
if value is None or value == "" or value == []:
    return match_type == "null"
```

## Serialization/Deserialization

### JSON Input
- Use Pydantic's `model_validate()` or `parse_obj()`
- Handles nested structures automatically
- See `utils/cde_impexport.py`

### JSON Output
- Use Pydantic's `model_dump()` or `dict()`
- Configure with `exclude_none=True` to omit null fields
- Pretty printing controlled by `--pretty` flag

### Alternative Formats
- **CSV/TSV**: Flattened output via `utils/output_writer.py`
- Used for counts, phrase lists, extracted fields
- Dot notation for nested paths (e.g., `"valueDomain.datatype"`)

## Data Model Gotchas

### Self-Referential Nesting
- `Classification.elements[].elements` - recursive classification trees
- `Property.value` can be a dict, potentially containing more properties
- Requires **recursive descent** engine (`core/recursor.py`)

### Field Naming Conventions
- Some API fields start with underscore (e.g., `_id`, `__v`)
- Pydantic converts these: `x_id`, `x__v` with Field aliases
- The `fix_underscores` action addresses this issue

### Duplicated Field Names
- `CDEForm.elementType` appears **twice** in the original (line 64 and 73)
- Likely a schema error, second declaration overwrites first
- No functional impact due to Pydantic's handling

### Typos in API
- `Comment.usename` and `Reply.usename` (should be `username`)
- These are **preserved** to match the API schema exactly

### Optional vs Required
- Only a few fields are truly required (no `= None` default)
- Most have `= None` to handle API's sparse responses
- This makes validation permissive but flexible

### Type Flexibility
- `Property.value: Union[str, dict]` - can be simple or nested
- `DatatypeNumber.maxValue: Union[float, int]` - numeric flexibility
- Models must handle this polymorphism gracefully

## Data Access Patterns

### Recursive Traversal
Use `core/recursor.py` for any deep inspection:
```python
recursive_descent(cde_item, path="", visitor=my_visitor, context={})
```

Visitor receives:
- `path`: Dot-separated path (e.g., `"designations.*.designation"`)
- `value`: The scalar value at that path
- `context`: Shared state dictionary

### Field Counting
See `logic/counter.py` for patterns:
- Group by top-level, path, or terminal field name
- Match by non_null, null, fixed value, or regex
- Type classification: int, float, str, strN (length-based)

### Path Specifications
Three interpretation modes (`--group-type`):
- **top**: Top-level field only (e.g., `tinyId`)
- **path**: Full path contains key (e.g., `valueDomain.datatypeText`)
- **terminal**: Deepest component matches (e.g., any `*.name`)

## LLM Classification Models (NEW)

### LLM_Classification.py

Data models for LLM-based phrase classification results.

**ConfidenceQuintile** - Enum for confidence levels
```python
class ConfidenceQuintile(str, Enum):
    HIGHLY_LIKELY = "highly_likely"      # 81-100% confidence
    LIKELY = "likely"                     # 61-80% confidence
    INDETERMINATE = "indeterminate"       # 41-60% confidence
    UNLIKELY = "unlikely"                 # 21-40% confidence
    HIGHLY_UNLIKELY = "highly_unlikely"   # 0-20% confidence
```

**LLMResponse** - Single provider response
```python
provider: str                    # Provider name (claude, openai, google)
model_id: str                    # Model identifier used
category: str                    # Classified category
confidence: float                # Confidence score (0.0-1.0)
reasoning: str                   # LLM's explanation
raw_response: Optional[str]      # Raw API response for debugging
latency_ms: Optional[float]      # Response time
```

**AggregatedClassification** - Multi-LLM aggregated result
```python
final_category: str              # Consensus category
final_quintile: ConfidenceQuintile
aggregated_confidence: float     # Combined confidence (0.0-1.0)
agreement_level: str             # unanimous, majority, split
individual_responses: List[LLMResponse]
vote_distribution: Dict[str, int]  # Category → vote count
combined_reasoning: str          # Merged reasoning from all LLMs
```

**PhraseContext** - Phrase with context for classification
```python
phrase_id: str                   # Unique identifier
phrase_text: str                 # Lemmatized phrase
verbatim_forms: List[str]        # Original text variants
occurrences: List[dict]          # Context per occurrence
n_tinyids: int                   # Number of CDEs containing phrase
total_frequency: int             # Total occurrences
```

**PhraseClassification** - Complete classification result
```python
phrase_context: PhraseContext    # Input phrase data
classification: AggregatedClassification  # Classification result
timestamp: str                   # ISO 8601 timestamp
module_name: str                 # Query module used
```

### Quintile Computation

Confidence scores (0.0-1.0) map to quintiles:
- 0.81-1.00 → highly_likely
- 0.61-0.80 → likely
- 0.41-0.60 → indeterminate
- 0.21-0.40 → unlikely
- 0.00-0.20 → highly_unlikely

### Aggregation Methods

Results from multiple LLMs are combined using configurable methods:

| Method | Description |
|--------|-------------|
| `unanimous` | All providers must agree |
| `majority` | Most common category wins (default) |
| `weighted_majority` | Weighted by confidence scores |
| `confidence_weighted` | Full confidence-weighted voting |

## Future Extensibility

The README mentions potential extension to:
- **SearchDocumentResponse** - Wrapper for CDE search results
- **SearchFormResponse** - Wrapper for Form search results

These would add outer envelope structures around CDEItem/CDEForm lists with pagination metadata.
