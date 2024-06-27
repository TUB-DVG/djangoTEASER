"""Module to read simulation results of TEASER buildings."""
import os
import time
from dymola.dymola_interface import DymolaInterface
import pandas as pd
import datetime
from django import db
import citydb.shortcuts.time_series_data as ts_short
from citydb.models import AbstractEnergySystem
from citydb.models import IrregularTimeSeriesFile
from citydb.models import ObjectClass


def _get_dymola_results(dymola_interface, file_name, signals):
    """Get Dymola results and return pandas.DataFrame"""

    if os.path.isfile(file_name):

        dym_res = dymola_interface.readTrajectory(
            fileName=file_name,
            signals=signals,
            rows=dymola_interface.readTrajectorySize(fileName=os.path.join(file_name)),
        )

        results = pd.DataFrame().from_records(dym_res).T
        results = results.rename(columns=dict(zip(results.columns.values, signals)))
        return results
    else:
        return False


def _upload_time_series(
    results, bldg, end_use, conversion_system, csv, workspace, remote_path
):
    """Prepares all information for upload."""
    END_USE_MAP = {
        "spaceHeating": "PHeat",
        "spaceCooling": "PCool",
        "ventilationHeating": "PHeatAHU",
        "ventilationCooling": "PCoolAHU",
        "electricalAppliances": "Pel",
    }

    try:
        IrregularTimeSeriesFile.objects.get(
            file_id="{}_{}_{}".format(bldg.gmlid, conversion_system, end_use)
        )
        print(
            "{}_{}_{} is already in database, no further action will be executed".format(
                bldg.gmlid, conversion_system, end_use
            )
        )
        return
    except IrregularTimeSeriesFile.DoesNotExist:

        values = pd.DataFrame(
            data=results.filter(like=END_USE_MAP[end_use]).sum(axis=1),
            index=results.index,
            columns=["{}_{}_{}".format(bldg.gmlid, conversion_system, end_use)],
        )
        values = values.divide(1000)

        try:
            energy_system = bldg.energy_system.get(
                objectclass=ObjectClass.objects.get(classname=conversion_system),
                energy_conversion_system_obj__system_operation__end_use=end_use,
            )

        except AbstractEnergySystem.DoesNotExist:

            print("No AHU defined, results are not saved into DB")
            return

        ts_short.add_time_series(
            energy_system=energy_system,
            values=values,
            end_use=end_use,
            thematic_description="Power",
            acquisition_method="simulation",
            file_id=values.columns.values[0],
            source="Simulation",
            uom="kW",
            csv=csv,
            workspace=workspace,
            remote_path=remote_path,
        )


def read_results_heating(
    bldg_query_set,
    city_model,
    acquisition_method="simulation",
    index=pd.date_range(datetime.datetime(2015, 1, 1), periods=8760, freq="H"),
    results_path=os.path.join(os.path.expanduser("~"), "djangoteaserout", "results"),
    csv=False,
    remote_path=None,
):
    """Read simulation data from .mat file and save them into DB.

    Reads Dymola result files and saves them as time series in InfluxDB and
    PostgreSQL of django-citydb. Naming convention of time series follows
    proposed naming schema of Team GA. It assumes that all thermal_zones in
    PostgreSQL database are modeled as a thermal zone in Modelica. Thus this
    approach is not yet ready to be used with archetypes.

    Parameters
    ----------
    bldg_query_set : Django QuerySet, NumPy Array or any other iterable
        Iterable collection of BuildingEnergy objects
    city_model : CityModel instance
        CityModel instance of the buildings that are simulated. Please ensure
        if you are using multiprocessing that all buildings are within the same
        city_model.
    index : Pandas date_range
        Pandas date range of the simulation data. Must fit the length of
        simulation data. (default: hourly for year 2015)
    results_path : str
        Path where Dymola results should be stored. (default:
        /home/user/djangoteaserout/)

    """
    buildings_not_simulated = []
    db.connections.close_all()
    dir_result = results_path
    try:
        dymola = DymolaInterface()
    except:
        time.sleep(30)
        dymola = DymolaInterface()
    for count, bldg in enumerate(bldg_query_set):

        print("reading building {}".format(bldg.gmlid))
        static_signals = [
            "multizone.PHeater[{}]".format(i + 1)
            for i in range(len(bldg.thermal_zones.all()))
        ]
        ahu_signals = ["multizone.PHeatAHU"]
        try:
            static_results = _get_dymola_results(
                dymola_interface=dymola,
                file_name=os.path.join(dir_result, "{}.mat".format(bldg.gmlid)),
                signals=static_signals,
            )
            ahu_results = _get_dymola_results(
                dymola_interface=dymola,
                file_name=os.path.join(dir_result, "{}.mat".format(bldg.gmlid)),
                signals=ahu_signals,
            )
        except BaseException:
            # Dymola has strange exceptions
            print(
                "Reading results of building {} failed, "
                "please check result file".format(bldg.gmlid)
            )
            buildings_not_simulated.append(bldg.gmlid)
            dymola = DymolaInterface()
            continue
        try:
            static_results.index = index
            ahu_results.index = index
        except:
            print(
                "Simulation results of building {} are most likely "
                "faulty (series is shorter then one year), please check "
                "result file".format(bldg.gmlid)
            )
            buildings_not_simulated.append(bldg.gmlid)
            continue
        _upload_time_series(
            results=static_results,
            bldg=bldg,
            end_use="spaceHeating",
            conversion_system="GenericConversionSystem",
            csv=csv,
            workspace=dir_result,
            remote_path=remote_path,
        )
        _upload_time_series(
            results=ahu_results,
            bldg=bldg,
            end_use="ventilationHeating",
            conversion_system="MechanicalVentilation",
            csv=csv,
            workspace=dir_result,
            remote_path=remote_path,
        )
    dymola.close()
    return buildings_not_simulated


