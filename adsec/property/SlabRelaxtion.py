import glob
import json
import logging
import os
import re
import itertools
import numpy as np
from monty.serialization import dumpfn, loadfn
from ase.io import read,write
from ase.build.tools import sort
from apex.core.calculator.lib import abacus_utils
from apex.core.calculator.lib import vasp_utils
from apex.core.calculator.lib import abacus_scf
import shutil

from adsec.property.Property import Property

from adsec.struct.defaults import slab_settings
from adsec.struct.atoms_operators import (make_slabs_from_bulk_atoms,
                               orient_atoms_upwards,
                               constrain_slab,
                               is_structure_invertible,
                               flip_atoms,
                               tile_atoms,
                               find_adsorption_sites,
                               find_bulk_cn_dict,
                               find_surface_atoms_indices,
                               find_adsorption_vector,
                               add_adsorbate_onto_slab)
from pymatgen.io.ase import AseAtomsAdaptor

from dflow.python import upload_packages
upload_packages.append(__file__)


class SlabRelaxtion(Property):
    def __init__(self, parameter, inter_param=None):

        parameter.setdefault("cal_setting", {})
        self.cal_setting = parameter["cal_setting"]
        self.parameter = parameter
        self.inter_param = inter_param if inter_param != None else {"type": "vasp"}

    def make_confs(self, path_to_work): # path_to_work = pre+'/conf/std_fcc/slab/relaxtion'
        path_to_work = os.path.abspath(path_to_work)
        if os.path.exists(path_to_work):
            logging.debug("%s already exists" % path_to_work)
        else:
            os.makedirs(path_to_work)
        #path_to_equi = os.path.abspath(path_to_equi)

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


        equi_poscar = os.path.join(grandparent_path,"bulk","static","POSCAR")  #type(path_to_work) is str

        if not os.path.isfile(equi_poscar):
            raise RuntimeError(
                "Can not find %s, please provide poscar first" % equi_poscar
            )
        bulk_atoms = read(equi_poscar)

       
        cwd = os.getcwd()
        task_list = []
        miller_indices_set = self.parameter["miller_indices_set"]
        #min_xy = self.parameter["min_xy"]
        Nmax = self.parameter["Nmax"]
        default_slab_setting = slab_settings()
        slab_generator_settings = default_slab_setting["slab_generator_settings"]
        get_slab_settings = default_slab_setting["get_slab_settings"]
        #slab_generator_settings["min_slab_size"] = self.parameter["min_slab_size"]
        slab_generator_settings["min_vacuum_size"] = self.parameter["min_vacuum_size"]

        min_xy_set = list(np.arange(6.0, 4.5, -0.2))
        min_slab_size_set = list(np.arange(9,7,-0.2))

        combined_list = list(itertools.product(min_xy_set, min_slab_size_set))
        ind_set = []
        number_set = []

        total_task_num = len(miller_indices_set)
        for task_num in range(total_task_num):
            miller_indices = tuple(miller_indices_set[task_num])

            run_flag = True
            for ind_ in range(len(combined_list)):

                min_xy,min_slab_size = combined_list[ind_]
                slab_structs = make_slabs_from_bulk_atoms(atoms=bulk_atoms,
                                                          miller_indices=miller_indices,
                                                          slab_generator_settings=slab_generator_settings,
                                                          get_slab_settings=get_slab_settings)
                
        
                struct = slab_structs[0]
                slab_atoms = AseAtomsAdaptor.get_atoms(struct)
                slab_atoms = orient_atoms_upwards(slab_atoms)
                    
                slab_atoms_constrained = constrain_slab(slab_atoms)
                slab_atoms_tiled, slab_repeat = tile_atoms(atoms=slab_atoms_constrained,
                                                           min_x= min_xy,
                                                           min_y= min_xy)

                ind_set.append(ind_)
                number_set.append(len(slab_atoms_tiled))

                if len(slab_atoms_tiled) <= Nmax:
                    run_flag = False
                    m,k,l = miller_indices
                    task_name = 'slab_{}{}{}'.format(m,k,l) 
                    output_task = os.path.join(path_to_work, task_name)
                    os.makedirs(output_task, exist_ok=True)
                    os.chdir(output_task) 
          
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
                    write("{}.vasp".format(task_name),sort(slab_atoms_tiled), vasp5=True)
                    write("POSCAR",sort(slab_atoms_tiled), vasp5=True)
                    task_list.append(output_task)  
                    os.chdir(cwd)
                    break
            if run_flag:
                target = Nmax
                min_diff = float('inf')  # 设置为无穷大
                closest_index = -1

                for index, value in enumerate(number_set):
                    diff = abs(value - target)  # 计算差的绝对值
                    if diff < min_diff:
                        min_diff = diff
                        closest_index = index
                min_xy,min_slab_size = combined_list[closest_index]
                slab_structs = make_slabs_from_bulk_atoms(atoms=bulk_atoms,
                                                          miller_indices=miller_indices,
                                                          slab_generator_settings=slab_generator_settings,
                                                          get_slab_settings=get_slab_settings)


                struct = slab_structs[0]
                slab_atoms = AseAtomsAdaptor.get_atoms(struct)
                slab_atoms = orient_atoms_upwards(slab_atoms)

                slab_atoms_constrained = constrain_slab(slab_atoms)
                slab_atoms_tiled, slab_repeat = tile_atoms(atoms=slab_atoms_constrained,
                                                           min_x= min_xy,
                                                           min_y= min_xy)

                m,k,l = miller_indices
                task_name = 'slab_{}{}{}'.format(m,k,l)
                output_task = os.path.join(path_to_work, task_name)
                os.makedirs(output_task, exist_ok=True)
                os.chdir(output_task)

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
                write("{}.vasp".format(task_name),sort(slab_atoms_tiled), vasp5=True)
                write("POSCAR",sort(slab_atoms_tiled), vasp5=True)
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
