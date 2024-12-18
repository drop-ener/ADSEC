import os, glob, pathlib, shutil, subprocess, logging
from pathlib import Path
from typing import List
from dflow.python import (
    OP,
    OPIO,
    OPIOSign,
    Artifact,
    upload_packages
)

import logging
from monty.serialization import dumpfn
from apex.core.lib.utils import create_path

from adsec.calculator.calculator import make_calculator
from adsec.property.common_prop import make_property_instance
from adsec.utils.utils import recursive_search,generate_diff_path

upload_packages.append(__file__)


class PropsMake(OP):
    """
    OP class for making calculation tasks (make property)
    """

    def __init__(self):
        pass

    @classmethod
    def get_input_sign(cls):
        return OPIOSign({
            'input_work_path': Artifact(Path),
            'path_to_prop': str,
            'prop_param': dict,
            'inter_param': dict
        })

    @classmethod
    def get_output_sign(cls):
        return OPIOSign({
            'output_work_path': Artifact(Path),
            'task_names': List[str],
            'njobs': int,
            'task_paths': Artifact(List[Path])
        })

    @OP.exec_sign_check
    def execute(
            self,
            op_in: OPIO,
    ) -> OPIO:
        #from ..core.common_prop import make_property_instance
        #from ..core.calculator.calculator import make_calculator

        input_work_path = op_in["input_work_path"]
        path_to_prop = op_in["path_to_prop"]
        prop_param = op_in["prop_param"]
        inter_param = op_in["inter_param"]

        cwd = Path.cwd()
        os.chdir(input_work_path)
        abs_path_to_prop = input_work_path / path_to_prop  # /conf/std_bcc/bulk/relaxtion
    
        os.makedirs(str(abs_path_to_prop),exist_ok=True)

        conf_path = abs_path_to_prop.parent.parent
        prop_name = path_to_prop.split('/')[-2]+'-'+path_to_prop.split('/')[-1] # bulk-relaxtion
        #path_to_equi = conf_path / "relaxation" / "relax_task"

        inter_param_prop = inter_param

        prop = make_property_instance(prop_param, inter_param_prop)
        task_list = prop.make_confs(abs_path_to_prop)
        for kk in task_list:
            poscar = os.path.join(kk, "POSCAR")
            inter = make_calculator(inter_param_prop, poscar)
            inter.make_potential_files(kk)
            logging.debug(prop.task_type())  ### debug
            inter.make_input_file(kk, prop.task_param())
        prop.post_process(
            task_list
        )  # generate same KPOINTS file for elastic when doing VASP

        task_list.sort()
        #os.chdir(path_to_prop)
        #task_list_name = {'task_list': glob.glob('task.*').sort()}
        #dumpfn(task_list_name, 'task_list.json')

        os.chdir(input_work_path)
        #task_list_str = glob.glob(path_to_prop + '/' + 'task.*')
        #task_list_str.sort()

        task_list_str = [generate_diff_path(input_work_path,job) for job in task_list]

        all_jobs = task_list
        njobs = len(all_jobs)
        jobs = [pathlib.Path(job) for job in task_list]

        os.chdir(cwd)
        op_out = OPIO({
            "output_work_path": input_work_path,
            "task_names": task_list_str,
            "njobs": njobs,
            "task_paths": jobs
        })
        return op_out


class PropsPost(OP):
    """
    OP class for analyzing calculation results (post property)
    """

    def __init__(self):
        pass

    @classmethod
    def get_input_sign(cls):
        return OPIOSign({
            'input_post': Artifact(Path, sub_path=False),
            'input_all': Artifact(Path),
            'prop_param': dict,
            'inter_param': dict,
            'task_names': List[str],
            'path_to_prop': str
        })

    @classmethod
    def get_output_sign(cls):
        return OPIOSign({
            'retrieve_path': Artifact(Path)
        })

    @OP.exec_sign_check
    def execute(self, op_in: OPIO) -> OPIO:
        #from ..core.common_prop import make_property_instance
        cwd = os.getcwd()
        input_post = op_in["input_post"]
        input_all = op_in["input_all"]
        prop_param = op_in["prop_param"]
        inter_param = op_in["inter_param"]
        task_names = op_in["task_names"]
        path_to_prop = op_in["path_to_prop"]
        inter_type = inter_param["type"]
        copy_dir_list_input = [path_to_prop.split('/')[0]]
        os.chdir(input_all)
        copy_dir_list = []
        for ii in copy_dir_list_input:
            copy_dir_list.extend(glob.glob(ii))
        copy_dir_list = list(set(copy_dir_list))
        copy_dir_list.sort()

        # find path of finished tasks
        os.chdir(op_in['input_post'])
        src_path = recursive_search(copy_dir_list)
        if not src_path:
            raise RuntimeError(f'Fail to find input work path after slices!')


        if inter_type in ['vasp']:
            os.chdir(input_post)
            for ii in task_names:
                shutil.copytree(os.path.join(ii, "backward_dir"), ii, dirs_exist_ok=True)
                shutil.rmtree(os.path.join(ii, "backward_dir"))

            os.chdir(input_all)
            shutil.copytree(input_post, './', dirs_exist_ok=True)
        else:
            os.chdir(input_all)
            # src_path = str(input_post) + str(local_path)
            shutil.copytree(src_path, './', dirs_exist_ok=True)

        if ("cal_setting" in prop_param
                and "overwrite_interaction" in prop_param["cal_setting"]):
            inter_param = prop_param["cal_setting"]["overwrite_interaction"]

        abs_path_to_prop = Path.cwd() / path_to_prop
        prop = make_property_instance(prop_param, inter_param)
        param_json = os.path.join(abs_path_to_prop, "param.json")
        param_dict = prop.parameter
        param_dict.setdefault("skip", False) # default of "skip" is False
        param_dict.pop("skip")
        dumpfn(param_dict, param_json)
        prop.transfile(abs_path_to_prop)
        #prop.compute(
        #    os.path.join(abs_path_to_prop, "result.json"),
        #    os.path.join(abs_path_to_prop, "result.out"),
        #    abs_path_to_prop,
        #)

        os.chdir(cwd)
        #for ii in copy_dir_list:
        #    shutil.copytree(input_all / ii, ii, dirs_exist_ok=True)
        #retrieve_path = [Path(ii) for ii in copy_dir_list]
        # out_path = Path(cwd) / 'retrieve_pool'
        # os.mkdir(out_path)
        # shutil.copytree(input_all / path_to_prop,
        #                out_path / path_to_prop, dirs_exist_ok=True)

        op_out = OPIO({
            'retrieve_path': input_all
        })
        return op_out
