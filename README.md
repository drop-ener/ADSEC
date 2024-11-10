# ADSEC: ADSorption Energy Calculation

[ADSEC](https://github.com/drop-ener/ADSEC "ADSEC"): ADSorption Energy Calculation is a workflow used to compute the adsorption energies of relevant species and the energy barriers of transition states in catalysis, with the primary first-principles calculation software used in the current workflow being VASP.

## v.0.1.0 Main Features
- One can start from the bulk structure and calculate the adsorption energy of adsorbates on specified Miller index facets at specific sites (ontop/bridge/hollow) based on input parameters. The adsorbates currently considered mainly include H，CO，CO2，COOH，HCOO and HCOOH.
- One can calculate the transition state and the corresponding energy barrier between the specified initial and final structures.

## ADSEC Bohrium App
For easier calculation of adsorption energies and transition states using ADSEC, a web-based Bohrium App is under development.


## Table of Contents
- [ADSEC: ADSorption Energy Calculation](#adsec-adsorption-energy-calculation)
  - [v0.1.0 Main Features](#v01-main-features)
  - [ADSEC Bohrium App](#adsec-bohrium-app)
  - [Table of Contents](#table-of-contents)
  - [1. Overview](#1-overview)
  - [2. Quick Start](#2-quick-start)
    - [2.1. Install ADSEC](#21-install-adsec)
    - [2.2. Submission Examples](#22-submission-examples)
      - [2.2.1. Submit to the Bohrium](#233-submit-to-the-bohrium)
  - [3. Documents & User Guide](#3-documents--user-guide)
    - [3.1. Before Submission](#31-before-submission)
      - [3.1.1. Global Setting](#311-global-setting)
      - [3.1.2. Calculation Parameters](#312-calculation-parameters)
        - [3.1.2.1. Bulk](#3121-bulk)
        - [3.1.2.2. Slab](#3122-slab)
        - [3.1.2.3. Adslab](#3123-adslab)
        - [3.1.2.4. molecular](#3124-molecular)
        - [3.1.2.5. ts](#3125-ts)
    - [3.2. Submission](#32-submission)
      - [3.2.1. Workflow Submission](#321-workflow-submission)
      - [3.2.2. Workflow Inquiry \& Operations](#322-workflow-inquiry--operations)
      - [3.2.3. Run Individual Step](#323-run-individual-step)
    - [3.3. After Submission](#33-after-submission)
      - [3.3.1. Retrieve Results Manually](#331-retrieve-results-manually)

## 1. Overview
The calculation of adsorption energy plays a crucial role in the fields of materials science and surface chemistry, as it is a physical quantity that describes the strength of the interaction between the adsorbate and the adsorbent, with its magnitude directly reflecting the strength of the adsorption effect. However, the calculation process for adsorption energy is quite cumbersome, involving multiple structural relaxations and static calculations of bulk phases, different crystal facets, and various adsorption configurations. Therefore, we have developed a workflow called ADSEC based on [dflow](http://gitub.com/deepmodeling/dflow "dflow") and [APEX ](https://github.com/deepmodeling/APEX "APEX ")workflows, leveraging the advantages of cloud-native workflows for calculating adsorption energy.

The comprehensive architecture of ADSEC is demonstrated below:


ADSEC consists of  various types of pre-defined **workflow** that users can submit: `BulkRelaxtion`, `BulkStatic `, `SlabRelaxtion`, `SlabStatic `,`AdRelaxtion`, `Step1AdSlabRelaxtion`, `Step2AdSlabRelaxtion `,`AdStatic `,   and `all`. The corresponding relaxation and static workflows above each include three sequential steps: Make, Run, and Post. The `all` workflow encompass the entire process from bulk relaxation and static calculations to slab relaxation and static calculations, and then to adsorption configuration relaxation and static calculations. 

In all relaxation and static calculation workflows, the `Make` step prepares the corresponding computational tasks. These tasks are then transferred to the `Run` step that is responsible for task dispatch, calculation monitoring, and retrieval of completed tasks (implemented through the [DPDispatcher](https://github.com/deepmodeling/dpdispatcher/tree/master) plugin). Upon completion of all tasks, the `Post` step is initiated to collect data and obtain the desired property results.


ADSEC currently supports the following types of calculations:

* Bulk structure relaxation and static calculations.
* Slab structure relaxation and static calculations.
* Adslab structure relaxation and static calculations.
* Molecular structure relaxation and static calculations.
* Transition state structure calculation

Currently, ADSEC supports first-principles calculations using the **VASP** software.

## 2. Quick Start
### 2.1. Install APEX
The current approach is to intall from the source code. Firstly clone the code from repository:
```shell
git clone https://github.com/drop-ener/ADSEC.git
```
then install APEX by:
```shell
cd ADSEC
pip install .
```
### 2.2. Submission Examples
We present several case studies as introductory illustrations of ADSEC, tailored to distinct user scenarios. For our demonstration, we will utilize a [Al_slab_001_ads_H_ontop1_example](./examples/Al_slab_001_ads_H_ontop1) to  calculate the adsorption energy of hydrogen (H) on the top site of the 001 face of aluminum (Al) metal. To begin, we will examine the files prepared within the working directory for this specific case.

```
Al_slab_001_ads_H_ontop1_example
├── confs
│   ├── std-Al
│   │   └── POSCAR
├── vasp_input
│   ├── potcar
│   │   └── POTCAR.XX
│   │── INCAR
├── global_bohrium.json
├── param_ads.json
```

Here we h `global_bohrium.json`, along with a folder confs `confs` containing the bulk Al structure and VASP-related input files for the calculation.

#### 2.2.1. Submit to the Bohrium
The most efficient method for submitting an APEX workflow is through the pre-built execution environment of Argo on the [Bohrium cloud platform](https://bohrium.dp.tech). This is especially convenient and robust for massive task-intensive workflows running concurrently. It is necessary to create a **Bohrium account** before running. Below is an example of a global.json file for this approach.

```json
{
    "dflow_host": "https://workflows.deepmodeling.com",
    "k8s_api_server": "https://workflows.deepmodeling.com",
    "email": "YOUR_EMAIL",
    "password": "YOUR_PASSWD",
    "program_id": 1234,
    "group_size": 1,
    "apex_image_name":"registry.dp.tech/dptech/prod-11045/apex-dependency:1.2.0",
    "vasp_image_name":"registry.dp.tech/dptechl/oneapi/setvars.sh && ulimit -s     unlimited && mpirun -n 48 /opt/vasp.5.4.4/bin/vasp_std \"",
    "batch_type": "Bohrium",
    "context_type": "Bohrium",
    "scass_type":"c48_m192_cpu"
}
```
Then, one can submit a relaxation workflow via:
```shell
adsec submit param_all.json -c global_bohrium.json -f all
```
Remember to replace `email`, `password` and `program_id` of your own before submission. As for image, you can either build your own or use public images from Bohrium or pulling from the Docker Hub. Once the workflow is submitted, one can monitor it at https://workflows.deepmodeling.com.

## 3. Documents & User Guide

### 3.1. Before Submission
In ADSEC, there are **three essential components** required before submitting a workflow:
* **A global JSON file** containing parameters for configuring `dflow` and other global settings (default: "./global.json")
* **A calculation JSON file** containing parameters associated with calculations 

* **A work directory** consists of necessary files specified in the above JSON files, along with initial structures (default: "./")


#### 3.1.1. Global Setting
The instructions regarding global configuration, [dflow](https://github.com/deepmodeling/dflow), and [DPDispatcher](https://github.com/deepmodeling/dpdispatcher/tree/master) specific settings must be stored in a JSON format file. The table below describes some crucial keywords, classified into three categories: **Basic config**, **Dflow config**  (See [dflow document](https://deepmodeling.com/dflow/dflow.html) for more detail) and **Dispatcher config**(One may refer to [DPDispatcher's documentation](https://docs.deepmodeling.com/projects/dpdispatcher/en/latest/index.html) for details).

#### 3.1.2. Calculation Parameters
The parameter file for the corresponding adsorption energy calculation is as follows.

* **Structure and pseudopotential settings**
```json
 {
    "structures":    ["confs/std-*"],
    "include": "all",
    "exclude":[],
    "interaction": {
        "type":          "vasp",
        "incar":         "vasp_input/INCAR",
        "potcar_prefix": "vasp_input/potcar"},
```
* **Bulk-related parameters**
 ```json
 "bulk":
    { "relaxtion": {
        "type":      "bulk_relax",
        "cal_setting":   {"isif":            3,
                          "ispin":           1,
                          "ibrion":          2,
                          "nsw":             500,
                          "ediff":           1e-5,
                          "ediffg":          -0.03,
                          "encut":           500,
                          "kspacing":        0.25,
                          "kgamma":          false,
                          "gga":             "RP",
                          "ismear":           1,
                          "sigma":           0.5}

        },
      "static": {
        "type":      "bulk_sp",
        "cal_setting":   {"isif":            0,
                          "ispin":           1,
                          "nsw":             0,
                          "ediff":           1e-5,
                          "encut":           500,
                          "kspacing":        0.25,
                          "kgamma":          false,
                          "gga":             "RP",
                          "ismear":           1,
                          "sigma":           0.5}

        }
  },
```
* **Slab-related parameters**
 ```json
    "slab":
    { "relaxtion": {
        "type":      "slab_relax",
        "confs_from_previous":               false,
        "start_confs":   ["confs_test/std-*"],
        "miller_indices_set": [[0,0,1]],
        "min_vacuum_size": 20,
        "Nmax":         50,
        "cal_setting":   {"isif":            2,
                          "ispin":           1,
                          "ibrion":          2,
                          "nsw":             500,
                          "ediff":           1e-5,
                          "ediffg":          -0.03,
                          "encut":           400,
                          "kspacing":        0.3,
                          "kgamma":          false,
                          "lreal":           "auto",
                          "ldipot":          true,
                          "idipot":           3,
                          "gga":             "RP",
                          "ismear":           1,
                          "sigma":           0.5}

        },
       "static": {
        "type":      "slab_sp",
        "miller_indices_set": [[0,0,1],[0,1,1]],
        "cal_setting":   {"isif":            0,
                          "ispin":           1,
                          "nsw":             0,
                          "ediff":           1e-5,
                          "encut":           400,
                          "kspacing":        0.3,
                           "lreal":          "auto",
                          "kgamma":          false,
                          "ldipot":          true,
                          "idipot":           3,
                          "gga":             "RP",
                          "ismear":           1,
                          "sigma":           0.5}

        }
  },
```
* **Adslab-related parameters**
 ```json
   "adslab":
    { "relaxtion": {
        "type":      "adslab_relax",
        "confs_from_previous":               true,
        "max_relax_time": 30000,
        "miller_indices_set": [[0,0,1]],
        "positions": ["ontop_1"],
        "adsorbate_names": ["H"],
        "mol_from_file": false,
        "mol_structures":    ["mol_confs/std-*"],
        "cal_setting":   {"isif":            2,
                          "ispin":           1,
                          "ibrion":          2,
                          "nsw":             500,
                          "ediff":           1e-5,
                          "ediffg":          -0.03,
                          "encut":           400,
                          "kspacing":        0.3,
                          "kgamma":          false,
                          "lreal":           "auto",
                          "ldipot":          true,
                          "idipot":           3,
                          "gga":             "RP",
                          "ismear":           1,
                          "sigma":           0.5}

        },
     "relax_step": true,
     "relaxtion_1": {
        "type":      "adslab_relax_1",
        "confs_from_previous":               false,
        "start_confs": ["confs/std-*"],
        "max_relax_time": 43200,
        "miller_indices_set": [[0,0,1]],
        "positions": ["ontop_1"],
        "adsorbate_names": ["H"],
        "mol_from_file": false,
        "mol_structures":    ["mol_confs/std-*"],
        "cal_setting":   {"isif":            2,
                          "ispin":           1,
                          "ibrion":          2,
                          "nsw":             500,
                                  "sigma":           0.5}

        },
        "relaxtion_2": {
        "type":      "adslab_relax_2",
        "confs_from_previous":               true,
        "max_relax_time": 432000,
        "miller_indices_set": [[0,0,1]],
        "positions": ["ontop_1"],
        "adsorbate_names": ["H"],
        "filter_flag":                       false,
        "cal_setting":   {"isif":            2,
                          "ispin":           1,
                          "ibrion":        a":             "RP",
                          "ismear":           1,
                          "sigma":           0.5}

        },
     "static": {
        "type":      "adslab_sp",
        "confs_from_previous":               true,
        "miller_indices_set": [[0,0,1]],
        "positions": ["ontop_1"],
        "adsorbate_names": ["H"],
        "filter_flag":                       false,
        "cal_setting":   {"isif":            0,
                          "ispin":           1,
                                          "sigma":           0.5}

        }
    },
```
* **molecular-related parameters**
 ```json
 "molecular":
    { "relaxtion": {
        "mol_structures":    ["mol_confs/std-*"],
        "type":      "bulk_relax",
        "cal_setting":   {"isif":            2,
                          "ibrion":          2,
                          "nsw":             500,
                          "ediff":           1e-5,
                          "ediffg":          -0.03,
                          "encut":                      "kgamma":          false,
                          "gga":             "RP"}

        }
  }
}
```
### 3.2. Submission
#### 3.2.1. Workflow Submission
ADSEC will execute a specific dflow workflow upon each invocation of the command in the format: `adsec submit [-h] [-c [CONFIG]] [-w WORK [WORK ...]] [-s] [-f {'mol','bulkrelax', 'bulkstatic', 'slabrelax','slabstatic','adslabrelax','adslabrelax1','adslabrelax2','adslabstatic','all','ts','tsrun1','tsrun2','tsrun3'}] parameter`. The type of workflow and calculation method will be automatically determined by ADSEC based on the parameter file provided by users. Additionally, users can specify the **workflow type**, **configuration JSON file**, and **work directory** through an optional argument (Run `adsec submit -h` for further help). Here is an example to submit a `all` workflow:
```shell
adsec submit param_ads.json  -c ./global_bohrium.json  -f all 
```
if no config JSON (following `-c`) and work directory (following `-w`) is specified, `./global.json` and `./` will be passed as default values respectively.

#### 3.2.2. Workflow Inquiry & Operations
APEX supports several commonly used `dflow` inquiry and operation commands as listed below:
- `list`: List all workflows information
- `get`: Get detailed information of a workflow
- `getsteps`: Get detailed steps information of a workflow 
- `getkeys`: Get keys of steps from a workflow
- `delete`: Delete a workflow
- `resubmit`: Resubmit a workflow
- `retry`: Retry a workflow
- `resume`: Resume a workflow
- `stop`: Stop a workflow
- `suspend`: Suspend a workflow
- `terminate` Terminate a workflow


#### 3.2.3. Run Individual Step 
ADSEC also provides a **single-step test mode**, which can run `bulkrelax`, `bulkstatic`, `slabrelax`,`slabstatic`,`adslabrelax`, and `adslabstatic`step individually. **Please note that one needs to run commands under the work directory by setting the workflow type.**
User can invoke them by format of `adsec submit [-h] [-c [CONFIG]] parameter -f {'bulkrelax', 'bulkstatic', 'slabrelax','slabstatic','adslabrelax','adslabstatic'}` (Run `adsec run -h` for help). 


### 3.3. After Submission

#### 3.3.1. Download Results Manually

Sometimes when results auto-retrieving fails after workflows finish, you may try to retrieve completed test results manually by the `download` command with a specific workflow `ID` (or target `work_dir`) provided:
```shell
adsec download [-h] [-i ID] [-w WORK] [-c [CONFIG]]
```
where the `WORK` defaults to be `./`, and the `CONFIG` JSON (default: `config.json`) is used to connect to the remote storage.
