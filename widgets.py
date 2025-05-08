import tkinter as tk
from tkinter import ttk

class AutocompleteCombobox(ttk.Combobox):
    def __init__(self, master, completevalues=None, **kwargs):
        super().__init__(master, **kwargs)
        self.completevalues = completevalues or []
        self._hits = []
        self['values'] = self.completevalues

        # Bind key events:
        self.bind('<KeyRelease>', self._key_release)
        self.bind('<Tab>', self._handle_tab_key)
        self.bind('<Return>', self._select_and_next)
        # Let arrow keys be handled by the default behavior.

    def _key_release(self, event):
        # Ignore keys that we want the widget to handle normally.
        if event.keysym in ('Tab', 'Return', 'Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Up', 'Down'):
            return

        # Get the current text in lowercase.
        value = self.get().lower()

        # If empty, restore full list.
        if not value:
            self['values'] = self.completevalues
            return

        # Filter completevalues for matches.
        self._hits = [item for item in self.completevalues if value in item.lower()]
        self['values'] = self._hits

        # If there are matches, open the dropdown list.
       # if self._hits:
       #     self.event_generate('<Down>')

    def _handle_tab_key(self, event):
        # Mimic the behavior of the Down key to open the dropdown
        if self._hits:
            self.event_generate('<Down>')
        return 'break'  # Prevent default tab behavior
        
    def _select_and_next(self, event):
        """
        On Tab/Return, if a suggestion is highlighted (or if none is highlighted, use the first),
        then set the entry's value to that suggestion.
        """
        # Try to get the current highlighted index.
        try:
            index = self.current()
        except Exception:
            index = -1

        if index == -1:
            # No item is highlighted but we have matches: choose the first.
            if self._hits:
                self.set(self._hits[0])
        else:
            # Use the highlighted suggestion.
            values = list(self['values'])
            if index < len(values):
                self.set(values[index])

        # Clear selection and move focus (optional).
        self.selection_clear()
        self.icursor(tk.END)
        self.event_generate('<Tab>')
        return "break"

    def set_completion_list(self, completion_list):
        """Update the list of possible completions."""
        self.completevalues = completion_list
        self['values'] = completion_list