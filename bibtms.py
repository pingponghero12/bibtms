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
    repo_dir = os.path.dirname(os.path.abspath(file_path))
    file_name = os.path.basename(file_path)
    try:
        is_repo = subprocess.run(
            ["git", "-C", repo_dir, "rev-parse", "--is-inside-work-tree"],
            capture_output=True
        ).returncode == 0
        if not is_repo: return

        status = subprocess.run(
            ["git", "-C", repo_dir, "status", "--porcelain", file_name],
            capture_output=True, text=True
        ).stdout.strip()

        if status:
            print("\nDetected changes, syncing with Git...")
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            commit_msg = f"Bibliography update {date_str}"
            subprocess.run(["git", "-C", repo_dir, "add", file_name], check=True)
            subprocess.run(["git", "-C", repo_dir, "commit", "-m", commit_msg], check=True)
            
            has_remote = subprocess.run(
                ["git", "-C", repo_dir, "remote"], 
                capture_output=True, text=True
            ).stdout.strip()
            
            if has_remote:
                subprocess.run(["git", "-C", repo_dir, "push"], check=True)
    except Exception as e:
        print(f"Git sync failed: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--open", action="store_true", help="Open raw bib.toml")
    parser.add_argument("--genres", action="store_true", help="Browse by genres (Read-Only)")
    parser.add_argument("--list-genres", action="store_true", help="Print unique genres")
    parser.add_argument("--grep", help="Filter by string")
    parser.add_argument("--key", help="Open specific key")
    parser.add_argument("--add", action="store_true", help="Add new template")
    args = parser.parse_args()

    db = load_db()

    # --- 1. CLI UTILITIES ---
    if args.list_genres:
        all_genres = set()
        for entry in db.values():
            all_genres.update(entry.get('genres', []))
        for g in sorted(all_genres):
            print(g)
        return

    # --- 2. RAW OPEN MODE ---
    if args.open:
        subprocess.call([os.environ.get('EDITOR', 'nvim'), DB_FILE])
        git_sync(DB_FILE)
        return

    # --- 3. SELECTION LOGIC ---
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

    # --- 4. BUFFER BUILDING ---
    buffer_str = "# --- BIBTMS EDIT BUFFER ---\n"
    
    if args.add:
        buffer_str += "# Fill out the template and save.\n\n"
        buffer_str += '[NEW_KEY]\ntitle = ""\nrating = 0\nabstract = ""\nstatus = "Planned"\ngenres = []\nbibtex = """\n"""\n'
    
    elif args.genres:
        buffer_str += "# === GENRE BROWSE MODE (READ-ONLY) ===\n"
        buffer_str += "# Papers are duplicated under each genre. Changes will NOT be saved.\n\n"
        
        unique_genres = sorted({g for k in to_edit_keys for g in db.get(k, {}).get('genres', [])})
        for g in unique_genres:
            papers_in_genre = [k for k in to_edit_keys if g in db.get(k, {}).get('genres', [])]
            if papers_in_genre:
                buffer_str += f"# {'='*15} {g.upper()} {'='*15}\n"
                for k in sorted(papers_in_genre):
                    buffer_str += dumps({k: db[k]}).strip() + "\n\n"
        
        no_genres = [k for k in to_edit_keys if not db.get(k, {}).get('genres', [])]
        if no_genres:
            buffer_str += f"# {'='*15} UNTAGGED {'='*15}\n"
            for k in sorted(no_genres):
                buffer_str += dumps({k: db[k]}).strip() + "\n\n"

    else:
        buffer_str += "# Save and exit to sync. Delete a [block] to remove.\n\n"
        for status in STATUS_ORDER:
            papers = [k for k in to_edit_keys if db.get(k, {}).get('status') == status]
            if papers:
                buffer_str += f"# {'='*15} {status.upper()} {'='*15}\n"
                for k in sorted(papers):
                    buffer_str += dumps({k: db[k]}).strip() + "\n\n"

    # --- 5. EDITOR SESSION ---
    with tempfile.NamedTemporaryFile(suffix=".toml", mode="w+", delete=False) as tf:
        tf.write(buffer_str)
        temp_path = tf.name

    subprocess.call([os.environ.get('EDITOR', 'nvim'), temp_path])

    # --- 6. SYNC BACK LOGIC ---
    if args.genres:
        print("Exited Genre View (Read-Only).")
        os.remove(temp_path)
        return

    with open(temp_path, "r") as f:
        lines = [line for line in f if not line.strip().startswith("#")]
        content = "".join(lines)
        
        if not content.strip(): 
            os.remove(temp_path)
            return 
            
        try:
            edited_db = parse(content)
            if not args.add:
                for k in to_edit_keys:
                    if k not in edited_db: del db[k]

            for k, v in edited_db.items():
                if k != "NEW_KEY": db[k] = v
            
            save_db(db)
        except Exception as e:
            print(f"TOML Error: {e}. Changes NOT saved.")
            os.remove(temp_path)
            sys.exit(1)

    os.remove(temp_path)
    git_sync(DB_FILE)

if __name__ == "__main__":
    main()
