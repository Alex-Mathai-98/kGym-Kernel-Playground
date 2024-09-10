# Kernel-Playground
Kernel Playground - A playground to run large scale experiments on the Linux Kernel

Below are the list of steps to follow when trying to run a sample experiment from the paper ```kGym: A Platform and Dataset to Benchmark Large Language Models on Linux Kernel Crash Resolution```.

## Step 0 - Set up kGym
Follow the README.md file in KBDr_Runner and bring up kGym

## Step 1 - Clone the linux repository twice
### Step (1A) : Clone the first instance of linux and rename to "linux-2"
Run the below commands
```
git clone https://github.com/torvalds/linux.git
mv linux linux-2
```

### Step (1B) : Clone the second instance of linux
Run the below command
```
git clone https://github.com/torvalds/linux.git
```

## Step 2 - Set the below environment variables
```
export BASE_PATH="<PATH_TO_KERNEL_PLAYGROUND>"
export TIKTOKEN_CACHE_DIR="<PATH_TO_ANY_LOCAL_FOLDER_FOR_CACHING>"
export ANTHROPIC_API_KEY="<YOUR_ANTHROPIC_API_KEY>"
export GEMINI_API_KEY="<YOUR_GEMINI_API_KEY>"
export OPENAI_API_KEY="<YOUR_OPENAI_API_KEY>"
export KBDR_RUNNER_API_BASE_URL="<BASE_URL_OF_KGYM>"

export KBENCH_PATH="$BASE_PATH/Kernel_Benchmark"
export KGYM_PATH="$BASE_PATH/KBDr_Runner"
export KBENCH_EXPR_PATH="$BASE_PATH/Kernel_Bench_Experiments"
export GOLDEN_SUBSET_PATH="$BASE_PATH/golden_subset_benchmark_with_kernel_and_image_try_3.json"
export LINUX_PATH="$BASE_PATH/linux"
export LINUX_PATH_2="$BASE_PATH/linux-2"
```

## Step 3 - Populate the benchmark
Run the below command
```
python populate_benchmark.py
```

After running the above command, ```Kernel_Benchmark``` will have all kernel bugs populated with all the necessary fields.

## Step 4 - Create the linux dataset
Run the below command
```
python $KBENCH_EXPR_PATH/inference/make_datasets/make_linux_dataset.py
```

## Step 5 - Create the BM25 indices for kBench dataset (this takes ~ 3 hours)
Run the below command
```
bash $KBENCH_EXPR_PATH/bash_scripts/create_indices/parent_commit/create_indices_parent_commit.sh
```

## Step 6 - Create the prompt dataset for GPT 3.5 Turbo in the assisted Oracle setting
Run the below command
```
bash $KBENCH_EXPR_PATH/bash_scripts/create_dataset/parent_commit/create_dataset_parent_commit_oracle_gpt_3.5_turbo.sh
```

## Step 7 - Run the GPT 3.5 model on the prompt dataset to get back LLM-generated patches
Run the below command
```
bash $KBENCH_EXPR_PATH/bash_scripts/run_api/parent_commit/run_api_parent_commit_oracle_prompting_for_gpt_3.5.sh
```

## Step 8 - Run kGYM with the generated patches to apply the patch and run the reproducer file
Run the below command
```
bash $KBENCH_EXPR_PATH/bash_scripts/apply_patches/parent_commit/run_prompt_predictions_parent_commit_oracle_gpt_3.5.sh
```

## Step 9 - Populate the job status for each run kernel job
Run the below command
```
python $BASE_PATH/perform_sample_build_and_reproduction.py --job-receipt "$KBENCH_EXPR_PATH/bash_scripts/apply_patches/parent_commit/gpt-3.5-turbo-16k-0613__SWE-bench__style-3__fs-oracle__mcc-16000-cl100k--parent_commit__train_trial_1.json"
```

## Step 10 - Evaluate all the kernel jobs to see how many bugs were resolved
Run the below command
```
python kernel_bench_evaluator.py --job-receipt "$KBENCH_EXPR_PATH/bash_scripts/apply_patches/parent_commit/gpt-3.5-turbo-16k-0613__SWE-bench__style-3__fs-oracle__mcc-16000-cl100k--parent_commit__train_trial_1.json"
```


