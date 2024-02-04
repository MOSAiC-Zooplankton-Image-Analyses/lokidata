# lokidata

A Python library to process data of the Lightframe Onsight Keyspecies Investigation (LOKI).

## Features
## Read LOKI `.tmd`, `.dat` and `.log` files

```python
from lokidata import read_tmd, read_dat, read_log, read_yaml

# Read environmental frame metadata
tmd = read_tmd("path/to/file.tmd")
dat = read_dat("path/to/file.dat")

# Read sample metadata
log = read_log("path/to/file.log")

# Augment stored sample metadata with additional data
yaml = read_tmd("path/to/file.yaml")
log = {**log, **yaml}
```

## Command Line Interface (CLI):

```sh
# Find and compress LOKI data folders:
# This detects LOKI sample folders below the current directory and creates zip archives
lokidata compress .
```