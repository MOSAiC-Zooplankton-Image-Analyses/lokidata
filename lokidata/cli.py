import concurrent.futures
import glob
import os.path
import subprocess
from typing import List

import click
from tqdm.auto import tqdm
from werkzeug.utils import secure_filename

from . import LOG_FIELDS_TO_ECOTAXA, find_data_roots, read_log, read_yaml


@click.group()
def main():
    pass


@main.command()
@click.argument("root_dir")
@click.option("-j", "--n_workers", type=int, default=1)
@click.option("--skip-existing", is_flag=True)
@click.option("--ignore", multiple=True)
@click.option("--to", "target_dir")
def compress(root_dir, n_workers, skip_existing, ignore, target_dir):
    """
    Find and compress LOKI data folders.

    LOKI data consists of very many small files which are slow to read on most filesystems.
    By compressing whole folders, into zip files, these are quicker to transfer and to read.
    """

    if target_dir is None:
        target_dir = root_dir

    executor = concurrent.futures.ThreadPoolExecutor(n_workers)

    print("Discovering project directories...")
    futures: List[concurrent.futures.Future] = []
    existing_archive_fns = set()
    tasks = []
    for data_root in find_data_roots(root_dir, progress=False, ignore_patterns=ignore):
        # Read logfile and YAML meta
        (log_fn,) = glob.glob(os.path.join(data_root, "Log", "LOKI*.log"))
        yaml_meta_fn = os.path.join(data_root, "meta.yaml")
        meta = {
            **read_log(log_fn, remap_fields=LOG_FIELDS_TO_ECOTAXA),
            **read_yaml(yaml_meta_fn),
        }

        sample_id = "{sample_station}_{sample_haul}".format_map(meta)

        archive_fn = os.path.join(target_dir, secure_filename(sample_id)) + ".zip"
        print(data_root, "->", archive_fn)

        if archive_fn in existing_archive_fns:
            click.echo(f"Duplicate target archive filename {archive_fn}", err=True)
            raise click.Abort()

        existing_archive_fns.add(archive_fn)

        if skip_existing and os.path.isfile(archive_fn):
            print(archive_fn, "already exists.")
            continue

        tasks.append(
            (
                sample_id,
                (subprocess.run, ["zip", "-r", archive_fn, "."]),
                dict(cwd=data_root, check=True, stdout=subprocess.DEVNULL),
            )
        )

    print(f"Compressing {len(tasks)} samples...")
    for sample_id, args, kwargs in tasks:
        future = executor.submit(*args, **kwargs)
        future.add_done_callback(
            lambda _, sample_id=sample_id: print(sample_id, "finished.\n")
        )
        futures.append(future)

    for _ in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
        pass

    print("All done.")


if __name__ == "__main__":
    main()
