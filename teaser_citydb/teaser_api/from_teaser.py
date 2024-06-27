"""Contains functions to import information from TEASER to citydb app."""

import datetime
import pytz
import pandas as pd
import uuid
from citydb.models import CityModel
from citydb.models import EnergyBuilding
from citydb.models import ObjectClass
from citydb.models import ThermalZone
from citydb.models import UsageZone
from citydb.models import IrregularTimeSeriesFile
from citydb.models import TimeSeriesSchedule
from citydb.models import Occupants
from citydb.models import Facilities
from citydb.models import ThermalBoundary
from citydb.models import ThermalOpening
from citydb.models import Construction
from citydb.models import Layer
from citydb.models import LayerComponent
from citydb.models import SolidMaterial
from citydb.models import MechanicalVentilation
from citydb.models import HeatExchanger
from citydb.models import EnergyConversionSystem
from citydb.models import SystemOperation
from citydb.models import HeatExchangeType
from datetime import datetime as dt

BUILDING_FUNCTION = {
    "Office": "1300",
    "Institute": "1300/2000",
    "Institute4": "1300/2220",
    "SingleFamilyDwelling": "4400",
    "SingleFamilyHouse": "4400",
}


def import_city_model(
    project,
    description="Transfer a TEASER project to 3DCityDB.",
    updating_person="pre",
    reason_for_update="First entry of this project.",
):
    """Documentation is missing."""
    city_model = CityModel(
        gmlid=project.name,
        name=project.name,
        description=description,
        creation_date=datetime.datetime.now(pytz.timezone("Europe/Berlin")),
        last_modification_date=datetime.datetime.now(pytz.timezone("Europe/Berlin")),
        updating_person=updating_person,
        reason_for_update=reason_for_update,
    )
    city_model.save()

    for bldg_t in project.buildings:
        print("Import {} to database".format(bldg_t.name))
        bldg_dj = _import_energy_building(
            city_model=city_model, building=bldg_t, building_surface=None
        )
        city_model.city_object_member.add(bldg_dj)
        city_model.save()
    return city_model


def _import_energy_building(city_model, building, building_surface):
    """Documentation is missing."""
    building_dj = EnergyBuilding(
        objectclass=ObjectClass.objects.get(classname="Building"),
        gmlid=building.name,
        name=building.name,
        year_of_construction=datetime.date(building.year_of_construction, 1, 1),
        measured_height=(building.height_of_floors * building.number_of_floors),
        measured_height_unit="m",
        storeys_above_ground=building.number_of_floors,
        storey_heights_above_ground=building.height_of_floors,
        lod2_solid=building_surface,
        function=BUILDING_FUNCTION[type(building).__name__],
        building_type=type(building).__name__,
        construction_weight=building.construction_type,
    )
    building_dj.save()
    building_dj.floor_area = building.net_leased_area
    building_dj.volume = building.volume
    building_dj.height_above_ground = (
        building.height_of_floors * building.number_of_floors
    )
    building_dj.save()

    _import_energy_system(
        connected_to_network=False,
        purpose="spaceHeating",
        building_teaser=building,
        building_sql=building_dj,
    )
    _import_energy_system(
        connected_to_network=False,
        purpose="spaceCooling",
        building_teaser=building,
        building_sql=building_dj,
    )
    _import_energy_system(
        connected_to_network=False,
        purpose="electricalAppliances",
        building_teaser=building,
        building_sql=building_dj,
    )

    if building.central_ahu is not None:
        _import_mechanical_ventilation(
            ahu_teaser=building.central_ahu, building_sql=building_dj
        )

    for zone in building.thermal_zones:
        zone_sql = _import_thermal_zone(building_sql=building_dj, zone_teaser=zone)
        _import_usage_zone(
            building_sql=building_dj, zone_teaser=zone, zone_sql=zone_sql
        )
    return building_dj


