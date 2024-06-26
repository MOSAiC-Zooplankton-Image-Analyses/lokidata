import datetime
import logging
import pathlib
from typing import (
    Any,
    Collection,
    Dict,
    Mapping,
    Optional,
    Tuple,
    Union,
)
from tqdm.auto import tqdm
import fnmatch
import os
from . import _version
import yaml
import chardet


def _add_note(exc, note: str) -> None:
    if not isinstance(note, str):
        raise TypeError(
            f"Expected a string, got note={note!r} (type {type(note).__name__})"
        )

    if not hasattr(exc, "__notes__"):
        exc.__notes__ = []

    exc.__notes__.append(note)


__version__ = _version.get_versions()["version"]

logger = logging.getLogger(__name__)

StrOrPath = Union[str, pathlib.Path]

NAN = float("nan")


def german_float(s: str):
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return NAN


def german_date(s: str):
    return datetime.datetime.strptime(s, "%d.%m.%Y").date()


TMD_FIELDS = {
    1: ("DEVICE", None),  # Loki-Name
    5: ("GPS_LON", german_float),  # Longitude (GPS or fix),	[+E, -W]
    6: ("GPS_LAT", german_float),  # Latitude (GPS or fix),	[+N, -S]
    10: ("PRESS", german_float),  # Aandera 4017D, Pressure	[kPa]
    11: ("TEMP", german_float),  # Aandera 4017D, Temperature	[°C]
    20: ("OXY_CON", german_float),  # Aandera 4330F, Oxygen concentration	[mg*l^-1]
    21: ("OXY_SAT", german_float),  # Aandera 4330F, Oxygen saturation	[%]
    22: ("OXY_TEMP", german_float),  # Aandera 4330F, Oxygen temperature	[°C]
    30: ("COND_COND", german_float),  # Aandera 3919 A/W, Conductivity	[mS/cm]
    31: ("COND_TEMP", german_float),  # Aandera 3919 A/W, Temperature	[°C]
    32: ("COND_SALY", german_float),  # Aandera 3919 A/W, Salinity	[PSU]
    33: ("COND_DENS", german_float),  # Aandera 3919 A/W, Density	[kg/m^3]
    34: ("COND_SSPEED", german_float),  # Aandera 3919 A/W, Soundspeed	[m/s]
    40: ("FLOUR_1", german_float),  # Flourescence
    41: ("FLOUR_CR", german_float),  # HAARDT Flourescence, Clorophyll Range
    42: ("FLOUR_CV", german_float),  # HAARDT Flourescence, Clorophyll Value
    43: ("FLOUR_TR", german_float),  # HAARDT Flourescence, Turbidity Range
    44: ("FLOUR_TD", german_float),  # HAARDT Flourescence, Turbidity Val
    200: ("ROLL", german_float),  # ISITEC, Roll	[°]
    201: ("PITCH", german_float),  # ISITEC, Pitch	[°]
    202: ("NICK", german_float),  # ISITEC, Nick	[°]
    230: ("LOKI_REC", None),  # LOKI Recorder status
    231: ("LOKI_PIC", int),  # Loki Recorder consecutive picture number
    232: ("LOKI_FRAME", german_float),  # Loki Recorder frame rate	[fps]
    235: ("CAM_STAT", None),  # Camera status
    240: ("HOUSE_STAT", None),  # Housekeeping status
    241: ("HOUSE_T1", german_float),  # Housekeeping temperature 1	[°C]
    242: ("HOUSE_T2", german_float),  # Housekeeping temperature 2	[°C]
    243: ("HOUSE_VOLT", german_float),  # Housekeeping voltage	[V]
}

DAT_FIELDS = {
    1: ("FW_REV", None),  # Firmware version
    2: ("COND_SSPEED", float),  # Speed of sound
    3: ("COND_DENS", float),  # Density
    4: ("COND_TEMP", float),  # Temperature
    5: ("COND_COND", float),  # Conductivity
    6: ("COND_SALY", float),  # Salinity
    7: ("OXY_CON", float),  # Oxygen concentration
    8: ("OXY_SAT", float),  # Oxygen saturation
    9: ("OXY_TEMP", float),  # Temperature
    10: ("HOUSE_T1", float),  # Housekeeping temperature
    11: ("HOUSE_VOLT", float),  # Housekeeping  voltage
    16: ("FLOUR_1", float),  # Fluorescence
    17: ("UNKNOWN", None),  # ??
    18: ("UNKNOWN", None),  # ??
    19: ("UNKNOWN", None),  # ??
    20: ("PRESS", float),  # Pressure
    21: ("TEMP", float),  # Temperature
    22: ("UNKNOWN", None),  # ??
    23: ("LOKI_REC", None),  # Recorder status
    24: ("LOKI_PIC", None),  # Picture #
    25: ("LOKI_FRAME", None),  # Frame rate
    26: ("GPS_LAT", float),  # Position Latitute
    27: ("GPS_LON", float),  # Position Longitude
}

