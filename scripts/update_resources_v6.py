"""
v6: Handle multi-line imports, mixed module-level, and all-module-level by
    moving module-level declarations that use resource text into the component.
"""

import os
import re

DOMAIN_TO_HOOK = {
    "trips": "useTripsResources",
    "admin": "useAdminResources",
    "vehicles": "useVehiclesResources",
    "drivers": "useDriversResources",
    "fuel": "useFuelResources",
    "fleet": "useFleetResources",
    "locations": "useLocationsResources",
    "trailers": "useTrailersResources",
    "coaching": "useCoachingResources",
    "executive": "useExecutiveResources",
    "shared": "useSharedResources",
    "today": "useTodayResources",
    "reports": "useReportsResources",
    "reports-studio": "useReportsStudioResources",
    "routeLab": "useRouteLabResources",
    "tripPlanner": "useTripPlannerResources",
    "investigations": "useInvestigationsResources",
    "maintenancePredictions": "useMaintenancePredictionsResources",
}

# Matches single-line: import { ... } from "...resources/tr/domain";
SINGLE_LINE_TR = re.compile(
    r'^(import\s+\{[^}\n]+\}\s+from\s+["\']([^"\']*resources/tr/([^"\']+?))["\'];?)\s*$',
    re.MULTILINE,
)

# Matches multi-line: import {\n  ...\n} from "...resources/tr/domain";
MULTI_LINE_TR = re.compile(
    r'^(import\s+\{[^}]*\}\s+from\s+["\']([^"\']*resources/tr/([^"\']+?))["\'];?)\s*$',
    re.MULTILINE | re.DOTALL,
)


def find_all_tr_imports(content):
    """Find all TR import matches (single and multi-line), return sorted by start."""
    seen = set()
    matches = []
    for pat in (SINGLE_LINE_TR, MULTI_LINE_TR):
        for m in pat.finditer(content):
            if m.start() not in seen:
                seen.add(m.start())
                matches.append(m)
    matches.sort(key=lambda x: x.start())
    return matches


def compute_hook_import_path(existing_import_path):
    if existing_import_path.startswith("@/"):
        return "@/resources/useResources"
    parts = existing_import_path.split("/")
    try:
        tr_idx = parts.index("tr")
        base = "/".join(parts[:tr_idx])
        return base + "/useResources"
    except ValueError:
        return "../../resources/useResources"


def parse_imported_names(import_text):
    m = re.search(r"\{([^}]+)\}", import_text, re.DOTALL)
    if not m:
        return []
    return [n.strip() for n in re.split(r"[,\n]", m.group(1)) if n.strip()]


def find_end_of_imports(content):
    """Return character position of the end of the last import statement."""
    lines = content.split("\n")
    in_import = False
    last_end_line = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not in_import:
            if stripped.startswith("import "):
                if "}" in stripped or "{" not in stripped:
                    last_end_line = i
                else:
                    in_import = True
                    last_end_line = i
        else:
            last_end_line = i
            if "} from" in stripped or stripped.endswith(";"):
                in_import = False
    if last_end_line < 0:
        return 0
    pos = sum(len(lines[i]) + 1 for i in range(last_end_line + 1))
    return pos - 1


def skip_string(content, pos):
    """Skip a string starting at pos (', ", `) and return end position."""
    q = content[pos]
    i = pos + 1
    while i < len(content):
        c = content[i]
        if c == "\\":
            i += 2
            continue
        if q == "`" and c == "$" and i + 1 < len(content) and content[i + 1] == "{":
            # Template literal expression - skip it
            depth = 1
            i += 2
            while i < len(content) and depth > 0:
                if content[i] == "{":
                    depth += 1
                elif content[i] == "}":
                    depth -= 1
                elif content[i] in ('"', "'", "`"):
                    i = skip_string(content, i) - 1
                i += 1
            continue
        if c == q:
            return i + 1
        i += 1
    return i


