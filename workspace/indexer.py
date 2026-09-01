"""
Codebase indexer: extracts symbols and relationships from project files.

Python files are parsed with the stdlib `ast` module (modules, classes,
functions, imports, base classes). JavaScript/TypeScript, HTML, CSS and JSON
are handled with lightweight regex heuristics (imports, functions, routes,
ids/classes, top-level keys).

The index is cached at <workspace>/.jarvis_index.json and refreshed
incrementally: only files whose mtime or size changed are re-parsed, so
repeated queries on large projects stay fast.
"""

import ast
import json
import re
from pathlib import Path

from workspace.scanner import scan_tree, is_secret_path, classify_file

INDEX_FILE_NAME = ".jarvis_index.json"

# ---------------------------------------------------------------------------
# Python (stdlib ast)
# ---------------------------------------------------------------------------

def _index_python(path: Path) -> dict:
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
    except (SyntaxError, ValueError, OSError) as e:
        return {"language": "python", "error": f"parse error: {e}",
                "symbols": [], "imports": []}

    symbols = []
    imports = []

    def walk(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{child.name}"
                args = [a.arg for a in child.args.args]
                symbols.append({
                    "kind": "function", "name": name,
                    "line": child.lineno, "args": args,
                })
                walk(child, prefix="")
            elif isinstance(child, ast.ClassDef):
                name = f"{prefix}{child.name}"
                bases = []
                for b in child.bases:
                    if isinstance(b, ast.Name):
                        bases.append(b.id)
                    elif isinstance(b, ast.Attribute):
                        bases.append(b.attr)
                symbols.append({
                    "kind": "class", "name": name,
                    "line": child.lineno, "bases": bases,
                })
                walk(child, prefix=name + ".")
            elif isinstance(child, ast.Import):
                for alias in child.names:
                    imports.append(alias.name)
            elif isinstance(child, ast.ImportFrom):
                module = child.module or ""
                for alias in child.names:
                    imports.append(f"{module}.{alias.name}" if module else alias.name)

    walk(tree)
    return {"language": "python", "symbols": symbols, "imports": imports}


# ---------------------------------------------------------------------------
# JavaScript / TypeScript (regex heuristics)
# ---------------------------------------------------------------------------

_JS_IMPORT = re.compile(
    r"""(?:import\s+[^'"]*?from\s*['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\))""",
    re.MULTILINE,
)
_JS_FUNCTION = re.compile(
    r"""(?:function\s+([A-Za-z_$][\w$]*)\s*\(|"""
    r"""(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>|"""
    r"""(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*async\s+function)""",
)
_JS_CLASS = re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)")
_JS_ROUTE = re.compile(
    r"""@?(?:app|router|server)\.(?:get|post|put|patch|delete|use)\(\s*['"]([^'"]+)['"]""",
)


def _index_js(path: Path, language: str) -> dict:
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        return {"language": language, "error": str(e), "symbols": [], "imports": []}

    symbols = []
    for m in _JS_FUNCTION.finditer(source):
        name = m.group(1) or m.group(2) or m.group(3)
        if name:
            line = source[: m.start()].count("\n") + 1
            symbols.append({"kind": "function", "name": name, "line": line})
    for m in _JS_CLASS.finditer(source):
        line = source[: m.start()].count("\n") + 1
        symbols.append({"kind": "class", "name": m.group(1), "line": line})
    for m in _JS_ROUTE.finditer(source):
        line = source[: m.start()].count("\n") + 1
        symbols.append({"kind": "route", "name": m.group(1), "line": line})

    imports = []
    for m in _JS_IMPORT.finditer(source):
        imports.append(m.group(1) or m.group(2))

    return {"language": language, "symbols": symbols, "imports": imports}


# ---------------------------------------------------------------------------
# HTML / CSS / JSON (light heuristics)
# ---------------------------------------------------------------------------

_HTML_ID = re.compile(r"""\bid\s*=\s*["']([\w\-]+)["']""")
_CSS_SELECTOR = re.compile(r"""([.#][A-Za-z][\w\-]*)\s*\{""")
_JSON_KEY = re.compile(r"""^\s{0,8}"([\w\-]+)"\s*:""", re.MULTILINE)


def _index_html(path: Path) -> dict:
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        return {"language": "html", "error": str(e), "symbols": [], "imports": []}

    symbols = [{"kind": "id", "name": m.group(1),
                "line": source[: m.start()].count("\n") + 1}
               for m in _HTML_ID.finditer(source)]
    # linked scripts/styles = dependencies
    imports = re.findall(r"""(?:src|href)\s*=\s*["']([^"']+\.(?:js|css))["']""", source)
    return {"language": "html", "symbols": symbols[:80], "imports": imports[:60]}


def _index_css(path: Path) -> dict:
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        return {"language": "css", "error": str(e), "symbols": [], "imports": []}
    symbols = [{"kind": "selector", "name": m.group(1),
                "line": source[: m.start()].count("\n") + 1}
               for m in _CSS_SELECTOR.finditer(source)]
    return {"language": "css", "symbols": symbols[:150], "imports": []}


def _index_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, json.JSONDecodeError) as e:
        return {"language": "json", "error": str(e), "symbols": [], "imports": []}

    symbols = []
    if isinstance(data, dict):
        for key, value in list(data.items())[:60]:
            kind = "dependency" if key in ("dependencies", "devDependencies") else "key"
            detail = list(value.keys())[:15] if isinstance(value, dict) else None
            symbols.append({"kind": kind, "name": key, "detail": detail})
    return {"language": "json", "symbols": symbols, "imports": []}


