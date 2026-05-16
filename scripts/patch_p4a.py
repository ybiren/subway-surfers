import re, pathlib, sys

recipe = pathlib.Path("/tmp/p4a/pythonforandroid/recipes/python3/__init__.py")
if not recipe.exists():
    print(f"ERROR: recipe not found at {recipe}", file=sys.stderr)
    sys.exit(1)

text = recipe.read_text()
m = re.search(r"version\s*=\s*['\"]([^'\"]+)['\"]", text)
ver = m.group(1) if m else "NOT_FOUND"
print(f"Current python3 recipe version: {ver}")

if ver.startswith("3.14"):
    patched = re.sub(r"(version\s*=\s*['\"])[0-9.]+(['\"])", r"\g<1>3.13.0\g<2>", text)
    patched = re.sub(r"(sha\d+sum\s*=\s*['\"])[^'\"]*(['\"])", r"\g<1>\g<2>", patched)
    patched = re.sub(r"(md5sum\s*=\s*['\"])[^'\"]*(['\"])", r"\g<1>\g<2>", patched)
    recipe.write_text(patched)
    m2 = re.search(r"version\s*=\s*['\"]([^'\"]+)['\"]", patched)
    new_ver = m2.group(1) if m2 else "?"
    print(f"Patched to: {new_ver}")
    if not new_ver.startswith("3.13"):
        print("ERROR: patch did not apply!", file=sys.stderr)
        sys.exit(1)
else:
    print(f"Version '{ver}' does not need patching")
