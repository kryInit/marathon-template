__doc__ = """{f}
Usage:
    {f} CONFIG_FILE_PATH [-t|--testcase_num TESTCASE_NUM] [-c|--concurrency CONCURRENCY] [-f|--format FORMAT] [-i|--in_dir IN_DIR] [-o|--out_dir OUT_DIR] [-s|--score-only]

Options:
    -h, --help                          Show help options.
    -t, --testcase_num TESTCASE_NUM     Set number of testcase
    -c, --concurrency CONCURRENCY       Set concurrency option
    -f, --format FORMAT                 Set format option
    -i, --in_dir IN_DIR                 Set in dir option
    -o, --out_dir OUT_DIR               Set out dir option
    -s, --score-only
""".format(f=__file__)

import os
import sys
import toml
import subprocess
from docopt import docopt


def update_config(config, args):
    for x in ['TESTCASE_NUM', 'CONCURRENCY']:
        if args[f"--{x.lower()}"]:
            config[x] = int(args[f"--{x.lower()}"][0])
    for x in ['FORMAT', 'IN_DIR', 'OUT_DIR']:
        if args[f"--{x.lower()}"]:
            config[x] = args[f"--{x.lower()}"][0]


def safety(func, *args, print_prefix='    -> ', **kwargs):
    try:
        return func(*args, **kwargs)
    except KeyboardInterrupt as e:
        print_red(f'[{e.__class__.__name__}]', prefix=print_prefix)
        sys.exit(-1)
    except Exception as e:
        print_red(f'[{e.__class__.__name__}]: {e}', prefix=print_prefix)
        sys.exit(-1)


def print_red(*args, prefix='', **kwargs):
    print(prefix, end='')
    if sys.stdout.isatty():
        print('\033[31m', end='')
    print(*args, **kwargs)
    if sys.stdout.isatty():
        print('\033[0m', end='', flush=True)


def print_grn(*args, prefix='', **kwargs):
    print(prefix, end='')
    if sys.stdout.isatty():
        print('\033[32m', end='')
    print(*args, **kwargs)
    if sys.stdout.isatty():
        print('\033[0m', end='', flush=True)


def validate_and_fill_recursively(data, name, condition):
    if data is None:
        if len(condition) >= 2 and condition[1] is not None:
            if callable(condition[1]):
                data = condition[1]()
            else:
                data = condition[1]
        else:
            raise ValueError(name + ' is required')

    if not isinstance(data, type(condition[0])):
        raise ValueError(name + ' must be ' + type(condition[0]).__name__)

    if len(condition) >= 3:
        message = condition[2](data)
        if message is not None:
            raise ValueError(name + message)

    if isinstance(data, dict):
        tmp = {}
        for n, t in condition[0].items():
            tmp[n] = validate_and_fill_recursively(data.get(n), name+'.'+n, t)
        data = tmp
    elif isinstance(data, list):
        tmp = [0]*len(data)
        for i in range(len(data)):
            tmp[i] = validate_and_fill_recursively(data[i], name+f'[{i}]', condition[0])
        data = tmp

    return data


def validate_and_fill_config(config):
    conditions = ({
        'TESTCASE_NUM': (int(), 1),
        'FORMAT': (str(), "%04.0f"),
        'CONCURRENCY': (int(), 1),
        'IN_DIR': (str(), '${PROJECT_TOP_DIR}/in'),
        'OUT_DIR': (str(), '${PROJECT_TOP_DIR}/out'),
        'preprocess': ([{
            'name': (str(), 'unknown'),
            'run': ([str()],),
            'working-directory': (str(), '.'),
            'stdout': (bool(), True),
            'stderr': (bool(), True),
        }], []),
        'postprocess': ([{
            'name': (str(), 'unknown'),
            'run': ([str()],),
            'working-directory': (str(), '.'),
            'stdout': (bool(), True),
            'stderr': (bool(), True),
        }], []),
        'solver': ({
            'run': ([str()],),
            'working-directory': (str(), '.'),
            'stdout': (bool(), True),
            'stderr': (bool(), True),
        },),
        'scoring': ({
            'run': ([str()],),
            'working-directory': (str(), '.'),
            'stderr': (bool(), True),
        },)
    },)

    return validate_and_fill_recursively(config, 'config', conditions)


