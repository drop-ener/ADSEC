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


class TransitionState(Property):
    def __init__(self, parameter, inter_param=None):

        parameter.setdefault("cal_setting", {})
        self.cal_setting = parameter["cal_setting"]
        self.parameter = parameter
        self.inter_param = inter_param if inter_param != None else {"type": "vasp"}

        #if "input_prop" in self.cal_setting and os.path.isfile(self.cal_setting["input_prop"]):
        #    incar_file_path = os.path.abspath(self.cal_setting["input_prop"])
        #    self.images_val = self.extract_images_value(incar_file_path)
       
        self.images_val = self.cal_setting['images']
        vtst_path = os.path.abspath(self.parameter['vtst_path'])
        self.vtst_path = vtst_path

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

        parent_path = os.path.dirname(path_to_work)  #get the path of confs/std_bcc
        grandparent_path = os.path.dirname(parent_path) # confs/
        confs_path = os.path.dirname(grandparent_path)

        script_path = os.path.join(confs_path,'vtstscripts')
        current_path = os.environ.get('PATH', '')

        # 检查文件夹路径是否已经在PATH中
        if script_path not in current_path:
            # 将文件夹路径添加到PATH环境变量
            os.environ['PATH'] = f"{script_path}:{current_path}"

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

        output_task = path_to_work
        #os.makedirs(output_task, exist_ok=True)
        os.chdir(output_task)

        path_to_ini = os.path.join(path_to_work,'init_struct')
        path_to_fin = os.path.join(path_to_work,'final_struct')
        ini_outcar = os.path.join(path_to_ini,'OUTCAR')
        fin_outcar = os.path.join(path_to_fin,'OUTCAR')

        shutil.copy(ini_contcar, './ini_POSCAR')
        shutil.copy(fin_contcar,'./fin_POSCAR')

        dist_command = 'dist.pl ini_POSCAR  fin_POSCAR'
        dist_result = subprocess.run(dist_command, shell=True, capture_output=True, text=True)
        logging.debug('dist.pl output:{}'.format(dist_result.stdout))
        dist_val = float(dist_result.stdout)
        if dist_val > 5:
            logging.debug('The initial structure and the final structure differ too much, with a distance value of {}'.format(dist_val))
        
        makeneb_command = 'nebmake.pl ini_POSCAR fin_POSCAR {}'.format(self.images_val)
        #command = 'dist.pl ini/POSCAR  fin/POSCAR'
        #makeneb_result = subprocess.run(makeneb_command, shell=True, capture_output=True, text=True)
        subprocess.call("nebmake.pl ini_POSCAR fin_POSCAR {}".format(self.images_val),shell=True)

        shutil.copy(ini_outcar, '00/OUTCAR')
        shutil.copy(fin_outcar, '0{}/OUTCAR'.format(self.images_val+1))

        POSCAR = "POSCAR"

        task_list.append(output_task)
        #os.symlink(os.path.relpath(equi_contcar), POSCAR_orig)
        #os.symlink(os.path.relpath(ini_contcar), POSCAR)
        shutil.copy(ini_contcar,POSCAR)
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
        cwd = os.getcwd()
        path_to_prop = os.path.abspath(path_to_prop)
        parent_path = os.path.dirname(path_to_prop)  #get the path of confs/std_bcc
        grandparent_path = os.path.dirname(parent_path) # confs/
        confs_path = os.path.dirname(grandparent_path)

        script_path = os.path.join(confs_path,'vtstscripts')
        current_path = os.environ.get('PATH', '')

        # 检查文件夹路径是否已经在PATH中
        if script_path not in current_path:
            # 将文件夹路径添加到PATH环境变量
            os.environ['PATH'] = f"{script_path}:{current_path}"

        os.chdir(path_to_prop)
        nebresult_command = "nebresults.pl"
        nebresult = subprocess.run(nebresult_command, shell=True, capture_output=True, text=True)

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
