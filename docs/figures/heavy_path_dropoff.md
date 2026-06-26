# heavy_path_dropoff

Source: Film Sort Admin Analytics HTML export, 2026-06-01 to 2026-06-25.

- Data range: 2026-06-01 to 2026-06-25
- Applicable version: V2 canonical session funnels; Light starts at `list_opened`, Heavy starts at `list_selected`
- Statistical unit: unique session
- Denominator: each flow's own previous stage
- Horizontal comparability: Light and Heavy are path diagnostics with different user intent; they are not additive and should not be read as a causal comparison
- Scope note: Light Flow and Heavy Flow represent different user intents and should not be read as a causal A/B comparison.

| Flow | Entry Stage | Entry Sessions | Started Sessions | Start / Entry | Completed Sessions | Completed / Started | Share or Download Sessions | Asset Action / Completed |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Light Flow | `list_opened` | 760 | 760 | 100.0% | 167 | 22.0% | 33 | 19.8% |
| Heavy Flow | `list_selected` | 1,675 | 210 | 12.5% | 27 | 12.9% | 12 | 44.4% |

Product read: Heavy Flow has a large drop between configuration/list selection and actual sorting start. The comparison is observational because Heavy users may have different goals, imported list sizes, and intent strength.
