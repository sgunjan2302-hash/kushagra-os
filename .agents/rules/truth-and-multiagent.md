---
trigger: always_on
description: "Enforce brutal technical honesty (no sycophancy, no hidden errors) and conflict-free multi-agent parallel execution."
---

# Truthfulness & Multi-Agent Rules

1. **Call Right Right, Wrong Wrong:** Never hide failed commands, warnings, or flaws. If any validation exits non-zero, paste the exact error and mark it `[FAIL]`. Never agree with a broken idea just to be polite.
2. **Zero Fabrication:** Never invent RPM names, Flatpak IDs, Plasma APIs, or test results. Tag anything that requires Fedora 44 runtime testing as `[UNVERIFIED - NEEDS VM TEST]`.
3. **Disjoint File Ownership:** Parallel agents MUST work ONLY on their assigned non-overlapping files. Shared files (`recipes/recipe.yml`, `files/scripts/02-system-tuning.sh`, `GEMINI.md`) may ONLY be edited by the Lead Integrator after parallel workers finish.
4. **Mandatory Auditor Gate:** Every parallel wave must end with an independent Auditor pass running the `build-verify-os` skill and reporting unfiltered `PASS` / `WARN` / `FAIL` results.
