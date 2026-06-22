"""
Update all component files to use useResources hooks instead of static TR imports.
v5: Fixed module-level detection (excludes import lines themselves).
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

TR_IMPORT_PATTERN = re.compile(
    r'^(import\s+\{[^}\n]+\}\s+from\s+["\']([^"\']*resources/tr/([^"\']+?))["\'];?)\s*$',
    re.MULTILINE,
)


def compute_hook_import_path(existing_import_path: str) -> str:
    if existing_import_path.startswith("@/"):
        return "@/resources/useResources"
    parts = existing_import_path.split("/")
    try:
        tr_idx = parts.index("tr")
        base = "/".join(parts[:tr_idx])
        return base + "/useResources"
    except ValueError:
        return "../../resources/useResources"


def parse_imported_names(import_line: str) -> list:
    m = re.search(r"\{([^}]+)\}", import_line)
    if not m:
        return []
    return [n.strip() for n in m.group(1).split(",") if n.strip()]


def find_end_of_imports(content: str) -> int:
    """Find position after all import statements (handles multi-line)."""
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


def find_first_component_pos(content: str) -> int:
    """Find the start position of the first exported function/component."""
    patterns = [
        r"export\s+(?:default\s+)?function\s+\w",
        r"export\s+const\s+\w+\s*(?::\s*[\w.]+(?:<[^>]*>)?)?\s*=",
    ]
    best = len(content)
    for pat in patterns:
        m = re.search(pat, content)
        if m and m.start() < best:
            best = m.start()
    return best if best < len(content) else -1


def has_module_level_usage(
    content_no_imports: str, names: list, first_component_pos: int
) -> bool:
    """Check if any name is used before the first component in content with imports removed."""
    if first_component_pos <= 0:
        return False
    pre_component = content_no_imports[:first_component_pos]
    for name in names:
        if re.search(r"\b" + re.escape(name) + r"\b", pre_component):
            return True
    return False


def find_hook_insertion_point(content: str) -> int:
    """
    Find the position to insert hook calls inside the first exported component/hook.
    Handles: function, arrow function, React.FC, React.memo patterns.
    """
    candidates = []

    # 1. export default function or export function FooName
    for m in re.finditer(r"export\s+(?:default\s+)?function\s+\w*\s*\(", content):
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
                    brace_m = re.search(r"(?::\s*[^\n{]+)?\s*\{", rest)
                    if brace_m:
                        brace_abs = j + 1 + brace_m.end()
                        pos = brace_abs
                        if pos < len(content) and content[pos] == "\n":
                            pos += 1
                        candidates.append((m.start(), pos))
                    break
            j += 1

    # 2. export const X = ... including React.FC = ... and React.memo
    for m in re.finditer(
        r"export\s+const\s+\w+\s*(?::\s*[\w.]+(?:<[^>]*>)?)?\s*=\s*(?:React\.memo\s*\(\s*)?",
        content,
    ):
        search_from = m.end()
        # Find ') => {' pattern within next 5000 chars
        arrow_m = re.search(r"\)\s*=>\s*\{", content[search_from : search_from + 5000])
        if arrow_m:
            brace_abs = search_from + arrow_m.end()
            pos = brace_abs
            if pos < len(content) and content[pos] == "\n":
                pos += 1
            candidates.append((m.start(), pos))

    # 3. Hook functions (export function useXxx or export async function useXxx)
    for m in re.finditer(r"export\s+(?:async\s+)?function\s+use\w+\s*\(", content):
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
                    brace_m = re.search(r"(?::\s*[^\n{]+)?\s*\{", rest)
                    if brace_m:
                        brace_abs = j + 1 + brace_m.end()
                        pos = brace_abs
                        if pos < len(content) and content[pos] == "\n":
                            pos += 1
                        candidates.append((m.start(), pos))
                    break
            j += 1

    if not candidates:
        return -1

    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def process_file(file_path: str) -> bool:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    matches = list(TR_IMPORT_PATTERN.finditer(content))
    if not matches:
        return False

    domain_to_names: dict = {}
    domain_to_path: dict = {}
    match_positions = []

    for m in matches:
        import_line = m.group(1)
        import_path = m.group(2)
        domain = m.group(3).strip()
        if domain.endswith(".ts"):
            domain = domain[:-3]

        hook = DOMAIN_TO_HOOK.get(domain)
        if not hook:
            continue

        names = parse_imported_names(import_line)
        if domain not in domain_to_names:
            domain_to_names[domain] = []
            domain_to_path[domain] = import_path
        domain_to_names[domain].extend(names)
        match_positions.append(m)

    if not match_positions:
        return False

    # Build a version of content with TR import lines removed (for module-level check)
    content_no_tr_imports = content
    for m in sorted(match_positions, key=lambda x: x.start(), reverse=True):
        start = m.start()
        end = m.end()
        if end < len(content_no_tr_imports) and content_no_tr_imports[end] == "\n":
            end += 1
        content_no_tr_imports = (
            content_no_tr_imports[:start] + content_no_tr_imports[end:]
        )

    first_component_pos = find_first_component_pos(content_no_tr_imports)

    # Separate names into: module-level used vs component-level only
    all_names = []
    for names in domain_to_names.values():
        all_names.extend(names)
    all_names_unique = list(dict.fromkeys(all_names))

    module_level_names = set()
    for name in all_names_unique:
        if first_component_pos > 0:
            pre_comp = content_no_tr_imports[:first_component_pos]
            if re.search(r"\b" + re.escape(name) + r"\b", pre_comp):
                module_level_names.add(name)

    # Determine which domains to remove imports for vs keep
    # We remove a domain's import if NONE of its names are module-level
    # For domains with mixed usage (some module-level, some not), we keep the import
    # and only update for the non-module-level names
    domains_to_remove = []
    domains_to_keep = []
    for domain, names in domain_to_names.items():
        if any(n in module_level_names for n in names):
            domains_to_keep.append(domain)
        else:
            domains_to_remove.append(domain)

    # Build hook imports/calls only for names NOT used at module level
    hooks_needed = []
    hook_destructures = []
    for domain in domains_to_remove:
        hook = DOMAIN_TO_HOOK[domain]
        if hook not in hooks_needed:
            hooks_needed.append(hook)
        names = domain_to_names[domain]
        unique_names = list(dict.fromkeys(names))
        hook_destructures.append(f"  const {{ {', '.join(unique_names)} }} = {hook}();")

    if not hooks_needed:
        # All names are module-level - we can't convert this file automatically
        # The original TR import stays, translation won't work for this file
        return False

    first_import_path = list(domain_to_path.values())[0]
    hook_import_path = compute_hook_import_path(first_import_path)
    hook_import_line = (
        f'import {{ {", ".join(hooks_needed)} }} from "{hook_import_path}";'
    )
    hook_calls_str = "\n".join(hook_destructures)

    # Only remove imports for domains_to_remove
    remove_set = set(domains_to_remove)
    positions_to_remove = []
    for m in match_positions:
        domain = m.group(3).strip()
        if domain.endswith(".ts"):
            domain = domain[:-3]
        if domain in remove_set:
            positions_to_remove.append(m)

    new_content = content
    for m in sorted(positions_to_remove, key=lambda x: x.start(), reverse=True):
        start = m.start()
        end = m.end()
        if end < len(new_content) and new_content[end] == "\n":
            end += 1
        new_content = new_content[:start] + new_content[end:]

    # Insert hook import after all imports
    import_end = find_end_of_imports(new_content)
    new_content = (
        new_content[:import_end] + "\n" + hook_import_line + new_content[import_end:]
    )

    # Insert hook calls inside the exported component/hook function body
    if hook_calls_str:
        insert_pos = find_hook_insertion_point(new_content)
        if insert_pos != -1:
            new_content = (
                new_content[:insert_pos]
                + hook_calls_str
                + "\n"
                + new_content[insert_pos:]
            )
        else:
            print(f"WARNING: No function body in {os.path.basename(file_path)}")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return True


def main():
    root = "D:/PROJECT/LOJINEXT/frontend/src"
    processed = 0
    warnings = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ["__tests__", "node_modules"]]
        for fname in filenames:
            if not (fname.endswith(".tsx") or fname.endswith(".ts")):
                continue
            if ".test." in fname or ".spec." in fname:
                continue

            fpath = os.path.join(dirpath, fname).replace("\\", "/")
            try:
                changed = process_file(fpath)
                if changed:
                    processed += 1
            except Exception as e:
                warnings.append((fpath, str(e)))
                print(f"ERROR: {os.path.basename(fpath)}: {e}")

    print(f"\nDone. Updated {processed} files.")
    if warnings:
        print(f"Errors: {len(warnings)}")
        for f, e in warnings:
            print(f"  {os.path.basename(f)}: {e}")


if __name__ == "__main__":
    main()
