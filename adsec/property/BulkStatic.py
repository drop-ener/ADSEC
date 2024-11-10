import glob
import json
import logging
import os
import re
import numpy as np
from monty.serialization import dumpfn, loadfn
import shutil
from ase.io import read,write
from ase.build.tools import sort

from apex.core.calculator.lib import vasp_utils
from adsec.property.Property import Property

from dflow.python import upload_packages
upload_packages.append(__file__)


class BulkStatic(Property):
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
        "here path_to_work = /personal/hppo/adsflow/confs/std-fcc/bulk/relaxtion/"
        path_to_work = os.path.abspath(path_to_work) 
        "here path_to_work = /tmp/inputs/artifacts/input_work_path/personal/hppo/adsflow/confs/std-fcc/bulk/relaxtion/"
        if os.path.exists(path_to_work):
            logging.debug("%s already exists" % path_to_work)
        else:
            os.makedirs(path_to_work)
        
        parent_path = os.path.dirname(path_to_work)
        grandparent_path = os.path.dirname(parent_path)
        confs_from_previous = self.parameter["confs_from_previous"]
        if not confs_from_previous:
            bulk_names = []
            for entry in os.listdir(grandparent_path):
                full_path = os.path.join(grandparent_path, entry)
                if os.path.isfile(full_path):
                    if 'POSCAR' in entry:
                        bulk_names.append(entry)
            cwd = os.getcwd()
            task_list = []
            for vaspfile in bulk_names:
                path_to_poscar = os.path.join(grandparent_path,vaspfile)
                if not os.path.isfile(path_to_poscar):
                    raise RuntimeError("Can not find %s, please provide poscar first" % path_to_poscar)
                output_task = path_to_work
                os.makedirs(output_task, exist_ok=True)
                os.chdir(output_task)

                atoms = read(path_to_poscar)
                write("POSCAR",sort(atoms), vasp5=True)
                task_list.append(output_task)
                os.chdir(cwd)
            return  task_list

        cwd = os.getcwd()
        task_list = []


        path_to_equi = os.path.join(parent_path, "relaxtion")
        equi_contcar = os.path.join(path_to_equi, "CONTCAR")

        if not os.path.isfile(equi_contcar):
            raise RuntimeError(
                "Can not find %s, please do relaxation first" % equi_contcar
            )

        output_task = path_to_work
        os.makedirs(output_task, exist_ok=True)
        os.chdir(output_task)
            
        POSCAR = "POSCAR"
        POSCAR_orig = "POSCAR.orig"

        for ii in [
            "INCAR",
            "POTCAR",
            POSCAR_orig,
            POSCAR
        ]:
            if os.path.exists(ii):
                os.remove(ii)
        task_list.append(output_task)
        #os.symlink(os.path.relpath(equi_contcar), POSCAR_orig)
        #os.symlink(os.path.relpath(equi_contcar), POSCAR)
        shutil.copy(equi_contcar, POSCAR)
        os.chdir(cwd)
        return task_list

    def transfile(self, path_to_prop):
        """
        post_process the file.
        """
        pass
    def post_process(self, task_list):
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
