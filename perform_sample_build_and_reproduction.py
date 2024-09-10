import KBDr_Runner.kcomposer.KBDr.kcomposer as kcomp
from argparse import ArgumentParser
from typing import Tuple, List
from dotenv import load_dotenv
import traceback
import requests
import os
import json

###################### Utility Functions ######################
def get_linker(compiler) :
    if compiler == "gcc" :
        return "ld"
    elif compiler == "clang" :
        return "ld.lld"

def run_job(workers, args, labels) :
    # create a session;
    session = kcomp.KBDrSession(os.getenv("KBDR_RUNNER_API_BASE_URL"), timeout=10)
    job_id = session.create_job(workers, args, labels)
    print("Job ID : {}".format(job_id))
    return job_id

def save_json(data_dict,save_path,final_idx) :
    final_path = os.path.join(save_path,"trial_{}.json".format(final_idx))
    with open(final_path,"w") as f :
        json.dump(data_dict,f,indent=4)
##############################################################

######################### KBuilder ###########################
class KBuilder() :

    @classmethod
    def get_empty_kbuilder_params(cls) :
        kbuilder_dict = {}
        kbuilder_dict["kernel_commit_id"] = None
        kbuilder_dict["kernel_git_url"] = None
        kbuilder_dict["kernel_config"] = None
        kbuilder_dict["user_img"] = None
        kbuilder_dict["arch"] = None
        kbuilder_dict["compiler"] = None
        kbuilder_dict["linker"] = None
        kbuilder_dict["patch"] = ""
        return kbuilder_dict
    
    @classmethod
    def fill_kbuilder_params_from_bug_folder(cls, bug_folder, bug_id, 
            kbuilder_dict,user_img="buildroot.raw",get_parent_commit:bool=False,get_fix_commit:bool=False) :
        
        def get_kernel_git_url(bug_data) :
            crash = bug_data["crashes"][0]
            git_url = crash['kernel-source-git']
            if 'https://github.com/' in git_url:
                git_url = git_url.split('/commits/')[0]
            elif 'https://git.kernel.org/pub/scm/linux/kernel/git/' in git_url:
                git_url = git_url.split('/log/?id=')[0]
            else:
                raise ValueError('Git URL not supported')
            return git_url

        def read_compiler_version(bug_data) :
            compiler = bug_data["crashes"][0]["compiler-description"]
            if "gcc" in compiler :
                return "gcc"
            elif "clang" in compiler :
                return "clang"
            else :
                raise ValueError("Unknown Compiler")

        def get_patch(bug_data) :
            return bug_data.get("patch","")

        bug_folder_path = os.path.join(bug_folder,bug_id)
        bug_data_path = os.path.join(bug_folder_path,"original_data.json")
        
        if not os.path.exists(bug_data_path) :
            bug_folder_path = bug_folder
            bug_data_path = os.path.join(bug_folder_path,bug_id+".json")
            assert(os.path.exists(bug_data_path))
        
        bug_data = json.load(open(bug_data_path,"r"))
        kernel_commit_id = bug_data["crashes"][0]["kernel-source-commit"]

        if get_parent_commit :
            # take the parent of the fix commit id
            if bug_data.get("parent_of_fix_commit",-1) == -1 :
                raise ValueError("User wants to compile with parent of fix commit but 'parent_of_fix_commit' field is missing")
            else :
                print("\tTaking parent commit id as per user specifications")
            kernel_commit_id = bug_data["parent_of_fix_commit"]
        
        elif get_fix_commit :
            # take the fix commit id
            if bug_data["fix-commits"][0].get("hash",-1) == -1 :
                raise ValueError("User wants to compile with fix commit but this is missing in the bug data")
            else :
                print("\tTaking fix commit id as per user specifications")
            kernel_commit_id = bug_data["fix-commits"][0]["hash"]

        kernel_git_url = get_kernel_git_url(bug_data)
        kernel_config = bug_data["crashes"][0]["kernel-config-data"]
        user_img = user_img
        arch = bug_data["crashes"][0]["architecture"]
        # assert(arch == "amd64")
        compiler = read_compiler_version(bug_data)
        linker = get_linker(compiler)
        patch = get_patch(bug_data)

        if kbuilder_dict["kernel_commit_id"] is None :
            kbuilder_dict["kernel_commit_id"] = kernel_commit_id
        if kbuilder_dict["kernel_git_url"] is None :
            kbuilder_dict["kernel_git_url"] = kernel_git_url
        if kbuilder_dict["kernel_config"] is None :
            kbuilder_dict["kernel_config"] = kernel_config
        if kbuilder_dict["user_img"] is None :
            kbuilder_dict["user_img"] = user_img
        if kbuilder_dict["arch"] is None :
            kbuilder_dict["arch"] = arch
        if kbuilder_dict["compiler"] is None :
            kbuilder_dict["compiler"] = compiler
        if kbuilder_dict["linker"] is None :
            kbuilder_dict["linker"] = linker
        if kbuilder_dict["patch"] is None :
            kbuilder_dict["patch"] = patch

    @classmethod
    def execute_kbuilder_functionality(cls, kbuilder_dict, kcomp) :
        # workers
        workers = ['kbuilder']
        # arguments
        arg = kcomp.kbuilder_argument(
            kernel_git_url=kbuilder_dict["kernel_git_url"],
            commit_id=kbuilder_dict["kernel_commit_id"],
            kernel_config=kbuilder_dict["kernel_config"],
            userspace_img_name=kbuilder_dict["user_img"],
            arch=kbuilder_dict["arch"],
            compiler=kbuilder_dict["compiler"],
            linker=kbuilder_dict["linker"],
            generate_metadata_from_bug=None)
        # labels
        labels = {
            'composed-by': 'sample-k-builder',
            'contains-kernel-commit-{}-at'.format(kbuilder_dict["kernel_commit_id"]) : '0'
        }
            
        return run_job(workers, [arg], labels)
