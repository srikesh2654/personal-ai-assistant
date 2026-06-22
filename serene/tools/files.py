import os
import shutil
import subprocess

from serene.tools.registry import tool
from serene.tools.safety import resolve
from serene.tools.confirm import confirm


@tool("list_dir",
      "List the files and folders inside a directory.",
      {"path": {"type": "string",
                "description": "Folder path, e.g. 'Downloads' or "
                               "'OneDrive/Desktop'. Defaults to home."}})
def list_dir(path="."):
    """List the files and folders in a directory."""
    real = resolve(path)
    if not os.path.isdir(real):
        return f"'{path}' is not a folder."
    entries = os.listdir(real)
    if not entries:
        return f"'{path}' is empty."
    return "\n".join(entries)


@tool("read_file",
      "Read the text contents of a file.",
      {"path": {"type": "string", "description": "Path to the file."}},
      required=["path"])
def read_file(path):
    """Read the text contents of a file (first 5000 characters)."""
    real = resolve(path)
    if not os.path.isfile(real):
        return f"'{path}' is not a file."
    with open(real, "r", encoding="utf-8", errors="replace") as f:
        return f.read(5000)


@tool("search_files",
      "Find files whose name contains a pattern, searching everywhere under "
      "a folder.",
      {"pattern": {"type": "string",
                   "description": "Text to look for in file names."},
       "path": {"type": "string",
                "description": "Folder to search under. Defaults to home."}},
      required=["pattern"])
def search_files(pattern, path="."):
    """Find files whose name contains `pattern`, anywhere under `path`."""
    real = resolve(path)
    matches = []
    for root, dirs, files in os.walk(real):
        for name in files:
            if pattern.lower() in name.lower():
                matches.append(os.path.join(root, name))
    if not matches:
        return f"No files matching '{pattern}' found."
    return "\n".join(matches[:50])   # cap so we don't flood the model


@tool("open_path",
      "Open a file or folder with its default application.",
      {"path": {"type": "string",
                "description": "Path to the file or folder to open."}},
      required=["path"])
def open_path(path):
    """Open a file or folder with its default application."""
    real = resolve(path)
    os.startfile(real)               # Windows: launch with default app
    return f"Opened {path}."


# --- write / destructive operations (all gated by confirm) ----------------

@tool("make_folder",
      "Create a new folder.",
      {"path": {"type": "string",
                "description": "Path of the folder to create."}},
      required=["path"])
def make_folder(path):
    """Create a new folder (and any parent folders)."""
    real = resolve(path)
    os.makedirs(real, exist_ok=True)
    return f"Created folder {path}."


@tool("write_file",
      "Create or overwrite a text file with content. Asks the user to "
      "confirm first.",
      {"path": {"type": "string", "description": "Path of the file."},
       "content": {"type": "string",
                   "description": "Text to write into the file."}},
      required=["path", "content"])
def write_file(path, content):
    """Create or overwrite a text file with the given content.
    Creating a new file is allowed freely; OVERWRITING an existing one asks
    for confirmation (that's the part that can lose data)."""
    real = resolve(path)
    existed = os.path.exists(real)
    if existed and not confirm(f"overwrite the existing file {path}"):
        return "Cancelled — I left the file untouched."
    with open(real, "w", encoding="utf-8") as f:
        f.write(content)
    return f"{'Overwrote' if existed else 'Wrote'} {path}."


@tool("move_path",
      "Move a file or folder to a new location. Asks the user to confirm "
      "first.",
      {"src": {"type": "string", "description": "Current path."},
       "dst": {"type": "string", "description": "Destination path."}},
      required=["src", "dst"])
def move_path(src, dst):
    """Move a file or folder to a new location."""
    real_src = resolve(src)
    real_dst = resolve(dst)
    if not confirm(f"move {src} to {dst}"):
        return "Cancelled — nothing was moved."
    shutil.move(real_src, real_dst)
    return f"Moved {src} to {dst}."


@tool("rename_path",
      "Rename a file or folder. Asks the user to confirm first.",
      {"path": {"type": "string", "description": "Path to rename."},
       "new_name": {"type": "string", "description": "The new name."}},
      required=["path", "new_name"])
def rename_path(path, new_name):
    """Rename a file or folder (keeps it in the same folder)."""
    real = resolve(path)
    target = resolve(os.path.join(os.path.dirname(real), new_name))
    if not confirm(f"rename {path} to {new_name}"):
        return "Cancelled — nothing was renamed."
    os.rename(real, target)
    return f"Renamed {path} to {new_name}."


@tool("delete_path",
      "Delete a file or a folder and its contents. Asks the user to confirm "
      "first.",
      {"path": {"type": "string", "description": "Path to delete."}},
      required=["path"])
def delete_path(path):
    """Delete a file, or a folder and everything in it."""
    real = resolve(path)
    if real == resolve("."):
        return "I won't delete the whole allowed area — too dangerous."
    if not confirm(f"permanently DELETE {path}"):
        return "Cancelled — nothing was deleted."
    if os.path.isdir(real):
        shutil.rmtree(real)
    else:
        os.remove(real)
    return f"Deleted {path}."


# Friendly name -> the token Windows actually launches with.
_LAUNCH_ALIASES = {
    "calculator": "calc",
    "calc": "calc",
    "notepad": "notepad",
    "paint": "mspaint",
    "explorer": "explorer",
    "file explorer": "explorer",
    "command prompt": "cmd",
    "cmd": "cmd",
    "task manager": "taskmgr",
    "settings": "ms-settings:",
    "terminal": "wt",
}


@tool("launch_app",
      "Launch an application by name, e.g. notepad, calc, chrome.",
      {"name": {"type": "string",
                "description": "Name of the app/executable to launch."}},
      required=["name"])
def launch_app(name):
    """Launch an application by name (e.g. 'notepad', 'calculator', 'chrome')."""
    token = _LAUNCH_ALIASES.get(name.lower().strip(), name)
    result = subprocess.run(["cmd", "/c", "start", "", token],
                            capture_output=True, text=True)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        return f"Couldn't launch {name}. {err}"
    return f"Launching {name}."


@tool("close_app",
      "Close a running application by name, e.g. notepad, calculator, chrome.",
      {"name": {"type": "string",
                "description": "Name of the app to close."}},
      required=["name"])
def close_app(name):
    """Close a running app by name. We SEARCH the running processes for one
    whose image name matches, so 'calculator', 'calc', or 'Calculator' all
    work even though the real process is CalculatorApp.exe."""
    key = name.lower().replace(".exe", "").strip()
    if not key:
        return "Which app should I close?"

    out = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                         capture_output=True, text=True).stdout
    targets = []
    for line in out.splitlines():
        if line.startswith('"'):
            image = line.split('","')[0].strip('"')      # e.g. CalculatorApp.exe
            if key in image.lower() and image not in targets:
                targets.append(image)

    if not targets:
        return f"I don't see {name} running."

    closed = []
    for image in targets:
        r = subprocess.run(["taskkill", "/IM", image, "/F"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            closed.append(image)

    return f"Closed {name}." if closed else f"Couldn't close {name}."
