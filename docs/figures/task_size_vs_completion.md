# task_size_vs_completion

Source: Film Sort Admin Analytics HTML export, 2026-06-01 to 2026-06-25.

- Data range: 2026-06-01 to 2026-06-25
- Statistical unit: template/list sessions
- Inclusion rule: templates with enough observed starts in the exported list analysis for directional comparison
- Denominator: completion rate uses completed sessions / started sessions for each template

| Template | Started Sessions | Completed Sessions | Completion Rate | Average List Size | Average Comparisons |
|---|---:|---:|---:|---:|---:|
| `nolan` | 81 | 74 | 91.4% | 12.0 | 22.6 |
| `chinese-highscore` | 97 | 86 | 88.7% | 20.0 | 36.5 |
| `douban-top50` | 581 | 160 | 27.5% | 50.0 | 92.3 |
| `douban-collect` | 611 | 149 | 24.4% | 269.8 | 599.9 |

Interpretation boundary: task size appears associated with completion friction, but template content, user motivation, source channel, and entry path may all confound this relationship.
