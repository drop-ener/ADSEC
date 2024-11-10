import glob
import json
import logging
import os
import re
import numpy as np
from monty.serialization import dumpfn, loadfn
from ase.io import read,write
from ase.build.tools import sort
import shutil

from apex.core.calculator.lib import abacus_utils
from apex.core.calculator.lib import vasp_utils
from apex.core.calculator.lib import abacus_scf

from dflow.python import upload_packages

from adsec.property.Property import Property
from adsec.utils.utils import list_directories_with_subdirectories,adsorbate_from_file

from adsec.struct import defaults
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
                               add_adsorbate_onto_slab,
                               sorted_site_by_dist)
from pymatgen.io.ase import AseAtomsAdaptor

from dflow.python import upload_packages
upload_packages.append(__file__)


class Step1AdSlabRelaxtion(Property):
    def __init__(self, parameter, inter_param=None):

        parameter.setdefault("cal_setting", {})
        self.cal_setting = parameter["cal_setting"]
        self.parameter = parameter
        self.inter_param = inter_param if inter_param != None else {"type": "vasp"}
        self.mol_from_file = parameter["mol_from_file"]
        self.mol_structures = parameter["mol_structures"]

    def make_confs(self, path_to_work): # path_to_work = pre+'/conf/std_fcc/adslab/relax'
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
            adslab_names = []
            for entry in os.listdir(grandparent_path):
                full_path = os.path.join(grandparent_path, entry)
                if os.path.isfile(full_path):
                    if 'ads' in entry:
                        adslab_names.append(entry)
            cwd = os.getcwd()
            task_list = []
            for vaspfile in adslab_names:
                task_name = vaspfile.split('.')[0]
                path_to_poscar = os.path.join(grandparent_path,vaspfile)
                if not os.path.isfile(path_to_poscar):
                    raise RuntimeError("Can not find %s, please provide poscar first" % path_to_poscar)
                output_task = os.path.join(path_to_work, task_name, "relax_1")
                os.makedirs(output_task, exist_ok=True)
                os.chdir(output_task)

                atoms = read(path_to_poscar)
                write("POSCAR",sort(atoms), vasp5=True)
                task_list.append(output_task)
                os.chdir(cwd)
            return  task_list
     
        #equi_poscar = os.path.join(grandparent_path, "POSCAR")  #type(path_to_work) is str
        slab_static_path = os.path.join(grandparent_path,"slab","static")

        if self.mol_from_file:
            thirdparent_path = os.path.dirname(grandparent_path)
            fourthparent_path = os.path.dirname(thirdparent_path)
            mol_struct_path = os.path.join(fourthparent_path,self.mol_structures[0].split('/')[0])
        #if not os.path.isfile(equi_poscar):
        #    raise RuntimeError(
        #        "Can not find %s, please provide slab struct first" % equi_poscar
        #    )

        bulk_poscar = os.path.join(grandparent_path, "bulk","static","POSCAR")
        if not os.path.isfile(bulk_poscar):
            raise RuntimeError(
                "Can not find %s, please provide bulk struct first" % bulk_poscar
            )

        cwd = os.getcwd()

        bulk_atoms = read(bulk_poscar)
        bulk_cn_dict = find_bulk_cn_dict(bulk_atoms)

        ADSLAB_SETTINGS = defaults.adslab_settings()
        ADSORBATES = defaults.adsorbates()
        rotation =  ADSLAB_SETTINGS["rotation"]

        positions = self.parameter["positions"]
        adsorbate_names = self.parameter["adsorbate_names"]        
        #adsorbate_name = "CO"

        task_list = []

        slab_static_dir = list_directories_with_subdirectories(slab_static_path)

        for slab_index in range(len(slab_static_dir)):
            slab_miller_path = slab_static_dir[slab_index]  # /personal/hppo/adsflow/confs/std-bcc/slab/static/slab_001
            slab_name = slab_miller_path.split("/")[-1]
            if not slab_name.startswith("slab_"):
                continue
            slab_poscar = os.path.join(slab_miller_path,"POSCAR")
            if not os.path.isfile(slab_poscar):
                raise RuntimeError(
                    "Can not find %s, please provide bulk struct first" % slab_poscar
                )
            slab_atoms = read(slab_poscar)
            supercell_slab_atoms = slab_atoms.repeat((2, 2, 1))
            surface_atoms_list = find_surface_atoms_indices(bulk_cn_dict, supercell_slab_atoms)

            sites_dict = find_adsorption_sites(slab_atoms)
            sites = sites_dict["all"]       
    
            for adsorption_site_name in positions:  # [ontop,bridge,hollow]
    
                site_indice = int(adsorption_site_name.split("_")[-1])-1
                sites = sites_dict[adsorption_site_name.split("_")[0]]
                num_sites = len(sites)
                if num_sites >= 1:
                    sorted_sites = sorted_site_by_dist(sites,slab_atoms)
                    if site_indice <= num_sites:
                        adsorption_site = sorted_sites[site_indice]
                    else:
                        raise RuntimeError("number of adsorption site is %s, site_indice is greater than it" % str(site_indice))

                    adsorption_vector = find_adsorption_vector(bulk_cn_dict, supercell_slab_atoms,
                                                        surface_atoms_list, adsorption_site)
    
                    for adsorbate_name in adsorbate_names:
                        if self.mol_from_file:
                            adsorbate_poscar = os.path.join(mol_struct_path,"std-{}".format(adsorbate_name),"molecular/static/POSCAR")

                            if not os.path.isfile(adsorbate_poscar):
                                raise RuntimeError("Can not find %s, please provide molecular struct first" % adsorbate_poscar)
                            adsorbate = adsorbate_from_file(adsorbate_poscar)
                        else:
                            adsorbate = ADSORBATES[adsorbate_name].copy()
                        adsorbate.euler_rotate(**rotation)
                        aligned_adsorbate = adsorbate.copy()
                        aligned_adsorbate.rotate(np.array([0., 0., 1.]), adsorption_vector)
                        adslab = add_adsorbate_onto_slab(adsorbate=aligned_adsorbate,
                                                         slab=slab_atoms,
                                                         site=adsorption_site)
    
                        task_name = "{}_ads_{}_on_{}".format(slab_name,adsorbate_name,adsorption_site_name)
                        output_task = os.path.join(path_to_work, task_name,"relax_1")
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
                        write("{}.vasp".format(task_name),sort(adslab), vasp5=True)
                        write("POSCAR",sort(adslab), vasp5=True)
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
