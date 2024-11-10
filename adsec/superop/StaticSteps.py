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


class StaticSteps(Steps):
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
    ):
        self._input_parameters = {
            "flow_id": InputParameter(type=str, value="", optional=True),
            "path_to_prop": InputParameter(type=str),
            "prop_param": InputParameter(type=dict),
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

        self._keys = ["make", "run", "post"]
        self.step_keys = {}
        name_1 = name.split("-")[0]
        key = "make"
        key_1 = "{}-make".format(name)
        self.step_keys[key] = '-'.join(
            [str(self.inputs.parameters["flow_id"]), key_1]
        )
        key = "run"
        key_1 = "{}-run".format(name_1)
        self.step_keys[key] = '-'.join(
            [str(self.inputs.parameters["flow_id"]), key_1 + "-{{item}}"]
        )

        key = "post"
        key_1 = "{}-post".format(name_1)
        self.step_keys[key] = '-'.join(
            [str(self.inputs.parameters["flow_id"]), key_1]
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
            upload_python_packages
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
    ):
        # Step for static make
        static_make = Step(
            name="static-make",
            template=PythonOPTemplate(
                make_op,
                image=make_image,
                python_packages=upload_python_packages,
                command=["python3"]
            ),
            artifacts={"input_work_path": self.inputs.artifacts["input_work_path"]},
            parameters={"prop_param": self.inputs.parameters["prop_param"],
                        "inter_param": self.inputs.parameters["inter_param"],
                        "path_to_prop": self.inputs.parameters["path_to_prop"]},
            key=self.step_keys["make"]
        )
        self.add(static_make)
        
        # Step for static run
        if calculator in ['vasp']:
            run_fp = PythonOPTemplate(
                run_op,
                slices=Slices(
                              "{{item}}",
                    input_parameter=["task_name"],
                    input_artifact=["task_path"],
                    output_artifact=["backward_dir"],
                    group_size=group_size,
                    pool_size=pool_size
                ),
                python_packages=upload_python_packages,
                image=run_image
            )
        if calculator == 'vasp':
            static_runcal = Step(
                name="static-run",
                template=run_fp,
                parameters={
                    "run_image_config": {"command": run_command},
                    "task_name": static_make.outputs.parameters["task_names"],
                    "backward_list": ["INCAR", "POSCAR","POTCAR","KPOINTS","OUTCAR", "vasprun.xml","CONTCAR","DOSCAR","EIGENVAL","IBZKPT","OSZICAR","PCDAT","XDATCAR"]           
                    },
                artifacts={
                    "task_path": static_make.outputs.artifacts["task_paths"]
                },
                with_param=argo_range(argo_len(static_make.outputs.parameters["task_names"])),
                key=self.step_keys["run"],
                executor=executor,
            )
    
        else:
            raise RuntimeError(f'Incorrect calculator type to initiate step: {calculator}')
        self.add(static_runcal)

        # Step for static post
        static_post = Step(
            name="static-post",
            template=PythonOPTemplate(
                post_op,
                image=post_image,
                python_packages=upload_python_packages,
                command=["python3"]
            ),
            artifacts={
                "input_post": static_runcal.outputs.artifacts["backward_dir"],
                "input_all": static_make.outputs.artifacts["output_work_path"]
            },
            parameters={
                "prop_param": self.inputs.parameters["prop_param"],
                "inter_param": self.inputs.parameters["inter_param"],
                "task_names": static_make.outputs.parameters["task_names"],
                "path_to_prop": self.inputs.parameters["path_to_prop"]
            },
            key=self.step_keys["post"]
        )
        self.add(static_post)

        self.outputs.artifacts["retrieve_path"]._from \
            = static_post.outputs.artifacts["retrieve_path"]