##############################################################

######################### KVMManager #########################
class KVMManager () :

    @classmethod
    def get_empty_kvmmanager_params(cls) :
        kvm_manager = {}
        kvm_manager["reproducer-type"] = None
        kvm_manager["reproducer-text"] = None
        kvm_manager["nproc"] = None
        kvm_manager["restart-time"] = None
        kvm_manager["machine_type"] = None
        kvm_manager["image_from_worker"] = None
        kvm_manager["syzkaller-checkout"] = None
        kvm_manager["syzkaller-rollback-to-latest"] = None
        kvm_manager["ninstance"] = None
        return kvm_manager

    @classmethod
    def fill_kvm_manager_params_from_bug_folder(cls, data_folder_path, bug_id, kvm_manager_dict, nproc: int=8,
                        restart_time: str='10m', machine_type: str='gce:e2-standard-2', reproducer_type:str="c",
                        ninstance:int=1) :
        
        # read data for reproducer    
        bug_folder_path = os.path.join(data_folder_path,bug_id)
        bug_data_path = os.path.join(bug_folder_path,"original_data.json")
        
        if not os.path.exists(bug_data_path) :
            bug_folder_path = data_folder_path
            bug_data_path = os.path.join(bug_folder_path,bug_id+".json")
            assert(os.path.exists(bug_data_path))

        bug_data = json.load(open(bug_data_path,"r"))

        # store all the parameters for running a reproducer in the kernel
        # kvm_manager_dict = final_dict["kvm_manager_parameters"]
        for crash in bug_data['crashes']:
            if not ('c-reproducer-data' in crash or 'syz-reproducer-data' in crash):
                raise ValueError(bug_data['id'], 'No reproducer')

            if reproducer_type == "c" :
                kvm_manager_dict["reproducer-type"] = 'c'
                kvm_manager_dict["reproducer-text"] = crash.get('c-reproducer-data', '')
                kvm_manager_dict["nproc"] = nproc
                kvm_manager_dict["restart-time"] = restart_time
                kvm_manager_dict["syzkaller-checkout"] = crash.get("syzkaller-commit","")
                kvm_manager_dict["syzkaller-rollback-to-latest"] = True
                kvm_manager_dict["ninstance"] = ninstance

            elif reproducer_type == "log" :
                kvm_manager_dict["reproducer-type"] = "log"
                kvm_manager_dict["reproducer-text"] = crash.get('syz-reproducer-data', '')
                kvm_manager_dict["nproc"] = nproc
                kvm_manager_dict["restart-time"] = restart_time
                kvm_manager_dict["syzkaller-checkout"] = crash.get("syzkaller-commit","")
                kvm_manager_dict["syzkaller-rollback-to-latest"] = True
                kvm_manager_dict["ninstance"] = ninstance

                print("\tTaking log reproducer as per user specifications")
        
        kvm_manager_dict["machine_type"] = machine_type
        kvm_manager_dict["image_from_worker"] = 0
