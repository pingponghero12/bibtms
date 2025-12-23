#!/usr/bin/env python3
import os
import sys
import argparse
import tempfile
import subprocess
from datetime import datetime
from tomlkit import parse, dumps

# --- CONFIG LOADING ---
CONFIG_PATH = os.path.expanduser("~/.config/bibtms/config.toml")
STATUS_ORDER = ["Reading", "Skimmed", "Abstract", "Completed", "Planned"]

def get_db_path():
    if not os.path.exists(CONFIG_PATH):
        print(f"Error: Config not found at {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, "r") as f:
        cfg = parse(f.read())
        path = cfg.get("bib_path", "")
        return os.path.expanduser(path)

DB_FILE = get_db_path()

def load_db():
    if not os.path.exists(DB_FILE):
        return parse("")
    with open(DB_FILE, "r") as f:
        return parse(f.read())

def save_db(data):
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    with open(DB_FILE, "w") as f:
        f.write(dumps(data).strip() + "\n")

def git_sync(file_path):
    """Checks if file is in a git repo and syncs changes if they exist."""
    repo_dir = os.path.dirname(os.path.abspath(file_path))
    file_name = os.path.basename(file_path)
    
    # 1. Check if it's a git repo
    try:
        is_repo = subprocess.run(
            ["git", "-C", repo_dir, "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True
        ).returncode == 0
    except FileNotFoundError:
        return # Git not installed

    if not is_repo:
        return

    # 2. Check for changes specifically in the bib file
    status = subprocess.run(
        ["git", "-C", repo_dir, "status", "--porcelain", file_name],
        capture_output=True, text=True
    ).stdout.strip()

    if status:
        print("\nDetected changes, syncing with Git...")
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        commit_msg = f"Bibliography update {date_str}"
        
        try:
            # Stage, commit, and push
            subprocess.run(["git", "-C", repo_dir, "add", file_name], check=True)
            subprocess.run(["git", "-C", repo_dir, "commit", "-m", commit_msg], check=True)
            
            # Use 'push' only if a remote is configured
            has_remote = subprocess.run(
                ["git", "-C", repo_dir, "remote"], 
                capture_output=True, text=True
            ).stdout.strip()
            
            if has_remote:
                subprocess.run(["git", "-C", repo_dir, "push"], check=True)
                print(f"Successfully pushed: {commit_msg}")
            else:
                print(f"Committed locally: {commit_msg} (No remote found)")
        except subprocess.CalledProcessError as e:
            print(f"Git sync failed: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--open", action="store_true", help="Open raw bib.toml")
    parser.add_argument("--grep", help="Filter by string")
    parser.add_argument("--key", help="Open specific key")
    parser.add_argument("--add", action="store_true", help="Add new template")
    args = parser.parse_args()

    db = load_db()
    to_edit_keys = []

    if args.open:
        subprocess.call([os.environ.get('EDITOR', 'nvim'), DB_FILE])
        git_sync(DB_FILE)
        return

    if args.add:
        to_edit_keys = []
    elif args.key:
        to_edit_keys = [args.key] if args.key in db else []
    elif args.grep:
        q = args.grep.lower()
        to_edit_keys = [
            k for k, v in db.items() 
            if q in k.lower() or q in v.get('title', '').lower() or q in v.get('status', '').lower()
            or any(q in g.lower() for g in v.get('genres', []))
        ]
    else:
        to_edit_keys = list(db.keys())

    # Build buffer
    buffer_str = "# --- BIBTMS EDIT BUFFER ---\n"
    if args.add:
        buffer_str += "# Fill out the template and save.\n\n"
        buffer_str += '[NEW_KEY]\ntitle = ""\nrating = 0\nabstract = ""\nstatus = "Planned"\nread_count = 0\ncited_in = []\nurl = ""\ngenres = []\nread_time = ""\nbibtex = """\n"""\n'
    else:
        buffer_str += "# Save and exit to sync. Delete a [block] to remove.\n\n"
        processed_keys = set()
        for status in STATUS_ORDER:
            papers = [k for k in to_edit_keys if db.get(k, {}).get('status') == status]
            if papers:
                buffer_str += f"# {'='*15} {status.upper()} {'='*15}\n"
                for k in papers:
                    buffer_str += dumps({k: db[k]}).strip() + "\n\n"
                    processed_keys.add(k)

    # Use a temporary file for editing
    with tempfile.NamedTemporaryFile(suffix=".toml", mode="w+", delete=False) as tf:
        tf.write(buffer_str)
        temp_path = tf.name

    # Open editor
    subprocess.call([os.environ.get('EDITOR', 'vim'), temp_path])

    # Read back the data
    with open(temp_path, "r") as f:
        # Ignore lines starting with #
        lines = [line for line in f if not line.strip().startswith("#")]
        content = "".join(lines)
        
        if not content.strip(): 
            os.remove(temp_path)
            return 
            
        try:
            edited_db = parse(content)
        except Exception as e:
            print(f"TOML Error during sync: {e}")
            os.remove(temp_path)
            sys.exit(1)

    # If not in add mode, check for deletions
    if not args.add:
        for k in to_edit_keys:
            if k not in edited_db:
                del db[k]

    # Merge edited data back to master db
    for k, v in edited_db.items():
        if k == "NEW_KEY": continue 
        db[k] = v

    # Save to original TOML file
    save_db(db)
    
    # Clean up temp file
    if os.path.exists(temp_path):
        os.remove(temp_path)

    # Trigger Git logic
    git_sync(DB_FILE)

if __name__ == "__main__":
    main()