def _import_thermal_zone(building_sql, zone_teaser):
    """Documentation is missing."""
    zone_sql = ThermalZone(
        gmlid="ThermalZone_{}_{}".format(building_sql.name, zone_teaser.name),
        name="ThermalZone_{}_{}".format(building_sql.name, zone_teaser.name),
        objectclass=ObjectClass.objects.get(classname="ThermalZone"),
        building=building_sql,
        infiltration_rate=zone_teaser.use_conditions.infiltration_rate,
        infiltration_rate_uom="1/h",
        is_cooled=zone_teaser.use_conditions.with_cooling,
        is_heated=zone_teaser.use_conditions.with_heating,
        is_ventilated=zone_teaser.use_conditions.with_ahu,
    )
    zone_sql.save()
    zone_sql.floor_area = zone_teaser.area
    zone_sql.volume = zone_teaser.volume
    zone_sql.save()

    for wall in zone_teaser.outer_walls:
        thermal_boundary = _import_thermal_boundary(
            teaser_wall=wall, zone_sql=zone_sql, tb_type="outerWall"
        )
        _import_thermal_opening(wall, zone_sql, thermal_boundary)

    for wall in zone_teaser.rooftops:
        thermal_boundary = _import_thermal_boundary(
            teaser_wall=wall, zone_sql=zone_sql, tb_type="roof"
        )
        _import_thermal_opening(wall, zone_sql, thermal_boundary)
    for wall in zone_teaser.ground_floors:
        thermal_boundary = _import_thermal_boundary(
            teaser_wall=wall, zone_sql=zone_sql, tb_type="groundSlab"
        )
    for wall in zone_teaser.inner_walls:
        thermal_boundary = _import_thermal_boundary(
            teaser_wall=wall, zone_sql=zone_sql, tb_type="interiorWall"
        )
    for wall in zone_teaser.floors:
        thermal_boundary = _import_thermal_boundary(
            teaser_wall=wall, zone_sql=zone_sql, tb_type="intermediateFloor"
        )
    for wall in zone_teaser.ceilings:
        thermal_boundary = _import_thermal_boundary(
            teaser_wall=wall, zone_sql=zone_sql, tb_type="intermediateCeiling"
        )
    for wall in zone_teaser.doors:
        thermal_boundary = _import_thermal_boundary(
            teaser_wall=wall, zone_sql=zone_sql, tb_type="door"
        )

    return zone_sql


def _import_usage_zone(building_sql, zone_teaser, zone_sql):
    """Documentation is missing."""
    influx_id = "bldg_{}_zone_{}_".format(
        building_sql.gmlid, zone_teaser.use_conditions.usage
    ).strip()

    usage_sql = UsageZone(
        objectclass=ObjectClass.objects.get(classname="UsageZone"),
        gmlid="UsageZone_{}_{}".format(
            building_sql.name, zone_teaser.use_conditions.usage
        ),
        name="UsageZone_{}_{}".format(
            building_sql.name, zone_teaser.use_conditions.usage
        ),
        building=building_sql,
        thermal_zone=zone_sql,
        usage_zone_type=zone_teaser.use_conditions.usage,
        usage_zone_type_codespace="SIA2024/DINV1859910/TEASER",
        used_floors=building_sql.storeys_above_ground,
    )
    usage_sql.save()
    usage_sql.floor_area = zone_teaser.area
    usage_sql.save()

    usage_sql.heating_schedule = _import_schedule(
        influx_id=influx_id,
        usage_zone=zone_teaser.use_conditions,
        objectclass_schedule="heating_schedule",
        time_depending_values=zone_teaser.use_conditions.schedules[
            "heating_profile"
        ].iloc[:168],
        uom="K",
    )
    usage_sql.cooling_schedule = _import_schedule(
        influx_id=influx_id,
        usage_zone=zone_teaser.use_conditions,
        objectclass_schedule="cooling_schedule",
        time_depending_values=zone_teaser.use_conditions.schedules[
            "cooling_profile"
        ].iloc[:168],
        uom="K",
    )

    occupants = Occupants(
        objectclass=ObjectClass.objects.get(classname="Occupants"),
        gmlid="Occupants_{}_{}".format(
            building_sql.name, zone_teaser.use_conditions.usage
        ),
        name="Occupants_{}_{}".format(
            building_sql.name, zone_teaser.use_conditions.usage
        ),
        usage_zone_occupied_by=usage_sql,
        number_of_occupants=zone_teaser.use_conditions.persons,
    )

    heat_flow_pers = HeatExchangeType(
        convective_fraction=zone_teaser.use_conditions.ratio_conv_rad_persons,
        radiant_fraction=(1 - zone_teaser.use_conditions.ratio_conv_rad_persons),
        total_value=zone_teaser.use_conditions.fixed_heat_flow_rate_persons,
        total_value_uom="W",
    )
    heat_flow_pers.save()

    schedule = _import_schedule(
        influx_id=influx_id,
        usage_zone=zone_teaser.use_conditions,
        objectclass_schedule="occupants",
        time_depending_values=zone_teaser.use_conditions.schedules[
            "persons_profile"
        ].iloc[:168],
        uom="-",
    )
    occupants.heat_dissipation = heat_flow_pers
    occupants.occupancy_rate = schedule
    occupants.save()

    machines = Facilities(
        objectclass=ObjectClass.objects.get(classname="ElectricalAppliances"),
        gmlid="ElectricalAppliances_{}_{}".format(
            building_sql.name, zone_teaser.use_conditions.usage
        ),
        name="ElectricalAppliances_{}_{}".format(
            building_sql.name, zone_teaser.use_conditions.usage
        ),
        usage_zone_equipped_with=usage_sql,
        electrical_power=zone_teaser.use_conditions.machines,
        electrical_power_uom="W/m2",
    )
    heat_flow_mach = HeatExchangeType(
        convective_fraction=zone_teaser.use_conditions.ratio_conv_rad_machines,
        radiant_fraction=(1 - zone_teaser.use_conditions.ratio_conv_rad_machines),
        total_value=zone_teaser.use_conditions.machines,
        total_value_uom="W/m2",
    )
    heat_flow_mach.save()

    operationschedule = _import_schedule(
        influx_id=influx_id,
        usage_zone=zone_teaser.use_conditions,
        objectclass_schedule="machines",
        time_depending_values=zone_teaser.use_conditions.schedules[
            "machines_profile"
        ].iloc[:168],
        uom="-",
    )
    machines.heat_dissipation = heat_flow_mach
    machines.operation_schedule = operationschedule
    machines.save()

    lighting = Facilities(
        objectclass=ObjectClass.objects.get(classname="LightingFacilities"),
        gmlid="LightingFacilities_{}_{}".format(
            building_sql.name, zone_teaser.use_conditions.usage
        ),
        name="LightingFacilities_{}_{}".format(
            building_sql.name, zone_teaser.use_conditions.usage
        ),
        usage_zone_equipped_with=usage_sql,
        electrical_power=zone_teaser.use_conditions.lighting_power,
        electrical_power_uom="W/m2",
    )
    heat_flow_light = HeatExchangeType(
        convective_fraction=zone_teaser.use_conditions.ratio_conv_rad_lighting,
        radiant_fraction=(1 - zone_teaser.use_conditions.ratio_conv_rad_lighting),
        total_value=zone_teaser.use_conditions.lighting_power,
        total_value_uom="W/m2",
    )
    heat_flow_light.save()

    operationschedule = _import_schedule(
        influx_id=influx_id,
        usage_zone=zone_teaser.use_conditions,
        objectclass_schedule="lighting",
        time_depending_values=zone_teaser.use_conditions.schedules[
            "lighting_profile"
        ].iloc[:168],
        uom="-",
    )
    lighting.heat_dissipation = heat_flow_light
    lighting.operation_schedule = operationschedule
    lighting.save()
    usage_sql.save()

    return usage_sql


