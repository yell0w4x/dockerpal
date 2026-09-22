
# Dockerpal

TUI based docker explorer: browse and clean up images, containers, networks and volumes.

![dockerpal](https://github.com/yell0w4x/assets/raw/main/dockerpal.png)

```
python -m venv .venv
source .venv/bin/activate
pip install dockerpal
dockerpal
```

## Keys

| Key | Action |
| --- | --- |
| `s` | Toggle the sidebar (Images / Containers / Networks / Volumes); `Enter` opens the highlighted screen |
| `j` / `k`, `f` / `b`, `gg` / `G` | Move down / up, page down / up, jump to top / bottom |
| `Space` | Select / deselect the row under the cursor (selection survives searching, refreshing and filtering) |
| `+` / `-` / `*` | Select all / deselect all / invert selection (visible rows only) |
| `a` | Actions menu for the current screen (acts on the selection; `Enter` runs, `Esc` closes) |
| `Enter` | Show the JSON details of the row under the cursor |
| `d` / `Delete` | Remove the selected rows (or the cursor row) after confirmation |
| `u` / `x` / `t` | Containers only: start / stop / restart the selected rows (or the cursor row) |
| `/` | Search: filter the list as you type. `Enter` keeps the filter (shown as `/query` in the footer), `Esc` abandons it |
| `r` | Refresh the list |
| `y` | Details view: copy the selection to the clipboard (the whole document when nothing is selected) |
| `e` | Details view: export the JSON to a file in the current directory |
| `Esc` | Close the sidebar, else clear an active filter, else go back / quit |
| `q` | Quit |

### Actions menu

`a` opens the actions the current screen offers, applied to the selection (or the
cursor row when nothing is selected):

| Screen | Actions |
| --- | --- |
| Images | Remove, Force remove, Details |
| Containers | Start, Stop, Restart, Remove, Force remove, Details |
| Networks | Remove, Details |
| Volumes | Remove, Force remove, Details |

## Development

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pytest pytest-asyncio -e .
pytest
```
