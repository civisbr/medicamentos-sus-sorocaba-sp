---
phase: 06-validation-data-quality
reviewed: 2026-05-06T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - src/utils/exporter.py
  - main.py
  - tests/test_exporter.py
findings:
  critical: 3
  warning: 4
  info: 3
  total: 10
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-05-06
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Three files were reviewed: `src/utils/exporter.py` (the `Exporter` class), `main.py` (CLI orchestrator), and `tests/test_exporter.py` (TDD suite). The exporter is structurally sound and handles most edge cases gracefully. However, three crash/data-corruption paths remain unguarded, all reachable in normal pipeline operation:

1. `gerar_csv` crashes with `KeyError` on an empty DataFrame (the exact fallback path main.py constructs when the source CSV is absent).
2. `gerar_html` emits `NaN` literals inside `<script>` blocks when any alert or supplier has `NaN` values (guaranteed with `SEM_REFERÊNCIA` items), breaking the JavaScript table sorter in every browser.
3. The fallback supplier-groupby in `gerar_summary` crashes with `KeyError` when `nome_fornecedor` or `nr_empenho` columns are absent from the alerts DataFrame.

The test suite covers most of the intended contract but has a weak assertion that lets a save/return mismatch go undetected, a fragile CSV parser in one test, and does not validate that the HTML `<script>` block contains parseable JSON.

---

## Critical Issues

### CR-01: `gerar_csv` crashes with `KeyError` when `alertas_df` is empty

**File:** `src/utils/exporter.py:93`

**Issue:** `df_out[COLUNAS_REQ008]` raises `KeyError: "None of [Index([...]) are in the [columns]]"` when `alertas_df` has no columns (i.e., is `pd.DataFrame()`). `main.py` constructs exactly this empty DataFrame at line 165 when `alertas_superfaturamento.csv` does not yet exist and `--step export` (or `--step all`) is called. The pipeline terminates with an unhandled exception instead of writing an empty-but-valid CSV.

**Fix:**
```python
def gerar_csv(self, alertas_df: pd.DataFrame, ano: int, output_file: str) -> None:
    if alertas_df.empty:
        # Write header-only CSV with disclaimer
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        buf = io.StringIO()
        buf.write(DISCLAIMER + "\n")
        pd.DataFrame(columns=COLUNAS_REQ008).to_csv(buf, index=False)
        out_path.write_text(buf.getvalue(), encoding="utf-8")
        return

    df_out = alertas_df.rename(columns=MAPA_COLUNAS)
    ...
```

---

### CR-02: `gerar_html` emits `NaN` literals in `<script>` block, breaking browser JavaScript

**File:** `src/utils/exporter.py:295` (alertas) and `src/utils/exporter.py:306` (fornecedores)

**Issue:** `alertas_df.to_dict("records")` preserves `float("nan")` values from any `SEM_REFERÊNCIA` row (where `preco_bps_mediana` and `variacao_percentual` are NaN). Jinja2's `tojson` filter emits these as the literal token `NaN`, which is not valid JSON. `JSON.parse` and the browser's implicit script evaluation fail silently or with an error, making the entire `sortTable()` function non-operational. The `test_dados_inline` test only checks that `const ALERTAS` appears in the HTML — it does not verify the JSON is parseable.

Confirmed via:
```python
from jinja2 import Environment
env = Environment(autoescape=False)
env.from_string('{{ data | tojson }}').render(data=[{"x": float("nan")}])
# → '[{"x": NaN}]'   ← invalid JSON
```

**Fix:** Sanitize NaN values before passing to the template:
```python
import math

def _sanitize_records(records: list) -> list:
    """Replace NaN/inf floats with None so tojson emits null (valid JSON)."""
    clean = []
    for rec in records:
        clean.append({
            k: (None if isinstance(v, float) and not math.isfinite(v) else v)
            for k, v in rec.items()
        })
    return clean

# In gerar_html, replace:
alertas = alertas_df.to_dict("records")
# with:
alertas = _sanitize_records(alertas_df.to_dict("records"))
# And similarly for fornecedores.
```

---

### CR-03: Fallback supplier aggregation crashes with `KeyError` when `nome_fornecedor` or `nr_empenho` absent

**File:** `src/utils/exporter.py:192-210`

**Issue:** The `elif` branch that computes `top_fornecedores` from `alertas_df` (when `fornecedores_file` is not provided) calls:
```python
alertas_df.groupby(["cnpj_fornecedor", "nome_fornecedor"])
    .agg(total_alertas=("nr_empenho", "count"), ...)
```
The entry condition on line 192 only checks `"cnpj_fornecedor" in alertas_df.columns`. If `nome_fornecedor` or `nr_empenho` is absent (columns differ across pipeline stages), `groupby` raises `KeyError`. The crash is silent: no warning is logged, no graceful empty result is returned.

**Fix:**
```python
required_cols = {"cnpj_fornecedor", "nome_fornecedor", "nr_empenho", "valor_excedente_total"}
elif not alertas_df.empty and required_cols.issubset(alertas_df.columns):
    grp = (
        alertas_df.groupby(["cnpj_fornecedor", "nome_fornecedor"])
        .agg(
            total_alertas=("nr_empenho", "count"),
            valor_excedente_total=("valor_excedente_total", "sum"),
        )
        ...
    )
```

---

## Warnings

### WR-01: `tier_suspeito` truthiness check mislabels any non-empty string as `SUSPEITO`

**File:** `src/utils/exporter.py:190`

