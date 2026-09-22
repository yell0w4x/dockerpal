
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
| `Space` | Select / deselect the row under the cursor |
| `+` / `-` / `*` | Select all / deselect all / invert selection |
| `Enter` | Show the JSON details of the row under the cursor |
| `d` / `Delete` | Delete the selected rows (or the cursor row) after confirmation |
| `u` / `x` / `t` | Containers only: start / stop / restart the selected rows (or the cursor row) |
| `/` | Search: filter the list as you type; `Enter` keeps the filter, `Esc` drops it |
| `r` | Refresh the list |
| `Esc` | Close the sidebar / go back / quit |
| `q` | Quit |

## Development

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pytest pytest-asyncio -e .
pytest
```
