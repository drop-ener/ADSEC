import argparse
import logging
import os
import datetime
from typing import List

from dflow import (
    Workflow,
    query_workflows,
    download_artifact
)

from apex.config import Config

from adsec.utils.utils import (
    judge_flow,
    load_config_file,
    json2dict,
    copy_all_other_files,
    sepline,
    handle_prop_suffix,
    backup_path
)

from adsec import __version__
from adsec.submit import submit_from_args
from adsec.restart import restart_from_args

def parse_args():
    parser = argparse.ArgumentParser(
        description=f"ADSEC: A scientific workflow for ADSorption Energy Calculation "
                    f"using simulations (v{__version__})\n"
                    f"Type 'adsec -h' for help.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    subparsers = parser.add_subparsers(title="Valid subcommands", dest="cmd")

    # version
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"ADSEC v{__version__}"
    )
    ##########################################
    # Submit
    parser_submit = subparsers.add_parser(
        "submit",
        help="Submit an ADSEC workflow",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser_submit.add_argument(
        "parameter", type=str, nargs='+',
        help='Json files to indicate calculation parameters'
    )
    parser_submit.add_argument(
        "-c", "--config",
        type=str, nargs='?',
        default='./global.json',
        help="The json file to config workflow",
    )
    parser_submit.add_argument(
        "-w", "--work",
        type=str, nargs='+',
        default='.',
        help="(Optional) Work directories to be submitted",
    )
    parser_submit.add_argument(
        '-f', "--flow",
        choices=['bulk', 'slab','adslab', 'joint','mol','bulkrelax', 'bulkstatic', 'slabrelax','slabstatic','adslabrelax','adslabrelax1','adslabrelax2','adslabstatic','all','ts','tsrun1','tsrun2','tsrun3'],
        help="(Optional) Specify type of workflow to submit: (bulk | slab | adslab |joint|mol|bulkrelax|bulkstatic|slabrelax|slabstatic|adslabrelax|adslabrelax1|adslabrelax2|adslabstatic|ts|tsrun1|tsrun2|tsrun3)"
    )
 
    parser_submit.add_argument(
        "-n", "--name",
        type=str, default=None,
        help="(Optional) Specify name of the workflow",
    )


    ##########################################
    # restart
    parser_submit = subparsers.add_parser(
        "restart",
        help="restart an ADSEC workflow",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser_submit.add_argument(
        "parameter", type=str, nargs='+',
        help='Json files to indicate calculation parameters'
    )
    parser_submit.add_argument(
        "-c", "--config",
        type=str, nargs='?',
        default='./global.json',
        help="The json file to config workflow",
    )
    parser_submit.add_argument(
        "-w", "--work",
        type=str, nargs='+',
        default='.',
        help="(Optional) Work directories to be submitted",
    )
    parser_submit.add_argument(
        '-s', "--step",
        choices=['bulkstatic', 'slabrelax','slabstatic','adslabrelax','adslabrelax1','adslabrelax2','adslabstatic','tsrun2'],
        help="(Optional) Specify type of workflow to submit: ( bulkstatic | slabrelax | slabstatic | adslabrelax | adslabrelax1|adslabrelax2|adslabstatic|tsrun2)"
    )

    parser_submit.add_argument(
        "-n", "--name",
        type=str, default=None,
        help="(Optional) Specify name of the workflow",
    )

    ##########################################
    ### dflow operations
    # list workflows
    parser_list = subparsers.add_parser(
        "list",
        help="List workflows",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_list.add_argument(
        "-l",
        "--label",
        type=str,
        default=None,
        help="query by labels",
    )
    parser_list.add_argument(
        "-c", "--config",
        type=str, nargs='?',
        default='./global.json',
        help="The json file to config workflow",
    )

    ##########################################
    # Download artifacts manually
    parser_download = subparsers.add_parser(
        "download",
        help="Download results of an workflow with key provided manually",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser_download.add_argument(
        "-i", "--id", type=str, default=None,
        help='Workflow ID to be download'
    )
    parser_download.add_argument(
        "-w", "--work", type=str, default='.',
        help='Target work directory to be download'
    )
    parser_download.add_argument(
        "-c", "--config",
        type=str, nargs='?',
        default='./global.json',
        help="The json file to config workflow",
    )

    # retrieve artifacts manually
    parser_retrieve = subparsers.add_parser(
        "retrieve",
        help="Download results of an workflow with key provided manually",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser_retrieve.add_argument(
        "-i", "--id", type=str, default=None,
        help='Workflow ID to be download'
    )
    parser_retrieve.add_argument(
        "-w", "--work", type=str, default='.',
        help='Target work directory to be download'
    )
    parser_retrieve.add_argument(
        "-c", "--config",
        type=str, nargs='?',
        default='./global.json',
        help="The json file to config workflow",
    )

    parser_retrieve.add_argument(
        "-k", "--key", type=str, default=None,
        help='step key'
    )

    # stop workflow
    parser_stop = subparsers.add_parser(
        "stop",
        help="Stop a workflow",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_stop.add_argument(
        "-i", "--id", type=str, default=None,
        help='Workflow ID to stop'
    )
    parser_stop.add_argument(
        "-w", "--work", type=str, default='.',
        help='Target work directory to stop'
    )
    parser_stop.add_argument(
        "-c", "--config",
        type=str, nargs='?',
        default='./global.json',
        help="The json file to config workflow",
    )

    # suspend workflow
    parser_suspend = subparsers.add_parser(
        "suspend",
        help="Suspend a workflow",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_suspend.add_argument(
        "-i", "--id", type=str, default=None,
        help='Workflow ID to suspend'
    )
    parser_suspend.add_argument(
        "-w", "--work", type=str, default='.',
        help='Target work directory to suspend'
    )
    parser_suspend.add_argument(
        "-c", "--config",
        type=str, nargs='?',
        default='./global.json',
        help="The json file to config workflow",
    )

    # terminate workflow
    parser_terminate = subparsers.add_parser(
        "terminate",
        help="Terminate a workflow",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_terminate.add_argument(
        "-i", "--id", type=str, default=None,
        help='Workflow ID to terminate'
    )
    parser_terminate.add_argument(
        "-w", "--work", type=str, default='.',
        help='Target work directory to terminate'
    )
    parser_terminate.add_argument(
        "-c", "--config",
        type=str, nargs='?',
        default='./global.json',
        help="The json file to config workflow",
    )

    # resubmit workflow
    parser_resubmit = subparsers.add_parser(
        "resubmit",
        help="Resubmit a workflow",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_resubmit.add_argument(
        "-i", "--id", type=str, default=None,
        help='Workflow ID to resubmit'
    )
    parser_resubmit.add_argument(
        "-w", "--work", type=str, default='.',
        help='Target work directory to resubmit'
    )
    parser_resubmit.add_argument(
        "-c", "--config",
        type=str, nargs='?',
        default='./global.json',
        help="The json file to config workflow",
    )

    # retry workflow
    parser_retry = subparsers.add_parser(
        "retry",
        help="Retry a workflow",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_retry.add_argument(
        "-i", "--id", type=str, default=None,
        help='Workflow ID to retry'
    )
    parser_retry.add_argument(
        "-w", "--work", type=str, default='.',
        help='Target work directory to retry'
    )
    parser_retry.add_argument(
        "-s",
        "--step",
        type=str,
        default=None,
        help="retry a step in a running workflow with step ID (experimental)",
    )

    parser_retry.add_argument(
        "-c", "--config",
        type=str, nargs='?',
        default='./global.json',
        help="The json file to config workflow",
    )

    # resume workflow
    parser_resume = subparsers.add_parser(
        "resume",
        help="Resume a workflow",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_resume.add_argument(
        "-i", "--id", type=str, default=None,
        help='Workflow ID to resume'
    )
    parser_resume.add_argument(
        "-w", "--work", type=str, default='.',
        help='Target work directory to resume'
    )
    parser_resume.add_argument(
        "-c", "--config",
        type=str, nargs='?',
        default='./global.json',
        help="The json file to config workflow",
    )

    # get workflow
    parser_get = subparsers.add_parser(
        "get",
        help="Get a workflow",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_get.add_argument(
        "-i", "--id", type=str, default=None,
        help='Workflow ID to get'
    )
    parser_get.add_argument(
        "-w", "--work", type=str, default='.',
        help='Target work directory to get'
    )
    parser_get.add_argument(
        "-c", "--config",
        type=str, nargs='?',
        default='./global.json',
        help="The json file to config workflow",
    )
    #  getkeys of workflow
    parser_getkeys = subparsers.add_parser(
        "getkeys",
        help="Get keys of steps from a workflow",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_getkeys.add_argument(
        "-i", "--id", type=str, default=None,
        help='Workflow ID to get keys'
    )
    parser_getkeys.add_argument(
        "-w", "--work", type=str, default='.',
        help='Target work directory get keys'
    )
    parser_getkeys.add_argument(
        "-c", "--config",
        type=str, nargs='?',
        default='./global.json',
        help="The json file to config workflow",
    )

        # get steps of workflow
    parser_getsteps = subparsers.add_parser(
        "getsteps",
        help="Get steps from a workflow",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_getsteps.add_argument("ID", help="the workflow ID.")
    parser_getsteps.add_argument(
        "-n",
        "--name",
        type=str,
        default=None,
        help="query by name",
    )
    parser_getsteps.add_argument(
        "-k",
        "--key",
        type=str,
        default=None,
        help="query by key",
    )
    parser_getsteps.add_argument(
        "-p",
        "--phase",
        type=str,
        default=None,
        help="query by phase",
    )
    parser_getsteps.add_argument(
        "-i",
        "--id",
        type=str,
        default=None,
        help="workflow ID to query",
    )
    parser_getsteps.add_argument(
        "-w", "--work", type=str, default='.',
        help='Target work directory'
    )
    parser_getsteps.add_argument(
        "-t",
        "--type",
        type=str,
        default=None,
        help="query by type",
    )
    parser_getsteps.add_argument(
        "-c", "--config",
        type=str, nargs='?',
        default='./global.json',
        help="The json file to config workflow",
    )

    parsed_args = parser.parse_args()
    # print help if no parser
    if not parsed_args.cmd:
        parser.print_help()

    return parser, parsed_args

def config_dflow(config_file: os.PathLike) -> None:
    # config dflow_config and s3_config
    config_dict = load_config_file(config_file)
    wf_config = Config(**config_dict)
    Config.config_dflow(wf_config.dflow_config_dict)
    Config.config_bohrium(wf_config.bohrium_config_dict)
    Config.config_s3(wf_config.dflow_s3_config_dict)

def format_time_delta(td: datetime.timedelta) -> str:
    if td.days > 0:
        return "%dd" % td.days
    elif td.seconds >= 3600:
        return "%dh" % (td.seconds // 3600)
    else:
        return "%ds" % td.seconds

def format_print_table(t: List[List[str]]):
    ncol = len(t[0])
    maxlen = [0] * ncol
    for row in t:
        for i, s in enumerate(row):
            if len(str(s)) > maxlen[i]:
                maxlen[i] = len(str(s))
    for row in t:
        for i, s in enumerate(row):
            print(str(s) + " " * (maxlen[i]-len(str(s))+3), end="")
        print()

def get_id_from_record(work_dir: os.PathLike, operation_name: str = None) -> str:
    logging.info(msg='No workflow_id is provided, will employ the latest workflow')
    workflow_log = os.path.join(work_dir, '.workflow.log')
    assert os.path.isfile(workflow_log), \
        'No workflow_id is provided and no .workflow.log file found in work_dir'
    with open(workflow_log, 'r') as f:
        try:
            last_record = f.readlines()[-1]
        except IndexError:
            raise RuntimeError('No workflow_id is provided and .workflow.log file is empty!')
    workflow_id = last_record.split('\t')[0]
    assert workflow_id, 'No workflow ID for operation!'
    logging.info(msg=f'Operating on workflow ID: {workflow_id}')
    if operation_name:
        modified_record = last_record.split('\t')
        modified_record[1] = operation_name
        modified_record[2] = datetime.datetime.now().isoformat()
        with open(workflow_log, 'a') as f:
            f.write('\t'.join(modified_record))
    return workflow_id


def main():
    # logging
    logging.basicConfig(level=logging.INFO)
    # parse args
    parser, args = parse_args()
    if args.cmd == 'submit':
        #header()
        submit_from_args(
            parameters=args.parameter,
            config_file=args.config,
            work_dirs=args.work,
            indicated_flow_type=args.flow,
            flow_name=args.name
        )
    elif args.cmd == 'restart':
        #header()
        restart_from_args(
            parameters=args.parameter,
            config_file=args.config,
            work_dirs=args.work,
            restart_step = args.step,
            flow_name=args.name
        )
    elif args.cmd == "list":
        config_dflow(args.config)
        if args.label is not None:
            labels = {}
            for label in args.label.split(","):
                key, value = label.split("=")
                labels[key] = value
        else:
            labels = None
        wfs = query_workflows(labels=labels)
        t = [["NAME", "STATUS", "AGE", "DURATION"]]
        for wf in wfs:
            tc = datetime.datetime.strptime(wf.metadata.creationTimestamp,
                                            "%Y-%m-%dT%H:%M:%SZ")
            age = format_time_delta(datetime.datetime.now() - tc)
            dur = format_time_delta(wf.get_duration())
            t.append([wf.id, wf.status.phase, age, dur])
        format_print_table(t)
    elif args.cmd == 'download':
        config_dflow(args.config)
        wf_id = args.id
        if not wf_id:
            wf_id = get_id_from_record(args.work, 'download')
        wf = Workflow(id=wf_id)
        work_dir = args.work
        all_keys = wf.query_keys_of_steps()
        wf_info = wf.query()
        #print(all_keys)
        download_keys = [key for key in all_keys if key.split('-')[0] == 'adsec']
        #download_keys = all_keys
        task_left = len(download_keys)
        print(f'Downloading {task_left} workflow results {wf_id} to {work_dir}')

        for key in download_keys:
            step = wf_info.get_step(key=key)[0]
            task_left -= 1
            if step['phase'] == 'Succeeded':
                logging.info(f"Download {key}...({task_left} more left)")
                download_artifact(
                    artifact=step.outputs.artifacts['retrieve_path'],
                    path=work_dir
                )
            else:
                logging.warning(f"Step {key} with status: {step['phase']} will be skipping...({task_left} more left)")
    elif args.cmd == 'retrieve':
        config_dflow(args.config)
        wf_id = args.id
        if not wf_id:
            wf_id = get_id_from_record(args.work, 'retrieve')
        wf = Workflow(id=wf_id)
        work_dir = args.work
        all_keys = wf.query_keys_of_steps()
        wf_info = wf.query()
        #print(all_keys)
        download_keys = [key for key in all_keys if key == args.key]
        #download_keys = all_keys
        task_left = len(download_keys)
        print(f'Downloading {task_left} workflow results {wf_id} to {work_dir}')

        for key in download_keys:
            step = wf_info.get_step(key=key)[0]
            task_left -= 1
            if step['phase'] == 'Succeeded':
                logging.info(f"Download {key}...({task_left} more left)")
                download_artifact(
                    artifact=step.outputs.artifacts['retrieve_path'],
                    path=work_dir
                )
            else:
                logging.warning(f"Step {key} with status: {step['phase']} will be skipping...({task_left} more left)")
    elif args.cmd == "stop":
        config_dflow(args.config)
        wf_id = args.id
        if not wf_id:
            wf_id = get_id_from_record(args.work, 'stop')
        wf = Workflow(id=wf_id)
        wf.stop()
        print(f'Workflow stopped! (ID: {wf.id}, UID: {wf.uid})')
    elif args.cmd == "suspend":
        config_dflow(args.config)
        wf_id = args.id
        if not wf_id:
            wf_id = get_id_from_record(args.work, 'suspend')
        wf = Workflow(id=wf_id)
        wf.suspend()
        print(f'Workflow suspended... (ID: {wf.id}, UID: {wf.uid})')
    elif args.cmd == "terminate":
        config_dflow(args.config)
        wf_id = args.id
        if not wf_id:
            wf_id = get_id_from_record(args.work, 'terminate')
        wf = Workflow(id=wf_id)
        wf.terminate()
    elif args.cmd == "resubmit":
        config_dflow(args.config)
        wf_id = args.id
        if not wf_id:
            wf_id = get_id_from_record(args.work, 'resubmit')
        wf = Workflow(id=wf_id)
        wf.resubmit()
        print(f'Workflow resubmitted... (ID: {wf.id}, UID: {wf.uid})')
    elif args.cmd == "resume":
        config_dflow(args.config)
        wf_id = args.id
        if not wf_id:
            wf_id = get_id_from_record(args.work, 'resume')
        wf = Workflow(id=wf_id)
        wf.resume()
        print(f'Workflow resumed... (ID: {wf.id}, UID: {wf.uid})')
    elif args.cmd == "retry":
        config_dflow(args.config)
        wf_id = args.id
        if not wf_id:
            wf_id = get_id_from_record(args.work, 'retry')
        wf = Workflow(id=wf_id)
        if args.step is not None:
            wf.retry_steps(args.step.split(","))
        else:
            wf.retry()
        print(f'Workflow retried... (ID: {wf.id}, UID: {wf.uid})')
    elif args.cmd == "get":
        config_dflow(args.config)
        wf_id = args.id
        if not wf_id:
            wf_id = get_id_from_record(args.work, 'get')
        wf = Workflow(id=wf_id)
        info = wf.query()
        t = []
        t.append(["Name:", info.id])
        t.append(["Status:", info.status.phase])
        t.append(["Created:", info.metadata.creationTimestamp])
        t.append(["Started:", info.status.startedAt])
        t.append(["Finished:", info.status.finishedAt])
        t.append(["Duration", format_time_delta(info.get_duration())])
        t.append(["Progress:", info.status.progress])
        format_print_table(t)
        print()
        steps = info.get_step()
        t = [["STEP", "ID", "KEY", "TYPE", "PHASE", "DURATION"]]
        for step in steps:
            if step.type in ["StepGroup"]:
                continue
            key = step.key if step.key is not None else ""
            dur = format_time_delta(step.get_duration())
            t.append([step.displayName, step.id, key, step.type, step.phase,
                      dur])
        format_print_table(t)
    elif args.cmd == "getkeys":
        config_dflow(args.config)
        wf_id = args.id
        if not wf_id:
            wf_id = get_id_from_record(args.work, 'getkeys')
        wf = Workflow(id=wf_id)
        keys = wf.query_keys_of_steps()
        print("\n".join(keys))
    elif args.cmd == "getsteps":
        config_dflow(args.config)
        wf_id = args.ID
        name = args.name
        key = args.key
        phase = args.phase
        id = args.id
        type = args.type
        if name is not None:
            name = name.split(",")
        if key is not None:
            key = key.split(",")
        if phase is not None:
            phase = phase.split(",")
        if id is not None:
            id = id.split(",")
        if type is not None:
            type = type.split(",")
        wf = Workflow(id=wf_id)
        if key is not None:
            steps = wf.query_step_by_key(key, name, phase, id, type)
        else:
            steps = wf.query_step(name, key, phase, id, type)
        for step in steps:
            if step.type in ["StepGroup"]:
                continue
            key = step.key if step.key is not None else ""
            dur = format_time_delta(step.get_duration())
            t = []
            t.append(["Step:", step.displayName])
            t.append(["ID:", step.id])
            t.append(["Key:", key])
            t.append(["Type:", step.type])
            t.append(["Phase:", step.phase])
            format_print_table(t)
            if hasattr(step, "outputs"):
                if hasattr(step.outputs, "parameters"):
                    print("Output parameters:")
                    for name, par in step.outputs.parameters.items():
                        if name[:6] == "dflow_":
                            continue
                        print("%s: %s" % (name, par.value))
                    print()
                if hasattr(step.outputs, "artifacts"):
                    print("Output artifacts:")
                    for name, art in step.outputs.artifacts.items():
                        if name[:6] == "dflow_" or name == "main-logs":
                            continue
                        key = ""
                        if hasattr(art, "s3"):
                            key = art.s3.key
                        elif hasattr(art, "oss"):
                            key = art.oss.key
                        print("%s: %s" % (name, key))
                    print()
            print()
