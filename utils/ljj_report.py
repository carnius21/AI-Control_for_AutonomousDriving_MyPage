"""Package small experiment records for chat upload; excludes models and data."""
import argparse
from pathlib import Path
import zipfile


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs', type=Path, nargs='+', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    allowed = ('manifest.json', 'progress.json', 'complete.json', 'summary.json',
               'evaluation.json', 'training_log.csv', 'eval_log.csv')
    if len({r.name for r in a.runs}) != len(a.runs):
        p.error('Run directory names must be unique')
    for run in a.runs:
        if not (run/'manifest.json').is_file():
            p.error('Missing manifest: '+str(run))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(a.output, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for run in a.runs:
            for name in allowed:
                path=run/name
                if path.is_file():
                    z.write(path, run.name+'/'+name)
    print(a.output)


if __name__ == '__main__':
    main()
