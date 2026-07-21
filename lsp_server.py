import logging
import re

from pygls.lsp.server import LanguageServer
from lsprotocol import types
from lsprotocol.types import (
    Range,
    Position,
    Hover,
    MarkupContent,
    MarkupKind,
    Location,
)

from textx import TextXSyntaxError
from grammar_loader import (
    load_model_from_str,
    ValidationError,
)

logging.basicConfig(level=logging.INFO)
logging.getLogger("pygls").setLevel(logging.WARNING)
logging.getLogger("pygls.protocol").setLevel(logging.WARNING)
logging.getLogger("pygls.feature_manager").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ==========================================================
# SERVER
# ==========================================================

server = LanguageServer(
    "testdatagen-language-server",
    "v1.0"
)

# ==========================================================
# REGEX
# ==========================================================

WORD_REGEX = r"[a-zA-Z0-9_]+"
ENTITY_REGEX = r"entity\s+([a-zA-Z0-9_]+)"

# ==========================================================
# DSL DEFINITIONS
# ==========================================================

KEYWORDS_DICTIONARY = {
    "schema": "Defines a new TestDataGen schema container.",
    "entity": "Defines a data entity (table/object structure) to generate records for.",
    "fields": "Block containing the individual property attributes of an entity.",
    "config": "Configuration block for setting up strategies and generation volume.",
    "ref": "Creates a relational reference to another defined Entity.",
    "enum": "Defines a custom enumeration type with a strict set of allowed text values.",
    "description": "Optional schema description.",
    "seed": "Seed value used for deterministic data generation.",
    "strategy": "Defines the generation strategy.",
    "combination_strategy": "Defines how values are combined during generation.",
    "generate": "Specifies how many instances should be generated.",
    "include": "Adds explicit test cases that must be included.",
}

TYPES_DICTIONARY = {
    "uuid": "Generates a unique universally unique identifier (UUIDv4).",
    "email": "Generates a valid, randomized email address string.",
    "number": "Generates a numeric value (integer or decimal based on constraints).",
    "boolean": "Generates a randomized boolean value (true or false).",
    "string": "Generates a randomized text string.",
    "fullName": "Generates a realistic full name (Firstname + Lastname).",
    "firstName": "Generates a randomized common first name.",
    "lastName": "Generates a randomized common last name.",
    "username": "Generates a randomized common username.",
    "datetime": "Generates a full ISO timestamp string.",
    "date": "Generates a standard calendar date string (YYYY-MM-DD).",
    "productName": "Generates realistic product names.",
    "companyName": "Generates realistic company names.",
    "address": "Generates realistic street addresses.",
    "city": "Generates realistic city names.",
    "country": "Generates realistic country names.",
    "phone": "Generates realistic phone numbers.",
    "url": "Generates valid URL strings.",
}

CONSTRAINTS_DICTIONARY = {
    "range": "Restricts scalar numbers or dates within a specific 'min..max' boundary.",
    "unique": "Ensures all generated items for this field contain unique values (no duplicates).",
    "precision": "Specifies the number of decimal places for numeric generation.",
    "special": "Controls the inclusion or exclusion of special characters in string generation.",
    "coverage": "Specifies the percentage of rows that must satisfy this condition (0.0 to 1.0).",
    "partitions": "Defines equivalent equivalence classes/sub-ranges for partition-based testing.",
    "partition": "Defines a single equivalence class within data partition testing.",
    "boundary": "Forces the generator to produce edge-case or limit-values for this field.",
}

STRATEGIES_DICTIONARY = {
    "random": "Standard generation strategy using random distributions.",
    "boundary": "Generation strategy focused on boundary values.",
    "partition": "Generation strategy focused on partition coverage.",
    "smart": "Intelligent generation strategy that automatically combines partitions and boundary values.",
}

COMBINATION_STRATEGIES_DICTIONARY = {
    "full": "Generates all possible combinations.",
    "pairwise": "Ensures every pair of values appears together.",
    "each-used": "Ensures every value is used at least once.",
}

