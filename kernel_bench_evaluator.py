from argparse import ArgumentParser
import json
import os

class KernelBenchEvaluator() :

    def __init__(self) -> None:
        self.rerun_success = 3
        self.max_trys = 5

    def get_cleaned_bug_id(self, bug_id) :
        return bug_id.split("__")

    def get_correct_key(self, trial_dict) :
        keys = list(trial_dict.keys())
        for key in keys :
            if trial_dict[key] is None :
                return key
        return None

    def reach_max_success(self,trial_dict) :
        counter = 0
        for key,value in trial_dict.items() :
            if value == "no crash reproduced" :
                counter += 1
                if counter == self.rerun_success :
                    return True
        return False
    
    def reach_max_attempts(self, trial_dict) :
        for key,value in trial_dict.items() :
            if value is None :
                return False
        return True

    def parse_job_receipt(self, job_receipt_path) :

        kernel_bench_path = "/".join(job_receipt_path.split("/")[:-1]) + "/KernelBench_" + job_receipt_path.split("/")[-1]
        trial_index = kernel_bench_path.find("_trial")
        json_index = kernel_bench_path.find(".json")
        kernel_bench_path = kernel_bench_path[:trial_index] + kernel_bench_path[json_index:]

        job_receipt = json.load(open(job_receipt_path,"r"))
        jobs = job_receipt["jobs"]

        first_run = False
        if os.path.exists(kernel_bench_path) :
            successful_bugs = json.load(open(kernel_bench_path,"r"))
            if job_receipt_path.split("/")[-1] in successful_bugs["evaluated_files"] :
                print("Result file has already been analyzed. Aborting.")
                return
            else :
                successful_bugs["evaluated_files"].append(job_receipt_path.split("/")[-1])
        else :
            first_run = True
            successful_bugs = {}
            successful_bugs["evaluated_files"] = [job_receipt_path.split("/")[-1]]

        ans = []
        for job in jobs :
            bug_id = job["bug_id"]
            
            if not first_run :
                if bug_id not in successful_bugs["redo"] :
                    # the bug had a crash in one of the attempts
                    continue

            try :
                cleaned_bug_id, K = self.get_cleaned_bug_id(bug_id)
            except Exception as e :
                cleaned_bug_id, K = bug_id, "0"

            try :
                message = job["execution"]["message"]
                crash_description = None
                if message is None :
                    crash_description = job["execution"]["crash_description"]

                if not first_run :
                    # > 1st run of KernelBenchEvaluator
                    if successful_bugs.get(cleaned_bug_id) :
                        if successful_bugs[cleaned_bug_id].get(K) :
                            # '{cleaned_bug_id}_{K}' was previously successful
                            trial_dict = successful_bugs[cleaned_bug_id].get(K)
                            correct_key = self.get_correct_key(trial_dict)
                            if message :
                                trial_dict[correct_key] = message.lower()
                            else :
                                trial_dict[correct_key] = crash_description
                            assert(trial_dict[correct_key] is not None)
                            max_success_flag = self.reach_max_success(trial_dict)
                            max_attempt_flag = self.reach_max_attempts(trial_dict)
                            if (not max_success_flag) and (not max_attempt_flag) and (crash_description is None) :
                                ans.append(bug_id)
                else :
                    if crash_description is not None :
                        continue
                    # first run of KernelBenchEvaluator
                    if message.lower() == "no crash reproduced" :
                        if successful_bugs.get(cleaned_bug_id) :
                            bug_dict = successful_bugs.get(cleaned_bug_id)
                        else :
                            successful_bugs[cleaned_bug_id] = {}
                            bug_dict = successful_bugs[cleaned_bug_id]
                        trial_dict = {idx+1:None for idx in range(self.max_trys)}
                        trial_dict[1] = message.lower()
                        bug_dict[K] = trial_dict
                        ans.append(bug_id)
            
            except Exception as e :
                continue
        
        successful_bugs["redo"] = ans
        json.dump(successful_bugs,open(kernel_bench_path,"w"),indent=4)
        return kernel_bench_path

    def final_successes(self, kernel_bench_path) :
        successful_jobs = []
        kernel_bench_data = json.load(open(kernel_bench_path,"r"))
        counter = 0
        for key,value in kernel_bench_data.items() :
            if (key == "evaluated_files") or (key == "redo") :
                continue
            else :
                for K, trial_dict in value.items() :
                    max_success = self.reach_max_success(trial_dict)
                    if max_success :
                        counter += 1
                        successful_jobs.append(key + "__" + K)
                        break
        print("Final number of successes is {}".format(counter))
        return successful_jobs

if __name__ == '__main__' :

    parser = ArgumentParser()
    parser.add_argument("--job-receipt",type=str,required=True)

    args = parser.parse_args()

    kb_eval = KernelBenchEvaluator()
    job_receipt = args.job_receipt
    
    kernel_bench_receipt_path = kb_eval.parse_job_receipt(job_receipt)
    kb_eval.final_successes(kernel_bench_receipt_path)
