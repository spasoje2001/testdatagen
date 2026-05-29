from unittest.mock import Mock
from lsprotocol import types
from lsp_server import (
    completions,
    hover,
    go_to_definition,
    find_references,
    validate,
)


# ==========================================================
# MOCK DOCUMENT
# ==========================================================

TEST_TEXT = """
schema Test {

    entity User {
        fields {
            id: uuid
            name: string
        }
    }

    entity Order {
        fields {
            owner: ref User
        }
    }
}
""".strip()


class MockDocument:

    def __init__(self, text):
        self.source = text
        self.lines = text.splitlines()


class MockWorkspace:

    def __init__(self, text):
        self.document = MockDocument(text)

    def get_text_document(self, uri):
        return self.document


class MockServer:

    def __init__(self, text):
        self.workspace = MockWorkspace(text)
        self.published = None

    def text_document_publish_diagnostics(self, params):
        self.published = params


# ==========================================================
# COMPLETION
# ==========================================================

def test_completion():

    ls = MockServer(TEST_TEXT)

    params = types.CompletionParams(
        text_document=types.TextDocumentIdentifier(
            uri="file:///test.tdata"
        ),
        position=types.Position(
            line=3,
            character=5
        )
    )

    result = completions(ls, params)

    labels = [item.label for item in result.items]

    assert "schema" in labels
    assert "entity" in labels
    assert "uuid" in labels
    assert "User" in labels


# ==========================================================
# HOVER
# ==========================================================

def test_hover():

    ls = MockServer(TEST_TEXT)

    params = types.HoverParams(
        text_document=types.TextDocumentIdentifier(
            uri="file:///test.tdata"
        ),
        position=types.Position(
            line=0,
            character=2
        )
    )

    result = hover(ls, params)

    assert result is not None
    assert "schema" in result.contents.value


# ==========================================================
# GO TO DEFINITION
# ==========================================================

def test_definition():

    ls = MockServer(TEST_TEXT)

    params = types.DefinitionParams(
        text_document=types.TextDocumentIdentifier(
            uri="file:///test.tdata"
        ),
        position=types.Position(
            line=11,
            character=24
        )
    )

    result = go_to_definition(ls, params)

    assert result is not None
    assert result.range.start.line == 2


# ==========================================================
# REFERENCES
# ==========================================================

def test_references():

    ls = MockServer(TEST_TEXT)

    params = types.ReferenceParams(
        text_document=types.TextDocumentIdentifier(
            uri="file:///test.tdata"
        ),
        position=types.Position(
            line=2,
            character=12
        ),
        context=types.ReferenceContext(
            include_declaration=True
        )
    )

    result = find_references(ls, params)

    assert len(result) >= 2


# ==========================================================
# DIAGNOSTICS
# ==========================================================

def test_diagnostics():

    invalid_text = """
schema Test {

    entity User {
        fields {
            id uuid
        }
    }
}
"""

    ls = MockServer(invalid_text)

    validate(ls, "file:///bad.tdata")

    assert ls.published is not None

    diagnostics = ls.published.diagnostics

    assert len(diagnostics) > 0

    assert diagnostics[0].severity == types.DiagnosticSeverity.Error