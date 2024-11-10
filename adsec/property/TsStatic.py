import glob
import subprocess
import json
import logging
import os
import re
import numpy as np
from monty.serialization import dumpfn, loadfn
from pathlib import Path
import shutil

from apex.core.calculator.lib import abacus_utils
from apex.core.calculator.lib import vasp_utils
from apex.core.calculator.lib import abacus_scf
from apex.core.property.Property import Property
from apex.core.refine import make_refine
from apex.core.reproduce import make_repro, post_repro
from dflow.python import upload_packages
upload_packages.append(__file__)


class TsStatic(Property):
    def __init__(self, parameter, inter_param=None):

        parameter.setdefault("cal_setting", {})
        self.cal_setting = parameter["cal_setting"]
        self.parameter = parameter
        self.inter_param = inter_param if inter_param != None else {"type": "vasp"}

        #if "input_prop" in self.cal_setting and os.path.isfile(self.cal_setting["input_prop"]):
        #    incar_file_path = os.path.abspath(self.cal_setting["input_prop"])
        #    self.images_val = self.extract_images_value(incar_file_path)
       

    def make_confs(self, path_to_work):
        path_to_work = os.path.abspath(path_to_work)
        if os.path.exists(path_to_work):
            logging.debug("%s already exists" % path_to_work)
        else:
            os.makedirs(path_to_work)

        if "start_confs_path" in self.parameter and os.path.exists(
            self.parameter["start_confs_path"]
        ):
            init_path_list = glob.glob(
                os.path.join(self.parameter["start_confs_path"], "*")
            )
            struct_init_name_list = [os.path.basename(ii) for ii in init_path_list]
            struct_output_name = os.path.basename(os.path.dirname(path_to_work))
            assert struct_output_name in struct_init_name_list
            path_to_equi = os.path.abspath(
                os.path.join(
                    self.parameter["start_confs_path"],
                    struct_output_name,
                    "relaxation",
                    "relax_task",
                )
            )

        cwd = os.getcwd()
        task_list = []

        parent_path = os.path.dirname(path_to_work)  #get the path of conf/std_bcc
        grandparent_path = os.path.dirname(parent_path)

        ini_contcar = os.path.join(parent_path, "ini_POSCAR")
        fin_contcar = os.path.join(parent_path, "fin_POSCAR")

        if not os.path.isfile(ini_contcar):
            raise RuntimeError(
                "Can not find %s" % init_contcar
            )

        if not os.path.isfile(fin_contcar):
            raise RuntimeError(
                "Can not find %s" % fin_contcar
            )

        output_task_1 = os.path.join(path_to_work,'init_struct')
        output_task_2 = os.path.join(path_to_work,'final_struct')
        os.makedirs(output_task_1, exist_ok=True)
        os.makedirs(output_task_2, exist_ok=True)
   
        #os.chdir(output_task_1)
         
        shutil.copy(ini_contcar, '{}/ini_POSCAR'.format(output_task_1))
        shutil.copy(ini_contcar, '{}/POSCAR'.format(output_task_1))
        shutil.copy(fin_contcar,'{}/fin_POSCAR'.format(output_task_2))
        shutil.copy(fin_contcar,'{}/POSCAR'.format(output_task_2))

        task_list.append(output_task_1)
        task_list.append(output_task_2)
        os.chdir(cwd)

        return task_list

    def post_process(self, task_list):
        pass

    def task_type(self):
        return self.parameter["type"]

    def task_param(self):
        return self.parameter

    def transfile(self, path_to_prop):
        """
        post_process the file.
        """
        pass

    def _compute_lower(self, output_file, all_tasks, all_res):
        output_file = os.path.abspath(output_file)
        res_data = {}
        ptr_data = "conf_dir: " + os.path.dirname(output_file) + "\n"
      
        path_to_prop = os.path.dirname(output_file)
        path_to_conf = Path(path_to_prop).parent
        ini_outcar = path_to_conf/'ini_OUTCAR'
        fin_outcar = path_to_conf/'fin_OUTCAR'

        script_path = str(path_to_conf.parent.parent/'vtstscripts')
        current_path = os.environ.get('PATH', '')

        # 检查文件夹路径是否已经在PATH中
        if script_path not in current_path:
            # 将文件夹路径添加到PATH环境变量
            os.environ['PATH'] = f"{script_path}:{current_path}"

        ptr_data += " Filename  EpA(eV)\n"
        for ii in range(len(all_tasks)):
            # vol = self.vol_start + ii * self.vol_step
            #vol = loadfn(os.path.join(all_tasks[ii], "eos.json"))["volume"]
            #task_result = loadfn(all_res[ii])
            #res_data[self.init_from_suffix] = task_result["energies"][-1] / sum(
            #    task_result["atom_numbs"]
            #)
            path_to_nebtask = os.path.join(path_to_prop,'task.000000')           
            os.chdir(path_to_nebtask)
            shutil.copy(ini_outcar,'00/OUTCAR')
            shutil.copy(fin_outcar,'02/OUTCAR')

            nebresult_command = "nebresults.pl"
            nebresult = subprocess.run(nebresult_command, shell=True, capture_output=True, text=True)

            with open('neb.dat','r') as f:
                ptr_data = f.read()


        with open(output_file, "w") as fp:
            json.dump(res_data, fp, indent=4)

        return res_data, ptr_data

    def extract_images_value(self, file_path):
        pattern = re.compile(r'IMAGES\s*=\s*(\d+)')
        try:
            with open(file_path, 'r') as file:
                content = file.read()
                match = pattern.search(content)
                if match:
                    # 如果找到匹配项，返回IMAGES的值
                    return int(match.group(1))
        except FileNotFoundError:
            print("file path has not found")
        except Exception as e:
            print("err: {e}")
    
        return None  
