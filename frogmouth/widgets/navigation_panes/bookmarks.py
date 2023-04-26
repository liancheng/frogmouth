"""Provides the bookmarks navigation pane."""

from __future__ import annotations

from pathlib import Path

from httpx import URL
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from ...data import Bookmark, load_bookmarks, save_bookmarks
from ...dialogs import InputDialog, YesNoDialog
from .navigation_pane import NavigationPane


class Entry(Option):
    """An entry in the bookmark list."""

    def __init__(self, bookmark: Bookmark) -> None:
        super().__init__(self._as_prompt(bookmark))
        self.bookmark = bookmark
        """The bookmark that this entry relates to."""

    @staticmethod
    def _as_prompt(bookmark: Bookmark) -> Text:
        """Depict the bookmark as a decorated prompt.

        Args:
            bookmark: The bookmark to depict.

        Returns:
            A prompt with icon, etc.
        """
        return Text.from_markup(
            f":{'page_facing_up' if isinstance(bookmark.location, Path) else 'globe_with_meridians'}: "
            f"[bold]{bookmark.title}[/]\n[dim]{bookmark.location}[/]",
            overflow="ellipsis",
        )


class Bookmarks(NavigationPane):
    """Bookmarks navigation pane."""

    DEFAULT_CSS = """
    Bookmarks {
        height: 100%;
    }

    Bookmarks > OptionList {
        background: $panel;
    }
    """
    """The default CSS for the bookmarks navigation pane."""

    BINDINGS = [
        Binding("delete", "delete", "Delete the bookmark"),
        Binding("r", "rename", "Rename the bookmark"),
    ]
    """The bindings for the bookmarks navigation pane."""

    def __init__(self) -> None:
        """Initialise the bookmarks navigation pane."""
        super().__init__("Bookmarks")
        self._bookmarks: list[Bookmark] = load_bookmarks()
        """The internal list of bookmarks."""

    def compose(self) -> ComposeResult:
        """Compose the child widgets."""
        yield OptionList(*[Entry(bookmark) for bookmark in self._bookmarks])

    def set_focus_within(self) -> None:
        """Focus the option list."""
        self.query_one(OptionList).focus()

    def _bookmarks_updated(self) -> None:
        """Handle the bookmarks being updated."""
        # It's slightly costly, but currently there's no easier way to do
        # this; and really it's not going to be that frequent. Here we nuke
        # the content of the OptionList and rebuild it based on the actual
        # list of bookmarks.
        bookmarks = self.query_one(OptionList)
        old_position = bookmarks.highlighted
        bookmarks.clear_options()
        for bookmark in self._bookmarks:
            bookmarks.add_option(Entry(bookmark))
        save_bookmarks(self._bookmarks)
        bookmarks.highlighted = old_position

    def add_bookmark(self, title: str, location: Path | URL) -> None:
        """Add a new bookmark.

        Args:
            title: The title of the bookmark.
            location: The location of the bookmark.
        """
        self._bookmarks.append(Bookmark(title, location))
        self._bookmarks = sorted(self._bookmarks, key=lambda bookmark: bookmark.title)
        self._bookmarks_updated()

    class Goto(Message):
        """Message that requests that the viewer goes to a given bookmark."""

        def __init__(self, bookmark: Bookmark) -> None:
            """Initialise the bookmark goto message.

            Args:
                bookmark: The bookmark to go to.
            """
            super().__init__()
            self.bookmark = bookmark

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle an entry in the bookmarks being selected.

        Args:
            event: The event to handle.
        """
        event.stop()
        assert isinstance(event.option, Entry)
        self.post_message(self.Goto(event.option.bookmark))

    def action_delete(self) -> None:
        """Delete the highlighted bookmark."""
        if self.query_one(OptionList).highlighted is not None:
            self.app.push_screen(
                YesNoDialog(
                    self,
                    "Delete bookmark",
                    "Are you sure you want to delete the bookmark?",
                    id="delete",
                )
            )

    def on_yes_no_dialog_positive_reply(self, event: YesNoDialog.PositiveReply) -> None:
        """Handle a yes/no dialog giving a positive reply.

        Args:
            event: The event to handle.
        """
        bookmarks = self.query_one(OptionList)
        if event.sender_id == "delete" and bookmarks.highlighted is not None:
            del self._bookmarks[bookmarks.highlighted]
            self._bookmarks_updated()

    def action_rename(self) -> None:
        """Rename the highlighted bookmark."""
        if (bookmark := self.query_one(OptionList).highlighted) is not None:
            self.app.push_screen(
                InputDialog(
                    self,
                    "Bookmark title:",
                    self._bookmarks[bookmark].title,
                    bookmark,
                    id="edit_title",
                )
            )

    def on_input_dialog_result(self, event: InputDialog.Result) -> None:
        """Handle an input dialog result being passed to us."""
        if event.sender_id == "edit_title":
            # The cargo value for the result should be the index of the
            # bookmark we're changing.
            assert isinstance(event.cargo, int)
            # Everything looks good, update the bookmarks.
            self._bookmarks[event.cargo] = Bookmark(
                event.value, self._bookmarks[event.cargo].location
            )
            self._bookmarks_updated()
