import argparse
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT_EXT = r"(?:py|sh|mjs)"
SKILLS_PATH = re.compile(r"(?:\$\{?SKILLS\}?/|(?<![\w/.$-])(?:skills/)?)([A-Za-z][\w.-]*)/scripts/([\w.-]+\." + SCRIPT_EXT + r")\b")
RELATIVE_PATH = re.compile(r"(?<![\w/$}.-])((?:\.\./)*|\$\{?\w+\}?/)scripts/([\w.-]+\." + SCRIPT_EXT + r")\b")
BARE_NAME = re.compile(r"(?<![\w/$}.-])([\w-]+\." + SCRIPT_EXT + r")\b")
FENCE = re.compile(r"^\s*(```+|~~~+)\s*([\w+-]*)")
SHELL_LANGS = {"", "bash", "sh", "shell", "console", "zsh"}
FLAG = re.compile(r"^(--[A-Za-z0-9][\w-]*)")
INLINE = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")


def low_priority():
    prefix = []
    if shutil.which("nice"):
        prefix += ["nice", "-n", "19"]
    if shutil.which("ionice"):
        prefix += ["ionice", "-c", "3"]
    return prefix


def doc_files(root):
    names = {"SKILL.md", "README.md", "PREVIEW.md"}
    found = []
    for path in sorted(root.rglob("*.md")):
        if "node_modules" in path.parts or any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        if path.name in names or path.parent.name == "references":
            found.append(path)
    return found


def skill_root(doc, skills):
    try:
        rel = doc.relative_to(skills)
    except ValueError:
        return None
    return skills / rel.parts[0] if len(rel.parts) > 1 else None


def resolve(match, doc, skills, pattern):
    if pattern is BARE_NAME:
        base = skill_root(doc, skills)
        candidate = base / "scripts" / match.group(1) if base else None
        return candidate if candidate is not None and candidate.is_file() else None
    if pattern is SKILLS_PATH:
        explicit = match.group(0).startswith(("$", "skills/"))
        if not explicit and not (skills / match.group(1)).is_dir():
            return None
        return skills / match.group(1) / "scripts" / match.group(2)
    prefix, name = match.group(1), match.group(2)
    if prefix.startswith("$"):
        base = skill_root(doc, skills)
        return base / "scripts" / name if base else None
    candidates = [(doc.parent / prefix / "scripts" / name).resolve()]
    base = skill_root(doc, skills)
    if base:
        candidates += [(folder / prefix / "scripts" / name).resolve() for folder in [base, *sorted(d for d in base.iterdir() if d.is_dir())]]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def script_refs(text, doc, skills):
    refs = []
    for pattern in (SKILLS_PATH, RELATIVE_PATH, BARE_NAME):
        for match in pattern.finditer(text):
            path = resolve(match, doc, skills, pattern)
            if path is not None:
                refs.append((match.start(), match.end(), path))
    refs.sort(key=lambda r: r[0])
    kept = []
    for ref in refs:
        if kept and ref[0] < kept[-1][1]:
            continue
        kept.append(ref)
    return kept


class HelpCache:
    def __init__(self, python):
        self.python = python
        self.cache = {}

    def text(self, script, sub=None):
        return self.run(script, sub)[0]

    def error(self, script, sub=None):
        return self.run(script, sub)[1]

    def run(self, script, sub=None):
        key = (script, sub)
        if key not in self.cache:
            if script.suffix == ".py":
                command = [self.python, "-I", "-B", str(script)]
            elif script.suffix == ".sh":
                command = ["bash", str(script)]
            else:
                self.cache[key] = (None, None)
                return self.cache[key]
            command += ([sub] if sub else []) + ["--help"]
            try:
                done = subprocess.run(low_priority() + command, capture_output=True, text=True, timeout=120, cwd=script.parent)
            except subprocess.TimeoutExpired:
                self.cache[key] = (None, "--help timed out after 120 s")
                return self.cache[key]
            output = done.stdout + done.stderr
            if done.returncode != 0 or "usage" not in output.lower():
                last = next((line.strip() for line in reversed(output.splitlines()) if line.strip()), f"exit {done.returncode}, no output")
                self.cache[key] = (None, f"exit {done.returncode}: {last}")
            else:
                self.cache[key] = (output, None)
        return self.cache[key]


def has_flag(help_text, flag):
    return re.search(r"(?<![\w-])" + re.escape(flag) + r"(?![\w-])", help_text) is not None


def subcommands(help_text):
    match = re.search(r"\{([\w,-]+)\}", help_text or "")
    return set(match.group(1).split(",")) if match else set()


