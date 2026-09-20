"""Check whether the canonical menu keys list includes DEPOSITS."""
try:
    from app.constants.menu_keys import MENU_KEYS
    print("Imported MENU_KEYS from app.constants.menu_keys")
    print("Type:", type(MENU_KEYS))

    if isinstance(MENU_KEYS, dict):
        keys = list(MENU_KEYS.keys())
    elif isinstance(MENU_KEYS, (list, tuple, set)):
        keys = list(MENU_KEYS)
    else:
        # maybe it's an object with attributes
        keys = [k for k in dir(MENU_KEYS) if k.isupper()]

    print(f"Total keys: {len(keys)}")
    print()
    print("Accounting keys:")
    for k in sorted(keys):
        if "ACCOUNTING" in str(k):
            print("  ", k)
    print()
    has_deposits = any("DEPOSITS" in str(k) for k in keys)
    print("DEPOSITS in canonical list?", has_deposits)
except Exception as e:
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
print("menu_resolver.py — searching for hardcoded lists or filters:")
from pathlib import Path
p = Path("app/services/menu_resolver.py")
text = p.read_text(encoding="utf-8")
print(f"File size: {len(text)} bytes")
print()

# Find all uppercase menu-key-looking strings
import re
matches = set(re.findall(r"[\"']([A-Z][A-Z_]*(?:\.[A-Z_]+)?)[\"']", text))
accounting_matches = sorted(m for m in matches if "ACCOUNT" in m or "DEPOSIT" in m)
print("UPPERCASE strings found in menu_resolver.py that look like keys:")
for m in accounting_matches:
    print("  ", m)