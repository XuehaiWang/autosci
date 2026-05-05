---
name: data_analysis
description: Structured data analysis workflow from loading to conclusions
tags: [analysis, data, statistics, visualization, results, plotting]
required_tools: [execute_command, write_file, read_file]
---

## Procedure

1. **Load and inspect data**
   - Load the dataset/results files
   - Check dimensions, data types, missing values
   - Print summary statistics (mean, std, min, max, quartiles)
   - Identify any obvious anomalies

2. **Clean and preprocess**
   - Handle missing values (drop, impute, or flag)
   - Remove obvious outliers (document criteria)
   - Normalize/standardize if needed for comparison
   - Verify data integrity after preprocessing

3. **Exploratory analysis**
   - Compute descriptive statistics per condition/group
   - Create distribution plots (histograms, box plots)
   - Look for patterns, trends, and anomalies
   - Check correlations between variables

4. **Statistical testing**
   - Choose appropriate test based on data properties:
     - Normal distribution → t-test, ANOVA
     - Non-normal → Wilcoxon, Mann-Whitney, Kruskal-Wallis
     - Multiple comparisons → apply correction (Bonferroni, Holm)
   - Report: test statistic, p-value, effect size, confidence interval
   - State conclusions relative to significance level

5. **Visualization**
   - Create clear, publication-quality plots
   - Use consistent styling (colors, fonts, labels)
   - Include error bars (std or 95% CI)
   - Save plots as both PNG and PDF
   - Recommended plot types:
     - Bar charts for comparisons
     - Line plots for trends over time
     - Scatter plots for correlations
     - Box plots for distributions

6. **Summarize findings**
   - State main results in plain language
   - Highlight surprising or notable findings
   - Acknowledge limitations and caveats
   - Suggest follow-up analyses if needed
   - Save analysis summary to a file

## Tips

- Always look at the raw data before running statistical tests
- Report negative results honestly — they are valuable
- Use pandas + matplotlib/seaborn for Python analysis
- Save all intermediate results so analysis is reproducible
- Round numbers sensibly — don't report p=0.049999 as significant