def read_results(
    bldg_query_set,
    city_model,
    acquisition_method="simulation",
    index=pd.date_range(datetime.datetime(2015, 1, 1), periods=8760, freq="H"),
    results_path=os.path.join(os.path.expanduser("~"), "djangoteaserout", "results"),
    csv=False,
):
    """Read simulation data from .mat file and save them into DB.

    Reads Dymola result files and saves them as time series in InfluxDB and
    PostgreSQL of django-citydb. Naming convention of time series follows
    proposed naming schema of Team GA. It assumes that all thermal_zones in
    PostgreSQL database are modeled as a thermal zone in Modelica. Thus this
    approach is not yet ready to be used with archetypes.

    Parameters
    ----------
    bldg_query_set : Django QuerySet, NumPy Array or any other iterable
        Iterable collection of BuildingEnergy objects
    city_model : CityModel instance
        CityModel instance of the buildings that are simulated. Please ensure
        if you are using multiprocessing that all buildings are within the same
        city_model.
    index : Pandas date_range
        Pandas date range of the simulation data. Must fit the length of
        simulation data. (default: hourly for year 2015)
    results_path : str
        Path where Dymola results should be stored. (default:
        /home/user/djangoteaserout/)

    """
    buildings_not_simulated = []
    db.connections.close_all()
    dir_result = results_path
    dymola = DymolaInterface()
    for count, bldg in enumerate(bldg_query_set):

        print("reading building {}".format(bldg.gmlid))
        static_signals = [
            "multizone.PHeater[{}]".format(i + 1)
            for i in range(len(bldg.thermal_zones.all()))
        ]
        ahu_signals = ["multizone.PHeatAHU", "multizone.PCoolAHU", "multizone.Pel"]
        try:
            static_results = _get_dymola_results(
                dymola_interface=dymola,
                file_name=os.path.join(dir_result, "{}.mat".format(bldg.gmlid)),
                signals=static_signals,
            )
            ahu_results = _get_dymola_results(
                dymola_interface=dymola,
                file_name=os.path.join(dir_result, "{}.mat".format(bldg.gmlid)),
                signals=ahu_signals,
            )
        except BaseException:
            # Dymola has strange exceptions
            print(
                "Reading results of building {} failed, "
                "please check result file.".format(bldg.gmlid)
            )
            buildings_not_simulated.append(bldg.gmlid)
            continue
        try:
            static_results.index = index
            ahu_results.index = index
        except ValueError:
            print(
                "Simulation results of building {} are most likely "
                "faulty (series is shorter then one year), please check "
                "result file.".format(bldg.gmlid)
            )
            buildings_not_simulated.append(bldg.gmlid)
            continue
        _upload_time_series(
            results=static_results,
            bldg=bldg,
            end_use="spaceHeating",
            conversion_system="GenericConversionSystem",
            csv=csv,
        )
        _upload_time_series(
            results=static_results,
            bldg=bldg,
            end_use="spaceCooling",
            conversion_system="GenericConversionSystem",
            csv=csv,
        )
        _upload_time_series(
            results=ahu_results,
            bldg=bldg,
            end_use="electricalAppliances",
            conversion_system="GenericConversionSystem",
            csv=csv,
        )
        _upload_time_series(
            results=ahu_results,
            bldg=bldg,
            end_use="ventilationHeating",
            conversion_system="MechanicalVentilation",
            csv=csv,
        )
        _upload_time_series(
            results=ahu_results,
            bldg=bldg,
            end_use="ventilationCooling",
            conversion_system="MechanicalVentilation",
            csv=csv,
        )

    dymola.close()
    return buildings_not_simulated