###############################################################

######################### KReproducer #########################
class KReproducer() :
    
    @classmethod
    def get_empty_reproducer_params(cls) :
        complete_argument_dict = {}
        complete_argument_dict["bug_id"] = None
        complete_argument_dict["kvm_builder_parameters"] = KBuilder.get_empty_kbuilder_params()
        complete_argument_dict["kvm_manager_parameters"] = KVMManager.get_empty_kvmmanager_params()
        return complete_argument_dict

    @classmethod
    def fill_kbuilder_kvm_manager_params_from_bug_folder(cls, data_path,
                                bug_id,
                                complete_argument_dict:dict,
                                user_img="buildroot.raw",
                                get_parent_commit:bool=False,
                                get_fix_commit:bool=False,
                                reproducer_type:str="c",
                                ninstance:int=1) :

        complete_argument_dict["bug_id"] = bug_id

        KBuilder.fill_kbuilder_params_from_bug_folder(bug_folder=data_path, bug_id=bug_id, 
                kbuilder_dict=complete_argument_dict["kvm_builder_parameters"],
                user_img=user_img,get_parent_commit=get_parent_commit,get_fix_commit=get_fix_commit)
        
        KVMManager.fill_kvm_manager_params_from_bug_folder(data_folder_path=data_path,bug_id=bug_id,
                                                kvm_manager_dict=complete_argument_dict["kvm_manager_parameters"],
                                                nproc=8,restart_time='10m',machine_type='gce:e2-standard-2',
                                                reproducer_type=reproducer_type,
                                                ninstance=ninstance)
        
        return complete_argument_dict

    @classmethod
    def execute_bug_reproduction(cls, complete_argument_dict) -> Tuple[list, list, dict[str, str]]:
        """
        Compose a bug reproduction job.
        Return the list of workers, their arguments and useful kv;

        Usage:
        worker_list, arguments = compose_bug_reproduction(...)
        composition.create_job(
            worker_list,
            arguments,
            kv=kv
        )
        """

        # sanity checks
        for key,value in complete_argument_dict["kvm_builder_parameters"].items() :
            assert(value is not None)
        for key,value in complete_argument_dict["kvm_manager_parameters"].items() :
            assert(value is not None)

        workers = ['kbuilder', 'kvmmanager']

        kbuilder_args = kcomp.models.kbuilder_argument(
            kernel_git_url = complete_argument_dict["kvm_builder_parameters"]["kernel_git_url"],
            commit_id = complete_argument_dict["kvm_builder_parameters"]["kernel_commit_id"],
            kernel_config = complete_argument_dict["kvm_builder_parameters"]["kernel_config"],
            userspace_img_name = complete_argument_dict["kvm_builder_parameters"]["user_img"],
            arch = complete_argument_dict["kvm_builder_parameters"]["arch"],
            compiler = complete_argument_dict["kvm_builder_parameters"]["compiler"],
            linker = complete_argument_dict["kvm_builder_parameters"]["linker"],
            patch = complete_argument_dict["kvm_builder_parameters"]["patch"],
            generate_metadata_from_bug=None)

        if complete_argument_dict["kvm_builder_parameters"]["patch"] != "" :
            print("\tApplying Git Patch")

        kvmmanager_args = kcomp.models.kvmmanager_argument(reproducer={
                                        "reproducer-type" : complete_argument_dict["kvm_manager_parameters"]["reproducer-type"],
                                        "reproducer-text" : complete_argument_dict["kvm_manager_parameters"]["reproducer-text"],
                                        "nproc" : complete_argument_dict["kvm_manager_parameters"]["nproc"],
                                        "restart-time" : complete_argument_dict["kvm_manager_parameters"]["restart-time"],
                                        "syzkaller-checkout" : complete_argument_dict["kvm_manager_parameters"]["syzkaller-checkout"],
                                        "syzkaller-rollback-to-latest" : complete_argument_dict["kvm_manager_parameters"]["syzkaller-rollback-to-latest"],
                                        "ninstance" : complete_argument_dict["kvm_manager_parameters"]["ninstance"]},
                                machine_type=complete_argument_dict["kvm_manager_parameters"]["machine_type"],
                                image_from_worker=complete_argument_dict["kvm_manager_parameters"]["image_from_worker"])

        arguments = [
            kbuilder_args,
            kvmmanager_args
        ]

        labels = {
            'composed-by': 'kcomposer.bug_reproduction',
            f'contains-kernel-commit-{complete_argument_dict["kvm_builder_parameters"]["kernel_commit_id"]}-at': '0',
            f'contains-bug-kernel-{complete_argument_dict["bug_id"]}-at': '0',
            'bug-reproduction-for': complete_argument_dict["bug_id"]
        }
    
        return run_job(workers, arguments, labels)
    
    @classmethod
    def execute_bug_reproduction_with_kernel_image(cls, complete_argument_dict, kernel_image_url:str) -> Tuple[list, list, dict[str, str]]:
        """
        Compose a bug reproduction job that uses a pre-built kernel image.
        Return the list of workers, their arguments and useful kv;

        Usage:
        worker_list, arguments = compose_bug_reproduction(...)
        composition.create_job(
            worker_list,
            arguments,
            kv=kv
        )
        """

        # sanity checks
        for key,value in complete_argument_dict["kvm_builder_parameters"].items() :
            assert(value is not None)
        for key,value in complete_argument_dict["kvm_manager_parameters"].items() :
            assert(value is not None)

        workers = ['kvmmanager']
        kvmmanager_args = kcomp.models.kvmmanager_argument(reproducer={
                                        "reproducer-type" : complete_argument_dict["kvm_manager_parameters"]["reproducer-type"],
                                        "reproducer-text" : complete_argument_dict["kvm_manager_parameters"]["reproducer-text"],
                                        "nproc" : complete_argument_dict["kvm_manager_parameters"]["nproc"],
                                        "restart-time" : complete_argument_dict["kvm_manager_parameters"]["restart-time"],
                                        "syzkaller-checkout" : complete_argument_dict["kvm_manager_parameters"]["syzkaller-checkout"],
                                        "syzkaller-rollback-to-latest" : complete_argument_dict["kvm_manager_parameters"]["syzkaller-rollback-to-latest"],
                                        "ninstance" : complete_argument_dict["kvm_manager_parameters"]["ninstance"]},
                                machine_type=complete_argument_dict["kvm_manager_parameters"]["machine_type"],
                                image_url=kernel_image_url,
                                arch=complete_argument_dict["kvm_builder_parameters"]["arch"])

        arguments = [
            kvmmanager_args
        ]

        labels = {
            'composed-by': 'kcomposer.bug_reproduction',
            f'contains-kernel-commit-{complete_argument_dict["kvm_builder_parameters"]["kernel_commit_id"]}-at': '0',
            f'contains-bug-kernel-{complete_argument_dict["bug_id"]}-at': '0',
            'bug-reproduction-for': complete_argument_dict["bug_id"]
        }

        return run_job(workers, arguments, labels)

    @classmethod
    def try_original(cls,
                data_path,bug_id, 
                sanitizer:str, 
                force_image:str=None,
                kernel_url:str=None,
                apply_patch:bool=False,
                run_parent:bool=False,
                run_fix:bool=False,
                reproducer_type:str="c",
                ninstance:int=1) :
        try :
            assert(not(run_parent and run_fix))
            complete_argument_dict = KReproducer.get_empty_reproducer_params()
            complete_argument_dict = KReproducer.fill_kbuilder_kvm_manager_params_from_bug_folder(data_path=data_path,
                                                                bug_id=bug_id,
                                                                complete_argument_dict=complete_argument_dict,
                                                                get_parent_commit=run_parent,
                                                                get_fix_commit=run_fix,
                                                                reproducer_type=reproducer_type,
                                                                ninstance=ninstance)
            
            if force_image :
                # image provided forcefully
                complete_argument_dict["kvm_builder_parameters"]["user_img"] = force_image

            if not apply_patch :
                # do not apply the patch provided
                complete_argument_dict["kvm_builder_parameters"]["patch"] = ""
            else :
                # apply the patch provided
                if complete_argument_dict["kvm_builder_parameters"]["patch"] == "" :
                    print("WARNING : Apply Patch Flag is True but no patch found !")
                    raise ValueError("Missing Patch")
                elif kernel_url is not None :
                    print("WARNING : Apply Patch Flag is True but no patch found !")
                    raise ValueError("User want to apply patch but at the same time use pre-built kernel")

            if sanitizer.upper() == "KMSAN" :
                # KMSAN needs clang exclusively
                complete_argument_dict["compiler"] = "clang"
                complete_argument_dict["linker"] = get_linker("clang")
            
            if complete_argument_dict["kvm_builder_parameters"]["arch"] != "amd64" :
                # if architecture is not amd64, then just skip for now
                print("{} : Original : Architecture is not amd64".format(bug_id))
                return None, "{} : Original : Architecture is not amd64".format(bug_id)
            
            if kernel_url is None :
                # both build the kernel as well as run the reproducer
                job_id = KReproducer.execute_bug_reproduction(complete_argument_dict)
            else :
                # re-use the pre-built kernel
                job_id = KReproducer.execute_bug_reproduction_with_kernel_image(complete_argument_dict, kernel_image_url=kernel_url)
            
            return job_id, "Successful"

        except Exception as e :
            job_id = None
            message = "Exception encountered : {}".format(traceback.print_exc())
            return job_id, message
