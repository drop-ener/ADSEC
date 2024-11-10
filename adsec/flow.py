import os
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
import dflow
from dflow import (
    Step,
    upload_artifact,
    download_artifact,
    Workflow
)
from dflow.python.op import OP
from dflow.plugins.dispatcher import DispatcherExecutor


from apex.config import Config


from adsec.utils.utils import json2dict, handle_prop_suffix,load_config_file
from adsec.superop.property_ops import PropsMake, PropsPost
from adsec.superop.RelaxPropertySteps import RelaxPropertySteps
from adsec.superop.JointRelaxPropertySteps import JointRelaxPropertySteps
from adsec.superop.AllRelaxStaticSteps import AllRelaxStaticSteps
from adsec.superop.RelaxtionSteps import RelaxtionSteps
from adsec.superop.StaticSteps import StaticSteps
from adsec.superop.RestartbulkstaticSteps import RestartbulkstaticSteps
from adsec.superop.RestartslabstaticSteps import RestartslabstaticSteps
from adsec.superop.RestartslabrelaxSteps import RestartslabrelaxSteps
from adsec.superop.RestartadslabstaticSteps import RestartadslabstaticSteps
from adsec.superop.RestartadslabrelaxSteps import RestartadslabrelaxSteps
from adsec.superop.DiviAllRelaxStaticSteps import DiviAllRelaxStaticSteps
from adsec.superop.DiviRestartbulkstaticSteps import  DiviRestartbulkstaticSteps
from adsec.superop.DiviRestartslabrelaxSteps import DiviRestartslabrelaxSteps
from adsec.superop.DiviRestartslabstaticSteps import DiviRestartslabstaticSteps
from adsec.superop.DiviRestartadslabrelax1Steps import DiviRestartadslabrelax1Steps
from adsec.superop.DiviRestartadslabrelax2Steps import DiviRestartadslabrelax2Steps
from adsec.superop.TSCalcSteps import TSCalcSteps
from adsec.superop.RestartTsrun2Steps import RestartTsrun2Steps

from dflow.python import upload_packages

upload_packages.append(__file__)


