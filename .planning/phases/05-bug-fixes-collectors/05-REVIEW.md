---
phase: 05-bug-fixes-collectors
reviewed: 2026-05-06T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - tests/test_ai_analyzer.py
  - main.py
  - requirements.txt
  - tests/test_bps_collector.py
  - src/collectors/bps_collector.py
  - tests/test_cnpj_collector.py
  - src/collectors/cnpj_collector.py
findings:
  critical: 1
  warning: 4
  info: 4
  total: 9
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-05-06T00:00:00Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

The two collectors (`bps_collector.py`, `cnpj_collector.py`) and their test suites are largely sound: the BPS fallback-to-headless flow is correctly implemented and tested, the CNPJ enrichment and merge logic (STAB-03, STAB-05) work as intended, and error-handling paths are properly covered. However, one critical bug was found — the `enriquecer_fornecedores()` input file read has no error handling, meaning a missing or corrupt file crashes the entire pipeline silently instead of logging a warning and continuing, violating an explicit project convention. Several warnings cover a double-sleep that fires even on non-HTTP-call code paths, a requirements/CLAUDE.md version mismatch for pandas, a redundant inline import, and a TODO comment for unimplemented logic that ships in the `analyze` step. Info-level issues cover unused imports in two test files, an inconsistency between the documented pipeline steps in CLAUDE.md and the actual CLI choices, and the dead-code block in `test_usa_modelo_datado`.

---

## Critical Issues

### CR-01: `enriquecer_fornecedores()` crashes on missing or corrupt input file

**File:** `src/collectors/cnpj_collector.py:127`
**Issue:** `json.loads(Path(input_file).read_text(encoding="utf-8"))` is not wrapped in any error handler. A `FileNotFoundError` (input file absent) or `json.JSONDecodeError` (corrupt file) will propagate uncaught and terminate the pipeline. The project convention in CLAUDE.md is explicit: _"Erros de API: logar warning e continuar (nunca crash silencioso)"_ — this same principle applies to file I/O that feeds an external-data-dependent step.

The existing output-file read at line 183 already demonstrates the correct pattern with a `try/except (json.JSONDecodeError, KeyError, TypeError)` guard. The input read has no equivalent protection.

**Fix:**
```python
try:
    empenhos = json.loads(Path(input_file).read_text(encoding="utf-8"))
except FileNotFoundError:
    logger.warning("Arquivo de empenhos nao encontrado: %s", input_file)
    return []
except json.JSONDecodeError as e:
    logger.warning("Arquivo de empenhos invalido (JSON malformado): %s — %s", input_file, e)
    return []
```

---

## Warnings

### WR-01: Double sleep fires even when `consultar()` returned from in-memory cache

**File:** `src/collectors/cnpj_collector.py:156-157`
**Issue:** `time.sleep(0.35)` at line 157 is unconditional — it runs after every `consultar()` call regardless of whether `consultar()` made an HTTP request or returned a result from `self._cache` (in-memory deduplication cache, line 100-101). The sleep comment says _"rate limit BrasilAPI (~3 req/s)"_, but it fires even when no request was made. In the current flow `cnpj_datas` deduplicates entries so the in-memory cache hit is rare, but the semantic intent is wrong and will silently over-slow any caller that reuses a `CNPJCollector` instance across multiple `enriquecer_fornecedores()` calls.

Additionally, a successful HTTP 200 response already sleeps 0.4 s inside `consultar()` (line 108), meaning a successful fresh lookup sleeps a combined 0.75 s — half the declared target rate.

**Fix:** Move the rate-limit sleep inside `consultar()` to cover all HTTP outcomes consistently, and remove the outer sleep:

```python
# in consultar(), replace the sleep block:
if resp.status_code == 200:
    dados = resp.json()
    self._cache[cnpj_limpo] = dados
    time.sleep(0.35)   # single authoritative rate-limit delay
    return dados
elif resp.status_code == 404:
    time.sleep(0.35)   # still counts as a request
    return None
else:
    time.sleep(0.35)
    resp.raise_for_status()

# in enriquecer_fornecedores(), remove line 157 entirely
```

### WR-02: `requirements.txt` pins `pandas==2.1.4` but CLAUDE.md mandates `pandas 2.2.x`

**File:** `requirements.txt:2`
**Issue:** The project specification in CLAUDE.md lists `pandas 2.2.x` as the required version. `requirements.txt` pins `pandas==2.1.4`. Running `pip install -r requirements.txt` installs a version that violates the project's own dependency contract. This creates a reproducibility gap: code developed against 2.2.x features (e.g., copy-on-write behaviour changes) may silently misbehave when installed from `requirements.txt`.