################################################################

######################### CrossReproducer ######################
class CrossReproducer() :

    @classmethod
    def execute_bug_cross_reproduction(cls, complete_argument_dict) -> Tuple[list, list, dict] :

        # sanity checks
        for key,value in complete_argument_dict["kvm_builder_parameters"].items() :
            assert(value is not None)
        for kvm_manager in complete_argument_dict["kvm_manager_parameters"] : 
            for key,value in kvm_manager.items() :
                assert(value is not None)

        labels = {
            'composed-by': 'kcomposer.cross_reproduction',
            f'contains-kernel-commit-{complete_argument_dict["kvm_builder_parameters"]["kernel_commit_id"]}-at': '0',
            f'contains-bug-kernel-{complete_argument_dict["bug_id"]}-at': '0',
        }

        workers = ['kbuilder']
        kbuilder_args = kcomp.kbuilder_argument(
            kernel_git_url = complete_argument_dict["kvm_builder_parameters"]["kernel_git_url"],
            commit_id = complete_argument_dict["kvm_builder_parameters"]["kernel_commit_id"],
            kernel_config = complete_argument_dict["kvm_builder_parameters"]["kernel_config"],
            userspace_img_name = complete_argument_dict["kvm_builder_parameters"]["user_img"],
            arch = complete_argument_dict["kvm_builder_parameters"]["arch"],
            compiler = complete_argument_dict["kvm_builder_parameters"]["compiler"],
            linker = complete_argument_dict["kvm_builder_parameters"]["linker"],
            generate_metadata_from_bug=None)

        kvmmanager_arg_list = []
        for index,kvm_manager in enumerate(complete_argument_dict["kvm_manager_parameters"]) :
            workers.append('kvmmanager')
            kvmmanager_args = kcomp.kvmmanager_argument(reproducer={
                                            "reproducer-type" : kvm_manager["reproducer-type"],
                                            "reproducer-text" : kvm_manager["reproducer-text"],
                                            "nproc" : kvm_manager["nproc"],
                                            "restart-time" : kvm_manager["restart-time"]},
                                    machine_type=kvm_manager["machine_type"],
                                    image_from_worker=kvm_manager["image_from_worker"])
            kvmmanager_arg_list.append(kvmmanager_args)
            labels[f'cross-reproduction-kbug-{complete_argument_dict["bug_id"]}-rbug-{kvm_manager["repro-bug-id"]}'] = str(index+1)

        arguments = [kbuilder_args]
        arguments.extend(kvmmanager_arg_list)
        # assert(False)

        return run_job(workers, arguments, labels)

    @classmethod
    def get_sample_cross_reproduction_dict(cls, data_path, bug_id, reproducer_bug_ids, user_img="buildroot.raw") :

        complete_argument_dict = {}
        complete_argument_dict["bug_id"] = bug_id

        # read the building image parameters
        complete_argument_dict["kvm_builder_parameters"] = KBuilder.get_empty_kbuilder_params()
        KBuilder.fill_kbuilder_params_from_bug_folder(data_path, bug_id, complete_argument_dict["kvm_builder_parameters"], user_img=user_img)

        # for each duplicate bug store the reproducer file
        complete_argument_dict["kvm_manager_parameters"] = []
        for repro_bug_id in reproducer_bug_ids :
            complete_argument_dict = KReproducer.get_empty_reproducer_params()
            repro_argument_dict = KReproducer.fill_kbuilder_kvm_manager_params_from_bug_folder(data_path,repro_bug_id,
                                                                        complete_argument_dict=complete_argument_dict,
                                                                        user_img=user_img)
            complete_argument_dict["kvm_manager_parameters"].append(repro_argument_dict["kvm_manager_parameters"])
            complete_argument_dict["kvm_manager_parameters"][-1]["repro-bug-id"] = repro_bug_id
        return complete_argument_dict

    @classmethod
    def try_original_cross_reproduction(cls, data_path, bug_id, sanitizer:str, user_img:str, reproducer_bug_ids:List) :

        try :
            complete_argument_dict = CrossReproducer.get_sample_cross_reproduction_dict(data_path, bug_id, 
                                                                    reproducer_bug_ids, 
                                                                    user_img=user_img) 
            
            if sanitizer.upper() == "KMSAN" :
                # KMSAN needs clang exclusively
                complete_argument_dict["compiler"] = "clang"
                complete_argument_dict["linker"] = get_linker("clang")
            
            if complete_argument_dict["kvm_builder_parameters"]["arch"] != "amd64" :
                # if architecture is not amd64, then just skip for now
                print("{} : Original : Architecture is not amd64".format(bug_id))
                return None, "{} : Original : Architecture is not amd64".format(bug_id)
            
            job_id = CrossReproducer.execute_bug_cross_reproduction(complete_argument_dict)
            return job_id, "Successful"

        except Exception as e :
            job_id = None
            message = "Exception encountered : {}".format(traceback.print_exc())
            return job_id, message