def _import_schedule(
    influx_id, usage_zone, objectclass_schedule, time_depending_values, uom
):
    """Documentation is missing.

    Currently this will only import the first day of a schedule!

    """
    try:
        usage_name = usage_zone.usage
    except:
        usage_name = usage_zone
        pass
    try:
        schedule_values = IrregularTimeSeriesFile.objects.get(
            file_id="{}_{}".format(usage_name, objectclass_schedule)
        )
        values = schedule_values.get_values(
            start=dt(2014, 1, 1, 0, 0, 0), end=dt(2014, 1, 7, 23, 55, 0), mean="1h"
        )
        values["test"] = time_depending_values.values

        if values.ix[:, 0].equals(values["test"]):
            pass
        else:

            schedule_values = IrregularTimeSeriesFile(
                objectclass=ObjectClass.objects.get(
                    classname="IrregularTimeSeriesFile"
                ),
                name="IrregularTimeSeriesFile_{}_{}".format(
                    influx_id, objectclass_schedule
                ),
                gmlid="IrregularTimeSeriesFile_{}_{}".format(
                    influx_id, objectclass_schedule
                ),
                thematic_description="Schedule",
                source="TEASER",
                file_id="{}_{}".format(influx_id, objectclass_schedule),
                uom=uom,
                acquisition_method="unknown",
            )
            time_depending_values = time_depending_values.to_frame()
            time_depending_values.index = pd.date_range(
                "2014-01-01 00:00:00", periods=168, freq="H"
            )
            schedule_values.values = time_depending_values
            schedule_values.save()
    except IrregularTimeSeriesFile.DoesNotExist:
        schedule_values = IrregularTimeSeriesFile(
            objectclass=ObjectClass.objects.get(classname="IrregularTimeSeriesFile"),
            name="IrregularTimeSeriesFile_{}_{}".format(
                influx_id, objectclass_schedule
            ),
            gmlid="IrregularTimeSeriesFile_{}_{}".format(
                influx_id, objectclass_schedule
            ),
            thematic_description="Schedule",
            source="TEASER",
            file_id="{}_{}".format(influx_id, objectclass_schedule),
            uom=uom,
            acquisition_method="unknown",
        )
        time_depending_values = time_depending_values.to_frame()
        time_depending_values.index = pd.date_range(
            "2014-01-01 00:00:00", periods=168, freq="H"
        )
        schedule_values.values = time_depending_values
        schedule_values.save()

    ts_schedule = TimeSeriesSchedule(
        objectclass=ObjectClass.objects.get(classname="TimeSeriesSchedule"),
        name="TimeSeriesSchedule_{}_{}".format(influx_id, objectclass_schedule),
        gmlid="TimeSeriesSchedule_{}_{}".format(influx_id, objectclass_schedule),
        time_depending_values=schedule_values,
    )
    ts_schedule.save()
    return ts_schedule