LOG_FIELDS = {
    1: ("DATE", german_date),  # Startdate	UTC
    2: ("TIME", datetime.time.fromisoformat),  # Starttime	UTC
    3: ("PICTURE#", int),  # Aktuelle Bildnummer VPR-Recorder
    4: ("DEVICE", None),  # Loki-Name
    5: ("LOKI", None),  # Loki-Serial
    6: ("FW_REV", None),  # Firmwareversion
    7: ("SW_REV", None),  # Softwareversion
    8: ("CRUISE", None),  # Cruise Name
    9: ("STATION", None),  # Station
    10: ("STATION_NR", None),  # Stationsnumber
    11: ("HAUL", None),  # Haul
    12: ("USER", None),  # Investigator
    13: ("SHIP", None),  # Ship name
    14: ("SHIP_PORT", None),  # Port of Registry
    15: ("SHIP_STAT", None),  # State of Registry
    16: ("SHIP_AFF", None),  # Ship affiliation
    17: ("GPS_SRC", None),  # GPS Source (0 = NoGPS, 1 = Fixed, 2 = Ext.)
    18: ("FIX_LON", german_float),  # Fixed Longitude	[+E, -W]
    19: ("FIX_LAT", german_float),  # Fixed Latitude	[+N, -S]
    20: ("TEMP_INDEX", None),  # Temperature Sensor Index for calculation
    61: ("ERROR", None),  # Any Error Message
    62: ("WAKEUP", None),  # AnyWakeUp Controller Message
    63: ("STOP_DATE", german_date),  # Stopdate	UTC
    64: ("STOP_TIME", datetime.time.fromisoformat),  # Stoptime	UTC
}


def _parse_tmd_line(line: str, fields) -> Tuple[str, Any]:
    try:
        idx, value = line.rstrip("\n").split(";", 1)
    except BaseException as exc:
        _add_note(exc, f"Offending line: {line}")
        raise exc

    name, converter = fields[int(idx)]
    if converter is not None:
        try:
            value = converter(value)
        except BaseException as exc:
            _add_note(exc, f"Field {name}")
            raise exc

    return name, value


def _parse_dat_line(idx: int, line: str, fields) -> Tuple[str, Any]:
    value = line.rstrip("\n")

    name, converter = fields[idx]

    if converter is not None:
        try:
            value = converter(value)
        except BaseException as exc:
            _add_note(exc, f"Field {name}")
            raise exc

    return name, value


def read_tmd(fn: StrOrPath):
    if isinstance(fn, str):
        fn = pathlib.Path(fn)

    for encoding in ("utf-8", "Windows-1252"):
        try:
            with fn.open(encoding=encoding) as f:
                return dict(_parse_tmd_line(l, TMD_FIELDS) for l in f)
        except UnicodeDecodeError:
            pass

    with fn.open("rb") as f:
        detected = chardet.detect_all(f.read())

    raise ValueError(f"Unexpected encoding. Guessed {detected}")


def read_dat(fn: StrOrPath):
    if isinstance(fn, str):
        fn = pathlib.Path(fn)

    with fn.open() as f:
        # FIXME: Sometimes, a .dat contains multiple lines.
        # Here, we only use the first one.
        contents = f.readline()

    fields = contents.split("\t")

    return dict(
        _parse_dat_line(i, f, DAT_FIELDS)
        for i, f in enumerate(fields, 1)
        if i in DAT_FIELDS
    )


LOG_FIELDS_TO_ECOTAXA = {
    "sample_date": "DATE",
    "sample_time": "TIME",
    "acq_instrument_name": "DEVICE",
    "acq_instrument_serial": "LOKI",
    "sample_cruise": "CRUISE",
    "sample_station": "STATION",
    "sample_station_no": "STATION_NR",
    "sample_haul": "HAUL",
    "sample_user": "USER",
    "sample_vessel": "SHIP",
    "sample_gps_src": "GPS_SRC",
    "sample_latitude": "FIX_LAT",
    "sample_longitude": "FIX_LON",
}


def read_log(fn: StrOrPath, remap_fields: Optional[Mapping] = None):
    if isinstance(fn, str):
        fn = pathlib.Path(fn)

    with fn.open() as f:
        data = dict(_parse_tmd_line(l, LOG_FIELDS) for l in f)

    if remap_fields is not None:
        data = {ke: data[kl] for ke, kl in remap_fields.items()}

    return data


def read_yaml(fn: StrOrPath) -> Dict[str, Any]:
    if isinstance(fn, str):
        fn = pathlib.Path(fn)

    if not fn.is_file():
        return {}

    with fn.open() as f:
        value = yaml.safe_load(f)

        if not isinstance(value, dict):
            raise ValueError(f"Unexpected content in {fn}: {value}")

        return value


def find_data_roots(project_root: StrOrPath, ignore_patterns: Collection | None = None):
    if isinstance(project_root, str):
        project_root = pathlib.Path(project_root)

    logger.info(f"Checking {project_root}")

    if ignore_patterns is not None and any(
        project_root.match(pat) for pat in ignore_patterns
    ):
        return

    subdirs = [p for p in project_root.iterdir() if p.is_dir()]

    if any(p.name == "Pictures" for p in subdirs) and any(
        p.name == "Telemetrie" for p in subdirs
    ):
        yield project_root

    else:
        for subdir in subdirs:
            yield from find_data_roots(subdir, ignore_patterns)
