#!/usr/bin/env bash
# Pull Salesforce, Data Cloud and Marketing Cloud metadata, then rebuild data/dictionary.json.
# Local use:  bash pipeline/refresh.sh         (uses `sf org display -o blueowl-prod` and ~/.config/sfmc/env)
# CI use:     see .github/workflows/refresh.yml (SFDX_AUTH_URL + MC_* secrets)
set -euo pipefail
cd "$(dirname "$0")"
python3 pull_salesforce.py
python3 pull_datacloud.py
python3 pull_sfmc.py
python3 build.py
echo "dictionary rebuilt: $(python3 -c "import json;d=json.load(open('../data/dictionary.json'));print(d['generatedAt'], d['summary'])")"