SPECIAL_VALUES_DICTIONARY = {
    "null": "Represents a null value.",
    "empty": "Represents an empty value.",
    "invalid": "Represents intentionally invalid test data.",
}

HOVER_DICTIONARY = {
    **KEYWORDS_DICTIONARY,
    **TYPES_DICTIONARY,
    **CONSTRAINTS_DICTIONARY,
    **STRATEGIES_DICTIONARY,
    **COMBINATION_STRATEGIES_DICTIONARY,
    **SPECIAL_VALUES_DICTIONARY,
}

# ==========================================================
# HELPERS
# ==========================================================

def get_word_at_position(
    line: str,
    character: int
):

    for match in re.finditer(
        WORD_REGEX,
        line
    ):

        start = match.start()
        end = match.end()

        if start <= character < end:

            return {
                "word": match.group(0),
                "start": start,
                "end": end,
            }

    return None


def get_entity_definitions(document):

    entities = {}

    for line_index, line in enumerate(document.lines):

        match = re.search(
            ENTITY_REGEX,
            line
        )

        if match:

            entity_name = match.group(1)

            entities[entity_name] = {
                "line": line_index,
                "start": match.start(1),
                "end": match.end(1),
            }

    return entities


def create_completion_items(dictionary, kind):

    return [
        types.CompletionItem(
            label=key,
            kind=kind,
            documentation=value,
        )
        for key, value in dictionary.items()
    ]

# ==========================================================
# VALIDATION
# ==========================================================

def validate(
    ls: LanguageServer,
    uri: str
):

    diagnostics = []

    document = ls.workspace.get_text_document(uri)

    try:

        load_model_from_str(document.source)

    except TextXSyntaxError as e:

        line = max(e.line - 1, 0)
        col = max(e.col - 1, 0)

        diagnostics.append(
            types.Diagnostic(
                range=types.Range(
                    start=types.Position(
                        line=line,
                        character=col,
                    ),
                    end=types.Position(
                        line=line,
                        character=col + 10,
                    ),
                ),
                message=e.message,
                severity=types.DiagnosticSeverity.Error,
                source="textX",
            )
        )

    except ValidationError as e:

        diagnostics.append(
            types.Diagnostic(
                range=types.Range(
                    start=types.Position(
                        line=0,
                        character=0
                    ),
                    end=types.Position(
                        line=0,
                        character=10
                    ),
                ),
                message=str(e),
                severity=types.DiagnosticSeverity.Error,
                source="validation",
            )
        )

    ls.text_document_publish_diagnostics(
        types.PublishDiagnosticsParams(
            uri=uri,
            diagnostics=diagnostics,
        )
    )

# ==========================================================
# EVENTS
# ==========================================================

@server.feature(types.TEXT_DOCUMENT_DID_OPEN)
def did_open(
    ls: LanguageServer,
    params: types.DidOpenTextDocumentParams
):
    validate(ls, params.text_document.uri)


@server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
def did_change(
    ls: LanguageServer,
    params: types.DidChangeTextDocumentParams
):
    validate(ls, params.text_document.uri)


@server.feature(types.TEXT_DOCUMENT_DID_SAVE)
def did_save(
    ls: LanguageServer,
    params: types.DidSaveTextDocumentParams
):
    validate(ls, params.text_document.uri)

# ==========================================================
# COMPLETION
# ==========================================================

@server.feature(types.TEXT_DOCUMENT_COMPLETION)
def completions(
    ls: LanguageServer,
    params: types.CompletionParams,
):

    items = []

    items.extend(
        create_completion_items(
            KEYWORDS_DICTIONARY,
            types.CompletionItemKind.Keyword
        )
    )

    items.extend(
        create_completion_items(
            TYPES_DICTIONARY,
            types.CompletionItemKind.TypeParameter
        )
    )

    items.extend(
        create_completion_items(
            CONSTRAINTS_DICTIONARY,
            types.CompletionItemKind.Property
        )
    )

    items.extend(
        create_completion_items(
            STRATEGIES_DICTIONARY,
            types.CompletionItemKind.EnumMember
        )
    )

    items.extend(
        create_completion_items(
            COMBINATION_STRATEGIES_DICTIONARY,
            types.CompletionItemKind.EnumMember
        )
    )

    items.extend(
        create_completion_items(
            SPECIAL_VALUES_DICTIONARY,
            types.CompletionItemKind.Value
        )
    )

    try:

        document = ls.workspace.get_text_document(
            params.text_document.uri
        )

        entities = re.findall(
            ENTITY_REGEX,
            document.source,
        )

        for entity_name in set(entities):

            items.append(
                types.CompletionItem(
                    label=entity_name,
                    kind=types.CompletionItemKind.Class,
                    documentation=f"Entity: {entity_name}",
                )
            )

    except Exception as e:
        logger.exception(e)

    return types.CompletionList(
        is_incomplete=False,
        items=items,
    )