class FlowGenerator:
    def __init__(
            self,
            make_image: str,
            run_image: str,
            post_image: str,
            run_command: str,
            calculator: str,
            run_op: Type[OP],
            modify_run_op: Type[OP],
            props_make_op: Type[OP] = PropsMake,
            props_post_op: Type[OP] = PropsPost,
            group_size: Optional[int] = None,
            pool_size: Optional[int] = None,
            executor: Optional[DispatcherExecutor] = None,
            upload_python_packages: Optional[List[os.PathLike]] = None,
    ):
        self.download_path = None
        self.upload_path = None
        self.workflow = None
        self.relax_param = None
        self.props_param = None

        self.props_make_op = props_make_op
        self.props_post_op = props_post_op
        self.run_op = run_op
        self.modify_run_op = modify_run_op
        self.make_image = make_image
        self.run_image = run_image
        self.post_image = post_image
        self.run_command = run_command
        self.calculator = calculator
        self.group_size = group_size
        self.pool_size = pool_size
        self.executor = executor
        self.upload_python_packages = upload_python_packages

    @staticmethod
    def regulate_name(name):
        """
        Adjusts the given workflow name to conform to RFC 1123 subdomain requirements.
        It ensures the name is lowercase, contains only alphanumeric characters and hyphens,
        and starts and ends with an alphanumeric character.
        """
        # lowercase the name
        name = name.lower()
        # substitute invalid characters with hyphens
        name = re.sub(r'[^a-z0-9\-]', '-', name)
        # make sure the name starts and ends with an alphanumeric character
        name = re.sub(r'^[^a-z0-9]+', '', name)
        name = re.sub(r'[^a-z0-9]+$', '', name)

        return name

    def _monitor_props(
            self,
            subprops_key_list: List[str],
    ):
        subprops_left = subprops_key_list.copy()
        subprops_failed_list = []
        print(f'Waiting for sub-property results ({len(subprops_left)} left)...')
        while True:
            time.sleep(4)
            step_info = self.workflow.query()
            for kk in subprops_left:
                try:
                    step = step_info.get_step(key=kk)[0]
                except IndexError:
                    continue
                if step['phase'] == 'Succeeded':
                    print(f'Sub-workflow {kk} finished (ID: {self.workflow.id}, UID: {self.workflow.uid})')
                    print('Retrieving completed tasks to local...')
                    download_artifact(
                        artifact=step.outputs.artifacts['retrieve_path'],
                        path=self.download_path
                    )
                    subprops_left.remove(kk)
                    if subprops_left:
                        print(f'Waiting for sub-property results ({len(subprops_left)} left)...')
                elif step['phase'] == 'Failed':
                    print(f'Sub-workflow {kk} failed (ID: {self.workflow.id}, UID: {self.workflow.uid})')
                    subprops_failed_list.append(kk)
                    subprops_left.remove(kk)
                    if subprops_left:
                        print(f'Waiting for sub-property results ({len(subprops_left)} left)...')
            if not subprops_left:
                print(f'Workflow finished with {len(subprops_failed_list)} sub-property failed '
                      f'(ID: {self.workflow.id}, UID: {self.workflow.uid})')
                break

    def dump_flow_id(self):
        log_file = os.path.join(self.download_path, '.workflow.log')
        with open(log_file, 'a') as f:
            timestamp = datetime.datetime.now().isoformat()
            f.write(f'{self.workflow.id}\tsubmit\t{timestamp}\t{self.download_path}\n')

    def _set_mol_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:


        relaxPropertySteps = RelaxPropertySteps(
             name='mol-relaxstatic-flow',
             make_op=self.props_make_op,
             run_op=self.run_op,
             post_op=self.props_post_op,
             make_image=self.make_image,
             run_image=self.run_image,
             post_image=self.post_image,
             run_command=self.run_command,
             calculator=self.calculator,
             group_size=self.group_size,
             pool_size=self.pool_size,
             executor=self.executor,
             upload_python_packages=self.upload_python_packages
         )

        confs = props_parameter["molecular"]["relaxtion"]["mol_structures"]
        interaction = props_parameter["interaction"]
        relaxtion_prop_param_bulk = props_parameter["molecular"]["relaxtion"]
        static_prop_param_bulk = props_parameter["molecular"]["static"]

        conf_dirs = []
        flow_id_list = []
        path_to_prop_relaxtion_bulk_list = []
        path_to_prop_static_bulk_list = []
        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()
        for ii in conf_dirs:
            path_to_prop_relaxtion_bulk = os.path.join(ii, 'molecular/relaxtion')
            path_to_prop_relaxtion_bulk_list.append(path_to_prop_relaxtion_bulk)
            path_to_prop_static_bulk = os.path.join(ii, 'molecular/static')
            path_to_prop_static_bulk_list.append(path_to_prop_static_bulk)
            flow_id_list.append(ii + '-' + 'mol-relaxstatic')
            #if os.path.exists(path_to_prop_relaxtion):
            #    shutil.rmtree(path_to_prop_relaxtion)

        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []

        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)

            subprop_step =  Step(
                name=f'{clean_subflow_id}',
                template=relaxPropertySteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop_relaxtion": path_to_prop_relaxtion_bulk_list[ii],
                    "path_to_prop_static": path_to_prop_static_bulk_list[ii],
                    "relaxtion_prop_param": relaxtion_prop_param_bulk,
                    "static_prop_param": static_prop_param_bulk,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list

    def _set_ts_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:


        tscalcsteps = TSCalcSteps(
            name='ts-calc',
            make_op=self.props_make_op,
            run_op=self.run_op,
            modify_run_op = self.modify_run_op,
            post_op=self.props_post_op,
            make_image=self.make_image,
            run_image=self.run_image,
            post_image=self.post_image,
            run_command=self.run_command,
            calculator=self.calculator,
            group_size=self.group_size,
            pool_size=self.pool_size,
            executor=self.executor,
            upload_python_packages=self.upload_python_packages
        )

        confs = props_parameter["structures"]
        interaction = props_parameter["interaction"]
        tsrun1_prop_param = props_parameter["ts"]["tsrun1"]
        tsrun2_prop_param = props_parameter["ts"]["tsrun2"]
        tsrun3_prop_param = props_parameter["ts"]["tsrun3"]

        conf_dirs = []
        flow_id_list = []
        path_to_prop_ts_list = []
        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()
        for ii in conf_dirs:
            path_to_prop_ts = os.path.join(ii, 'ts')
            path_to_prop_ts_list.append(path_to_prop_ts)
            flow_id_list.append(ii + '-' + 'ts')
            #if os.path.exists(path_to_prop_relaxtion):
            #    shutil.rmtree(path_to_prop_relaxtion)

        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []
        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)

            subprop_step =  Step(
                name=f'{clean_subflow_id}',
                template= tscalcsteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop": path_to_prop_ts_list[ii],
                    "tsrun1_prop_param": tsrun1_prop_param,
                    "tsrun2_prop_param": tsrun2_prop_param,
                    "tsrun3_prop_param": tsrun3_prop_param,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list

    def _set_tsrun1_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:


        staticSteps = StaticSteps(
            name='tsrun1-calc',
            make_op=self.props_make_op,
            run_op=self.run_op,
            post_op=self.props_post_op,
            make_image=self.make_image,
            run_image=self.run_image,
            post_image=self.post_image,
            run_command=self.run_command,
            calculator=self.calculator,
            group_size=self.group_size,
            pool_size=self.pool_size,
            executor=self.executor,
            upload_python_packages=self.upload_python_packages
        )
        confs = props_parameter["structures"]
        interaction = props_parameter["interaction"]
        tsrun1_prop_param = props_parameter["ts"]["tsrun1"]

        conf_dirs = []
        flow_id_list = []
        path_to_prop_ts_list = []
        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()
        for ii in conf_dirs:
            path_to_prop_ts = os.path.join(ii, 'ts')
            path_to_prop_ts_list.append(path_to_prop_ts)
            flow_id_list.append(ii + '-' + 'ts')
            #if os.path.exists(path_to_prop_relaxtion):
            #    shutil.rmtree(path_to_prop_relaxtion)

        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []

        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)

            subprop_step =  Step(
                name=f'{clean_subflow_id}',
                template=staticSteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop": path_to_prop_ts_list[ii],
                    "prop_param": tsrun1_prop_param,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list
    
    def _set_tsrun2_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:


        relaxtionSteps = RelaxtionSteps(
            name='tsrun2-calc',
            make_op=self.props_make_op,
            run_op=self.modify_run_op,
            post_op=self.props_post_op,
            make_image=self.make_image,
            run_image=self.run_image,
            post_image=self.post_image,
            run_command=self.run_command,
            calculator=self.calculator,
            group_size=self.group_size,
            pool_size=self.pool_size,
            executor=self.executor,
            upload_python_packages=self.upload_python_packages
        )

        confs = props_parameter["structures"]
        interaction = props_parameter["interaction"]
        tsrun2_prop_param = props_parameter["ts"]["tsrun2"]
        
        conf_dirs = []
        flow_id_list = []
        path_to_prop_ts_list = []
        path_to_prop_frequency_list = []
        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()
        for ii in conf_dirs:
            path_to_prop_ts = os.path.join(ii, 'ts')
            path_to_prop_ts_list.append(path_to_prop_ts)
            flow_id_list.append(ii + '-' + 'ts')
            #if os.path.exists(path_to_prop_relaxtion):
            #    shutil.rmtree(path_to_prop_relaxtion)

        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []
        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)

            subprop_step =  Step(
                name=f'{clean_subflow_id}',
                template=relaxtionSteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop": path_to_prop_ts_list[ii],
                    "prop_param": tsrun2_prop_param,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list

    def _set_tsrun3_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:


        staticSteps = StaticSteps(
            name='tsrun3-calc',
            make_op=self.props_make_op,
            run_op=self.run_op,
            post_op=self.props_post_op,
            make_image=self.make_image,
            run_image=self.run_image,
            post_image=self.post_image,
            run_command=self.run_command,
            calculator=self.calculator,
            group_size=self.group_size,
            pool_size=self.pool_size,
            executor=self.executor,
            upload_python_packages=self.upload_python_packages
        )
        confs = props_parameter["structures"]
        interaction = props_parameter["interaction"]
        tsrun3_prop_param = props_parameter["ts"]["tsrun3"]

        conf_dirs = []
        flow_id_list = []
        path_to_prop_ts_list = []
        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()
        for ii in conf_dirs:
            path_to_prop_ts = os.path.join(ii, 'ts')
            path_to_prop_ts_list.append(path_to_prop_ts)
            flow_id_list.append(ii + '-' + 'ts')
            #if os.path.exists(path_to_prop_relaxtion):
            #    shutil.rmtree(path_to_prop_relaxtion)

        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []


        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)

            subprop_step =  Step(
                name=f'{clean_subflow_id}',
                template=staticSteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop": path_to_prop_ts_list[ii],
                    "prop_param": tsrun3_prop_param,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list


    def _set_bulk_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:


        relaxPropertySteps = RelaxPropertySteps(
             name='bulk-relaxstatic-flow',
             make_op=self.props_make_op,
             run_op=self.run_op,
             post_op=self.props_post_op,
             make_image=self.make_image,
             run_image=self.run_image,
             post_image=self.post_image,
             run_command=self.run_command,
             calculator=self.calculator,
             group_size=self.group_size,
             pool_size=self.pool_size,
             executor=self.executor,
             upload_python_packages=self.upload_python_packages
         )

        confs = props_parameter["structures"]
        interaction = props_parameter["interaction"]
        relaxtion_prop_param_bulk = props_parameter["bulk"]["relaxtion"]
        static_prop_param_bulk = props_parameter["bulk"]["static"]

        conf_dirs = []
        flow_id_list = []
        path_to_prop_relaxtion_bulk_list = []
        path_to_prop_static_bulk_list = []
        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()

        for ii in conf_dirs:
            path_to_prop_relaxtion_bulk = os.path.join(ii, 'bulk/relaxtion')
            path_to_prop_relaxtion_bulk_list.append(path_to_prop_relaxtion_bulk)
            path_to_prop_static_bulk = os.path.join(ii, 'bulk/static')
            path_to_prop_static_bulk_list.append(path_to_prop_static_bulk)
            flow_id_list.append(ii + '-' + 'bulk-relaxstatic')
            #if os.path.exists(path_to_prop_relaxtion):
            #    shutil.rmtree(path_to_prop_relaxtion)

        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []
        
        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)
    
            subprop_step =  Step(
                name=f'{clean_subflow_id}',
                template=relaxPropertySteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop_relaxtion": path_to_prop_relaxtion_bulk_list[ii],
                    "path_to_prop_static": path_to_prop_static_bulk_list[ii],
                    "relaxtion_prop_param": relaxtion_prop_param_bulk,
                    "static_prop_param": static_prop_param_bulk,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list


    def _set_slab_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:


        relaxPropertySteps = RelaxPropertySteps(
             name='slab-relaxstatic-flow',
             make_op=self.props_make_op,
             run_op=self.run_op,
             post_op=self.props_post_op,
             make_image=self.make_image,
             run_image=self.run_image,
             post_image=self.post_image,
             run_command=self.run_command,
             calculator=self.calculator,
             group_size=self.group_size,
             pool_size=self.pool_size,
             executor=self.executor,
             upload_python_packages=self.upload_python_packages
         )

        confs = props_parameter["structures"]
        interaction = props_parameter["interaction"]
        relaxtion_prop_param_slab = props_parameter["slab"]["relaxtion"]
        static_prop_param_slab = props_parameter["slab"]["static"]

        conf_dirs = []
        flow_id_list = []
        path_to_prop_relaxtion_slab_list = []
        path_to_prop_static_slab_list = []
        
        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()


        for ii in conf_dirs:
            path_to_prop_relaxtion_slab = os.path.join(ii, 'slab/relaxtion')
            path_to_prop_relaxtion_slab_list.append(path_to_prop_relaxtion_slab)
            path_to_prop_static_slab = os.path.join(ii, 'slab/static')
            path_to_prop_static_slab_list.append(path_to_prop_static_slab)
            flow_id_list.append(ii + '-' + 'slab-relaxstatic')
            #if os.path.exists(path_to_prop_relaxtion):
            #    shutil.rmtree(path_to_prop_relaxtion)
        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []
        
        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)
            subprop_step = Step(
                name=f'{clean_subflow_id}',
                template=relaxPropertySteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop_relaxtion": path_to_prop_relaxtion_slab_list[ii],
                    "path_to_prop_static": path_to_prop_static_slab_list[ii],
                    "relaxtion_prop_param": relaxtion_prop_param_slab,
                    "static_prop_param": static_prop_param_slab,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list

    def _set_adslab_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:

        relaxPropertySteps = RelaxPropertySteps(
             name='adslab-relaxstatic-flow',
             make_op=self.props_make_op,
             run_op=self.run_op,
             post_op=self.props_post_op,
             make_image=self.make_image,
             run_image=self.run_image,
             post_image=self.post_image,
             run_command=self.run_command,
             calculator=self.calculator,
             group_size=self.group_size,
             pool_size=self.pool_size,
             executor=self.executor,
             upload_python_packages=self.upload_python_packages
         )

        confs = props_parameter["structures"]
        interaction = props_parameter["interaction"]
        relaxtion_prop_param_adslab = props_parameter["adslab"]["relaxtion"]
        static_prop_param_adslab = props_parameter["adslab"]["static"]

        conf_dirs = []
        flow_id_list = []
        path_to_prop_relaxtion_adslab_list = []
        path_to_prop_static_adslab_list = []

        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()
        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()

        for ii in conf_dirs:
            path_to_prop_relaxtion_adslab = os.path.join(ii, 'adslab/relaxtion')
            path_to_prop_relaxtion_adslab_list.append(path_to_prop_relaxtion_adslab)
            path_to_prop_static_adslab = os.path.join(ii, 'adslab/static')
            path_to_prop_static_adslab_list.append(path_to_prop_static_adslab)
            flow_id_list.append(ii + '-' + 'adslab-relaxstatic')
        
        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []
    

        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)
            subprop_step = Step(
                name=f'{clean_subflow_id}',
                template=relaxPropertySteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop_relaxtion": path_to_prop_relaxtion_adslab_list[ii],
                    "path_to_prop_static": path_to_prop_static_adslab_list[ii],
                    "relaxtion_prop_param": relaxtion_prop_param_adslab,
                    "static_prop_param": static_prop_param_adslab,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )

            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list

    def _set_joint_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:


        relaxPropertySteps = JointRelaxPropertySteps(
            name='joint-relaxstatic-flow',
            make_op=self.props_make_op,
            run_op=self.run_op,
            post_op=self.props_post_op,
            make_image=self.make_image,
            run_image=self.run_image,
            post_image=self.post_image,
            run_command=self.run_command,
            calculator=self.calculator,
            group_size=self.group_size,
            pool_size=self.pool_size,
            executor=self.executor,
            upload_python_packages=self.upload_python_packages
        )

        confs = props_parameter["structures"]
        interaction = props_parameter["interaction"]

        relaxtion_prop_param_bulk = props_parameter["bulk"]["relaxtion"]
        static_prop_param_bulk = props_parameter["bulk"]["static"]
    
        relaxtion_prop_param_slab = props_parameter["slab"]["relaxtion"]
        static_prop_param_slab = props_parameter["slab"]["static"]
    
        relaxtion_prop_param_adslab = props_parameter["adslab"]["relaxtion"]
        static_prop_param_adslab = props_parameter["adslab"]["static"]

        conf_dirs = []
        flow_id_list = []
        path_to_prop_relaxtion_bulk_list = []
        path_to_prop_static_bulk_list = []
        path_to_prop_relaxtion_slab_list = []
        path_to_prop_static_slab_list = []
        path_to_prop_relaxtion_adslab_list = []
        path_to_prop_static_adslab_list = []

        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()
        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()

        for ii in conf_dirs:
            path_to_prop_relaxtion_bulk = os.path.join(ii, 'bulk/relaxtion')
            path_to_prop_relaxtion_bulk_list.append(path_to_prop_relaxtion_bulk)
            path_to_prop_static_bulk = os.path.join(ii, 'bulk/static')
            path_to_prop_static_bulk_list.append(path_to_prop_static_bulk)
    
            path_to_prop_relaxtion_slab = os.path.join(ii, 'slab/relaxtion')
            path_to_prop_relaxtion_slab_list.append(path_to_prop_relaxtion_slab)
            path_to_prop_static_slab = os.path.join(ii, 'slab/static')
            path_to_prop_static_slab_list.append(path_to_prop_static_slab)
    
            path_to_prop_relaxtion_adslab = os.path.join(ii, 'adslab/relaxtion')
            path_to_prop_relaxtion_adslab_list.append(path_to_prop_relaxtion_adslab)
            path_to_prop_static_adslab = os.path.join(ii, 'adslab/static')
            path_to_prop_static_adslab_list.append(path_to_prop_static_adslab)
            flow_id_list.append(ii + '-' + 'joint-relaxstatic')

        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []
        

        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)
            subprop_step = Step(
                name=f'{clean_subflow_id}',
                template=relaxPropertySteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop_relaxtion_bulk": path_to_prop_relaxtion_bulk_list[ii],
                    "path_to_prop_static_bulk": path_to_prop_static_bulk_list[ii],
                    "path_to_prop_relaxtion_slab": path_to_prop_relaxtion_slab_list[ii],
                    "path_to_prop_static_slab": path_to_prop_static_slab_list[ii],
                    "path_to_prop_relaxtion_adslab": path_to_prop_relaxtion_adslab_list[ii],
                    "path_to_prop_static_adslab": path_to_prop_static_adslab_list[ii],
                    "relaxtion_prop_param_bulk": relaxtion_prop_param_bulk,
                    "static_prop_param_bulk": static_prop_param_bulk,
                    "relaxtion_prop_param_slab": relaxtion_prop_param_slab,
                    "static_prop_param_slab": static_prop_param_slab,
                    "relaxtion_prop_param_adslab": relaxtion_prop_param_adslab,
                    "static_prop_param_adslab": static_prop_param_adslab,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list

    def _set_bulkrelax_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:


        relaxtionSteps = RelaxtionSteps(
            name='bulk-relaxtion',
            make_op=self.props_make_op,
            run_op=self.run_op,
            post_op=self.props_post_op,
            make_image=self.make_image,
            run_image=self.run_image,
            post_image=self.post_image,
            run_command=self.run_command,
            calculator=self.calculator,
            group_size=self.group_size,
            pool_size=self.pool_size,
            executor=self.executor,
            upload_python_packages=self.upload_python_packages
        )


        confs = props_parameter["structures"]
        interaction = props_parameter["interaction"]
        relaxtion_prop_param_bulk = props_parameter["bulk"]["relaxtion"]

        conf_dirs = []
        flow_id_list = []
        path_to_prop_relaxtion_bulk_list = []
        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']


        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()
            

            
        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()

        for ii in conf_dirs:
            path_to_prop_relaxtion_bulk = os.path.join(ii, 'bulk/relaxtion')
            path_to_prop_relaxtion_bulk_list.append(path_to_prop_relaxtion_bulk)
            flow_id_list.append(ii)
            #if os.path.exists(path_to_prop_relaxtion):
            #    shutil.rmtree(path_to_prop_relaxtion)

        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []

        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)

            subprop_step =  Step(
                name=f'{clean_subflow_id}',
                template= relaxtionSteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop": path_to_prop_relaxtion_bulk_list[ii],
                    "prop_param": relaxtion_prop_param_bulk,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list


    def _set_bulkstatic_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:


        staticSteps = StaticSteps(
            name='bulk-static',
            make_op=self.props_make_op,
            run_op=self.run_op,
            post_op=self.props_post_op,
            make_image=self.make_image,
            run_image=self.run_image,
            post_image=self.post_image,
            run_command=self.run_command,
            calculator=self.calculator,
            group_size=self.group_size,
            pool_size=self.pool_size,
            executor=self.executor,
            upload_python_packages=self.upload_python_packages
        )


        confs_from_previous = props_parameter["bulk"]["static"]["confs_from_previous"]
        if confs_from_previous:
            confs = props_parameter["structures"]
        else:
            confs = props_parameter["bulk"]["static"]["start_confs"]

        interaction = props_parameter["interaction"]
        static_prop_param_bulk = props_parameter["bulk"]["static"]
        conf_dirs = []
        flow_id_list = []
        path_to_prop_static_bulk_list = []
        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()

        for ii in conf_dirs:
            path_to_prop_static_bulk = os.path.join(ii, 'bulk/static')
            path_to_prop_static_bulk_list.append(path_to_prop_static_bulk)
            flow_id_list.append(ii)
            #if os.path.exists(path_to_prop_relaxtion):
            #    shutil.rmtree(path_to_prop_relaxtion)

        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []

        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)

            subprop_step =  Step(
                name=f'{clean_subflow_id}',
                template= staticSteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop": path_to_prop_static_bulk_list[ii],
                    "prop_param": static_prop_param_bulk,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list


    def _set_slabrelax_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:

        relaxtionSteps = RelaxtionSteps(
            name='slab-relaxtion',
            make_op=self.props_make_op,
            run_op=self.run_op,
            post_op=self.props_post_op,
            make_image=self.make_image,
            run_image=self.run_image,
            post_image=self.post_image,
            run_command=self.run_command,
            calculator=self.calculator,
            group_size=self.group_size,
            pool_size=self.pool_size,
            executor=self.executor,
            upload_python_packages=self.upload_python_packages
        )

        confs_from_previous = props_parameter["slab"]["relaxtion"]["confs_from_previous"]
        if confs_from_previous:
            confs = props_parameter["structures"]
        else:
            confs = props_parameter["slab"]["relaxtion"]["start_confs"]

        interaction = props_parameter["interaction"]
        relaxtion_prop_param_slab = props_parameter["slab"]["relaxtion"]


        conf_dirs = []
        flow_id_list = []
        path_to_prop_relaxtion_slab_list = []

        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()

        for ii in conf_dirs:
            path_to_prop_relaxtion_slab = os.path.join(ii, 'slab/relaxtion')
            path_to_prop_relaxtion_slab_list.append(path_to_prop_relaxtion_slab)
            flow_id_list.append(ii)
            #if os.path.exists(path_to_prop_relaxtion):
            #    shutil.rmtree(path_to_prop_relaxtion)
        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []


        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)
            subprop_step = Step(
                name=f'{clean_subflow_id}',
                template=relaxtionSteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop": path_to_prop_relaxtion_slab_list[ii],
                    "prop_param": relaxtion_prop_param_slab,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list


    def _set_slabstatic_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:


        staticSteps = StaticSteps(
            name='slab-static',
            make_op=self.props_make_op,
            run_op=self.run_op,
            post_op=self.props_post_op,
            make_image=self.make_image,
            run_image=self.run_image,
            post_image=self.post_image,
            run_command=self.run_command,
            calculator=self.calculator,
            group_size=self.group_size,
            pool_size=self.pool_size,
            executor=self.executor,
            upload_python_packages=self.upload_python_packages
        )


        confs_from_previous = props_parameter["slab"]["static"]["confs_from_previous"]
        if confs_from_previous:
            confs = props_parameter["structures"]
        else:
            confs = props_parameter["slab"]["static"]["start_confs"]

        interaction = props_parameter["interaction"]
        static_prop_param_slab = props_parameter["slab"]["static"]


        conf_dirs = []
        flow_id_list = []
        path_to_prop_static_slab_list = []

        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()

        for ii in conf_dirs:
            path_to_prop_static_slab = os.path.join(ii, 'slab/static')
            path_to_prop_static_slab_list.append(path_to_prop_static_slab)
            flow_id_list.append(ii)
            #if os.path.exists(path_to_prop_relaxtion):
            #    shutil.rmtree(path_to_prop_relaxtion)
        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []

        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)
            subprop_step = Step(
                name=f'{clean_subflow_id}',
                template= staticSteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop": path_to_prop_static_slab_list[ii],
                    "prop_param": static_prop_param_slab,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list


    def _set_adslabrelax_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:

        max_relax_time = props_parameter["adslab"]["relaxtion"]["max_relax_time"]
        relaxtionSteps = RelaxtionSteps(
            name='adslab-relax',
            make_op=self.props_make_op,
            run_op=self.run_op,
            post_op=self.props_post_op,
            make_image=self.make_image,
            run_image=self.run_image,
            post_image=self.post_image,
            run_command=self.run_command,
            calculator=self.calculator,
            group_size=self.group_size,
            pool_size=self.pool_size,
            executor=self.executor,
            upload_python_packages=self.upload_python_packages,
            timeout = max_relax_time
        )


        confs_from_previous = props_parameter["adslab"]["relaxtion"]["confs_from_previous"]
        if confs_from_previous:
            confs = props_parameter["structures"]
        else:
            confs = props_parameter["adslab"]["relaxtion"]["start_confs"]

        interaction = props_parameter["interaction"]
        static_prop_param_slab = props_parameter["slab"]["static"]


        interaction = props_parameter["interaction"]
        relaxtion_prop_param_adslab = props_parameter["adslab"]["relaxtion"]

        conf_dirs = []
        flow_id_list = []
        path_to_prop_relaxtion_adslab_list = []


        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()

        for ii in conf_dirs:
            path_to_prop_relaxtion_adslab = os.path.join(ii, 'adslab/relaxtion')
            path_to_prop_relaxtion_adslab_list.append(path_to_prop_relaxtion_adslab)
            flow_id_list.append(ii)

        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []

        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)
            subprop_step = Step(
                name=f'{clean_subflow_id}',
                template= relaxtionSteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop": path_to_prop_relaxtion_adslab_list[ii],
                    "prop_param": relaxtion_prop_param_adslab,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )

            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list

    def _set_adslabrelax1_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:


        max_relax_time = props_parameter["adslab"]["relaxtion_1"]["max_relax_time"]
        relaxtionSteps = RelaxtionSteps(
            name='adslab-relaxtion-1',
            make_op=self.props_make_op,
            run_op=self.run_op,
            post_op=self.props_post_op,
            make_image=self.make_image,
            run_image=self.run_image,
            post_image=self.post_image,
            run_command=self.run_command,
            calculator=self.calculator,
            group_size=self.group_size,
            pool_size=self.pool_size,
            executor=self.executor,
            upload_python_packages=self.upload_python_packages,
            timeout = max_relax_time
        )

        confs_from_previous = props_parameter["adslab"]["relaxtion_1"]["confs_from_previous"]
        if confs_from_previous:
            confs = props_parameter["structures"]
        else:
            confs = props_parameter["adslab"]["relaxtion_1"]["start_confs"]

        interaction = props_parameter["interaction"]
        relaxtion_prop_param_adslab = props_parameter["adslab"]["relaxtion_1"]

        conf_dirs = []
        flow_id_list = []
        path_to_prop_relaxtion_adslab_list = []

        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()

        for ii in conf_dirs:
            path_to_prop_relaxtion_adslab = os.path.join(ii, 'adslab/relaxtion')
            path_to_prop_relaxtion_adslab_list.append(path_to_prop_relaxtion_adslab)
            flow_id_list.append(ii)

        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []
        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)
            subprop_step = Step(
                name=f'{clean_subflow_id}',
                template= relaxtionSteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop": path_to_prop_relaxtion_adslab_list[ii],
                    "prop_param": relaxtion_prop_param_adslab,
                    "inter_param": interaction
                    },
                key=subflow_key
            )

            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list

    def _set_adslabrelax2_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:

        max_relax_time = props_parameter["adslab"]["relaxtion_2"]["max_relax_time"]
        relaxtionSteps = RelaxtionSteps(
            name='adslab-relaxtion-2',
            make_op=self.props_make_op,
            run_op=self.run_op,
            post_op=self.props_post_op,
            make_image=self.make_image,
            run_image=self.run_image,
            post_image=self.post_image,
            run_command=self.run_command,
            calculator=self.calculator,
            group_size=self.group_size,
            pool_size=self.pool_size,
            executor=self.executor,
            upload_python_packages=self.upload_python_packages,
            timeout = max_relax_time
        )

        confs_from_previous = props_parameter["adslab"]["relaxtion_2"]["confs_from_previous"]
        if confs_from_previous:
            confs = props_parameter["structures"]
        else:
            confs = props_parameter["adslab"]["relaxtion_2"]["start_confs"]

        interaction = props_parameter["interaction"]
        relaxtion_prop_param_adslab = props_parameter["adslab"]["relaxtion_2"]

        conf_dirs = []
        flow_id_list = []
        path_to_prop_relaxtion_adslab_list = []


        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()

        for ii in conf_dirs:
            path_to_prop_relaxtion_adslab = os.path.join(ii, 'adslab/relaxtion')
            path_to_prop_relaxtion_adslab_list.append(path_to_prop_relaxtion_adslab)
            flow_id_list.append(ii)

        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []


        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)
            subprop_step = Step(
                name=f'{clean_subflow_id}',
                template= relaxtionSteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop": path_to_prop_relaxtion_adslab_list[ii],
                    "prop_param": relaxtion_prop_param_adslab,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )

            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list


    def _set_adslabstatic_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:


        staticSteps = StaticSteps(
            name='adslab-static',
            make_op=self.props_make_op,
            run_op=self.run_op,
            post_op=self.props_post_op,
            make_image=self.make_image,
            run_image=self.run_image,
            post_image=self.post_image,
            run_command=self.run_command,
            calculator=self.calculator,
            group_size=self.group_size,
            pool_size=self.pool_size,
            executor=self.executor,
            upload_python_packages=self.upload_python_packages
        )

        confs_from_previous = props_parameter["adslab"]["static"]["confs_from_previous"]
        if confs_from_previous:
            confs = props_parameter["structures"]
        else:
            confs = props_parameter["adslab"]["static"]["start_confs"]

        interaction = props_parameter["interaction"]
        static_prop_param_adslab = props_parameter["adslab"]["static"]
        conf_dirs = []
        flow_id_list = []
        path_to_prop_static_adslab_list = []


        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()

        for ii in conf_dirs:
            path_to_prop_static_adslab = os.path.join(ii, 'adslab/static')
            path_to_prop_static_adslab_list.append(path_to_prop_static_adslab)
            flow_id_list.append(ii)

        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []

        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)
            subprop_step = Step(
                name=f'{clean_subflow_id}',
                template=staticSteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop": path_to_prop_static_adslab_list[ii],
                    "prop_param": static_prop_param_adslab,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )

            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list


    def _set_all_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:


        adslab_relax_step_flag = props_parameter['adslab']['relax_step']
        if adslab_relax_step_flag:
            timeout_1 = props_parameter["adslab"]["relaxtion_1"]["max_relax_time"]
            timeout_2 = props_parameter["adslab"]["relaxtion_2"]["max_relax_time"]
            allrelaxstaticSteps = DiviAllRelaxStaticSteps(
                name='divi-all-relaxstatic-flow',
                make_op=self.props_make_op,
                run_op=self.run_op,
                post_op=self.props_post_op,
                make_image=self.make_image,
                run_image=self.run_image,
                post_image=self.post_image,
                run_command=self.run_command,
                calculator=self.calculator,
                group_size=self.group_size,
                pool_size=self.pool_size,
                executor=self.executor,
                upload_python_packages=self.upload_python_packages,
                timeout_1 = timeout_1,
                timeout_2 = timeout_2
            )
        else:
            max_relax_time = props_parameter["adslab"]["relaxtion"]["max_relax_time"]
            allrelaxstaticSteps = AllRelaxStaticSteps(
                name='all-relaxstatic-flow',
                make_op=self.props_make_op,
                run_op=self.run_op,
                post_op=self.props_post_op,
                make_image=self.make_image,
                run_image=self.run_image,
                post_image=self.post_image,
                run_command=self.run_command,
                calculator=self.calculator,
                group_size=self.group_size,
                pool_size=self.pool_size,
                executor=self.executor,
                upload_python_packages=self.upload_python_packages,
                timeout = max_relax_time
            )


        confs = props_parameter["structures"]
        interaction = props_parameter["interaction"]

        relaxtion_prop_param_bulk = props_parameter["bulk"]["relaxtion"]
        static_prop_param_bulk = props_parameter["bulk"]["static"]

        relaxtion_prop_param_slab = props_parameter["slab"]["relaxtion"]
        static_prop_param_slab = props_parameter["slab"]["static"]

        relaxtion_prop_param_adslab = props_parameter["adslab"]["relaxtion"]
        static_prop_param_adslab = props_parameter["adslab"]["static"]

        relaxtion_1_prop_param_adslab = props_parameter["adslab"]["relaxtion_1"]
        relaxtion_2_prop_param_adslab = props_parameter["adslab"]["relaxtion_2"]


        conf_dirs = []
        flow_id_list = []
        path_to_prop_relaxtion_bulk_list = []
        path_to_prop_static_bulk_list = []
        path_to_prop_relaxtion_slab_list = []
        path_to_prop_static_slab_list = []
        path_to_prop_relaxtion_adslab_list = []
        path_to_prop_static_adslab_list = []

        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()

        for ii in conf_dirs:
            path_to_prop_relaxtion_bulk = os.path.join(ii, 'bulk/relaxtion')
            path_to_prop_relaxtion_bulk_list.append(path_to_prop_relaxtion_bulk)
            path_to_prop_static_bulk = os.path.join(ii, 'bulk/static')
            path_to_prop_static_bulk_list.append(path_to_prop_static_bulk)

            path_to_prop_relaxtion_slab = os.path.join(ii, 'slab/relaxtion')
            path_to_prop_relaxtion_slab_list.append(path_to_prop_relaxtion_slab)
            path_to_prop_static_slab = os.path.join(ii, 'slab/static')
            path_to_prop_static_slab_list.append(path_to_prop_static_slab)

            path_to_prop_relaxtion_adslab = os.path.join(ii, 'adslab/relaxtion')
            path_to_prop_relaxtion_adslab_list.append(path_to_prop_relaxtion_adslab)
            path_to_prop_static_adslab = os.path.join(ii, 'adslab/static')
            path_to_prop_static_adslab_list.append(path_to_prop_static_adslab)
            flow_id_list.append(ii)

        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []
        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)
            subprop_step = Step(
                name=f'{clean_subflow_id}',
                template=allrelaxstaticSteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop_relaxtion_bulk": path_to_prop_relaxtion_bulk_list[ii],
                    "path_to_prop_static_bulk": path_to_prop_static_bulk_list[ii],
                    "path_to_prop_relaxtion_slab": path_to_prop_relaxtion_slab_list[ii],
                    "path_to_prop_static_slab": path_to_prop_static_slab_list[ii],
                    "path_to_prop_relaxtion_adslab": path_to_prop_relaxtion_adslab_list[ii],
                    "path_to_prop_static_adslab": path_to_prop_static_adslab_list[ii],
                    "relaxtion_prop_param_bulk": relaxtion_prop_param_bulk,
                    "static_prop_param_bulk": static_prop_param_bulk,
                    "relaxtion_prop_param_slab": relaxtion_prop_param_slab,
                    "static_prop_param_slab": static_prop_param_slab,
                    "relaxtion_prop_param_adslab": relaxtion_prop_param_adslab,
                    "relaxtion_prop_param_1_adslab": relaxtion_1_prop_param_adslab,
                    "relaxtion_prop_param_2_adslab": relaxtion_2_prop_param_adslab,
                    "static_prop_param_adslab": static_prop_param_adslab,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list

    def _set_restart_bulkstatic_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:

        adslab_relax_step_flag = props_parameter['adslab']['relax_step']

        if adslab_relax_step_flag:
            timeout_1 = props_parameter["adslab"]["relaxtion_1"]["max_relax_time"]
            timeout_2 = props_parameter["adslab"]["relaxtion_2"]["max_relax_time"]
            restartbulkstaticSteps = DiviRestartbulkstaticSteps(
                name='divi-restart-step-bulkstatic-flow',
                make_op=self.props_make_op,
                run_op=self.run_op,
                post_op=self.props_post_op,
                make_image=self.make_image,
                run_image=self.run_image,
                post_image=self.post_image,
                run_command=self.run_command,
                calculator=self.calculator,
                group_size=self.group_size,
                pool_size=self.pool_size,
                executor=self.executor,
                upload_python_packages=self.upload_python_packages,
                timeout_1 = timeout_1,
                timeout_2 = timeout_2,
        )
        else:
            max_relax_time = props_parameter["adslab"]["relaxtion"]["max_relax_time"]
            restartbulkstaticSteps = RestartbulkstaticSteps(
                name='restart-step-bulkstatic-flow',
                make_op=self.props_make_op,
                run_op=self.run_op,
                post_op=self.props_post_op,
                make_image=self.make_image,
                run_image=self.run_image,
                post_image=self.post_image,
                run_command=self.run_command,
                calculator=self.calculator,
                group_size=self.group_size,
                pool_size=self.pool_size,
                executor=self.executor,
                upload_python_packages=self.upload_python_packages,
                timeout = max_relax_time
        )

        confs = props_parameter["structures"]
        interaction = props_parameter["interaction"]

        relaxtion_prop_param_bulk = props_parameter["bulk"]["relaxtion"]
        static_prop_param_bulk = props_parameter["bulk"]["static"]

        relaxtion_prop_param_slab = props_parameter["slab"]["relaxtion"]
        static_prop_param_slab = props_parameter["slab"]["static"]

        relaxtion_prop_param_adslab = props_parameter["adslab"]["relaxtion"]
        static_prop_param_adslab = props_parameter["adslab"]["static"]
 
        relaxtion_1_prop_param_adslab = props_parameter["adslab"]["relaxtion_1"]
        relaxtion_2_prop_param_adslab = props_parameter["adslab"]["relaxtion_2"]

        conf_dirs = []
        flow_id_list = []
        path_to_prop_relaxtion_bulk_list = []
        path_to_prop_static_bulk_list = []
        path_to_prop_relaxtion_slab_list = []
        path_to_prop_static_slab_list = []
        path_to_prop_relaxtion_adslab_list = []
        path_to_prop_static_adslab_list = []

        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()
        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()

        for ii in conf_dirs:
            path_to_prop_relaxtion_bulk = os.path.join(ii, 'bulk/relaxtion')
            path_to_prop_relaxtion_bulk_list.append(path_to_prop_relaxtion_bulk)
            path_to_prop_static_bulk = os.path.join(ii, 'bulk/static')
            path_to_prop_static_bulk_list.append(path_to_prop_static_bulk)

            path_to_prop_relaxtion_slab = os.path.join(ii, 'slab/relaxtion')
            path_to_prop_relaxtion_slab_list.append(path_to_prop_relaxtion_slab)
            path_to_prop_static_slab = os.path.join(ii, 'slab/static')
            path_to_prop_static_slab_list.append(path_to_prop_static_slab)

            path_to_prop_relaxtion_adslab = os.path.join(ii, 'adslab/relaxtion')
            path_to_prop_relaxtion_adslab_list.append(path_to_prop_relaxtion_adslab)
            path_to_prop_static_adslab = os.path.join(ii, 'adslab/static')
            path_to_prop_static_adslab_list.append(path_to_prop_static_adslab)
            flow_id_list.append(ii)
        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []
        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)
            subprop_step = Step(
                name=f'{clean_subflow_id}',
                template=restartbulkstaticSteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop_relaxtion_bulk": path_to_prop_relaxtion_bulk_list[ii],
                    "path_to_prop_static_bulk": path_to_prop_static_bulk_list[ii],
                    "path_to_prop_relaxtion_slab": path_to_prop_relaxtion_slab_list[ii],
                    "path_to_prop_static_slab": path_to_prop_static_slab_list[ii],
                    "path_to_prop_relaxtion_adslab": path_to_prop_relaxtion_adslab_list[ii],
                    "path_to_prop_static_adslab": path_to_prop_static_adslab_list[ii],
                    "relaxtion_prop_param_bulk": relaxtion_prop_param_bulk,
                    "static_prop_param_bulk": static_prop_param_bulk,
                    "relaxtion_prop_param_slab": relaxtion_prop_param_slab,
                    "static_prop_param_slab": static_prop_param_slab,
                    "relaxtion_prop_param_adslab": relaxtion_prop_param_adslab,
                    "relaxtion_prop_param_1_adslab": relaxtion_1_prop_param_adslab,
                    "relaxtion_prop_param_2_adslab": relaxtion_2_prop_param_adslab,
                    "static_prop_param_adslab": static_prop_param_adslab,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list

    def _set_restart_slabrelax_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:

        adslab_relax_step_flag = props_parameter['adslab']['relax_step']
        if adslab_relax_step_flag:
             timeout_1 = props_parameter["adslab"]["relaxtion_1"]["max_relax_time"]
             timeout_2 = props_parameter["adslab"]["relaxtion_2"]["max_relax_time"]
             restartslabrelaxSteps = DiviRestartslabrelaxSteps(
                name='divi-restart-step-slabrelax-flow',
                make_op=self.props_make_op,
                run_op=self.run_op,
                post_op=self.props_post_op,
                make_image=self.make_image,
                run_image=self.run_image,
                post_image=self.post_image,
                run_command=self.run_command,
                calculator=self.calculator,
                group_size=self.group_size,
                pool_size=self.pool_size,
                executor=self.executor,
                upload_python_packages=self.upload_python_packages,
                timeout_1 = timeout_1,
                timeout_2 = timeout_2,
            )
        else:
            max_relax_time = props_parameter["adslab"]["relaxtion"]["max_relax_time"]
            restartslabrelaxSteps = RestartslabrelaxSteps(
                name='restart-step-slabrelax-flow',
                make_op=self.props_make_op,
                run_op=self.run_op,
                post_op=self.props_post_op,
                make_image=self.make_image,
                run_image=self.run_image,
                post_image=self.post_image,
                run_command=self.run_command,
                calculator=self.calculator,
                group_size=self.group_size,
                pool_size=self.pool_size,
                executor=self.executor,
                upload_python_packages=self.upload_python_packages,
                timeout = max_relax_time
            )
        confs = props_parameter["structures"]
        interaction = props_parameter["interaction"]


        relaxtion_prop_param_slab = props_parameter["slab"]["relaxtion"]
        static_prop_param_slab = props_parameter["slab"]["static"]

        relaxtion_prop_param_adslab = props_parameter["adslab"]["relaxtion"]
        static_prop_param_adslab = props_parameter["adslab"]["static"]

        relaxtion_1_prop_param_adslab = props_parameter["adslab"]["relaxtion_1"]
        relaxtion_2_prop_param_adslab = props_parameter["adslab"]["relaxtion_2"]

        conf_dirs = []
        flow_id_list = []
        path_to_prop_relaxtion_slab_list = []
        path_to_prop_static_slab_list = []
        path_to_prop_relaxtion_adslab_list = []
        path_to_prop_static_adslab_list = []

        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()

        for ii in conf_dirs:

            path_to_prop_relaxtion_slab = os.path.join(ii, 'slab/relaxtion')
            path_to_prop_relaxtion_slab_list.append(path_to_prop_relaxtion_slab)
            path_to_prop_static_slab = os.path.join(ii, 'slab/static')
            path_to_prop_static_slab_list.append(path_to_prop_static_slab)

            path_to_prop_relaxtion_adslab = os.path.join(ii, 'adslab/relaxtion')
            path_to_prop_relaxtion_adslab_list.append(path_to_prop_relaxtion_adslab)
            path_to_prop_static_adslab = os.path.join(ii, 'adslab/static')
            path_to_prop_static_adslab_list.append(path_to_prop_static_adslab)
            flow_id_list.append(ii)
        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []
        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)
            subprop_step = Step(
                name=f'{clean_subflow_id}',
                template=restartslabrelaxSteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop_relaxtion_slab": path_to_prop_relaxtion_slab_list[ii],
                    "path_to_prop_static_slab": path_to_prop_static_slab_list[ii],
                    "path_to_prop_relaxtion_adslab": path_to_prop_relaxtion_adslab_list[ii],
                    "path_to_prop_static_adslab": path_to_prop_static_adslab_list[ii],
                    "relaxtion_prop_param_slab": relaxtion_prop_param_slab,
                    "static_prop_param_slab": static_prop_param_slab,
                    "relaxtion_prop_param_adslab": relaxtion_prop_param_adslab,
                    "relaxtion_prop_param_1_adslab": relaxtion_1_prop_param_adslab,
                    "relaxtion_prop_param_2_adslab": relaxtion_2_prop_param_adslab,
                    "static_prop_param_adslab": static_prop_param_adslab,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list

    def _set_restart_slabstatic_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:

        adslab_relax_step_flag = props_parameter['adslab']['relax_step']
        if adslab_relax_step_flag:

            timeout_1 = props_parameter["adslab"]["relaxtion_1"]["max_relax_time"]
            timeout_2 = props_parameter["adslab"]["relaxtion_2"]["max_relax_time"]
            restartslabstaticSteps = DiviRestartslabstaticSteps(
                name='divi-restart-step-slabstatic-flow',
                make_op=self.props_make_op,
                run_op=self.run_op,
                post_op=self.props_post_op,
                make_image=self.make_image,
                run_image=self.run_image,
                post_image=self.post_image,
                run_command=self.run_command,
                calculator=self.calculator,
                group_size=self.group_size,
                pool_size=self.pool_size,
                executor=self.executor,
                upload_python_packages=self.upload_python_packages,
                timeout_1 = timeout_1,
                timeout_2 = timeout_2,
            )
        else:
            max_relax_time = props_parameter["adslab"]["relaxtion"]["max_relax_time"]
            restartslabstaticSteps = RestartslabstaticSteps(
                name='restart-step-slabstatic-flow',
                make_op=self.props_make_op,
                run_op=self.run_op,
                post_op=self.props_post_op,
                make_image=self.make_image,
                run_image=self.run_image,
                post_image=self.post_image,
                run_command=self.run_command,
                calculator=self.calculator,
                group_size=self.group_size,
                pool_size=self.pool_size,
                executor=self.executor,
                upload_python_packages=self.upload_python_packages,
                timeout = max_relax_time
            )
        confs = props_parameter["structures"]
        interaction = props_parameter["interaction"]


        static_prop_param_slab = props_parameter["slab"]["static"]


        relaxtion_prop_param_adslab = props_parameter["adslab"]["relaxtion"]
        static_prop_param_adslab = props_parameter["adslab"]["static"]
        relaxtion_1_prop_param_adslab = props_parameter["adslab"]["relaxtion_1"]
        relaxtion_2_prop_param_adslab = props_parameter["adslab"]["relaxtion_2"]

        conf_dirs = []
        flow_id_list = []
        path_to_prop_static_slab_list = []
        path_to_prop_relaxtion_adslab_list = []
        path_to_prop_static_adslab_list = []

        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()

        for ii in conf_dirs:

            path_to_prop_static_slab = os.path.join(ii, 'slab/static')
            path_to_prop_static_slab_list.append(path_to_prop_static_slab)

            path_to_prop_relaxtion_adslab = os.path.join(ii, 'adslab/relaxtion')
            path_to_prop_relaxtion_adslab_list.append(path_to_prop_relaxtion_adslab)
            path_to_prop_static_adslab = os.path.join(ii, 'adslab/static')
            path_to_prop_static_adslab_list.append(path_to_prop_static_adslab)
            flow_id_list.append(ii)
        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []
        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)
            subprop_step = Step(
                name=f'{clean_subflow_id}',
                template=restartslabstaticSteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop_static_slab": path_to_prop_static_slab_list[ii],
                    "path_to_prop_relaxtion_adslab": path_to_prop_relaxtion_adslab_list[ii],
                    "path_to_prop_static_adslab": path_to_prop_static_adslab_list[ii],
                    "static_prop_param_slab": static_prop_param_slab,
                    "relaxtion_prop_param_adslab": relaxtion_prop_param_adslab,
                    "relaxtion_prop_param_1_adslab": relaxtion_1_prop_param_adslab,
                    "relaxtion_prop_param_2_adslab": relaxtion_2_prop_param_adslab,
                    "static_prop_param_adslab": static_prop_param_adslab,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list

    def _set_restart_adslabrelax_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:

        max_relax_time = props_parameter["adslab"]["relaxtion"]["max_relax_time"]
        restartadslabrelaxSteps = RestartadslabrelaxSteps(
            name='restart-step-adslabrelax-flow',
            make_op=self.props_make_op,
            run_op=self.run_op,
            post_op=self.props_post_op,
            make_image=self.make_image,
            run_image=self.run_image,
            post_image=self.post_image,
            run_command=self.run_command,
            calculator=self.calculator,
            group_size=self.group_size,
            pool_size=self.pool_size,
            executor=self.executor,
            upload_python_packages=self.upload_python_packages,
            timeout = max_relax_time
        )
        confs = props_parameter["structures"]
        interaction = props_parameter["interaction"]



        relaxtion_prop_param_adslab = props_parameter["adslab"]["relaxtion"]
        static_prop_param_adslab = props_parameter["adslab"]["static"]
        conf_dirs = []
        flow_id_list = []
        path_to_prop_relaxtion_adslab_list = []
        path_to_prop_static_adslab_list = []

        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()

        for ii in conf_dirs:

            path_to_prop_relaxtion_adslab = os.path.join(ii, 'adslab/relaxtion')
            path_to_prop_relaxtion_adslab_list.append(path_to_prop_relaxtion_adslab)
            path_to_prop_static_adslab = os.path.join(ii, 'adslab/static')
            path_to_prop_static_adslab_list.append(path_to_prop_static_adslab)
            flow_id_list.append(ii)
        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []

        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)
            subprop_step = Step(
                name=f'{clean_subflow_id}',
                template=restartadslabrelaxSteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop_relaxtion_adslab": path_to_prop_relaxtion_adslab_list[ii],
                    "path_to_prop_static_adslab": path_to_prop_static_adslab_list[ii],
                    "relaxtion_prop_param_adslab": relaxtion_prop_param_adslab,
                    "static_prop_param_adslab": static_prop_param_adslab,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list


    def _set_restart_adslabrelax1_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:

        timeout_1 = props_parameter["adslab"]["relaxtion_1"]["max_relax_time"]
        timeout_2 = props_parameter["adslab"]["relaxtion_2"]["max_relax_time"]
        restartadslabrelaxSteps = DiviRestartadslabrelax1Steps(
            name='divi-restart-step-adslabrelax-1-flow',
            make_op=self.props_make_op,
            run_op=self.run_op,
            post_op=self.props_post_op,
            make_image=self.make_image,
            run_image=self.run_image,
            post_image=self.post_image,
            run_command=self.run_command,
            calculator=self.calculator,
            group_size=self.group_size,
            pool_size=self.pool_size,
            executor=self.executor,
            upload_python_packages=self.upload_python_packages,
            timeout_1 = timeout_1,
            timeout_2 = timeout_2,
        )
        confs = props_parameter["structures"]
        interaction = props_parameter["interaction"]


        relaxtion_prop_param_adslab = props_parameter["adslab"]["relaxtion"]
        static_prop_param_adslab = props_parameter["adslab"]["static"]
        relaxtion_1_prop_param_adslab = props_parameter["adslab"]["relaxtion_1"]
        relaxtion_2_prop_param_adslab = props_parameter["adslab"]["relaxtion_2"]

        conf_dirs = []
        flow_id_list = []
        path_to_prop_relaxtion_adslab_list = []
        path_to_prop_static_adslab_list = []

        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            symmetric_difference = []
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            #print(exclude_confs_dirs)
            for _ in conf_dirs:
                if _ not in exclude_confs_dirs:
                    symmetric_difference.append(_)
            conf_dirs  = symmetric_difference
            conf_dirs.sort()

        #print(conf_dirs)
        #print(len(conf_dirs))
        #sys.exit(0)
        for ii in conf_dirs:

            path_to_prop_relaxtion_adslab = os.path.join(ii, 'adslab/relaxtion')
            path_to_prop_relaxtion_adslab_list.append(path_to_prop_relaxtion_adslab)
            path_to_prop_static_adslab = os.path.join(ii, 'adslab/static')
            path_to_prop_static_adslab_list.append(path_to_prop_static_adslab)
            flow_id_list.append(ii)
        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []

        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)
            subprop_step = Step(
                name=f'{clean_subflow_id}',
                template=restartadslabrelaxSteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop_relaxtion_adslab": path_to_prop_relaxtion_adslab_list[ii],
                    "path_to_prop_static_adslab": path_to_prop_static_adslab_list[ii],
                    "relaxtion_prop_param_adslab": relaxtion_prop_param_adslab,
                    "relaxtion_prop_param_1_adslab": relaxtion_1_prop_param_adslab,
                    "relaxtion_prop_param_2_adslab": relaxtion_2_prop_param_adslab,
                    "static_prop_param_adslab": static_prop_param_adslab,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list


    def _set_restart_adslabrelax2_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:


        timeout_2 = props_parameter["adslab"]["relaxtion_2"]["max_relax_time"]
        restartadslabrelaxSteps = DiviRestartadslabrelax2Steps(
            name='divi-restart-step-adslabrelax-2-flow',
            make_op=self.props_make_op,
            run_op=self.run_op,
            post_op=self.props_post_op,
            make_image=self.make_image,
            run_image=self.run_image,
            post_image=self.post_image,
            run_command=self.run_command,
            calculator=self.calculator,
            group_size=self.group_size,
            pool_size=self.pool_size,
            executor=self.executor,
            upload_python_packages=self.upload_python_packages,
            timeout_2 = timeout_2,
        )
        confs = props_parameter["structures"]
        interaction = props_parameter["interaction"]
        relaxtion_prop_param_adslab = props_parameter["adslab"]["relaxtion"]
        static_prop_param_adslab = props_parameter["adslab"]["static"]
        relaxtion_1_prop_param_adslab = props_parameter["adslab"]["relaxtion_1"]
        relaxtion_2_prop_param_adslab = props_parameter["adslab"]["relaxtion_2"]

        conf_dirs = []
        flow_id_list = []
        path_to_prop_relaxtion_adslab_list = []
        path_to_prop_static_adslab_list = []

        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()

        for ii in conf_dirs:

            path_to_prop_relaxtion_adslab = os.path.join(ii, 'adslab/relaxtion')
            path_to_prop_relaxtion_adslab_list.append(path_to_prop_relaxtion_adslab)
            path_to_prop_static_adslab = os.path.join(ii, 'adslab/static')
            path_to_prop_static_adslab_list.append(path_to_prop_static_adslab)
            flow_id_list.append(ii)
        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []

        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)
            subprop_step = Step(
                name=f'{clean_subflow_id}',
                template=restartadslabrelaxSteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop_relaxtion_adslab": path_to_prop_relaxtion_adslab_list[ii],
                    "path_to_prop_static_adslab": path_to_prop_static_adslab_list[ii],
                    "relaxtion_prop_param_adslab": relaxtion_prop_param_adslab,
                    "relaxtion_prop_param_1_adslab": relaxtion_1_prop_param_adslab,
                    "relaxtion_prop_param_2_adslab": relaxtion_2_prop_param_adslab,
                    "static_prop_param_adslab": static_prop_param_adslab,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list

    def _set_restart_adslabstatic_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:


        restartadslabstaticSteps = RestartadslabstaticSteps(
            name='restart-step-adslabstatic-flow',
            make_op=self.props_make_op,
            run_op=self.run_op,
            post_op=self.props_post_op,
            make_image=self.make_image,
            run_image=self.run_image,
            post_image=self.post_image,
            run_command=self.run_command,
            calculator=self.calculator,
            group_size=self.group_size,
            pool_size=self.pool_size,
            executor=self.executor,
            upload_python_packages=self.upload_python_packages
        )
        confs = props_parameter["structures"]
        interaction = props_parameter["interaction"]

        static_prop_param_adslab = props_parameter["adslab"]["static"]
        conf_dirs = []
        flow_id_list = []
        path_to_prop_static_adslab_list = []
        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()

        for ii in conf_dirs:
            path_to_prop_static_adslab = os.path.join(ii, 'adslab/static')
            path_to_prop_static_adslab_list.append(path_to_prop_static_adslab)
            flow_id_list.append(ii)
        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []
        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)
            subprop_step = Step(
                name=f'{clean_subflow_id}',
                template=restartadslabstaticSteps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop_static_adslab": path_to_prop_static_adslab_list[ii],
                    "static_prop_param_adslab": static_prop_param_adslab,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list


    def _set_restart_tsrun2_flow(
            self,
            input_work_dir: dflow.common.S3Artifact,
            props_parameter: dict
    ) -> [List[Step], List[str]]:


        restarttsrun2steps = RestartTsrun2Steps(
            name='restart-tsrun2-calc',
            make_op=self.props_make_op,
            run_op=self.run_op,
            modify_run_op = self.modify_run_op,
            post_op=self.props_post_op,
            make_image=self.make_image,
            run_image=self.run_image,
            post_image=self.post_image,
            run_command=self.run_command,
            calculator=self.calculator,
            group_size=self.group_size,
            pool_size=self.pool_size,
            executor=self.executor,
            upload_python_packages=self.upload_python_packages
        )

        confs = props_parameter["structures"]
        interaction = props_parameter["interaction"]
        tsrun2_prop_param = props_parameter["ts"]["tsrun2"]
        tsrun3_prop_param = props_parameter["ts"]["tsrun3"]

        conf_dirs = []
        flow_id_list = []
        path_to_prop_ts_list = []
        for conf in confs:
            conf_dirs.extend(glob.glob(conf))
        conf_dirs = list(set(conf_dirs))
        conf_dirs.sort()

        include_confs = props_parameter['include']
        exclude_confs = props_parameter['exclude']

        if isinstance(include_confs, list) and len(include_confs)>0:
            include_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in include_confs]
            intersection_set = set(conf_dirs) & set(include_confs_dirs)
            conf_dirs  = list(intersection_set)
            conf_dirs.sort()

        if isinstance(exclude_confs, list) and len(exclude_confs)>0:
            exclude_confs_dirs = ['confs/{}'.format(struct_name) for struct_name in exclude_confs]
            symmetric_difference = list(set(conf_dirs) ^ set(exclude_confs_dirs))
            conf_dirs  = list(symmetric_difference)
            conf_dirs.sort()

        for ii in conf_dirs:
            path_to_prop_ts = os.path.join(ii, 'ts')
            path_to_prop_ts_list.append(path_to_prop_ts)
            flow_id_list.append(ii + '-' + 'ts')
            #if os.path.exists(path_to_prop_relaxtion):
            #    shutil.rmtree(path_to_prop_relaxtion)

        nflow = len(flow_id_list)
        subprops_list = []
        subprops_key_list = []
        for ii in range(nflow):
            clean_subflow_id = re.sub(r'[^a-zA-Z0-9-]', '-', flow_id_list[ii]).lower()
            subflow_key = f'adsec-{clean_subflow_id}'
            subprops_key_list.append(subflow_key)

            subprop_step =  Step(
                name=f'{clean_subflow_id}',
                template= restarttsrun2steps,
                artifacts={
                    "input_work_path": input_work_dir
                },
                parameters={
                    "flow_id": flow_id_list[ii],
                    "path_to_prop": path_to_prop_ts_list[ii],
                    "tsrun2_prop_param": tsrun2_prop_param,
                    "tsrun3_prop_param": tsrun3_prop_param,
                    "inter_param": interaction,
                    },
                key=subflow_key
            )
            subprops_list.append(subprop_step)

        return subprops_list, subprops_key_list

    @json2dict
    def submit_bulk(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-bulk'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_bulk_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    @json2dict
    def submit_slab(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-slab'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_slab_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    def submit_adslab(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = False,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-adslab'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_adslab_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id


    def submit_joint(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-joint'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_joint_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
        # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id


    def submit_bulkrelax(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-bulkrelax'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_bulkrelax_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    def submit_bulkstatic(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-bulkstatic'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_bulkstatic_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    def submit_slabrelax(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-slabrelax'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_slabrelax_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    def submit_slabstatic(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-slabstatic'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_slabstatic_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    def submit_adslabrelax(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-adslabrelax'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_adslabrelax_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    def submit_adslabrelax1(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-adslabrelax-1'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_adslabrelax1_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    def submit_adslabrelax2(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-adslabrelax-2'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_adslabrelax2_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    def submit_adslabstatic(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-adslabstatic'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_adslabstatic_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    def submit_all(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-all'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_all_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
        # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    def submit_ts(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-ts'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_ts_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
        # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    def submit_tsrun1(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-ts'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_tsrun1_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
        # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    def submit_tsrun2(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-ts'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_tsrun2_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
        # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id


    def submit_tsrun3(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-ts'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_tsrun3_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
        # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    @json2dict
    def submit_mol(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-mol'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_mol_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)


        return self.workflow.id

    def restart_bulkstatic(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-restart-step-bulkstatic'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_restart_bulkstatic_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    def restart_slabrelax(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-restart-step-slabrelax'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_restart_slabrelax_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    def restart_slabstatic(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-restart-step-slabstatic'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_restart_slabstatic_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    def restart_adslabrelax(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-restart-step-adslabrelax'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_restart_adslabrelax_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    def restart_adslabrelax1(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-restart-step-adslabrelax-1'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_restart_adslabrelax1_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    def restart_adslabrelax2(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-restart-step-adslabrelax-2'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_restart_adslabrelax2_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

    def restart_adslabstatic(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-restart-step-adslabstatic'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_restart_adslabstatic_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id


    def restart_tsrun2(
            self,
            upload_path: Union[os.PathLike, str],
            download_path: Union[os.PathLike, str],
            props_parameter: dict,
            submit_only: bool = True,
            name: Optional[str] = None,
            labels: Optional[dict] = None
    ) -> str:
        self.upload_path = upload_path
        self.download_path = download_path
        self.props_param = props_parameter
        flow_name = name if name else self.regulate_name(os.path.basename(download_path))
        flow_name += '-restart-tsrun2'
        self.workflow = Workflow(name=flow_name, labels=labels)
        subprops_list, subprops_key_list = self._set_restart_tsrun2_flow(
            input_work_dir=upload_artifact(upload_path),
            props_parameter=props_parameter
        )
        self.workflow.add(subprops_list)
        self.workflow.submit()
        self.dump_flow_id()
        if not submit_only:
            # wait for and retrieve sub-property flows
            self._monitor_props(subprops_key_list)

        return self.workflow.id

