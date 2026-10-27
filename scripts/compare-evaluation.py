"""Fail when a regenerated evaluation's confusion matrices differ from docs/evaluation.json."""
import json
import sys

committed, fresh = (json.load(open(path)) for path in sys.argv[1:3])
keys = [(split, model) for split in committed["splits"] for model in ("rules-0.2", "rules-0.1")]
diff = [(s, m) for s, m in keys if committed["splits"][s][m]["confusion_matrix"] != fresh["splits"][s][m]["confusion_matrix"]]
if committed["rule_fingerprint"] != fresh["rule_fingerprint"] or diff:
    sys.exit(f"Evaluation differs from the committed file: {diff or 'rule fingerprint'}")
print(f"Evaluation matches committed confusion matrices for {len(keys)} split/model pairs.")