def create_envars(config):
    PROJECT_TOP_DIR = os.path.abspath(os.path.dirname(sys.argv[0]))
    envars = f"PROJECT_TOP_DIR={PROJECT_TOP_DIR}; "
    for x in ['TESTCASE_NUM', 'FORMAT', 'CONCURRENCY', 'IN_DIR', 'OUT_DIR']:
        envars += f"{x}={config[x]}; "
    return envars


def execute_process(process, envars):
    cmd = envars + f"cd {process['working-directory']} && " + ' && '.join(process['run'])
    result = subprocess.run(cmd, shell=True,
                            stdout=subprocess.DEVNULL if not process['stdout'] else None,
                            stderr=subprocess.DEVNULL if not process['stderr'] else None)
    if result.returncode != 0:
        raise ChildProcessError("process failed")


def execute_solver(config, envars):
    solver_cmd = f"seq -f \"{config['FORMAT']}\" 0 {config['TESTCASE_NUM']-1} | xargs -L 1 -P {config['CONCURRENCY']} sh -c "
    solver_cmd += f"'{envars}" + "IN_PATH=${IN_DIR}/$0.txt; OUT_PATH=${OUT_DIR}/$0.txt; "
    solver_cmd += f"cd {config['solver']['working-directory']} && " + ' && '.join(config['solver']['run']) + "'"
    result = subprocess.run(solver_cmd, shell=True,
                            stdout=subprocess.DEVNULL if not config['solver']['stdout'] else None,
                            stderr=subprocess.DEVNULL if not config['solver']['stderr'] else None)
    if result.returncode != 0:
        raise ChildProcessError("solver failed")


def execute_scoring(config, envars):
    scoring = f"seq -f \"{config['FORMAT']}\" 0 {config['TESTCASE_NUM']-1} | xargs -L 1 -P {config['CONCURRENCY']} sh -c "
    scoring += f"'{envars}" + "IN_PATH=${IN_DIR}/$0.txt; OUT_PATH=${OUT_DIR}/$0.txt; "
    scoring += f"cd {config['scoring']['working-directory']} && " + ' && '.join(config['scoring']['run']) + "'"
    scoring += " | awk '{sum+=$0} END {print sum}'"
    result = subprocess.run(scoring, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL if not config['scoring']['stderr'] else None)
    if result.returncode != 0:
        raise ChildProcessError("scoring failed")
    return int(result.stdout)


def run_with_score_only():
    cmd = 'python ' + ' '.join(filter(lambda x: x != '--score-only', sys.argv))
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if result.returncode != 0:
        exit(result.returncode)

    print(int(result.stdout.split()[-1]))
    exit(0)


if __name__ == '__main__':
    args = docopt(__doc__)

    if args['--score-only']:
        run_with_score_only()

    print('load config.toml')
    config = safety(toml.load, args['CONFIG_FILE_PATH'])
    print_grn('done', prefix='    -> ')

    print('\nupdate config by argument')
    safety(update_config, config, args)
    print_grn('done', prefix='    -> ')

    print('\nvalidate and fill config')
    config = safety(validate_and_fill_config, config)
    print_grn('done', prefix='    -> ')

    envars = create_envars(config)

    if config['preprocess']:
        print('\nexecute preprocess')
    for process in config['preprocess']:
        print(f"[{process['name']}] start")
        safety(execute_process, process, envars)
        print_grn('done', prefix=f"[{process['name']}] ")

    print("\nexecute solver")
    safety(execute_solver, config, envars)
    print_grn('done', prefix='    -> ')

    print("\nexecute scoring")
    score = safety(execute_scoring, config, envars)
    print_grn('done', prefix='    -> ')

    if config['postprocess']:
        print('\nexecute postprocess')
    for process in config['postprocess']:
        print(f"[{process['name']}] start")
        safety(execute_process, process, envars)
        print_grn('done', prefix='    -> ')

    print_grn('\nall done')
    print(f"\nscore: {score}")

