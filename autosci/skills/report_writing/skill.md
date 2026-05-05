---
name: report_writing
description: Guidelines for writing publication-quality research reports with proper structure, figures, and quantitative results
tags: [report, writing, paper, figures, results, discussion, markdown, academic]
required_tools: [write_file, read_file, list_dir]
---

## Report Structure

Write `report/report.md` with these sections in order:

1. **Title** — Clear, specific, matches the research task
2. **Abstract** (100-200 words) — Problem, method, key results with numbers, conclusion
3. **Introduction** — Background, research questions, what this report addresses
4. **Data & Methods** — What data was used, what analysis was performed, what tools/libraries
5. **Results** — Quantitative findings with figures and tables
6. **Discussion** — Interpret results, compare with reference values, limitations
7. **Conclusion** — Summary of findings, answer to research questions

## Figures

1. **Every figure must be referenced in text**: `![Caption](images/figure_name.png)`
2. **Use relative paths**: `images/xxx.png` (not absolute paths)
3. **Descriptive captions**: state what the figure shows and the key takeaway
4. **All figures must be PNG format** saved in `report/images/`
5. **Match expected figures**: if the task or paper describes specific figure types
   (heatmap, time series, choropleth, scatter), use those exact types

## Quantitative Results

1. **Always include specific numbers** — "accuracy improved by 15%" not "accuracy improved"
2. **Include units** — "mass change of -267 ± 16 Gt/yr" not "negative mass change"
3. **Compare with references** — if the paper reports baseline values, show yours alongside
4. **Use tables for multi-dimensional comparisons** (methods × metrics, regions × values)

## Common Mistakes to Avoid

- Writing a plan instead of a report (the report must contain actual results)
- Referencing figures that don't exist in `report/images/`
- Using absolute file paths in image references
- Omitting error bars, confidence intervals, or uncertainty estimates
- Describing what you "would do" instead of what you did and found
- Forgetting to cover all analysis dimensions mentioned in the task

## Checklist Before Finishing

- [ ] `report/report.md` exists and is complete
- [ ] All figures referenced in the report exist in `report/images/`
- [ ] Results include specific quantitative values with units
- [ ] All analysis dimensions from the task are covered
- [ ] Methodology section explains what was actually done
- [ ] Discussion compares results with reference/expected values