import logging

from rich.logging import RichHandler
from rich.style import Style
from rich.text import Text

"""
Copyright (c) 2020 Will McGugan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
Modified code from rich (https://github.com/textualize/rich)
"""


class LogHandler(RichHandler):
    def __init__(self, device_name, log_name_len, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filter_strings = []
        self._log_render = LogRender(
            device_name=device_name,
            log_name_len=log_name_len,
            show_time=True,
            show_level=True,
            show_path=False,
            time_format="[%x %X]",
            omit_repeated_times=True,
            level_width=None,
        )

    def add_filter_string(self, s):
        self.filter_strings.append(s)

    def _filter(self, s):
        for i in self.filter_strings:
            s = s.replace(i, "REDACTED")
        return s

    def format(self, record):
        original = super().format(record)
        return self._filter(original)


class LogRender:
    def __init__(
        self,
        device_name,
        log_name_len,
        show_time=True,
        show_level=False,
        show_path=True,
        time_format="[%x %X]",
        omit_repeated_times=True,
        level_width=8,
    ):
        self.filter_strings = []
        self.log_name_len = log_name_len
        self.device_name = device_name
        self.show_time = show_time
        self.show_level = show_level
        self.show_path = show_path
        self.time_format = time_format
        self.omit_repeated_times = omit_repeated_times
        self.level_width = level_width
        self._last_time = None

    def __call__(
        self,
        console,
        renderables,
        log_time,
        time_format=None,
        level="",
        path=None,
        line_no=None,
        link_path=None,
    ):
        from rich.containers import Renderables
        from rich.table import Table

        output = Table.grid(padding=(0, 1))
        output.expand = True
        if self.show_time:
            output.add_column(style="log.time")
        if self.show_level:
            output.add_column(style="log.level", width=self.level_width)
        output.add_column(
            width=self.log_name_len, style=Style(color="yellow"), overflow="fold"
        )
        output.add_column(ratio=1, style="log.message", overflow="fold")
        if self.show_path and path:
            output.add_column(style="log.path")
        row = []
        if self.show_time:
            log_time = log_time or console.get_datetime()
            time_format = time_format or self.time_format
            if callable(time_format):
                log_time_display = time_format(log_time)
            else:
                log_time_display = Text(log_time.strftime(time_format))
            if log_time_display == self._last_time and self.omit_repeated_times:
                row.append(Text(" " * len(log_time_display)))
            else:
                row.append(log_time_display)
                self._last_time = log_time_display
        if self.show_level:
            row.append(level)
        row.append(Text(self.device_name))
        row.append(Renderables(renderables))
        if self.show_path and path:
            path_text = Text()
            path_text.append(
                path, style=f"link file://{link_path}" if link_path else ""
            )
            if line_no:
                path_text.append(":")
                path_text.append(
                    f"{line_no}",
                    style=f"link file://{link_path}#{line_no}" if link_path else "",
                )
            row.append(path_text)

        output.add_row(*row)
        return output


class LogFormatter(logging.Formatter):
    def __init__(
        self, fmt=None, datefmt=None, style="%", validate=True, filter_strings=None
    ):
        super().__init__(fmt, datefmt, style, validate)
        self.filter_strings = filter_strings or []

    def add_filter_string(self, s):
        self.filter_strings.append(s)

    def _filter(self, s):
        print(s)
        for i in self.filter_strings:
            s = s.replace(i, "REDACTED")
        return s

    def format(self, record):
        original = logging.Formatter.format(self, record)
        return self._filter(original)