**Fix:**
```
pandas==2.2.2
```
(or `pandas>=2.2.0,<2.3.0` if a range is preferred)

### WR-03: `import json as _json` inside function body duplicates top-level `import json`

**File:** `main.py:108`
**Issue:** `json` is already imported at module level (line 13). Inside the `main()` function, line 108 re-imports it as `_json` to avoid a perceived name collision that does not exist. The alias is used only at lines 110-111 and could simply use the already-available `json` name. The redundant inline import suggests the author feared shadowing but there is no shadowing here — the module-level `json` is in scope throughout `main()`.

**Fix:** Remove line 108 (`import json as _json`) and change lines 110-111 to use `json.dumps(...)` directly, which is already in scope.

### WR-04: Unimplemented `SupplierAnalyzer.analisar()` called unconditionally with TODO comment in-line

**File:** `main.py:115-120`
**Issue:** Lines 115-120 call `supplier_analyzer.analisar(...)` with an inline `TODO (Claude Code): agrupar alertas por CNPJ, calcular score de risco, identificar padrões de reincidência`. If `SupplierAnalyzer.analisar()` raises `NotImplementedError` (which is the common stub pattern for unfinished methods), the entire `analyze` step crashes. The `collect` step's `NotImplementedError` for `BPSCollector` and `CNPJCollector` is guarded by `except NotImplementedError` blocks (lines 62-64 and 71-72), but the supplier analyzer call has no equivalent guard.

**Fix:** Apply the same defensive pattern used elsewhere:
```python
try:
    supplier_analyzer.analisar(
        alertas_file=str(ROOT / "data/reports/alertas_superfaturamento.csv"),
        cnpj_file=str(ROOT / "data/processed/fornecedores_enriquecidos.json"),
        output_file=str(ROOT / "data/reports/fornecedores_suspeitos.csv")
    )
except NotImplementedError:
    console.print("[yellow]SupplierAnalyzer ainda não implementado — pulando[/yellow]")
```

---

## Info

### IN-01: `_criar_session` imported but never used in `test_bps_collector.py`

**File:** `tests/test_bps_collector.py:13`
**Issue:** `_criar_session` is imported from `src.collectors.bps_collector` at line 13 but no test in the file invokes or asserts against it. The import is dead code.

**Fix:** Remove `_criar_session` from the import line:
```python
from src.collectors.bps_collector import (
    BPS_DATASET_PAGE,
    _descobrir_url_csv,
    _descobrir_url_csv_headless,
)
```

### IN-02: `avaliar_risco_cnpj_standalone` imported but never used in `test_cnpj_collector.py`

**File:** `tests/test_cnpj_collector.py:16`
**Issue:** `avaliar_risco_cnpj_standalone` is imported but never called in any test case. It was likely intended for a standalone unit-test class for `avaliar_risco_cnpj` (currently tested only indirectly through `enriquecer_fornecedores`). Either tests for it are missing, or the import should be removed.

**Fix:** Either add direct unit tests for the flag logic using this function, or remove the unused import.

### IN-03: Dead code block in `test_usa_modelo_datado` (lines 221-229)

**File:** `tests/test_ai_analyzer.py:221-229`
**Issue:** Lines 221-229 attempt three different ways to extract the `model` value from `call_kwargs` — none of which are actually used in the final assertion on line 230. The assertion correctly reads from `all_kwargs` (line 226). The intermediate extraction attempts at lines 221-225 are unreachable/unused dead code that creates misleading noise.

**Fix:** Simplify to:
```python
call_kwargs = mock_client.messages.create.call_args
assert call_kwargs is not None
all_kwargs = dict(call_kwargs.kwargs) if call_kwargs.kwargs else {}
assert all_kwargs.get("model") == "claude-sonnet-4-5-20250929", (
    f"Esperado 'claude-sonnet-4-5-20250929', recebido: {all_kwargs.get('model')}"
)
```

### IN-04: Pipeline step `normalize` documented in CLAUDE.md but absent from CLI

**File:** `main.py:29`
**Issue:** CLAUDE.md documents the pipeline as `--step normalize → data/processed/`, but the `click.Choice` at line 29 is `["all", "collect", "analyze", "export"]`. There is no `normalize` choice. The normalization is bundled inside `analyze`. This creates a discrepancy between the project specification and the actual interface, which can mislead contributors who follow CLAUDE.md as a guide.

**Fix:** Either add `"normalize"` as a discrete step option that runs only the `MedicamentoNormalizer` logic, or update CLAUDE.md to reflect the actual three-step structure (`collect → analyze → export`).

---

_Reviewed: 2026-05-06T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