################################################################

######################### Job Analyzer #########################
class JobAnalyzer() :

    @classmethod
    def get_important_job_info(cls, job_id, job_type:str='simple_reproduction') :
        """ Collects the status and the crash description. """
        
        headers = {'accept': 'application/json'}
        job_id = job_id.replace("\"","")
        resp = requests.get(url=os.getenv("KBDR_RUNNER_API_BASE_URL")+'/jobs/{}'.format(job_id),headers=headers)
        resp_dict = resp.json()

        if job_type == "simple_reproduction" :
            ans_dict = {}
            ans_dict["status"] = resp_dict["status"]
            status = resp_dict["status"]
            if status == "finished" :

                if len(resp_dict["worker-results"]) == 1 :
                    # shortcut reproduction with pre-built kernel image
                    if resp_dict["worker-results"][0].get("crash-description", -1) != -1 :
                        crash_description = resp_dict["worker-results"][0]["crash-description"]
                        ans_dict["crash_description"] = crash_description
                        ans_dict["message"] = None
                    else :
                        # if crash description does not exist then look at the 'message' field
                        message = resp_dict["worker-results"][0]["message"]
                        ans_dict["crash_description"] = None
                        ans_dict["message"] = message
                    ans_dict["vm-image-url"] = resp_dict["worker-arguments"][0]["image"]["image-url"]
                    ans_dict["final-syzkaller-checkout"] = resp_dict["worker-results"][0]["final-syzkaller-checkout"]
                    ans_dict["argument-syzkaller-checkout"] = resp_dict["worker-arguments"][0]["reproducer"]["syzkaller-checkout"]
                    ans_dict["rollback-operation-performed"] = (ans_dict["final-syzkaller-checkout"] != ans_dict["argument-syzkaller-checkout"])

                elif len(resp_dict["worker-results"]) == 2 :
                    # normal reproduction - build image and then reproduce
                    if resp_dict["worker-results"][1].get("crash-description", -1) != -1 :
                        crash_description = resp_dict["worker-results"][1]["crash-description"]
                        ans_dict["crash_description"] = crash_description
                        ans_dict["message"] = None
                    else :
                        # if crash description does not exist then look at the 'message' field
                        message = resp_dict["worker-results"][1]["message"]
                        ans_dict["crash_description"] = None
                        ans_dict["message"] = message
                    ans_dict["kernel_image_url"] = resp_dict["worker-results"][0]["kernel-image-url"]
                    ans_dict["vm-image-url"] = resp_dict["worker-results"][0]["vm-image-url"]
                    ans_dict["final-syzkaller-checkout"] = resp_dict["worker-results"][1]["final-syzkaller-checkout"]
                    ans_dict["argument-syzkaller-checkout"] = resp_dict["worker-arguments"][1]["reproducer"]["syzkaller-checkout"]
                    ans_dict["rollback-operation-performed"] = (ans_dict["final-syzkaller-checkout"] != ans_dict["argument-syzkaller-checkout"])

            elif status == "aborted" or status == "in_progress" or status == "pending" :
                ans_dict["crash_description"] = None
                ans_dict["message"] = None
                ans_dict["kernel_image_url"] = None
            
            else :
                print("Status : {}".format(status))
            
            return ans_dict
        
        elif job_type == "cross_reproduction" :
            ans_dict = {}
            ans_dict["status"] = resp_dict["status"]
            ans_dict["results"] = []
            status = resp_dict["status"]
            if status == "finished" :
                for index in range(1,len(resp_dict["worker-results"])) :
                    if resp_dict["worker-results"][index].get("crash-description", -1) != -1 :
                        crash_description = resp_dict["worker-results"][index]["crash-description"]
                        ans_dict["results"].append({"crash_description" : crash_description, "message" : None})
                    else :
                        # if crash description does not exist then look at the 'message' field
                        message = resp_dict["worker-results"][index]["message"]
                        ans_dict["crash_description"] = None
                        ans_dict["message"] = message
                        ans_dict["results"].append({"crash_description" : None, "message" : message})

            elif status == "aborted" :
                ans_dict["crash_description"] = None
                ans_dict["message"] = None
            return ans_dict

    @classmethod
    def populate_job_status(cls, all_job_path, job_type) :
        """ Populate the all_job_dict with the final outcomes of running the job. """

        with open(all_job_path,"r") as f :
            all_job_dict = json.load(f)

        for job_ele in all_job_dict["jobs"] :
            job_id = job_ele["job_id"]
            if job_id is None :
                # this job was not executed in the first place
                continue
            job_info = cls.get_important_job_info(job_id, job_type)

            if job_type == "simple_reproduction" :
                if job_info.get("vm-image-url",-1) != -1 :
                    job_ele["vm-image-url"] = job_info["vm-image-url"] 
                job_ele["execution"] = {}
                job_ele["execution"]["status"] = job_info["status"]
                job_ele["execution"]["crash_description"] = job_info["crash_description"]
                job_ele["execution"]["message"] = job_info["message"]
                job_ele["execution"]["rollback-operation-performed"] = None
                if job_info["status"] == "finished":
                    job_ele["execution"]["rollback-operation-performed"] = job_info["rollback-operation-performed"]

            elif job_type == "cross_reproduction" :
                job_ele["execution"] = {}
                job_ele["execution"]["status"] = job_info["status"]
                job_ele["execution"]["results"] = []
                for result in job_info["results"] :
                    # {'crash_description': None, 'message': 'Failed to set up instance'}
                    job_ele["execution"]["results"].append({
                            "crash_description" : result["crash_description"],
                            "message" : result["message"]})

        with open(all_job_path,"w") as f :
            json.dump(all_job_dict,f,indent=4)

