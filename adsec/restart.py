import apex
import fpop
import dpdata
import adsec
import os
import sys
from monty.serialization import loadfn
import glob
import time
import shutil
import re
import datetime
from typing import (
    Optional,
    Type,
    Union,
    List
)
import logging
import dflow
from dflow import (
    Step,
    upload_artifact,
    download_artifact,
    Workflow
)

from dflow.python.op import OP
from dflow.plugins.dispatcher import DispatcherExecutor
from dflow.python import upload_packages
from dflow import config, s3_config

from apex.config import Config

from fpop.vasp import RunVasp
from adsec.superop.modify_vasp import ModifyRunVasp
from adsec.utils.utils import json2dict, handle_prop_suffix,load_config_file
from adsec.superop.RelaxPropertySteps import RelaxPropertySteps
from adsec.superop.JointRelaxPropertySteps import JointRelaxPropertySteps
from adsec.flow import FlowGenerator

import multiprocess

upload_packages.append(__file__)


def restart(
        flow,
        restart_step,
        work_dir,
        props_param,
        wf_config,
        conf=config,
        s3_conf=s3_config,
        is_sub=False,
        labels=None,
):
    if is_sub:
        # reset dflow global config for sub-processes
        logging.info(msg=f'Sub-process working on: {work_dir}')
        config.update(conf)
        s3_config.update(s3_conf)
        logging.basicConfig(level=logging.INFO)
    else:
        cwd = os.getcwd()
        logging.info(msg=f'Working on: {work_dir}')
        flow_id = None
        flow_name = wf_config.flow_name
        submit_only = wf_config.submit_only

        if restart_step =='bulkstatic':
            flow_id = flow.restart_bulkstatic(
                upload_path=work_dir,
                download_path=work_dir,
                props_parameter=props_param,
                submit_only=submit_only,
                name=flow_name,
                labels=labels
            )
        elif restart_step == 'slabrelax':
            flow_id = flow.restart_slabrelax(
                upload_path=work_dir,
                download_path=work_dir,
                props_parameter=props_param,
                submit_only=submit_only,
                name=flow_name,
                labels=labels
            )
        elif restart_step == 'slabstatic':
            flow_id = flow.restart_slabstatic(
                upload_path=work_dir,
                download_path=work_dir,
                props_parameter=props_param,
                submit_only=submit_only,
                name=flow_name,
                labels=labels
            )
        elif restart_step == 'adslabrelax':
            flow_id = flow.restart_adslabrelax(
                upload_path=work_dir,
                download_path=work_dir,
                props_parameter=props_param,
                submit_only=submit_only,
                name=flow_name,
                labels=labels
            )
        elif restart_step == 'adslabrelax1':
            flow_id = flow.restart_adslabrelax1(
                upload_path=work_dir,
                download_path=work_dir,
                props_parameter=props_param,
                submit_only=submit_only,
                name=flow_name,
                labels=labels
            )
        elif restart_step == 'adslabrelax2':
            flow_id = flow.restart_adslabrelax2(
                upload_path=work_dir,
                download_path=work_dir,
                props_parameter=props_param,
                submit_only=submit_only,
                name=flow_name,
                labels=labels
            )
        elif restart_step == 'adslabstatic':
            flow_id = flow.restart_adslabstatic(
                upload_path=work_dir,
                download_path=work_dir,
                props_parameter=props_param,
                submit_only=submit_only,
                name=flow_name,
                labels=labels
            )

        elif restart_step == 'tsrun2':
            flow_id = flow.restart_tsrun2(
                upload_path=work_dir,
                download_path=work_dir,
                props_parameter=props_param,
                submit_only=submit_only,
                name=flow_name,
                labels=labels
            )

        os.chdir(cwd)


def restart_workflow(
        work_dirs: os.PathLike,
        props_parameter: dict,
        config_dict: dict,
        restart_step: str,
        flow_name: str,
        submit_only=False,
        labels=None
) -> [List[Step], List[str]]:

    run_op = RunVasp
    modify_run_op = ModifyRunVasp

    wf_config = Config(**config_dict)
    Config.config_dflow(wf_config.dflow_config_dict)
    Config.config_bohrium(wf_config.bohrium_config_dict)
    Config.config_s3(wf_config.dflow_s3_config_dict)

    if submit_only:
        print('Submit only mode activated, no auto-retrieval of results.')
        wf_config.submit_only = True

    if flow_name:
        wf_config.flow_name = flow_name

    make_image = wf_config.basic_config_dict["apex_image_name"]
    run_image = wf_config.basic_config_dict[f"vasp_image_name"]
    run_command = wf_config.basic_config_dict["vasp_run_command"]
    post_image = make_image
    group_size = wf_config.basic_config_dict["group_size"]
    pool_size = wf_config.basic_config_dict["pool_size"]
    executor = wf_config.get_executor(wf_config.dispatcher_config_dict)
    calculator= 'vasp'

    upload_python_packages = wf_config.basic_config_dict["upload_python_packages"]
    upload_python_packages.extend(list(apex.__path__))
    upload_python_packages.extend(list(fpop.__path__))
    upload_python_packages.extend(list(dpdata.__path__))
    upload_python_packages.extend(list(adsec.__path__))
    upload_python_packages.extend(list(multiprocess.__path__))


    flow = FlowGenerator(
        make_image=make_image,
        run_image=run_image,
        post_image=post_image,
        run_command=run_command,
        calculator=calculator,
        run_op=run_op,
        modify_run_op=modify_run_op,
        group_size=group_size,
        pool_size=pool_size,
        executor=executor,
        upload_python_packages=upload_python_packages
    )

     # submit the workflows
    work_dir_list = []
    for ii in work_dirs:
        glob_list = glob.glob(os.path.abspath(ii))
        work_dir_list.extend(glob_list)
        work_dir_list.sort()
    if len(work_dir_list) > 1:
        n_processes = len(work_dir_list)
        print(f'Submitting via {n_processes} processes...')
        pool = Pool(processes=n_processes)
        for ii in work_dir_list:
            res = pool.apply_async(
                restart,
                (flow,
                 restart_step,
                 ii,
                 props_parameter,
                 wf_config,
                 config,
                 s3_config,
                 True,
                 labels)
            )
        pool.close()
        pool.join()
    elif len(work_dir_list) == 1:
        restart(
            flow,
            restart_step,
            work_dir_list[0],
            props_parameter,
            wf_config,
            labels=labels,
        )
    else:
        raise NotADirectoryError('Empty work directory indicated, please check your argument')


def restart_from_args(
        parameters,
        config_file: os.PathLike,
        work_dirs,
        restart_step: str,
        flow_name: str = None,
        submit_only = True,
):
 
    #download_path = "/personal/save_result/slab_relax_res_0918_932"
    props_parameter = loadfn(parameters[0])
    config_dict = load_config_file(config_file)

    restart_workflow(
            work_dirs = work_dirs,
            props_parameter = props_parameter,
            config_dict = config_dict,
            restart_step = restart_step,
            flow_name = flow_name,
            submit_only=submit_only,
            labels = None
        )
