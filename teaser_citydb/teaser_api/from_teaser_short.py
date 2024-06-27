"""Contains functions to import information from TEASER to citydb app."""

import datetime
import pytz
import uuid
from citydb.models import CityModel
from citydb.models import EnergyBuilding
from citydb.models import ObjectClass
from citydb.models import MechanicalVentilation
from citydb.models import HeatExchanger
from citydb.models import EnergyConversionSystem
from citydb.models import SystemOperation
from citydb.models import ThermalZone

BUILDING_FUNCTION = {
    "Office": "1300",
    "Institute": "1300/2000",
    "Institute4": "1300/2220",
    "SingleFamilyDwelling": "4400",
    "SingleFamilyHouse": "4400",
}


def import_city_model_short(
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
        bldg_dj = _import_energy_building_short(
            city_model=city_model, building=bldg_t, building_surface=None
        )
        city_model.city_object_member.add(bldg_dj)
        city_model.save()
    return city_model


def _import_energy_building_short(city_model, building, building_surface):
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
        _import_thermal_zone_short(building_sql=building_dj, zone_teaser=zone)
    return building_dj


def _import_thermal_zone_short(building_sql, zone_teaser):
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


def _import_mechanical_ventilation(ahu_teaser, building_sql):
    """Documentation is missing."""

    mech_vent = MechanicalVentilation(
        gmlid="MechanicalVentilation_{}".format(building_sql.name),
        name="MechanicalVentilation_{}".format(building_sql.name),
        objectclass=ObjectClass.objects.get(classname="MechanicalVentilation"),
        has_heat_recovery=ahu_teaser.heat_recovery,
        recuperation_factor=ahu_teaser.efficiency_recovery,
        recuperation_factor_uom="-",
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