################################################################

##### Start : Collecting the dataset experiment #####
def run_experiment(save_path,
                   data_folder_path,
                   bug_list_path,
                   per_point_user_image_flag:bool=False,
                   per_point_kernel_image_flag:bool=False,
                   per_point_apply_patch_flag:bool=True,
                   run_on_parent_of_fix_commit:bool=False,
                   run_on_fix_commit:bool=False,
                   reproducer_type:str="c",
                   ninstance:int=5) :

    experiment_dict = {"jobs" : []}
    experiment_dict["data_folder_path"] = data_folder_path

    final_idx = -1
    for idx in range(1000) :
        final_path = os.path.join(save_path,"trial_{}.json".format(idx+1))
        if os.path.exists(final_path) :
            continue
        else :
            final_idx = idx+1
            break

    with open(bug_list_path,"r") as f :
        bug_list_json = json.load(f)
    bug_list = bug_list_json["bugs"]
    
    index = 0
    kernel_image_url = None

    for bug in bug_list :
        if per_point_user_image_flag :
            bug_id = bug["id"].replace(".json","")
            force_image = bug["image"]
            
            if per_point_kernel_image_flag and \
                run_on_parent_of_fix_commit :
                kernel_image_url = bug["parent-vm-image-url"]
                print("\tRe-using Pre-built parent of fix-commit image")
            elif per_point_kernel_image_flag and \
                run_on_fix_commit :
                kernel_image_url = bug["fix-vm-image-url"]
                print("\tRe-using Pre-built fix-commit VM image")
            elif per_point_kernel_image_flag :
                kernel_image_url = bug["vm-image-url"]
                print("\tRe-using Pre-built VM image")

            job_id, message = KReproducer.try_original(data_path=data_folder_path,
                                           bug_id=bug_id,
                                           sanitizer="",
                                           force_image=force_image,
                                           kernel_url=kernel_image_url,
                                           apply_patch=per_point_apply_patch_flag,
                                           run_parent=run_on_parent_of_fix_commit,
                                           run_fix=run_on_fix_commit,
                                           reproducer_type=reproducer_type,
                                           ninstance=ninstance)

            experiment_dict["jobs"].append({"bug_id" : bug_id,
                                            "job_id" : job_id,
                                            "message" : message,
                                            "original" : "N/A",
                                            "type" : "vanilla"})
            save_json(experiment_dict,save_path,final_idx)
        else :
            force_image = bug.get("image",None)
            bug_id = bug["id"].replace(".json","")
            job_id, message = KReproducer.try_original(data_path=data_folder_path,
                                                    bug_id=bug_id,
                                                    sanitizer="",
                                                    force_image=force_image,
                                                    kernel_url=kernel_image_url,
                                                    apply_patch=per_point_apply_patch_flag,
                                                    run_parent=run_on_parent_of_fix_commit,
                                                    run_fix=run_on_fix_commit,
                                                    reproducer_type=reproducer_type,
                                                    ninstance=ninstance)
            experiment_dict["jobs"].append({"bug_id" : bug_id,
                                            "job_id" : job_id,
                                            "message" : message,
                                            "original" : "N/A",
                                            "type" : "vanilla"})
            save_json(experiment_dict,save_path,final_idx)
        index += 1
##### End : Collecting the dataset experiment #####


if __name__ == '__main__':
    
    parser = ArgumentParser()
    parser.add_argument("--job-receipt",type=str,required=True)
    args = parser.parse_args()

    JobAnalyzer.populate_job_status(all_job_path=args.job_receipt,job_type="simple_reproduction")
    
    # run_experiment(save_path=os.path.join(base_path,"easy_experiment_data/sublists"),
    #     data_folder_path=os.path.join(base_path,"Kernel_Benchmark"),
    #     bug_list_path=os.path.join(base_path,"golden_subset_benchmark_with_kernel_and_image_try_3.json"),
    #     per_point_user_image_flag=False,
    #     per_point_kernel_image_flag=False,
    #     per_point_apply_patch_flag=False,
    #     run_on_parent_of_fix_commit=True,
    #     run_on_fix_commit=False,
    #     reproducer_type="log",
    #     ninstance=5)