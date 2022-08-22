import sys
import subprocess

import matplotlib.pyplot as plt

import numpy as np
from netCDF4 import default_fillvals


def to_netcdf_clean(dset, path, netcdf3=True, **kwargs):
    """wrap to_netcdf method to circumvent some xarray shortcomings"""

    dset = dset.copy()

    # ensure _FillValues are not added to coordinates
    for v in dset.coords:
        dset[v].encoding["_FillValue"] = None

    for v in dset.data_vars:

        # if dtype has been set explicitly in encoding, obey
        if "dtype" in dset[v].encoding:
            if dset[v].encoding["dtype"] == np.float64:
                fv = default_fillvals["f8"]
            elif dset[v].encoding["dtype"] == np.float32:
                fv = default_fillvals["f4"]
            elif dset[v].encoding["dtype"] in [np.int32]:
                fv = default_fillvals["i4"]

            if '_FillValue' not in dset[v].encoding:
                dset[v].encoding["_FillValue"] = fv

        # otherwise, default to single precision output
        elif dset[v].dtype in [np.float32, np.float64]:
            fv = default_fillvals["f4"]
            dset[v].encoding["dtype"] = np.float32

        elif dset[v].dtype in [np.int32, np.int64]:
            fv = default_fillvals["i4"]
            dset[v].encoding["dtype"] = np.int32

        elif dset[v].dtype == object:
            pass

        else:
            warnings.warn(f"warning: unrecognized dtype for {v}: {dset[v].dtype}")

        if "_FillValue" not in dset[v].encoding:
            dset[v].encoding["_FillValue"] = None

    sys.stderr.flush()

    print("-" * 30)
    print(f"Writing {path}")
    dset.to_netcdf(path, **kwargs)
    print("")
    if netcdf3:
        ncks_fl_fmt64bit(path)

    dumps = subprocess.check_output(["ncdump", "-h", path]).strip().decode("utf-8")
    print(dumps)
    dumps = subprocess.check_output(["ncdump", "-k", path]).strip().decode("utf-8")
    print(f"format: {dumps}")
    print("-" * 30)


def ncks_fl_fmt64bit(file_in, file_out=None):
    """
    Converts file to netCDF-3 64bit by calling:
      ncks --fl_fmt=64bit  file_in file_out

    Parameter
    ---------
    file : str
      The file to convert.
    """

    if file_out is None:
        file_out = file_in

    ncks_cmd = " ".join(["ncks", "-O", "--fl_fmt=64bit", file_in, file_out])
    cmd = " && ".join(["module load nco", ncks_cmd])

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

    stdout, stderr = p.communicate()
    if p.returncode != 0:
        print(stdout.decode("UTF-8"))
        print(stderr.decode("UTF-8"))
        raise