def find_top_level_declarations_using(content, names):
    """
    Find all top-level (brace depth 0) non-import declarations that reference
    any of the given names. Returns list of (start, end) char ranges.
    """
    if not names:
        return []

    name_re = re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")\b")
    results = []
    i = 0
    n = len(content)
    depth = 0
    in_import = False
    decl_start = -1
    in_block_comment = False

    def char_at(pos):
        return content[pos] if pos < n else ""

    while i < n:
        c = content[i]

        # Skip line comments
        if c == "/" and char_at(i + 1) == "/" and not in_block_comment:
            while i < n and content[i] != "\n":
                i += 1
            continue

        # Skip block comments
        if c == "/" and char_at(i + 1) == "*" and not in_block_comment:
            in_block_comment = True
            i += 2
            continue
        if in_block_comment:
            if c == "*" and char_at(i + 1) == "/":
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue

        # Skip strings
        if c in ('"', "'", "`"):
            i = skip_string(content, i)
            continue

        # Track import blocks (depth 0)
        if depth == 0:
            if content[i : i + 7] == "import " and not in_import:
                # Check if it's a multi-line import
                in_import = True

        if c == "{" or c == "[" or c == "(":
            depth += 1
        elif c == "}" or c == "]" or c == ")":
            depth -= 1
            if depth == 0 and in_import:
                # Skip rest of import line
                while i < n and content[i] != "\n":
                    i += 1
                in_import = False
                i += 1
                continue
            if depth < 0:
                depth = 0

        # At top level: detect declaration starts
        if depth == 0 and not in_import and decl_start == -1:
            # Look for const/function/let/var declarations
            if re.match(r"(const|function|let|var)\s", content[i : i + 10]):
                decl_start = i

        # At top level after a declaration: detect its end
        if depth == 0 and decl_start != -1 and i > decl_start:
            # Declaration ends at ; or at closing } if it's a function
            if c == ";":
                decl_text = content[decl_start : i + 1]
                if name_re.search(decl_text):
                    results.append((decl_start, i + 1))
                decl_start = -1
            elif c == "\n" and depth == 0:
                # Check if previous non-blank line ended the declaration
                # This handles function declarations
                snippet = content[decl_start:i]
                if snippet.count("{") == snippet.count("}") and "{" in snippet:
                    decl_text = snippet
                    if name_re.search(decl_text):
                        results.append((decl_start, i))
                    decl_start = -1

        i += 1

    return results


def find_first_component_and_body_start(content):
    """Find (start_of_decl, start_of_body) for the first exported component/hook."""
    candidates = []

    # 1. export function / export default function / export async function
    for m in re.finditer(
        r"export\s+(?:default\s+)?(?:async\s+)?function\s+\w*\s*\(", content
    ):
        i = m.end() - 1
        depth = 0
        j = i
        while j < len(content):
            if content[j] == "(":
                depth += 1
            elif content[j] == ")":
                depth -= 1
                if depth == 0:
                    rest = content[j + 1 :]
                    bm = re.search(r"(?::\s*[^\n{]+)?\s*\{", rest)
                    if bm:
                        body_start = j + 1 + bm.end()
                        if body_start < len(content) and content[body_start] == "\n":
                            body_start += 1
                        candidates.append((m.start(), body_start))
                    break
            j += 1

    # 2. export const X = ... (React.FC, React.memo, or plain arrow)
    for m in re.finditer(
        r"export\s+const\s+\w+\s*(?::\s*[\w.]+(?:<[^>]*>)?)?\s*=\s*(?:React\.memo\s*\(\s*)?",
        content,
    ):
        search_from = m.end()
        am = re.search(r"\)\s*=>\s*\{", content[search_from : search_from + 5000])
        if am:
            body_start = search_from + am.end()
            if body_start < len(content) and content[body_start] == "\n":
                body_start += 1
            candidates.append((m.start(), body_start))

    if not candidates:
        return -1, -1
    candidates.sort(key=lambda x: x[0])
    return candidates[0]


