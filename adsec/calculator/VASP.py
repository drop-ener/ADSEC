import os
import logging

from dpdata import LabeledSystem
from monty.serialization import dumpfn
from pymatgen.core.structure import Structure
from pymatgen.io.vasp import Incar, Kpoints

from apex.core.calculator.Task import Task
from apex.core.calculator.lib import vasp_utils
from apex.core.calculator.lib.vasp_utils import incar_upper
from apex.utils import sepline
from collections import Counter
from ase.io import read,write

from dflow.python import upload_packages
upload_packages.append(__file__)


class VASP(Task):
    def __init__(self, inter_parameter, path_to_poscar):
        self.inter = inter_parameter
        self.inter_type = inter_parameter["type"]
        self.incar = inter_parameter["incar"]
        self.potcar_prefix = inter_parameter.get("potcar_prefix", "")
        self.path_to_poscar = path_to_poscar

    def make_potential_files(self, output_dir):
        poscar = os.path.abspath(os.path.join(output_dir, "POSCAR"))
        pos_str = Structure.from_file(poscar)
        ele_pos_list_tmp = [ii.as_dict()["element"] for ii in pos_str.species]

        ele_pos_list = [ele_pos_list_tmp[0]]
        for ii in range(1, len(ele_pos_list_tmp)):
            if not ele_pos_list_tmp[ii] == ele_pos_list_tmp[ii - 1]:
                ele_pos_list.append(ele_pos_list_tmp[ii])

        def write_potcar(ele_list, potcar_path):
            with open(potcar_path, "w") as fp:
                for element in ele_list:
                    potcar_name = "POTCAR.{}".format(element)
                    potcar_file = os.path.join(self.potcar_prefix, potcar_name)
                    with open(potcar_file,"r") as fc:
                        fp.write(fc.read())
 
        potcar_path = output_dir+"/POTCAR"
        if not os.path.exists(potcar_path):
            write_potcar(ele_pos_list, potcar_path)
            
        dumpfn(self.inter, output_dir+"/inter.json", indent=4)

    def make_input_file(self, output_dir, task_param):

        poscar = os.path.abspath(os.path.join(output_dir, "POSCAR"))
        pos_str = Structure.from_file(poscar)
        ele_pos_list_tmp = [ii.as_dict()["element"] for ii in pos_str.species]
        ele_pos_list = [ele_pos_list_tmp[0]]
        for ii in range(1, len(ele_pos_list_tmp)):
            if not ele_pos_list_tmp[ii] == ele_pos_list_tmp[ii - 1]:
                ele_pos_list.append(ele_pos_list_tmp[ii])

        tmp_atoms = read(poscar)
        elements = tmp_atoms.get_chemical_symbols()
        element_count = Counter(elements)
        element_dict = dict(element_count)
        mag_elements = ['Ho', 'Pr', 'V', 'Cr', 'La', 'Tb', 'Tm', 'Nd', 'Ni', 'Er', 'Ce', 'W', 'Co', 'Fe', 'Gd', 'Dy', 'Yb', 'Lu', 'Mn', 'Mo', 'Pm', 'Sm', 'Eu']

        sepline(ch=output_dir)
        dumpfn(task_param, os.path.join(output_dir, "task.json"), indent=4)

        assert os.path.exists(self.incar), "no INCAR file for relaxation"
        relax_incar_path = os.path.abspath(self.incar)
        incar_relax = incar_upper(Incar.from_file(relax_incar_path))

        # deal with relaxation
        cal_setting = task_param["cal_setting"]

        # user input INCAR for APEX calculation
        if "input_prop" in cal_setting and os.path.isfile(cal_setting["input_prop"]):
            incar_prop = os.path.abspath(cal_setting["input_prop"])
            incar = incar_upper(Incar.from_file(incar_prop))
            logging.info(f"Will use user specified INCAR (path: {incar_prop}) for {prop_type} calculation")

        # revise INCAR based on the INCAR provided in the "interaction"
        else:
            incar = incar_relax       
            if "isif" in cal_setting:
                logging.info(
                    "%s setting ISIF to %s"
                    % (self.make_input_file.__name__, cal_setting["isif"])
                )
                incar["ISIF"] = cal_setting["isif"]
            if "nsw" in cal_setting:
                logging.info(
                    "%s setting NSW to %s"
                    % (self.make_input_file.__name__, cal_setting["nsw"])
                )
                incar["NSW"] = cal_setting["nsw"]

            if "ediff" in cal_setting:
                logging.info(
                    "%s setting EDIFF to %s"
                    % (self.make_input_file.__name__, cal_setting["ediff"])
                )
                incar["EDIFF"] = cal_setting["ediff"]

            if "ediffg" in cal_setting:
                logging.info(
                    "%s setting EDIFFG to %s"
                    % (self.make_input_file.__name__, cal_setting["ediffg"])
                )
                incar["EDIFFG"] = cal_setting["ediffg"]

            if "encut" in cal_setting:
                logging.info(
                    "%s setting ENCUT to %s"
                    % (self.make_input_file.__name__, cal_setting["encut"])
                )
                incar["ENCUT"] = cal_setting["encut"]

            if "kspacing" in cal_setting:
                logging.info(
                    "%s setting KSPACING to %s"
                    % (self.make_input_file.__name__, cal_setting["kspacing"])
                )
                incar["KSPACING"] = cal_setting["kspacing"]

            if "kgamma" in cal_setting:
                logging.info(
                    "%s setting KGAMMA to %s"
                    % (self.make_input_file.__name__, cal_setting["kgamma"])
                )
                incar["KGAMMA"] = cal_setting["kgamma"]
            if "ldipot" in cal_setting:
                logging.info(
                    "%s setting LDIPOT to %s"
                    % (self.make_input_file.__name__, cal_setting["ldipot"])
                )
                incar["LDIPOT"] = cal_setting["ldipot"]
            if "idipot" in cal_setting:
                logging.info(
                    "%s setting IDIPOT to %s"
                    % (self.make_input_file.__name__, cal_setting["idipot"])
                )
                incar["IDIPOT"] = cal_setting["idipot"]
            if "isym" in cal_setting:
                logging.info(
                    "%s setting isym to %s"
                    % (self.make_input_file.__name__, cal_setting["isym"])
                )
                incar["ISYM"] = cal_setting["isym"]
            if "symprec" in cal_setting:
                logging.info(
                    "%s setting symprec to %s"
                    % (self.make_input_file.__name__, cal_setting["symprec"])
                )
                incar["SYMPREC"] = cal_setting["symprec"]
            if "lreal" in cal_setting:
                logging.info(
                    "%s setting lreal to %s"
                    % (self.make_input_file.__name__, cal_setting["lreal"])
                )
                incar["LREAL"] = cal_setting["lreal"]
            if "ibrion" in cal_setting:
                logging.info(
                    "%s setting ibrion to %s"
                    % (self.make_input_file.__name__, cal_setting["ibrion"])
                )
                incar["IBRION"] = cal_setting["ibrion"]
            if "gga" in cal_setting:
                logging.info(
                    "%s setting gga to %s"
                    % (self.make_input_file.__name__, cal_setting["gga"])
                )
                incar["GGA"] = cal_setting["gga"]
            if "ismear" in cal_setting:
                logging.info(
                    "%s setting ismear to %s"
                    % (self.make_input_file.__name__, cal_setting["ismear"])
                )
                incar["ISMEAR"] = cal_setting["ismear"]
            if "sigma" in cal_setting:
                logging.info(
                    "%s setting sigma to %s"
                    % (self.make_input_file.__name__, cal_setting["sigma"])
                )
                incar["SIGMA"] = cal_setting["sigma"]
            if "ispin" in cal_setting:
                logging.info(
                    "%s setting ispin to %s"
                    % (self.make_input_file.__name__, cal_setting["ispin"])
                )
                incar["ISPIN"] = cal_setting["ispin"]
                if cal_setting["ispin"] == 2:
                    magmom_content = ""
                    for ele in ele_pos_list:
                        if ele in mag_elements:
                            indi_mag_content = "{}*3 ".format(element_dict[ele])
                        else:
                            indi_mag_content = "{}*0.6 ".format(element_dict[ele])
                        magmom_content += indi_mag_content
                    incar["MAGMOM"] = magmom_content
            if "magmom" in cal_setting:
                logging.info(
                    "%s setting magmom to %s"
                     % (self.make_input_file.__name__, cal_setting["magmom"])
                )
                incar["MAGMOM"] = cal_setting["magmom"]
            if "ivdw" in cal_setting:
                logging.info(
                    "%s setting ivdw to %s"
                     % (self.make_input_file.__name__, cal_setting["ivdw"])
                )
                incar["IVDW"] = cal_setting["ivdw"]
            if "ichain" in cal_setting:
                logging.info(
                    "%s setting ichain to %s"
                     % (self.make_input_file.__name__, cal_setting["ichain"])
                )
                incar["ICHAIN"] = cal_setting["ichain"]
            if "images" in cal_setting:
                logging.info(
                    "%s setting images to %s"
                     % (self.make_input_file.__name__, cal_setting["images"])
                )
                incar["IMAGES"] = cal_setting["images"]
            if "iopt" in cal_setting:
                logging.info(
                    "%s setting iopt to %s"
                     % (self.make_input_file.__name__, cal_setting["iopt"])
                )
                incar["IOPT"] = cal_setting["iopt"]
            if "lclimb" in cal_setting:
                logging.info(
                    "%s setting lclimb to %s"
                     % (self.make_input_file.__name__, cal_setting["lclimb"])
                )
                incar["LCLIMB"] = cal_setting["lclimb"]
            if "potim" in cal_setting:
                logging.info(
                    "%s setting potim to %s"
                     % (self.make_input_file.__name__, cal_setting["potim"])
                )
                incar["POTIM"] = cal_setting["potim"]
            if "nfree" in cal_setting:
                logging.info(
                    "%s setting nfree to %s"
                     % (self.make_input_file.__name__, cal_setting["nfree"])
                )
                incar["NFREE"] = cal_setting["nfree"]


        kspacing = incar.get("KSPACING", None)
        if kspacing is None:
            raise RuntimeError("KSPACING must be given in INCAR")
        kgamma = incar.get("KGAMMA", False)

        self._write_incar_and_kpoints(incar, output_dir, kspacing, kgamma)

    def _write_incar_and_kpoints(self, incar, output_dir, kspacing, kgamma):
        incar.write_file(os.path.join(output_dir, "INCAR"))
        #self._link_file("../INCAR", os.path.join(output_dir, "INCAR"))
        ret = vasp_utils.make_kspacing_kpoints(self.path_to_poscar, kspacing, kgamma)
        Kpoints.from_str(ret).write_file(os.path.join(output_dir, "KPOINTS"))
    
    def _link_file(self, target, link_name):
        if not os.path.islink(link_name):
            os.symlink(target, link_name)
        elif os.readlink(link_name) != target:
            os.remove(link_name)
            os.symlink(target, link_name)

    def compute(self, output_dir):
        outcar = os.path.join(output_dir, "OUTCAR")
        if not os.path.isfile(outcar):
            logging.warning("cannot find OUTCAR in " + output_dir + " skip")
            return None
        
        #stress = []
        #with open(outcar, "r") as fin:
        #    lines = fin.read().split("\n")
        #for line in lines:
        #    if "in kB" in line:
        #        stress_xx = float(line.split()[2])
        #        stress_yy = float(line.split()[3])
        #        stress_zz = float(line.split()[4])
        #        stress_xy = float(line.split()[5])
        #        stress_yz = float(line.split()[6])
        #        stress_zx = float(line.split()[7])
        #        stress.append([])
        #        stress[-1].append([stress_xx, stress_xy, stress_zx])
        #        stress[-1].append([stress_xy, stress_yy, stress_yz])
        #        stress[-1].append([stress_zx, stress_yz, stress_zz])

        ls = LabeledSystem(outcar)
        outcar_dict = ls.as_dict()
        #outcar_dict["data"]["stress"] = {
        #    "@module": "numpy",
        #    "@class": "array",
        #    "dtype": "float64",
        #    "data": stress,
        #}

        return outcar_dict

    def forward_files(self, property_type="relaxation"):
        return ["INCAR", "POSCAR", "KPOINTS", "POTCAR"]

    def forward_common_files(self, property_type="relaxation"):
        return []
    def backward_files(self, property_type="relaxation"):
        if property_type == "phonon":
            return ["OUTCAR", "outlog", "CONTCAR", "OSZICAR", "XDATCAR", "vasprun.xml"]
        else:
            return ["OUTCAR", "outlog", "CONTCAR", "OSZICAR", "XDATCAR"]
