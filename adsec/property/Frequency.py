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


class Frequency(Property):
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


        path_to_nebfile = os.path.join(path_to_work,'neb.dat')

        if not os.path.isfile(path_to_nebfile):
            raise RuntimeError(
                "Can not find %s" % path_to_nebfile
            )


        file_nums = []
        energy_sets =[]
        with open(path_to_nebfile, 'r') as file:
            for line in file:
                columns = re.split(r'\s+', line.strip())
                column_data = columns[0]
                file_nums.append(columns[0])
                energy_sets.append(float(columns[2]))
        
        max_value = max(energy_sets)
        
        max_index = energy_sets.index(max_value)
        if max_index==0 or max_index== int(file_nums[-1]):
            raise RuntimeError('Transition states should not be the initial structure and the final structure')
                
        ts_filename = "0{}".format(file_nums[max_index])
        ts_poscar = os.path.join(path_to_work,ts_filename,"CONTCAR")

        output_task= os.path.join(path_to_work,'frequency')
        os.makedirs(output_task, exist_ok=True)
   
        os.chdir(output_task)
        shutil.copy(ts_poscar, './POSCAR')

        task_list.append(output_task)
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
        path_to_prop = os.path.abspath(path_to_prop)
        path_to_outcar = os.path.join(path_to_prop,'frequency/OUTCAR')

        subprocess.call("grep 'THz' {} >freq_res".format(path_to_outcar),shell=True)

    def _compute_lower(self, output_file, all_tasks, all_res):
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
