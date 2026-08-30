"""yamlite — zero-dependency YAML emitter for SZL ledgers.

Emit-only. Handles the subset of YAML the SZL estate uses:
dicts, lists, scalars (str/int/float/bool/None), multiline strings.

ZERO-BANDAID LAW (type level): None renders as the literal string UNKNOWN.
An empty field reads as an oversight; UNKNOWN reads as an audited state.
"""
from __future__ import annotations


def scalar(v) -> str:
    if v is None:
        return "UNKNOWN"  # Zero-Bandaid Law: absence is an audited state, not a blank
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    s = str(v)
    if s == "" :
        return '""'
    if "\n" in s:
        return "|-\n" + "\n".join("    " + line for line in s.splitlines())
    low = s.lower()
    if low in {"true", "false", "null", "yes", "no", "unknown", "~"} or s != s.strip() \
       or any(c in s for c in ":#{}[],&*?|<>=%@`\"'") or s[0].isdigit() or "  " in s:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def _emit(obj, indent: int, out: list[str]) -> None:
    pad = "  " * indent
    if isinstance(obj, dict):
        if not obj:
            out.append(pad + "{}")
            return
        for k, v in obj.items():
            key = scalar(k)
            if isinstance(v, (dict, list)) and v:
                out.append(f"{pad}{key}:")
                _emit(v, indent + 1, out)
            elif isinstance(v, dict):
                out.append(f"{pad}{key}: {{}}")
            elif isinstance(v, list):
                out.append(f"{pad}{key}: []")
            else:
                out.append(f"{pad}{key}: {scalar(v)}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict) and item:
                first = True
                for k, v in item.items():
                    key = scalar(k)
                    if first:
                        if isinstance(v, (dict, list)) and v:
                            out.append(f"{pad}- {key}:")
                            _emit(v, indent + 2, out)
                        elif isinstance(v, dict):
                            out.append(f"{pad}- {key}: {{}}")
                        elif isinstance(v, list):
                            out.append(f"{pad}- {key}: []")
                        else:
                            out.append(f"{pad}- {key}: {scalar(v)}")
                        first = False
                    else:
                        if isinstance(v, (dict, list)) and v:
                            out.append(f"{pad}  {key}:")
                            _emit(v, indent + 2, out)
                        elif isinstance(v, dict):
                            out.append(f"{pad}  {key}: {{}}")
                        elif isinstance(v, list):
                            out.append(f"{pad}  {key}: []")
                        else:
                            out.append(f"{pad}  {key}: {scalar(v)}")
            elif isinstance(item, (dict, list)):
                out.append(pad + "-")
                _emit(item, indent + 1, out)
            else:
                out.append(f"{pad}- {scalar(item)}")
    else:
        out.append(pad + scalar(obj))


def dump(obj) -> str:
    out: list[str] = []
    _emit(obj, 0, out)
    return "\n".join(out) + "\n"
