# bibtms: Bibliography TUI Managment System

A terminal tool to manage papers and books you read using a single TOML file and `vim`. Group your papers into status on reading, planning etc, by genres and easly grep them and edit them in `vim`.

### 1. Setup

1. **Install dependency:**
`pip install tomlkit`
2. **Configure path:**
Create `~/.config/bibtms/config.toml` and add:
```toml
bib_path = "~/path/to/your/bib.toml"
```
3. **Make scripts executable:**
```bash
chmod +x bibtms bibtms.py
```
4. **Add to PATH:**
Add the script folder to your `.bashrc` or `.zshrc`.

---

### 2. Commands

* `bibtms` — Open the whole database in Vim.
* `bibtms --add` — Add a new paper using a blank template.
* `bibtms -fzf` — Search by title and open one paper.
* `bibtms --grep <word>` — Search for a specific status, genre, or keyword.

```
bibtms --help
usage: bibtms.py [-h] [--grep GREP] [--key KEY] [--add]

options:
  -h, --help   show this help message and exit
  --grep GREP  Filter by string
  --key KEY    Open specific key
  --add        Add new template
```

---

### 3. How it Works

* **Editing:** When you run a command, it opens a temporary file in Vim. Change whatever you want and save/exit (`:wq`).
* **Deleting:** Delete the entire `[Key]` block in Vim to remove a paper.
* **Git:** If your bibliography folder is a Git repo, `bibtms` automatically commits and pushes your changes every time you close Vim.

---

### 4. Data Example

```toml
[Bengio2003]
title = "A Neural Probabilistic Language Model"
rating = 9
abstract = "A classic paper that introduced neural word embeddings and the use of feed-forward neural networks for language modeling."
status = "Completed"
read_count = 2
cited_in = ["DeepLearningReview"]
url = "https://www.jmlr.org/papers/volume3/bengio03a/bengio03a.pdf"
genres = ["NLP", "Deep Learning", "Word Embeddings"]
read_time = "90m"
bibtex = """
@article{Bengio2003,
  author = {Bengio, Yoshua and Ducharme, R{\\'e}jean and Vincent, Pascal and Jauvin, Christian},
  title = {A Neural Probabilistic Language Model},
  journal = {Journal of Machine Learning Research},
  volume = {3},
  pages = {1137--1155},
  year = {2003}
}
"""

```

