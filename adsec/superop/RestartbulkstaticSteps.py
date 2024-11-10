import os
import sys
from pathlib import (
    Path,
)
from typing import (
    List,
    Optional,
    Type,
)
from dflow import (
    InputArtifact,
    InputParameter,
    Inputs,
    OutputArtifact,
    Outputs,
    Step,
    Steps,
    argo_len,
    argo_range,
    upload_artifact,
)
from dflow.python import (
    OP,
    PythonOPTemplate,
    Slices,
)
from dflow.plugins.dispatcher import DispatcherExecutor
from adsec.superop.RelaxPropertySteps import RelaxPropertySteps
from adsec.superop.RelaxtionSteps import RelaxtionSteps
from adsec.superop.StaticSteps import StaticSteps


class RestartbulkstaticSteps(Steps):
    def __init__(
        self,
        name: str,
        make_op: Type[OP],
        run_op: Type[OP],
        post_op: Type[OP],
        make_image: str,
        run_image: str,
        post_image: str,
        run_command: str,
        calculator: str,
        group_size: Optional[int] = None,
        pool_size: Optional[int] = None,
        executor: Optional[DispatcherExecutor] = None,
        upload_python_packages: Optional[List[os.PathLike]] = None,
        timeout: Optional[float] = 72000
    ):
        self._input_parameters = {
            "flow_id": InputParameter(type=str, value=""),
            "path_to_prop_relaxtion_bulk": InputParameter(type=str),
            "path_to_prop_static_bulk": InputParameter(type=str),
            "path_to_prop_relaxtion_slab": InputParameter(type=str),
            "path_to_prop_static_slab": InputParameter(type=str),
            "path_to_prop_relaxtion_adslab": InputParameter(type=str),
            "path_to_prop_static_adslab": InputParameter(type=str),
            "relaxtion_prop_param_bulk": InputParameter(type=dict),
            "static_prop_param_bulk": InputParameter(type=dict),
            "relaxtion_prop_param_slab": InputParameter(type=dict),
            "static_prop_param_slab": InputParameter(type=dict),
            "relaxtion_prop_param_adslab": InputParameter(type=dict),
            "relaxtion_prop_param_1_adslab": InputParameter(type=dict),
            "relaxtion_prop_param_2_adslab": InputParameter(type=dict),
            "static_prop_param_adslab": InputParameter(type=dict),
            "inter_param": InputParameter(type=dict)
        }
        self._input_artifacts = {
            "input_work_path": InputArtifact(type=Path)
        }
        self._output_parameters = {}
        self._output_artifacts = {
            "retrieve_path": OutputArtifact(type=Path)
        }

        super().__init__(
            name=name,
            inputs=Inputs(
                parameters=self._input_parameters,
                artifacts=self._input_artifacts
            ),
            outputs=Outputs(
                parameters=self._output_parameters,
                artifacts=self._output_artifacts
            ),
        )

        self._keys = ["bulk-static-step", "slab-relaxtion-step","slab-static-step","adslab-relaxtion-step","adslab-static-step"]
        self.step_keys = {}

        key = "bulk-static-step"
        self.step_keys[key] = '--'.join(
            [str(self.inputs.parameters["flow_id"]), key]
        )

        key = "slab-relaxtion-step"
        self.step_keys[key] = '--'.join(
            [str(self.inputs.parameters["flow_id"]), key]
        )
        key = "slab-static-step"
        self.step_keys[key] = '--'.join(
            [str(self.inputs.parameters["flow_id"]), key]
        )

        key = "adslab-relaxtion-step"
        self.step_keys[key] = '--'.join(
            [str(self.inputs.parameters["flow_id"]), key]
        )
        key = "adslab-static-step"
        self.step_keys[key] = '--'.join(
            [str(self.inputs.parameters["flow_id"]), key]
        )

        self._build(
            name,
            make_op,
            run_op,
            post_op,
            make_image,
            run_image,
            post_image,
            run_command,
            calculator,
            group_size,
            pool_size,
            executor,
            upload_python_packages,
            timeout
        )

    @property
    def input_parameters(self):
        return self._input_parameters

    @property
    def input_artifacts(self):
        return self._input_artifacts

    @property
    def output_parameters(self):
        return self._output_parameters

    @property
    def output_artifacts(self):
        return self._output_artifacts

    @property
    def keys(self):
        return self._keys

    def _build(
        self,
        name: str,
        make_op: Type[OP],
        run_op: Type[OP],
        post_op: Type[OP],
        make_image: str,
        run_image: str,
        post_image: str,
        run_command: str,
        calculator: str,
        group_size: Optional[int] = None,
        pool_size: Optional[int] = None,
        executor: Optional[DispatcherExecutor] = None,
        upload_python_packages: Optional[List[os.PathLike]] = None,
        timeout: Optional[float] = 72000
    ):


        staticSteps = StaticSteps(
             name='bulk-static',
             make_op= make_op,
             run_op= run_op,
             post_op= post_op,
             make_image= make_image,
             run_image= run_image,
             post_image= post_image,
             run_command= run_command,
             calculator= calculator,
             group_size= group_size,
             pool_size= pool_size,
             executor= executor,
             upload_python_packages= upload_python_packages
         )


        bulk_static_step = Step(
            name=f'bulk-static-step',
            template = staticSteps,
            artifacts={
                "input_work_path": self.inputs.artifacts["input_work_path"]},
            parameters={
                "flow_id": self.inputs.parameters["flow_id"],
                "path_to_prop": self.inputs.parameters["path_to_prop_static_bulk"],
                "prop_param": self.inputs.parameters["static_prop_param_bulk"],
                "inter_param": self.inputs.parameters["inter_param"],
               },
            key= self.step_keys["bulk-static-step"]
        )
        self.add(bulk_static_step)


        relaxtionSteps = RelaxtionSteps(
            name='slab-relaxtion',
            make_op= make_op,
            run_op= run_op,
            post_op= post_op,
            make_image= make_image,
            run_image= run_image,
            post_image= post_image,
            run_command= run_command,
            calculator= calculator,
            group_size= group_size,
            pool_size= pool_size,
            executor= executor,
            upload_python_packages= upload_python_packages
        )

        slab_relaxtion_step = Step(
            name=f'slab-relaxtion-step',
            template = relaxtionSteps,
            artifacts={
                "input_work_path": bulk_static_step.outputs.artifacts["retrieve_path"]},
            parameters={
                "flow_id": self.inputs.parameters["flow_id"],
                "path_to_prop": self.inputs.parameters["path_to_prop_relaxtion_slab"],
                "prop_param": self.inputs.parameters["relaxtion_prop_param_slab"],
                "inter_param": self.inputs.parameters["inter_param"],
               },
            key= self.step_keys["slab-relaxtion-step"]
        )
        self.add(slab_relaxtion_step)

        staticSteps = StaticSteps(
             name='slab-static',
             make_op= make_op,
             run_op= run_op,
             post_op= post_op,
             make_image= make_image,
             run_image= run_image,
             post_image= post_image,
             run_command= run_command,
             calculator= calculator,
             group_size= group_size,
             pool_size= pool_size,
             executor= executor,
             upload_python_packages= upload_python_packages
         )


        slab_static_step = Step(
            name=f'slab-static-step',
            template = staticSteps,
            artifacts={
                "input_work_path": slab_relaxtion_step.outputs.artifacts["retrieve_path"]},
            parameters={
                "flow_id": self.inputs.parameters["flow_id"],
                "path_to_prop": self.inputs.parameters["path_to_prop_static_slab"],
                "prop_param": self.inputs.parameters["static_prop_param_slab"],
                "inter_param": self.inputs.parameters["inter_param"],
               },
            key= self.step_keys["slab-static-step"]
        )
        self.add(slab_static_step)

        relaxtionSteps = RelaxtionSteps(
            name='adslab-relaxtion',
            make_op= make_op,
            run_op= run_op,
            post_op= post_op,
            make_image= make_image,
            run_image= run_image,
            post_image= post_image,
            run_command= run_command,
            calculator= calculator,
            group_size= group_size,
            pool_size= pool_size,
            executor= executor,
            upload_python_packages= upload_python_packages,
            timeout = timeout
        )

        adslab_relaxtion_step = Step(
            name=f'adslab-relaxtion-step',
            template = relaxtionSteps,
            artifacts={
                "input_work_path": slab_static_step.outputs.artifacts["retrieve_path"]},
            parameters={
                "flow_id": self.inputs.parameters["flow_id"],
                "path_to_prop": self.inputs.parameters["path_to_prop_relaxtion_adslab"],
                "prop_param": self.inputs.parameters["relaxtion_prop_param_adslab"],
                "inter_param": self.inputs.parameters["inter_param"],
               },
            key= self.step_keys["adslab-relaxtion-step"]
        )
        self.add(adslab_relaxtion_step)

        staticSteps = StaticSteps(
             name='adslab-static',
             make_op= make_op,
             run_op= run_op,
             post_op= post_op,
             make_image= make_image,
             run_image= run_image,
             post_image= post_image,
             run_command= run_command,
             calculator= calculator,
             group_size= group_size,
             pool_size= pool_size,
             executor= executor,
             upload_python_packages= upload_python_packages
         )


        adslab_static_step = Step(
            name=f'adslab-static-step',
            template = staticSteps,
            artifacts={
                "input_work_path": adslab_relaxtion_step.outputs.artifacts["retrieve_path"]},
            parameters={
                "flow_id": self.inputs.parameters["flow_id"],
                "path_to_prop": self.inputs.parameters["path_to_prop_static_adslab"],
                "prop_param": self.inputs.parameters["static_prop_param_adslab"],
                "inter_param": self.inputs.parameters["inter_param"],
               },
            key= self.step_keys["adslab-static-step"]
        )
        self.add(adslab_static_step)

        self.outputs.artifacts["retrieve_path"]._from \
            = adslab_static_step.outputs.artifacts["retrieve_path"]