def _import_thermal_boundary(teaser_wall, zone_sql, tb_type):
    """Documentation is missing."""
    thermal_boundary = ThermalBoundary(
        objectclass=ObjectClass.objects.get(classname="ThermalBoundary"),
        name="ThermalBoundary_{}_{}".format(zone_sql.name, teaser_wall.name),
        gmlid="ThermalBoundary_{}_{}".format(zone_sql.name, teaser_wall.name),
        area=teaser_wall.area,
        area_uom="m2",
        azimuth=teaser_wall.orientation,
        azimuth_uom="deg",
        inclination=teaser_wall.tilt,
        inclination_uom="deg",
        thermal_boundary_type=tb_type,
    )
    thermal_boundary.save()
    thermal_boundary.delimites.add(zone_sql)
    construction = Construction(
        objectclass=ObjectClass.objects.get(classname="Construction"),
        gmlid="Construction_{}_ {}".format(zone_sql.name, teaser_wall.name),
        name="Construction_{}_ {}".format(zone_sql.name, teaser_wall.name),
        u_value=teaser_wall.u_value,
        u_value_uom="W/(m2*K)",
    )
    construction.save()
    thermal_boundary.construction = construction
    thermal_boundary.save()
    for lay in teaser_wall.layer:
        _import_layer(layer=lay, construction_sql=thermal_boundary.construction)
    return thermal_boundary


def _import_thermal_opening(teaser_wall, zone_sql, thermal_boundary):
    """Documentation is missing."""
    windows = teaser_wall.parent.find_wins(teaser_wall.orientation, teaser_wall.tilt)

    for win in windows:

        thermal_opening = ThermalOpening(
            gmlid="ThermalOpening_{}_{}".format(zone_sql.name, win.name),
            name="ThermalOpening_{}_{}".format(zone_sql.name, win.name),
            objectclass=ObjectClass.objects.get(classname="ThermalOpening"),
            area=win.area,
            area_uom="m2",
        )
        thermal_opening.save()
        thermal_opening.thermal_boundary = thermal_boundary
        construction = Construction(
            objectclass=ObjectClass.objects.get(classname="Construction"),
            gmlid="Construction_{}_{}".format(zone_sql.name, win.name),
            name="Construction_{}_{}".format(zone_sql.name, win.name),
            u_value=win.u_value,
            u_value_uom="W/(m2*K)",
        )
        construction.save()
        thermal_opening.construction = construction
        thermal_opening.save()
        for lay in win.layer:
            _import_layer(layer=lay, construction_sql=thermal_opening.construction)


def _import_layer(layer, construction_sql):
    """Documentation is missing."""
    lay_sql = Layer(
        objectclass=ObjectClass.objects.get(classname="Layer"),
        gmlid="Layer_".format(construction_sql.name),
        name="Layer_".format(construction_sql.name),
        construction=construction_sql,
    )
    lay_sql.save()
    lay_comp_sql = LayerComponent(
        objectclass=ObjectClass.objects.get(classname="LayerComponent"),
        gmlid="LayerComponent_{}".format(construction_sql.name),
        name="LayerComponent_{}".format(construction_sql.name),
        area_fraction=1,
        area_fraction_uom="-",
        layer=lay_sql,
        thickness=layer.thickness,
        thickness_uom="m",
    )
    try:
        lay_comp_sql.material = SolidMaterial.objects.get(gmlid=layer.material.name)

    except SolidMaterial.DoesNotExist:
        material = SolidMaterial(
            gmlid=layer.material.name,
            name=layer.material.name,
            objectclass=ObjectClass.objects.get(classname="SolidMaterial"),
            conductivity=layer.material.thermal_conduc,
            conductivity_uom="W/(m*K)",
            density=layer.material.density,
            density_uom="kg/m3",
            specific_heat=layer.material.heat_capac,
            specific_heat_uom="kJ/(kg*K)",
        )
        material.save()
        lay_comp_sql.material = material
    lay_comp_sql.save()