# ---------------------------------------------------------------------------
# Index management
# ---------------------------------------------------------------------------

class ProjectIndex:
    """Incremental, cached symbol index for a workspace."""

    def __init__(self, workspace: str):
        self.workspace = str(Path(workspace).resolve())
        self.cache_path = Path(self.workspace) / INDEX_FILE_NAME
        self._data = {"files": {}, "version": 1}
        self._load_cache()

    # -- cache ---------------------------------------------------------------

    def _load_cache(self):
        if self.cache_path.is_file():
            try:
                data = json.loads(self.cache_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("version") == 1:
                    self._data = data
            except (OSError, json.JSONDecodeError):
                pass  # corrupt cache: rebuild from scratch

    def _save_cache(self):
        try:
            self.cache_path.write_text(
                json.dumps(self._data), encoding="utf-8"
            )
        except OSError:
            pass  # cache is best-effort; never break a query over it

    # -- indexing ------------------------------------------------------------

    def refresh(self, force: bool = False) -> dict:
        """
        Re-indexes changed files (mtime/size based). Returns stats:
        {"indexed": n_changed, "total": n_files, "cached": bool}
        """
        entries = scan_tree(self.workspace)
        changed = 0
        seen = set()

        for entry in entries:
            rel = entry["path"]
            seen.add(rel)
            full = Path(self.workspace) / rel
            info = classify_file(full)
            if not info["is_text"] or info["size"] == 0:
                continue

            prev = self._data["files"].get(rel)
            stat_sig = [entry["size"], int(full.stat().st_mtime)]
            if not force and prev and prev.get("sig") == stat_sig:
                continue  # unchanged

            changed += 1
            lang = info["language"]
            if lang == "python":
                parsed = _index_python(full)
            elif lang in ("javascript", "typescript"):
                parsed = _index_js(full, lang)
            elif lang == "html":
                parsed = _index_html(full)
            elif lang == "css":
                parsed = _index_css(full)
            elif lang == "json":
                parsed = _index_json(full)
            else:
                parsed = {"language": lang, "symbols": [], "imports": []}

            parsed["sig"] = stat_sig
            self._data["files"][rel] = parsed

        # drop files that no longer exist
        for rel in list(self._data["files"].keys()):
            if rel not in seen:
                del self._data["files"][rel]

        if changed:
            self._save_cache()
        return {"indexed": changed, "total": len(self._data["files"]),
                "cached": changed == 0}

    # -- queries ---------------------------------------------------------------

    def file_list(self) -> list[str]:
        return sorted(self._data["files"].keys())

    def file_info(self, rel_path: str) -> dict | None:
        return self._data["files"].get(rel_path)

    def search_symbols(self, query: str, limit: int = 25) -> list[dict]:
        """Finds symbols whose name contains the query (case-insensitive)."""
        q = query.lower()
        hits = []
        for rel, info in sorted(self._data["files"].items()):
            for sym in info.get("symbols", []):
                if q in sym["name"].lower():
                    hits.append({"file": rel, **sym})
                    if len(hits) >= limit:
                        return hits
        return hits

    def search_text(self, query: str, limit: int = 30, context_chars: int = 80) -> list[dict]:
        """
        Literal text search across indexed text files.
        Returns [{"file", "line", "excerpt"}] with secrets redacted by caller.
        """
        q = query.lower()
        hits = []
        for rel in sorted(self._data["files"].keys()):
            full = Path(self.workspace) / rel
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as f:
                    for lineno, line in enumerate(f, 1):
                        if q in line.lower():
                            excerpt = line.strip()[:context_chars * 2]
                            hits.append({"file": rel, "line": lineno,
                                         "excerpt": excerpt})
                            if len(hits) >= limit:
                                return hits
            except OSError:
                continue
        return hits

    def import_graph(self, limit_files: int = 40) -> list[dict]:
        """
        Internal import/require relationships as edges:
        [{"from": file, "to": module_or_file}] for Mermaid diagrams.
        """
        edges = []
        file_stems = {}
        for rel in self._data["files"]:
            p = Path(rel)
            file_stems[p.stem] = rel

        for rel, info in list(self._data["files"].items())[:limit_files]:
            for imp in info.get("imports", [])[:20]:
                target = None
                # python: match module path to file
                mod = imp.replace(".", "/")
                for cand in (f"{mod}.py", f"{mod}/__init__.py"):
                    if cand in self._data["files"]:
                        target = cand
                        break
                if target is None:
                    # js: match by stem
                    stem = Path(imp.replace("./", "").replace("../", "")).stem
                    if stem and stem in file_stems:
                        target = file_stems[stem]
                if target and target != rel:
                    edges.append({"from": rel, "to": target, "raw": imp})
        return edges

    def project_summary(self) -> dict:
        """High-level stats used for the workspace brief in the system prompt."""
        langs = {}
        symbol_count = 0
        for info in self._data["files"].values():
            lang = info.get("language") or "other"
            langs[lang] = langs.get(lang, 0) + 1
            symbol_count += len(info.get("symbols", []))
        return {
            "root": self.workspace,
            "files": len(self._data["files"]),
            "languages": dict(sorted(langs.items(), key=lambda kv: -kv[1])),
            "symbols": symbol_count,
        }