# ==========================================================
# HOVER
# ==========================================================

@server.feature(types.TEXT_DOCUMENT_HOVER)
def hover(
    ls: LanguageServer,
    params: types.HoverParams
):

    document = ls.workspace.get_text_document(
        params.text_document.uri
    )

    line_num = params.position.line
    char_num = params.position.character

    line = document.lines[line_num]

    result = get_word_at_position(
        line,
        char_num,
    )

    if not result:
        return None

    word = result["word"]

    if word in HOVER_DICTIONARY:

        return Hover(
            contents=MarkupContent(
                kind=MarkupKind.Markdown,
                value=f"## {word}\n{HOVER_DICTIONARY[word]}"
            ),
            range=Range(
                start=Position(
                    line=line_num,
                    character=result["start"]
                ),
                end=Position(
                    line=line_num,
                    character=result["end"]
                ),
            )
        )

    return None

# ==========================================================
# GO TO DEFINITION
# ==========================================================

@server.feature(types.TEXT_DOCUMENT_DEFINITION)
def go_to_definition(
    ls: LanguageServer,
    params: types.DefinitionParams,
):

    document = ls.workspace.get_text_document(
        params.text_document.uri
    )

    line_num = params.position.line
    char_num = params.position.character

    current_line = document.lines[line_num]

    result = get_word_at_position(
        current_line,
        char_num,
    )

    if not result:
        return None

    selected_word = result["word"]

    entities = get_entity_definitions(document)

    if selected_word not in entities:
        return None

    entity = entities[selected_word]

    return Location(
        uri=params.text_document.uri,
        range=Range(
            start=Position(
                line=entity["line"],
                character=entity["start"],
            ),
            end=Position(
                line=entity["line"],
                character=entity["end"],
            ),
        )
    )

# ==========================================================
# FIND REFERENCES
# ==========================================================

@server.feature(types.TEXT_DOCUMENT_REFERENCES)
def find_references(
    ls: LanguageServer,
    params: types.ReferenceParams,
):

    document = ls.workspace.get_text_document(
        params.text_document.uri
    )

    line_num = params.position.line
    char_num = params.position.character

    current_line = document.lines[line_num]

    result = get_word_at_position(
        current_line,
        char_num,
    )

    if not result:
        return []

    selected_word = result["word"]

    entities = get_entity_definitions(document)

    if selected_word not in entities:
        return []

    locations = []

    # entity definition
    entity = entities[selected_word]

    locations.append(
        Location(
            uri=params.text_document.uri,
            range=Range(
                start=Position(
                    line=entity["line"],
                    character=entity["start"],
                ),
                end=Position(
                    line=entity["line"],
                    character=entity["end"],
                ),
            )
        )
    )

    # ref usages
    ref_regex = rf"ref\s+({re.escape(selected_word)})\b"

    for line_index, line in enumerate(document.lines):

        for match in re.finditer(
            ref_regex,
            line
        ):

            start = match.start(1)
            end = match.end(1)

            locations.append(
                Location(
                    uri=params.text_document.uri,
                    range=Range(
                        start=Position(
                            line=line_index,
                            character=start,
                        ),
                        end=Position(
                            line=line_index,
                            character=end,
                        ),
                    )
                )
            )

    return locations

# ==========================================================
# START
# ==========================================================

if __name__ == "__main__":
    server.start_io()