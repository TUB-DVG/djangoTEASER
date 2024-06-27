"""Module to simulate buildings"""
import os
import django
import datetime
import pandas as pd
import multiprocessing

django.setup()
from citydb.shortcuts import buildings_data as bd_short
import teaser_citydb.simulation.simulate_models as sim
import teaser_citydb.simulation.read_results as read


def simulate_city_model(
    prj,
    index=pd.date_range(datetime.datetime(2014, 1, 1), periods=8760, freq="H"),
    number_of_workers=multiprocessing.cpu_count() - 1,
    buildings_to_simulate=None,
    csv=False,
    remote_path="/Diss/blob_storage/results/",
    workspace=None,
    model_path=os.path.join(os.path.expanduser("~"), "TEASEROutput"),
):
    city_teaser_juelich = bd_short.get_city_model_by_name(name=prj.name)

    if buildings_to_simulate is None:
        buildings_to_simulate = bd_short.get_all_buildings(
            city_model=city_teaser_juelich
        )
    else:
        pass

    if number_of_workers > 60:
        number_of_workers = 58
    else:
        pass

    index_lookup = pd.DataFrame(
        index=range(0, 31536000 + 31622400 + 31536000, 3600), columns=["time"]
    )
    index_lookup.loc[:, "time"] = pd.date_range(
        datetime.datetime(2014, 1, 1), periods=26304, freq="H"
    )

    start_time = index_lookup.loc[
        index_lookup["time"] == index[0].to_pydatetime()
    ].index.values[0]
    stop_time = index_lookup.loc[
        index_lookup["time"] == index[-1].to_pydatetime()
    ].index.values[0]
    print("Start simulation...")
    sim.queue_simulation(
        sim_function=sim.simulate,
        bldg_query_set=buildings_to_simulate,
        city_model=city_teaser_juelich,
        number_of_workers=number_of_workers,
        model_path=model_path,
        results_path=workspace,
        start_time=start_time,
        stop_time=stop_time,
        output_interval=3600.0,
        method="Dassl",
        tolerance=0.0001,
    )

    buildings_not_simulated = read.read_results_heating(
        bldg_query_set=buildings_to_simulate,
        city_model=city_teaser_juelich,
        index=index,
        results_path=workspace,
        csv=csv,
        remote_path=remote_path,
    )

    return buildings_not_simulated
