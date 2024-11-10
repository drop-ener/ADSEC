import glob
import json
import logging
import os
import re
import numpy as np
from monty.serialization import dumpfn, loadfn
import shutil

from apex.core.calculator.lib import abacus_utils
from apex.core.calculator.lib import vasp_utils
from apex.core.calculator.lib import abacus_scf

from adsec.property.Property import Property
from ase.io import read,write
from ase.build.tools import sort
from dflow.python import upload_packages
upload_packages.append(__file__)


class SlabStatic(Property):
    def __init__(self, parameter, inter_param=None):

        default_cal_setting = {
            "relax_pos": False,
            "relax_shape": False,
            "relax_vol": False,
            }
        parameter.setdefault("cal_setting", {})
        parameter["cal_setting"].update(
            {k: v for k, v in default_cal_setting.items() if k not in parameter["cal_setting"]})
        self.cal_setting = parameter["cal_setting"]
        #parameter["init_from_suffix"] = parameter.get("init_from_suffix", "00")
        #self.init_from_suffix = parameter["init_from_suffix"]
        self.parameter = parameter
        self.inter_param = inter_param if inter_param != None else {"type": "vasp"}

    def make_confs(self, path_to_work):
        "here path_to_work = /personal/hppo/adsflow/confs/std-fcc/slab/static/"
        path_to_work = os.path.abspath(path_to_work) 
        "here path_to_work = /tmp/inputs/artifacts/input_work_path/personal/hppo/adsflow/confs/std-fcc/bulk/static/"
        if os.path.exists(path_to_work):
            logging.debug("%s already exists" % path_to_work)
        else:
            os.makedirs(path_to_work)
        
        parent_path = os.path.dirname(path_to_work)
        grandparent_path = os.path.dirname(parent_path)

        confs_from_previous = self.parameter["confs_from_previous"]
        if not confs_from_previous:
            slab_names = []
            for entry in os.listdir(grandparent_path):
                full_path = os.path.join(grandparent_path, entry)
                if os.path.isfile(full_path):
                    if 'slab' in entry and 'ads' not in entry:
                        slab_names.append(entry)
            cwd = os.getcwd()
            task_list = []
            for vaspfile in slab_names:
                task_name = vaspfile.split('.')[0]
                path_to_poscar = os.path.join(grandparent_path,vaspfile)
                if not os.path.isfile(path_to_poscar):
                    raise RuntimeError("Can not find %s, please provide poscar first" % path_to_poscar)
                output_task = os.path.join(path_to_work, task_name)
                os.makedirs(output_task, exist_ok=True)
                os.chdir(output_task)

                atoms = read(path_to_poscar)
                write("POSCAR",sort(atoms), vasp5=True)
                task_list.append(output_task)
                os.chdir(cwd)
            return  task_list

        cwd = os.getcwd()
        task_list = []


        path_to_relaxtion = os.path.join(parent_path, "relaxtion")

        miller_indices_set = self.parameter["miller_indices_set"]
        include_names = []

        for i in range(len(miller_indices_set)):
            val_x,val_y,val_z = miller_indices_set[i]
            slab_name = "slab_{}{}{}".format(val_x,val_y,val_z)
            include_names.append(slab_name)

        slab_folders = []
        task_names = []
        # os.walk()遍历目录树
        flag = False
        if flag:
            for root, dirs, files in os.walk(path_to_relaxtion):
                for dir_name in dirs:
                    if dir_name.startswith('slab_') and dir_name in include_names:
                        slab_folders.append(os.path.join(root, dir_name))
                        task_names.append(dir_name)
        else:
            for root, dirs, files in os.walk(path_to_relaxtion):
                for dir_name in dirs:
                    if 'slab_' in dir_name:
                        slab_folders.append(os.path.join(root, dir_name))
                        task_names.append(dir_name)

        total_task_num = len(slab_folders)

        for task_num in range(total_task_num):
            task_name = task_names[task_num]
            output_task = os.path.join(path_to_work, task_name)
            os.makedirs(output_task, exist_ok=True)
            os.chdir(output_task)
            equi_contcar = os.path.join(slab_folders[task_num], "CONTCAR")

            if not os.path.isfile(equi_contcar):
                raise RuntimeError(
                    "Can not find %s, please do relaxation first" % equi_contcar
                )

            POSCAR = "POSCAR"
            POSCAR_orig = "POSCAR.orig"

            for ii in [
                "INCAR",
                "POTCAR",
                POSCAR_orig,
                POSCAR,
            ]:
                if os.path.exists(ii):
                    os.remove(ii)

            shutil.copy(equi_contcar,POSCAR)
            #os.symlink(os.path.relpath(equi_contcar), POSCAR)
            task_list.append(output_task)
            os.chdir(cwd)

        return task_list

    def post_process(self, task_list):
        pass

    def transfile(self, path_to_prop):
        """
        post_process the file.
        """
        pass

    def task_type(self):
        return self.parameter["type"]

    def task_param(self):
        return self.parameter

    def _compute_lower(self, output_file, all_tasks, all_res):
        output_file = os.path.abspath(output_file)
        res_data = {}
        ptr_data = "conf_dir: " + os.path.dirname(output_file) + "\n"
        
        ptr_data += " Filename  EpA(eV)\n"
        for ii in range(len(all_tasks)):
            # vol = self.vol_start + ii * self.vol_step
            #vol = loadfn(os.path.join(all_tasks[ii], "eos.json"))["volume"]
            task_result = loadfn(all_res[ii])
            res_data[all_tasks[ii]] = task_result["energies"][-1] / sum(
                task_result["atom_numbs"]
            )
            ptr_data += "%s  %8.4f \n" % (
                all_tasks[ii],
                task_result["energies"][-1] / sum(task_result["atom_numbs"]),
            )


        with open(output_file, "w") as fp:
            json.dump(res_data, fp, indent=4)

        return res_data, ptr_data
