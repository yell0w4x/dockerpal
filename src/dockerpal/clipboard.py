"""System clipboard access.

Textual's own ``copy_to_clipboard`` writes an OSC 52 escape sequence, which
most terminals ignore unless it is explicitly enabled. So try the platform's
clipboard helper first and keep the escape sequence as a fallback (it is what
works over ssh and inside tmux).
"""

import shutil
import subprocess


# In preference order; the ones that do not fit the session simply fail and we
# move on to the next (wl-copy errors without a Wayland display, and so on).
COPY_COMMANDS = (
    ('wl-copy', ()),                            # Wayland
    ('xclip', ('-selection', 'clipboard')),     # X11
    ('xsel', ('--clipboard', '--input')),       # X11
    ('pbcopy', ()),                             # macOS
    ('clip.exe', ()),                           # WSL
)

TIMEOUT_SEC = 5


def copy(text):
    """Put ``text`` on the system clipboard.

    Returns the name of the tool that took it, or None when none could."""

    for tool, args in COPY_COMMANDS:
        path = shutil.which(tool)
        if path is None:
            continue

        try:
            subprocess.run([path, *args], input=text.encode(), check=True,
                           timeout=TIMEOUT_SEC, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            continue

        return tool

    return None