**Issue:**
```python
"nivel_risco": "SUSPEITO" if row.get("tier_suspeito") else "OK",
```
When `fornecedores_suspeitos.csv` stores `tier_suspeito` as a string (e.g., `"ALTO"`, `"MÉDIO"`, `"BAIXO"`), every non-empty string evaluates as truthy. A supplier classified `"MÉDIO"` would be reported as `"SUSPEITO"`. The test fixture `fornecedores_df_fixture` already uses string values `"ALTO"` and `"MÉDIO"` — but no test asserts the resulting `nivel_risco` values for the fixture's `"MÉDIO"` entries, so this bug passes silently.

**Fix:** Treat the column as a string label and map explicitly:
```python
tier_val = str(row.get("tier_suspeito", "") or "")
SUSPEITO_TIERS = {"ALTO", "CRÍTICO", True, "True"}
"nivel_risco": "SUSPEITO" if tier_val in SUSPEITO_TIERS or tier_val is True else "OK",
```
Or, if the column is always boolean in the actual supplier output:
```python
"nivel_risco": "SUSPEITO" if row.get("tier_suspeito") is True else "OK",
```

---

### WR-02: `float()` (not `_safe_float()`) used for `valor_excedente_total` in `top_fornecedores`, allowing NaN into JSON

**File:** `src/utils/exporter.py:189`

**Issue:**
```python
"valor_excedente_total": float(row.get("valor_excedente_total", 0) or 0),
```
`float("nan") or 0` evaluates to `float("nan")` because NaN is truthy. The result is a raw `float("nan")` stored in the summary dict, which `json.dumps` serialises as the token `NaN` — invalid JSON per RFC 8259 and rejected by browser `JSON.parse`. The `_safe_float` helper exists exactly for this purpose but is only used for `top_itens`.

Additionally, on line 207 the same pattern appears in the fallback path:
```python
"valor_excedente_total": float(row.get("valor_excedente_total", 0) or 0),
```

**Fix:** Use `_safe_float` consistently:
```python
"valor_excedente_total": _safe_float(row.get("valor_excedente_total")) or 0.0,
```

---

### WR-03: `int(total_alertas or 0)` raises `ValueError` when value is `NaN`

**File:** `src/utils/exporter.py:188` and `src/utils/exporter.py:207`

**Issue:**
```python
"total_alertas": int(row.get("total_alertas", 0) or 0),
```
If `total_alertas` in the CSV is `NaN` (possible for any row with missing data), `row.get(...)` returns `float("nan")`. Since `float("nan")` is truthy, `nan or 0` evaluates to `nan`, and `int(nan)` raises `ValueError: cannot convert float NaN to integer`. This is an unhandled exception that would terminate the pipeline.

**Fix:**
```python
import math

def _safe_int(v, default: int = 0) -> int:
    try:
        f = float(v)
        return default if math.isnan(f) else int(f)
    except (TypeError, ValueError):
        return default

"total_alertas": _safe_int(row.get("total_alertas", 0)),
```

---

### WR-04: Duplicate `import json` inside `if`-block in `main.py`

**File:** `main.py:108`

**Issue:**
```python
import json as _json   # line 108, inside if step in ("all", "analyze"):
```
`json` is already imported at the top of the file on line 13. The inner import is redundant and adds noise. More importantly, it shadow-names the module as `_json` only within the `if` block, which is a confusing pattern.

**Fix:** Remove lines 108 and use the top-level `json` import:
```python
# Remove line 108: import json as _json
_stats_path.write_text(json.dumps(estatisticas, ensure_ascii=False, indent=2), encoding="utf-8")
```

---

## Info

### IN-01: Redundant `.copy()` call in `gerar_csv`

**File:** `src/utils/exporter.py:89`

**Issue:**
```python
df_out = alertas_df.rename(columns=MAPA_COLUNAS)  # already returns a new DataFrame
if "narrativa_ia" not in df_out.columns:
    df_out = df_out.copy()   # <-- no-op: rename() already produced a copy
    df_out["narrativa_ia"] = ""
```
`DataFrame.rename()` with `inplace=False` (the default) always returns a new object. The explicit `.copy()` on line 89 is redundant.

**Fix:** Remove the redundant copy:
```python
if "narrativa_ia" not in df_out.columns:
    df_out["narrativa_ia"] = ""
```

---

### IN-02: Weak assertion in `test_salva_arquivo` allows saved-vs-returned value mismatch

**File:** `tests/test_exporter.py:469`

**Issue:**
```python
assert saved == result or saved.keys() == result.keys()
```
The `or` condition means the test passes if the key sets match even when values differ (e.g., `gerado_em` timestamps differ due to clock skew between the write and subsequent `json.loads`). The intent is clearly to verify round-trip fidelity, but the assertion is too lenient.

**Fix:** Assert structural equivalence excluding the dynamic timestamp:
```python
saved.pop("gerado_em", None)
result_cmp = {k: v for k, v in result.items() if k != "gerado_em"}
assert saved == result_cmp, "Conteúdo do arquivo salvo difere do dict retornado"
```

---

### IN-03: `test_ordenacao_desc` uses naive comma-split instead of `csv.reader`

**File:** `tests/test_exporter.py:162-168`

**Issue:**
```python
cols = line.split(",")
try:
    valores.append(float(cols[idx_valor]))
```
If any CSV field value (e.g., a medication name or supplier name) contains a comma, `split(",")` produces wrong column offsets and `float(cols[idx_valor])` either raises `ValueError` or reads the wrong field. The current fixture happens to have no commas in field values, masking the fragility.

**Fix:** Use the `csv` module:
```python
import csv, io as _io
reader = csv.reader(_io.StringIO("\n".join(lines[2:])))
for row in reader:
    if row:
        try:
            valores.append(float(row[idx_valor]))
        except (ValueError, IndexError):
            pass
```

---

_Reviewed: 2026-05-06_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
