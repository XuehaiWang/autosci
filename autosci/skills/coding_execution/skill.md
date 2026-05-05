---
name: coding_execution
description: Best practices for writing and executing research code, including GPU usage, debugging, and long-running jobs
tags: [code, execution, gpu, pytorch, deep-learning, training, debugging, python, cuda]
required_tools: [execute_command, write_file, read_file, terminal_start, terminal_write]
---

## Before Writing Code

1. **Understand the data first**
   - Read data files (CSV headers, NetCDF variables, image samples) before writing analysis code
   - Note data shapes, types, and ranges — they determine your implementation choices

2. **Plan the pipeline**
   - List the steps: load data → process → analyze → visualize → save results
   - Identify which steps are computationally expensive (training, large-scale processing)

## Writing Code

1. **GPU usage (critical for deep learning)**
   - Always check GPU availability: `device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')`
   - Move models AND data to GPU: `model.to(device)`, `data = data.to(device)`
   - Never run PyTorch training on CPU — it will timeout or take hours
   - For TensorFlow: set `tf.config.list_physical_devices('GPU')` and verify

2. **Error handling**
   - Wrap main logic in try/except with informative error messages
   - Print progress at each major step so you can diagnose where failures occur
   - Save intermediate results frequently — don't lose hours of computation

3. **Output paths**
   - Save figures to `report/images/` as PNG: `plt.savefig('report/images/figure_name.png', dpi=150, bbox_inches='tight')`
   - Save intermediate data to `outputs/`
   - Use descriptive filenames that match what the report will reference

4. **Dependencies**
   - Install missing packages before running: `pip install package_name`
   - Common scientific stack: numpy, pandas, matplotlib, scipy, xarray, netCDF4
   - Common ML stack: torch, torchvision, scikit-learn

## Executing Code

1. **Short tasks (< 2 minutes)**
   - Use `execute_command` with appropriate timeout
   - Default timeout is 120s — increase for longer tasks: `timeout=300`

2. **Long tasks (training, large-scale processing)**
   - Use `terminal_start` + `terminal_write` for persistent sessions
   - This allows you to check progress with `terminal_read` without losing the process
   - Example pattern:
     ```
     terminal_start → terminal_write("python code/train.py") → 
     terminal_read (check progress) → terminal_read (wait for completion)
     ```

3. **Debugging failures**
   - Read the full error traceback — don't just retry the same command
   - Common issues: missing imports, wrong file paths, shape mismatches, OOM
   - For OOM: reduce batch size, use `torch.cuda.empty_cache()`, or process in chunks

## Validation

1. **Verify outputs exist** after running code
   - Check that expected files were created: `list_dir("report/images/")`
   - Open and inspect generated figures to ensure they're not blank or corrupted

2. **Sanity check results**
   - Are values in reasonable ranges?
   - Do trends match expectations from the paper/task description?
   - If results look wrong, debug before moving to report writing