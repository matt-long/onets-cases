import os
import shutil
from glob import glob
from subprocess import check_call

import textwrap

import cftime
import numpy as np
import xarray as xr

import pop_tools

USER = os.environ["USER"]

scriptroot = os.path.dirname(os.path.realpath(__file__))

project = "P93300670"

project_root = f"/glade/work/{USER}/onets-cases"
os.makedirs(project_root, exist_ok=True)

caseroot_root = f"{project_root}/cesm-cases"
os.makedirs(caseroot_root, exist_ok=True)

coderoot = "/glade/work/klindsay/cesm2_tags/cesm2.2.0"
refcase = "g.e22.GOMIPECOIAF_JRA-1p4-2018.TL319_g17.SMYLE.005"
refcase_root = "/glade/work/klindsay/cesm22_cases/SMYLE"
refcaserest_root = "/glade/work/mclong/SMYLE-FOSI/rest"

scratch = f"/glade/scratch/{USER}"


nmolcm2s_to_molm2yr = 1.0e-9 * 1.0e4 * 86400.0 * 365.0
nmolcm2_to_molm2 = 1.0e-9 * 1.0e4


def create_clone(
    case,
    alk_forcing_file='none',
    fe_fert_forcing_file='none',    
    refdate="0347-01-01",
    stop_n=4,
    stop_option="nyear",
    job_queue="economy",
    wallclock="12:00:00",
    clobber=False,
    submit=False,
):
    caseroot = f"{caseroot_root}/{case}"
    if os.path.exists(caseroot) and not clobber:
        print(f"Case {case} exists; skipping.")
        return

    rundir = f"{scratch}/{case}"
    archive_root = f"{scratch}/archive/{case}"

    check_call(["rm", "-fr", caseroot])
    check_call(["rm", "-fr", rundir])
    check_call(["rm", "-fr", archive_root])

    check_call(
        [
            "./create_clone",
            "--clone",
            f"{refcase_root}/{refcase}",
            "--case",
            caseroot,
            "--project",
            project,
            "--cime-output-root",
            scratch,
        ],
        cwd=f"{coderoot}/cime/scripts",
    )

    # copy source mods
    src_pop_files = glob(f"{scriptroot}/SourceMods/src.pop/*")
    for src in src_pop_files:
        src_basename = os.path.basename(src)
        if src_basename == "diagnostics_latest.yaml":
            check_call(
                [
                    f"{coderoot}/components/pop/externals/MARBL/MARBL_tools/./yaml_to_json.py",
                    "-y",
                    f"{src}",
                    "-o",
                    f"{caseroot}/SourceMods/src.pop",
                ]
            )
        else:
            dst = f"{caseroot}/SourceMods/src.pop/{src_basename}"
            shutil.copyfile(src, dst)

    # xml settings
    def xmlchange(arg):
        """call xmlchange"""
        check_call(["./xmlchange", arg], cwd=caseroot)

    xmlchange("RUN_TYPE=branch")
    xmlchange(f"RUN_STARTDATE={refdate}")
    xmlchange(f"RUN_REFCASE={refcase}")
    xmlchange(f"RUN_REFDATE={refdate}")

    # copy restarts
    check_call(
        f"cp {refcaserest_root}/{refdate}-00000/* /glade/scratch/{USER}/{case}/run/.",
        shell=True,
    )

    # set ALT_CO2 tracers to CO2 tracers
    check_call(
        ["./set-alt-co2.sh", f"{rundir}/run/{refcase}.pop.r.{refdate}-00000.nc"],
        cwd=scriptroot,
    )

    check_call(["./case.setup"], cwd=caseroot)

    # namelist
    user_nl = dict()

    lalk_forcing_apply_file_flux = (
        '.true.' if alk_forcing_file != 'none' else '.false.'
    )
    lfe_fert_forcing_apply_file_flux = (
        '.true.' if fe_fert_forcing_file != 'none' else '.false.'
    )

    user_nl["pop"] = textwrap.dedent(
        f"""\
    lecosys_tavg_alt_co2 = .true.
    atm_alt_co2_opt = 'drv_diag'
    !
    ! OAE
    lalk_forcing_apply_file_flux = {lalk_forcing_apply_file_flux}
    alk_forcing_shr_stream_year_first = 1999
    alk_forcing_shr_stream_year_last = 2019
    alk_forcing_shr_stream_year_align = 347
    alk_forcing_shr_stream_file = '{alk_forcing_file}'
    alk_forcing_shr_stream_scale_factor = 1.0e5 ! convert from mol/m^2/s to nmol/cm^2/s
    !
    ! Fe fertilization
    lfe_fert_forcing_apply_file_flux = {lfe_fert_forcing_apply_file_flux}
    fe_fert_forcing_shr_stream_year_first = 1999
    fe_fert_forcing_shr_stream_year_last = 2019
    fe_fert_forcing_shr_stream_year_align = 347
    fe_fert_forcing_shr_stream_file = '{fe_fert_forcing_file}'
    fe_fert_forcing_shr_stream_scale_factor = 1.0e5 ! convert from mol/m^2/s to nmol/cm^2/s
    """
    )

    for key, nl in user_nl.items():
        user_nl_file = f"{caseroot}/user_nl_{key}"
        with open(user_nl_file, "a") as fid:
            fid.write(user_nl[key])

    check_call(["./preview_namelists"], cwd=caseroot)

    check_call(["qcmd", "--", "./case.build"], cwd=caseroot)

    if submit:
        xmlchange(f"STOP_N={stop_n}")
        xmlchange(f"JOB_QUEUE={job_queue}")
        xmlchange(f"STOP_OPTION={stop_option}")
        xmlchange(f"JOB_WALLCLOCK_TIME={wallclock}")
        check_call(["./case.submit"], cwd=caseroot)