def _import_mechanical_ventilation(ahu_teaser, building_sql):
    """Documentation is missing."""
    influx_id = "bldg_{}_ahu_heating".format(building_sql.gmlid).strip()
    mech_vent = MechanicalVentilation(
        gmlid="MechanicalVentilation_{}".format(building_sql.name),
        name="MechanicalVentilation_{}".format(building_sql.name),
        objectclass=ObjectClass.objects.get(classname="MechanicalVentilation"),
        has_heat_recovery=ahu_teaser.heat_recovery,
        recuperation_factor=ahu_teaser.efficiency_recovery,
        recuperation_factor_uom="-",
        humidification=ahu_teaser.humidification,
        dehumidification=ahu_teaser.dehumidification,
    )
    mech_vent.save()
    mech_vent.installed_in.add(building_sql)
    ahu_cooling = SystemOperation(
        gmlid="SystemOperation_{}_{}".format("ventilationCooling", building_sql.name),
        name="SystemOperation_{}_{}".format("ventilationCooling", building_sql.name),
        objectclass=ObjectClass.objects.get(classname="SystemOperation"),
        end_use="ventilationCooling",
        energy_conversion_system=mech_vent,
    )
    ahu_cooling.save()
    ahu_heating = SystemOperation(
        gmlid="SystemOperation_{}_{}".format("ventilationHeating", building_sql.name),
        name="SystemOperation_{}_{}".format("ventilationHeating", building_sql.name),
        objectclass=ObjectClass.objects.get(classname="SystemOperation"),
        end_use="ventilationHeating",
        energy_conversion_system=mech_vent,
    )
    ahu_heating.save()
    ahu_heating.operation_time = _import_schedule(
        influx_id="bldg_{}_ahu_heating".format(building_sql.gmlid).strip(),
        usage_zone=None,
        objectclass_schedule="temperature_profile",
        time_depending_values=ahu_teaser.schedules["temperature_profile"].iloc[:168],
        uom="K",
    )
    ahu_elec = SystemOperation(
        gmlid="SystemOperation_{}_{}".format("electricalAppliances", building_sql.name),
        name="SystemOperation_{}_{}".format("electricalAppliances", building_sql.name),
        objectclass=ObjectClass.objects.get(classname="SystemOperation"),
        end_use="electricalAppliances",
        energy_conversion_system=mech_vent,
    )
    ahu_elec.save()
    mech_vent.save()


def _import_energy_system(connected_to_network, purpose, building_teaser, building_sql):
    """Documentation is missing."""

    if connected_to_network is True:
        heat_exchanger = HeatExchanger(
            gmlid="HeatExchanger_{}_{}".format(purpose, building_sql.name),
            name="HeatExchanger_{}_{}".format(purpose, building_sql.name),
            objectclass=ObjectClass.objects.get(classname="HeatExchanger"),
        )
        heat_exchanger.save()
        system_operation = SystemOperation(
            gmlid="SystemOperation_{}_{}".format(purpose, building_sql.name),
            name="SystemOperation_{}_{}".format(purpose, building_sql.name),
            objectclass=ObjectClass.objects.get(classname="SystemOperation"),
            end_use=purpose,
            energy_conversion_system=heat_exchanger,
        )
        system_operation.save()
        heat_exchanger.installed_in.add(building_sql)
        heat_exchanger.save()
    else:
        energy_system = EnergyConversionSystem(
            gmlid="EnergySystem_{}_{}".format(purpose, building_sql.name),
            name="EnergySystem_{}_{}".format(purpose, building_sql.name),
            objectclass=ObjectClass.objects.get(classname="GenericConversionSystem"),
        )
        energy_system.save()
        system_operation = SystemOperation(
            gmlid="SystemOperation_{}_{}".format(purpose, building_sql.name),
            name="SystemOperation_{}_{}".format(purpose, building_sql.name),
            objectclass=ObjectClass.objects.get(classname="SystemOperation"),
            end_use=purpose,
            energy_conversion_system=energy_system,
        )
        system_operation.save()
        energy_system.installed_in.add(building_sql)
        energy_system.save()
