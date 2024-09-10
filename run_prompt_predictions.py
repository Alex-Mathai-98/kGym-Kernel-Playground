from perform_sample_build_and_reproduction import KReproducer
from argparse import ArgumentParser
import json
import os
import traceback
import regex as re

def extract_diff(response):
    """
    Extracts the diff from a response formatted in different ways
    """
    if response is None:
        return None
    diff_matches = []
    other_matches = []
    pattern = re.compile(r"\<([\w-]+)\>(.*?)\<\/\1\>", re.DOTALL)
    for code, match in pattern.findall(response):
        if code in {"diff", "patch"}:
            diff_matches.append(match)
        else:
            other_matches.append(match)
    pattern = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)
    for code, match in pattern.findall(response):
        if code in {"diff", "patch"}:
            diff_matches.append(match)
        else:
            other_matches.append(match)
    if diff_matches:
        return diff_matches[0]
    if other_matches:
        return other_matches[0]
    return response.split("</s>")[0]

def save_json(data_dict,save_path,base_file,final_idx) :
    final_path = os.path.join(save_path,"{}_trial_{}.json".format(base_file,final_idx))
    with open(final_path,"w") as f :
        json.dump(data_dict,f,indent=4)

def read_benchmark_info(golden_subset) :
    ans = {}
    benchmark_data = json.load(open(golden_subset,"r"))
    for ele in benchmark_data["bugs"] :
        ans[ele["id"]] = ele
    return ans

def main(prediction_file, 
        benchmark_dump_path, 
        golden_subset,
        prediction_type) :

    # sanity checks
    assert(prediction_type in prediction_file)

    redo_bugs = None
    kernel_bench_path = "/".join(prediction_file.split("/")[:-1]) + "/KernelBench_" + prediction_file.split("/")[-1]
    kernel_bench_path = kernel_bench_path.replace("jsonl","json")
    kernel_bench_path = kernel_bench_path.replace("prompting_results","bash_scripts/apply_patches")
    if os.path.exists(kernel_bench_path) :
        redo_bugs = json.load(open(kernel_bench_path,"r"))["redo"]

    experiment_dict = {"jobs" : []}
    experiment_dict["data_folder_path"] = benchmark_dump_path
    benchmark_bug_data = read_benchmark_info(golden_subset)
    all_predictions = {}
    with open(prediction_file,"r") as f :
        lines = f.readlines()
        for line in lines :
            bug_ele = json.loads(line)
            all_predictions[bug_ele["instance_id"]] = bug_ele

    save_path = os.path.join(os.path.abspath(os.path.dirname(__file__)),"Kernel_Bench_Experiments/bash_scripts/apply_patches/{}".format(prediction_type))
    base_file = prediction_file.split("/")[-1].replace(".jsonl","")

    final_idx = -1
    for idx in range(1000) :    
        final_path = os.path.join(save_path,"{}_trial_{}.json".format(base_file,idx+1))
        print("Final Path Try : {}".format(final_path))
        if os.path.exists(final_path) :
            continue
        else :
            final_idx = idx+1
            break

    counter = 0

    keys = list(all_predictions.keys())
    index = 0
    while index < len(keys):
        bug_id = keys[index]
        val = all_predictions[bug_id]

        if redo_bugs :
            if bug_id not in redo_bugs :
                index += 1
                continue 

        orig_bug_id = bug_id
        if "__" in bug_id :
            bug_id = bug_id.split("__")[0]
        try :
            model_patch = val["model_patch"]
            complete_argument_dict = KReproducer.get_empty_reproducer_params()
            if prediction_type == "parent_commit" :
                complete_argument_dict = KReproducer.fill_kbuilder_kvm_manager_params_from_bug_folder(data_path=benchmark_dump_path,
                                                                                                    bug_id=bug_id,
                                                                                                    complete_argument_dict=complete_argument_dict,
                                                                                                    get_parent_commit=True,
                                                                                                    get_fix_commit=False,
                                                                                                    reproducer_type="log",
                                                                                                    ninstance=5)
            elif prediction_type == "original_commit" : 
                complete_argument_dict = KReproducer.fill_kbuilder_kvm_manager_params_from_bug_folder(data_path=benchmark_dump_path,
                                                                                                    bug_id=bug_id,
                                                                                                    complete_argument_dict=complete_argument_dict,
                                                                                                    get_parent_commit=False,
                                                                                                    get_fix_commit=False,
                                                                                                    reproducer_type="log",
                                                                                                    ninstance=5)
            complete_argument_dict["kvm_builder_parameters"]["user_img"] = benchmark_bug_data[bug_id]["image"]
            complete_argument_dict["kvm_builder_parameters"]["patch"] = model_patch
            job_id = KReproducer.execute_bug_reproduction(complete_argument_dict)
            experiment_dict["jobs"].append({"bug_id" : orig_bug_id,
                                "job_id" : job_id,
                                "message" : "Successful",
                                "original" : "N/A",
                                "type" : "vanilla"})
            save_json(experiment_dict,save_path,base_file,final_idx)
            #############
            counter += 1
            # assert(False)
            #############

        except Exception as e :
            print(traceback.format_exc())
            print("Exception encountered")
            index -= 1
            # if counter > 15 :
            #     assert(False)
        
        index += 1

    return

if __name__ == '__main__' :

    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prediction_file",
        type=str,
        required=True,
        help="Path to prediction"
    )
    parser.add_argument(
        "--benchmark_dump_path",
        type=str,
        required=True,
        help="Path to the benchmark dump"
    )
    parser.add_argument(
        "--golden_subset",
        type=str,
        required=True,
        help="Path to the golden subset"
    )
    parser.add_argument(
        "--prediction_type",
        type=str,
        required=True,
        choices=["parent_commit","original_commit"],
        help="One of parent_commit/original_commit"
    )

    args = parser.parse_args()

    main(prediction_file=args.prediction_file,
        benchmark_dump_path=args.benchmark_dump_path,
        golden_subset=args.golden_subset,
        prediction_type=args.prediction_type)