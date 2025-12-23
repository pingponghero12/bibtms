#!/usr/bin/env python3
import os
import sys
import argparse
import tempfile
import subprocess
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--grep", help="Filter by string")
    parser.add_argument("--key", help="Open specific key")
    parser.add_argument("--add", action="store_true", help="Add new template")
    args = parser.parse_args()

    db = load_db()
    to_edit_keys = []
    
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
                    entry_toml = dumps({k: db[k]}).strip()
                    buffer_str += entry_toml + "\n\n"
                    processed_keys.add(k)

    with tempfile.NamedTemporaryFile(suffix=".toml", mode="w+", delete=False) as tf:
        tf.write(buffer_str)
        temp_path = tf.name

    subprocess.call([os.environ.get('EDITOR', 'vim'), temp_path])

    with open(temp_path, "r") as f:
        content = "".join([line for line in f if not line.strip().startswith("#")])
        if not content.strip(): 
            os.remove(temp_path)
            return 
        try:
            edited_db = parse(content)
        except Exception as e:
            print(f"TOML Error: {e}")
            sys.exit(1)

    if not args.add:
        for k in to_edit_keys:
            if k not in edited_db:
                del db[k]

    for k, v in edited_db.items():
        if k == "NEW_KEY": continue 
        db[k] = v

    save_db(db)
    os.remove(temp_path)

if __name__ == "__main__":
    main()
