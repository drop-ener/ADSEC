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


class TSCalcSteps(Steps):
    def __init__(
        self,
        name: str,
        make_op: Type[OP],
        run_op: Type[OP],
        modify_run_op: Type[OP],
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
        timeout: Optional[float] = 360000
    ):
        self._input_parameters = {
            "flow_id": InputParameter(type=str, value=""),
            "path_to_prop": InputParameter(type=str),
            "tsrun1_prop_param": InputParameter(type=dict),
            "tsrun2_prop_param": InputParameter(type=dict),
            "tsrun3_prop_param": InputParameter(type=dict),
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

        self._keys = ["ts-run1-step", "ts-run2-step", "ts-run3-step"]
        self.step_keys = {}
        key = "ts-run1-step"
        self.step_keys[key] = '--'.join(
            [str(self.inputs.parameters["flow_id"]), key]
        )
        key = "ts-run2-step"
        self.step_keys[key] = '--'.join(
            [str(self.inputs.parameters["flow_id"]), key]
        )

        key = "ts-run3-step"
        self.step_keys[key] = '--'.join(
            [str(self.inputs.parameters["flow_id"]), key]
        )

        self._build(
            name,
            make_op,
            run_op,
            modify_run_op,
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
        modify_run_op: Type[OP],
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
            name='tsrun1-calc',
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
            upload_python_packages=upload_python_packages
        )

        tsrun1_step =  Step(
                name=f'ts-run1-step',
                template=staticSteps,
                artifacts={
                    "input_work_path": self.inputs.artifacts["input_work_path"]
                },
                parameters={
                    "flow_id": self.inputs.parameters["flow_id"],
                    "path_to_prop": self.inputs.parameters["path_to_prop"],
                    "prop_param": self.inputs.parameters["tsrun1_prop_param"],
                    "inter_param": self.inputs.parameters["inter_param"],
                    },
                key=self.step_keys["ts-run1-step"]
            )

        self.add(tsrun1_step)

        relaxtionSteps = RelaxtionSteps(
            name='tsrun2-calc',
            make_op= make_op,
            run_op=modify_run_op,
            post_op=post_op,
            make_image=make_image,
            run_image=run_image,
            post_image=post_image,
            run_command=run_command,
            calculator=calculator,
            group_size=group_size,
            pool_size=pool_size,
            executor=executor,
            upload_python_packages=upload_python_packages
        )

        tsrun2_step =  Step(
                name=f'ts-run2-step',
                template=relaxtionSteps,
                artifacts={
                    "input_work_path": tsrun1_step.outputs.artifacts["retrieve_path"]
                },
                parameters={
                    "flow_id": self.inputs.parameters["flow_id"],
                    "path_to_prop": self.inputs.parameters["path_to_prop"],
                    "prop_param": self.inputs.parameters["tsrun2_prop_param"],
                    "inter_param": self.inputs.parameters["inter_param"]
                    },
                key=self.step_keys["ts-run2-step"]
            )

        self.add(tsrun2_step)


        freq_staticSteps = StaticSteps(
            name='tsrun3-calc',
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


        tsrun3_step =  Step(
                name=f'ts-run3-step',
                template= freq_staticSteps,
                artifacts={
                    "input_work_path": tsrun2_step.outputs.artifacts["retrieve_path"]
                },
                parameters={
                    "flow_id": self.inputs.parameters["flow_id"],
                    "path_to_prop": self.inputs.parameters["path_to_prop"],
                    "prop_param": self.inputs.parameters["tsrun3_prop_param"],
                    "inter_param": self.inputs.parameters["inter_param"]
                    },
                key=self.step_keys["ts-run3-step"]
            )

        self.add(tsrun3_step)

        self.outputs.artifacts["retrieve_path"]._from \
            = tsrun3_step.outputs.artifacts["retrieve_path"]