def handle_arrow_no_braces(content, hook_calls):
    """
    For components like: export const X: T = ({ ... }) => (
    Convert to use braces and insert hook calls.
    Returns modified content or original if pattern not found.
    """
    # Pattern: `) => (` at the top level after an export const
    pattern = re.compile(
        r"(export\s+const\s+\w+[^=]*=\s*(?:React\.memo\s*\(\s*)?)\(((?:[^)(]|\([^)]*\))*)\)\s*=>\s*\("
    )
    m = pattern.search(content)
    if not m:
        return content, False

    # Find matching closing paren for the `=> (` part
    paren_start = m.end() - 1  # position of `(`
    depth = 0
    i = paren_start
    while i < len(content):
        if content[i] == "(":
            depth += 1
        elif content[i] == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    # content[paren_start:i+1] is the JSX wrapped in parens
    jsx_content = content[paren_start + 1 : i]  # without outer parens
    # Find trailing ); or )
    after = content[i + 1 :].lstrip()
    semi = ";" if after.startswith(";") else ""

    # Build replacement
    params = m.group(2)
    new_component = (
        m.group(1)
        + "("
        + params
        + ") => {\n"
        + hook_calls
        + "\n"
        + "  return (\n"
        + jsx_content
        + "\n  );\n}"
        + semi
    )
    new_content = content[: m.start()] + new_component + content[i + 1 + len(semi) :]
    return new_content, True


