__doc__ = """
Usage:
    {f} submit
    {f} show-log [-s|--sort] [--head HEAD_NUM]

Options:
    -h, --help                          Show help options.
    -s, --sort
    --head HEAD_NUM
""".format(f=__file__)


import os
import sys
import sqlite3
import subprocess
from docopt import docopt
from functools import reduce


def get_score():
    result = subprocess.run(f"python {PROJECT_TOP_DIR}/tester.py {PROJECT_TOP_DIR}/config.toml -t 1000 --score-only",
                            shell=True,
                            stdout=subprocess.PIPE)
    if result.returncode != 0:
        print("scoring failed")
        exit(-1)

    return int(result.stdout)


def git_commit(score):
    subprocess.run(f"git add {PROJECT_TOP_DIR}/main.cpp", shell=True)
    result = subprocess.run('git commit -m "[auto commit] score: {}, {:.3e}"'.format(score, score), shell=True)
    if result.returncode != 0:
        print("commit failed")
        exit(-1)


def submit():
    print("scoring...")
    score = get_score()
    print(score)

    git_commit(score)

    DATA_DIR = PROJECT_TOP_DIR + "/data"

    if not os.path.isdir(DATA_DIR):
        os.mkdir(DATA_DIR)

    db_path = DATA_DIR + "/submission_log.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS \
                submission_log (order_id INTEGER PRIMARY KEY AUTOINCREMENT, commit_hash STRING, score INTEGER)')

    result = subprocess.run("git rev-parse --short HEAD", shell=True, stdout=subprocess.PIPE)
    commit_hash = result.stdout.split()[-1].decode('utf-8')
    cur.execute(f'INSERT INTO submission_log(commit_hash, score) VALUES("{commit_hash}", {score})')

    conn.commit()
    cur.close()
    conn.close()


def show_log():
    DATA_DIR = PROJECT_TOP_DIR + "/data"

    if not os.path.isdir(DATA_DIR):
        raise FileExistsError("data/submission_log.db does not exists")

    db_path = DATA_DIR + "/submission_log.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute('SELECT * FROM submission_log')

    labels = ('id', 'hash', 'score')
    data = cur.fetchall()
    if args['--sort']:
        data.sort(key=lambda x: -x[2])
    if args['--head']:
        data = data[:int(args['--head'])]
    max_lengths = list(reduce(lambda xs, ys: map(max, zip(xs, ys)), map(lambda x: map(lambda y: len(str(y)), x), data), map(len, labels)))
    data_info_formatted = list(map(lambda xs: [str(xs[i]).ljust(max_lengths[i]) for i in range(len(xs))], data))
    labels_formatted = [labels[i].center(max_lengths[i]) for i in range(len(labels))]
    print(' | '.join(labels_formatted))
    print(' | '.join(map(lambda x: '-'*x, max_lengths)))
    for i in data_info_formatted:
        print(' | '.join(i))

    conn.commit()
    cur.close()
    conn.close()


if __name__ == '__main__':
    args = docopt(__doc__)
    PROJECT_TOP_DIR = os.path.abspath(os.path.dirname(sys.argv[0]))
    if args['submit']:
        submit()
    else:
        show_log()