def commands(lines):
    in_fence, lang, buffer, start = False, "", "", 0
    for number, line in enumerate(lines, 1):
        fence = FENCE.match(line)
        if fence:
            in_fence, lang = (not in_fence, fence.group(2).lower()) if not in_fence else (False, "")
            continue
        if in_fence:
            if lang not in SHELL_LANGS:
                continue
            stripped = line.strip()
            if not buffer:
                start = number
            buffer += " " + stripped.rstrip("\\")
            if stripped.endswith("\\"):
                continue
            yield start, buffer.strip()
            buffer = ""
        else:
            for span in INLINE.finditer(line):
                yield number, span.group(1)


def segments(command):
    for part in re.split(r"\s*(?:\|\||&&|\||;)\s*", command):
        part = re.sub(r"(^|\s)#\s.*$", "", part)
        if part.strip():
            yield part


def lint(root, skills, python, check_links):
    helps = HelpCache(python)
    misses = []
    reported = set()
    for doc in doc_files(root):
        rel_doc = doc.relative_to(root)
        lines = doc.read_text().splitlines()
        for number, line in enumerate(lines, 1):
            for _, _, path in script_refs(line, doc, skills):
                if "<" in str(path) or "*" in str(path):
                    continue
                if not path.exists():
                    misses.append((f"{rel_doc}:{number}", "missing", path.relative_to(root) if path.is_relative_to(root) else path))
            if check_links:
                for link in LINK.findall(line):
                    if re.match(r"^[a-z]+:", link) or "<" in link:
                        continue
                    target = (doc.parent / link).resolve()
                    if not target.exists():
                        misses.append((f"{rel_doc}:{number}", "missing-link", link))
        for number, command in commands(lines):
            for part in segments(command):
                refs = script_refs(part, doc, skills)
                if not refs:
                    continue
                start, end, script = refs[0]
                if not script.exists() or script.suffix not in (".py", ".sh"):
                    continue
                try:
                    tokens = shlex.split(part[end:], posix=True)
                except ValueError:
                    tokens = part[end:].split()
                if not any(FLAG.match(token) for token in tokens):
                    continue
                sub = None
                top = helps.text(script)
                choices = subcommands(top)
                if tokens and not tokens[0].startswith("-") and tokens[0] in choices:
                    sub = tokens[0]
                help_text = helps.text(script, sub) if sub else top
                name = f"{script.relative_to(skills)}" + (f" {sub}" if sub else "")
                if help_text is None:
                    failure = helps.error(script, sub)
                    if failure and name not in reported:
                        reported.add(name)
                        misses.append((f"{rel_doc}:{number}", "help-failed", f"{name}: {failure}"))
                    continue
                for token in tokens:
                    flag = FLAG.match(token)
                    if flag and not has_flag(help_text, flag.group(1)):
                        misses.append((f"{rel_doc}:{number}", flag.group(1), name))
    return misses


def default_python(root):
    venv = root / ".venv" / "bin" / "python"
    return str(venv) if venv.is_file() else sys.executable


def main():
    parser = argparse.ArgumentParser(
        description="Check the docs against the code: every $SKILLS/<skill>/scripts/<file> and scripts/<file> path in SKILL.md, README.md, "
                    "PREVIEW.md and references/*.md must exist, and every --flag passed to a script in a fenced shell block or an inline "
                    "code span must appear in that script's --help (python -I or bash, run once per script under nice). "
                    "A bare <name>.py in a skill's own docs resolves to that skill's scripts folder. "
                    "Prints 'file:line flag script' per miss, and 'file:line help-failed script: reason' once per script whose --help "
                    "exits nonzero or prints no usage (usually a missing dependency: run it with the repo's venv interpreter). Exits 1 on any.")
    parser.add_argument("--root", default=str(REPO), help="repo root (default: the repo this script lives in)")
    parser.add_argument("--python", help="interpreter for the --help calls, with the repo's requirements installed (default: <root>/.venv/bin/python when it exists, else this one)")
    parser.add_argument("--links", action="store_true", help="also check relative markdown links")
    parser.add_argument("--only", help="comma list of path prefixes (relative to --root) to report on, e.g. skills/reel-director,README.md")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    skills = root / "skills"
    misses = lint(root, skills, args.python or default_python(root), args.links)
    if args.only:
        prefixes = [p.strip() for p in args.only.split(",") if p.strip()]
        misses = [m for m in misses if any(m[0].startswith(p) for p in prefixes)]
    for where, what, script in misses:
        print(f"{where} {what} {script}")
    print(f"{len(misses)} misses in {len(doc_files(root))} docs", file=sys.stderr)
    sys.exit(1 if misses else 0)


if __name__ == "__main__":
    main()