def process_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    matches = find_all_tr_imports(content)
    if not matches:
        return False

    domain_to_names = {}
    domain_to_path = {}
    valid_matches = []

    for m in matches:
        import_text = m.group(1)
        import_path = m.group(2)
        domain = m.group(3).strip()
        if domain.endswith(".ts"):
            domain = domain[:-3]
        hook = DOMAIN_TO_HOOK.get(domain)
        if not hook:
            continue
        names = parse_imported_names(import_text)
        if domain not in domain_to_names:
            domain_to_names[domain] = []
            domain_to_path[domain] = import_path
        domain_to_names[domain].extend(names)
        valid_matches.append(m)

    if not valid_matches:
        return False

    # Step 1: Build content without TR imports to detect module-level usage
    content_no_tr = content
    for m in sorted(valid_matches, key=lambda x: x.start(), reverse=True):
        s, e = m.start(), m.end()
        # Remove the import line including trailing newline
        if e < len(content_no_tr) and content_no_tr[e] == "\n":
            e += 1
        content_no_tr = content_no_tr[:s] + content_no_tr[e:]

    # Step 2: Find first component start (in original content with imports removed)
    comp_start, body_start = find_first_component_and_body_start(content_no_tr)

    # Step 3: For each domain, separate module-level vs component-level names
    all_names_flat = []
    for names in domain_to_names.values():
        all_names_flat.extend(names)
    all_names_unique = list(dict.fromkeys(all_names_flat))

    pre_component = content_no_tr[:comp_start] if comp_start > 0 else ""
    module_level_names = set()
    for name in all_names_unique:
        if re.search(r"\b" + re.escape(name) + r"\b", pre_component):
            module_level_names.add(name)

    # Step 4: Find module-level declarations using those names
    module_decls = []
    if module_level_names and comp_start > 0:
        module_decls = find_top_level_declarations_using(
            content_no_tr[:comp_start], list(module_level_names)
        )

    # Step 5: All names will be handled by the hook
    # For module-level ones, we'll move their declarations inside the component
    hooks_needed = []
    hook_destructures = []
    for domain, names in domain_to_names.items():
        hook = DOMAIN_TO_HOOK[domain]
        if hook not in hooks_needed:
            hooks_needed.append(hook)
        unique_names = list(dict.fromkeys(names))
        hook_destructures.append(f"  const {{ {', '.join(unique_names)} }} = {hook}();")

    if not hooks_needed:
        return False

    first_import_path = list(domain_to_path.values())[0]
    hook_import_path = compute_hook_import_path(first_import_path)
    hook_import_line = (
        f'import {{ {", ".join(hooks_needed)} }} from "{hook_import_path}";'
    )
    hook_calls_str = "\n".join(hook_destructures)

    # Step 6: Build new content
    new_content = content

    # Remove all TR imports (reverse order)
    for m in sorted(valid_matches, key=lambda x: x.start(), reverse=True):
        s, e = m.start(), m.end()
        if e < len(new_content) and new_content[e] == "\n":
            e += 1
        new_content = new_content[:s] + new_content[e:]

    # Insert hook import after all other imports
    import_end = find_end_of_imports(new_content)
    new_content = (
        new_content[:import_end] + "\n" + hook_import_line + new_content[import_end:]
    )

    # Recalculate positions after import changes
    comp_start_new, body_start_new = find_first_component_and_body_start(new_content)

    if body_start_new == -1:
        # Try to handle `=> (` pattern
        new_content, converted = handle_arrow_no_braces(new_content, hook_calls_str)
        if not converted:
            print(f"WARNING: No body found in {os.path.basename(file_path)}")
    else:
        # Move module-level declarations inside component (if any)
        moved_decls_text = ""
        if module_decls:
            # We need to re-find declarations in new_content (imports changed)
            # Re-find them in new_content using content_no_tr positions with offset
            # Simpler: re-run on new_content
            comp_start_nc, _ = find_first_component_and_body_start(new_content)
            if comp_start_nc > 0:
                moved_decls = find_top_level_declarations_using(
                    new_content[:comp_start_nc], list(module_level_names)
                )
                if moved_decls:
                    decl_texts = []
                    for ds, de in moved_decls:
                        decl_texts.append(new_content[ds:de])

                    # Remove them in reverse order
                    for ds, de in sorted(moved_decls, reverse=True):
                        # Also remove trailing newline(s)
                        end = de
                        while end < len(new_content) and new_content[end] in (
                            "\n",
                            "\r",
                        ):
                            end += 1
                        new_content = new_content[:ds] + new_content[end:]

                    # Insert them inside component body
                    comp_start_new2, body_start_new2 = (
                        find_first_component_and_body_start(new_content)
                    )
                    if body_start_new2 != -1:
                        # Indent the moved declarations
                        indented = []
                        for dt in decl_texts:
                            # Add 2-space indent to each line
                            indented_dt = "\n".join(
                                "  " + line if line.strip() else line
                                for line in dt.split("\n")
                            )
                            indented.append(indented_dt)
                        moved_decls_text = "\n".join(indented) + "\n"
                        new_content = (
                            new_content[:body_start_new2]
                            + moved_decls_text
                            + new_content[body_start_new2:]
                        )

        # Re-find body start after moving declarations
        _, body_start_final = find_first_component_and_body_start(new_content)
        if body_start_final != -1:
            new_content = (
                new_content[:body_start_final]
                + hook_calls_str
                + "\n"
                + new_content[body_start_final:]
            )
        else:
            new_content, converted = handle_arrow_no_braces(new_content, hook_calls_str)
            if not converted:
                print(f"WARNING: No body after move in {os.path.basename(file_path)}")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return True


def main():
    # Only process the remaining files (not yet converted)
    import subprocess

    result = subprocess.run(
        [
            "grep",
            "-rl",
            "resources/tr/",
            "frontend/src",
            "--include=*.tsx",
            "--include=*.ts",
        ],
        capture_output=True,
        text=True,
        cwd="D:/PROJECT/LOJINEXT",
    )
    files = [
        f.strip().replace("\\", "/")
        for f in result.stdout.strip().split("\n")
        if f.strip()
        and "__tests__" not in f
        and ".test." not in f
        and ".spec." not in f
    ]

    processed = 0
    errors = []
    for fp in files:
        try:
            changed = process_file(fp)
            if changed:
                processed += 1
                print(f"  OK {fp.split('/')[-1]}")
        except Exception as e:
            errors.append((fp, str(e)))
            print(f"  ERR {fp.split('/')[-1]}: {e}")

    print(f"\nDone. Updated {processed} files.")
    if errors:
        print(f"Errors ({len(errors)}):")
        for f, e in errors:
            print(f"  {f.split('/')[-1]}: {e}")


if __name__ == "__main__":
    main()
