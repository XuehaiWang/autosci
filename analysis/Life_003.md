# Life_003 — 100%

## 任务概述
Input: Raw nanopore electrical signal (FAST5/POD5), basecalled reads, reference genome/transcriptome sequences, and k-mer pore models.
Output: Signal-to-reference alignments in BAM format, nucleotide modification calls (e.g., m6A sites), performance benchmarks, and trained pore models.
Scientific ...

> 评分器原始加权分: 46.9/100（评分器使用 0-100 分制，50分=与论文持平）

## 得分明细
| item | 得分 | 权重 | 类型 | 失分原因摘要 |
|------|------|------|------|------------|
| [0] | 48/100 | 0.3 | image | Mode B (subjective) applies because the criterion concerns qualitative positional and base-type effects visible in the substitution-profile heatmaps. The reproduced base-position h... |
| [1] | 47/100 | 0.3 | image | Mode A applies since the criterion is about quantitative performance benchmarks. The AI’s runtime and file-size plots match the ground-truth trends and relative magnitudes: Uncalle... |
| [2] | 46/100 | 0.4 | image | Mode A applies because the criterion is about quantitative PR performance (AUPRC and recall at fixed precision) and relative improvement. The reproduced PR curve closely matches th... |

## 成功原因
- item[0] (image, 48/100): Mode B (subjective) applies because the criterion concerns qualitative positional and base-type effects visible in the substitution-profile heatmaps. The reproduced base-position heatmaps show clear central-base dominanc
- item[1] (image, 47/100): Mode A applies since the criterion is about quantitative performance benchmarks. The AI’s runtime and file-size plots match the ground-truth trends and relative magnitudes: Uncalled4 is always the fastest and smallest, a
- item[2] (image, 46/100): Mode A applies because the criterion is about quantitative PR performance (AUPRC and recall at fixed precision) and relative improvement. The reproduced PR curve closely matches the target: Uncalled4 and Nanopolish trace
