from typing import List
from . import find_data_roots, read_log
import click
import concurrent.futures
import os.path
import glob
import subprocess
from tqdm.auto import tqdm

@click.group()
def main():
    pass

@main.command()
@click.argument('root_dir')
@click.option('-j', "--n_workers", type=int, default=1)
@click.option("--skip-existing", is_flag=True)
@click.option("--ignore", multiple=True)
def compress(root_dir, n_workers, skip_existing, ignore):
    """
    Find and compress LOKI data folders.
    
    LOKI data consists of very many small files which are slow to read on most filesystems.
    By compressing whole folders, into zip files, these are quicker to transfer and to read.
    """

    executor = concurrent.futures.ThreadPoolExecutor(n_workers)

    print("Discovering project directories...")
    futures: List[concurrent.futures.Future] = []
    existing_archive_fns = set()
    for data_root in find_data_roots(root_dir, progress=False, ignore_patterns=ignore):
        (log_fn,) = glob.glob(os.path.join(data_root, "Log", "LOKI*.log"))
        log = read_log(log_fn)
        sample_id = "{STATION}_{HAUL}".format_map(log)

        archive_fn = os.path.join(root_dir, sample_id) + ".zip"
        print(data_root, "->", archive_fn)

        if archive_fn in existing_archive_fns:
            click.echo(f"Duplicate target archive filename {archive_fn}", err=True)
            raise click.Abort()

        existing_archive_fns.add(archive_fn)

        if skip_existing and os.path.isfile(archive_fn):
            print(archive_fn, "already exists.")
            continue

        future=executor.submit(subprocess.run, ["zip", "-r", archive_fn, "."], cwd=data_root, check=True, stdout=subprocess.DEVNULL)
        future.add_done_callback(lambda _, sample_id=sample_id: print(sample_id, "finished.\n"))
        futures.append(future)

    print("Compressing...")
    for _ in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
        pass

    print("All done.")
        

if __name__ == "__main__":
    main()