"""A view into a Document which wraps the document at a certain
width and can be queried to retrieve lines from the *wrapped* version
of the document.

Allows for incremental updates, ensuring that we only re-wrap ranges of the document
that were influenced by edits.
"""
from __future__ import annotations

from rich._wrap import divide_line
from rich.text import Text

from textual.document._document import DocumentBase, Location


class WrappedDocument:
    def __init__(
        self,
        document: DocumentBase,
        width: int = 0,
    ) -> None:
        """Construct a WrappedDocument.

        Args:
            document: The document to wrap.
            width: The cell-width to wrap at.
        """
        self._document = document
        """The document wrapping is performed on."""

        self._width = width
        """The maximum cell-width per line."""

        self._wrap_offsets: list[list[int]] = []
        """Maps line indices to the offsets within the line wrapping
        breaks should be added."""

        self._offset_to_document_line: list[int] = []
        """Allows us to quickly go from a y-offset within the wrapped document
        to the index of the line in the raw document."""

    def wrap(self) -> None:
        """Wrap and cache all lines in the document."""
        new_wrap_offsets = []
        append_wrap_offset = new_wrap_offsets.append
        width = self._width

        for line in self._document.lines:
            append_wrap_offset(divide_line(line, width))

        self._wrap_offsets = new_wrap_offsets

    @property
    def lines(self) -> list[list[str]]:
        """The lines of the wrapped version of the Document.

        Each index in the returned list represents a line index in the raw
        document. The list[str] at each index is the content of the raw document line
        split into multiple lines via wrapping.
        """
        wrapped_lines = []
        for line_index, line in enumerate(self._document.lines):
            divided = Text(line).divide(self._wrap_offsets[line_index])
            wrapped_lines.append([section.plain for section in divided])
        return wrapped_lines

    def refresh_range(
        self,
        start: Location,
        old_end: Location,
        new_end: Location,
    ) -> None:
        """Incrementally recompute wrapping based on a performed edit.

        This must be called *after* the source document has been edited.

        Args:
            start: The start location of the edit that was performed in document-space.
            old_end: The old end location of the edit in document-space.
            new_end: The new end location of the edit in document-space.
        """

        # Get all the text on the lines between start and end in document space
        start_row, _ = start
        end_row, _ = new_end

        # +1 since we go to the start of the next row, and +1 for inclusive.
        new_lines = self._document.lines[start_row : end_row + 2]

        new_wrap_offsets = []
        for line_index, line in enumerate(new_lines, start_row):
            wrap_offsets = divide_line(line, self._width)
            new_wrap_offsets.append(wrap_offsets)

        # Replace the range start->old with the new wrapped lines
        old_end_row, _ = old_end
        self._wrap_offsets[start_row:old_end_row] = new_wrap_offsets

    def offset_to_line_index(self, offset: int) -> int:
        """Given an offset within the wrapped/visual display of the document,
        return the corresponding line index.

        Args:
            offset: The y-offset within the document.

        Raises:
            ValueError: When the given offset does not correspond to a line
                in the document.

        Returns:
            The line index corresponding to the given y-offset.
        """

        def invalid_offset_error():
            raise ValueError(
                f"No line exists at wrapped document offset {offset!r}. "
                f"Document wrapped with width {self._width!r}. "
            )

        if offset < 0:
            invalid_offset_error()

        current_offset = 0
        for line_index, line_offsets in enumerate(self._wrap_offsets):
            wrapped_line_height = len(line_offsets) + 1
            current_offset += wrapped_line_height
            if current_offset > offset:
                return line_index

        invalid_offset_error()  # Offset is greater than wrapped document height.

    def get_offsets(self, line_index: int) -> list[int]:
        """Given a line index, get the offsets within that line where wrapping
        should occur for the current document.

        Args:
            line_index: The index of the line within the document.

        Returns:
            The offsets within the line where wrapping should occur.
        """
        wrap_offsets = self._wrap_offsets
        out_of_bounds = line_index < 0 or line_index >= len(wrap_offsets)
        if out_of_bounds:
            raise ValueError(
                f"The document line index {line_index!r} is out of bounds. "
                f"The document contains {len(wrap_offsets)!r} lines."
            )
        return wrap_offsets[line_index]