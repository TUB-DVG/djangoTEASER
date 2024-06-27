from citydb.models import ObjectClass
from teaser.project import Project
from datetime import datetime as dt
from teaser.logic.archetypebuildings.tabula.de.singlefamilyhouse import (
    SingleFamilyHouse,
)
from teaser.logic.archetypebuildings.tabula.de.multifamilyhouse import MultiFamilyHouse
from teaser.logic.archetypebuildings.tabula.de.terracedhouse import TerracedHouse
from teaser.logic.archetypebuildings.tabula.de.apartmentblock import ApartmentBlock
from teaser.logic.archetypebuildings.bmvbs.office import Office
from teaser.logic.buildingobjects.building import Building
from teaser.logic.archetypebuildings.bmvbs.custom.institute import Institute
from teaser.logic.archetypebuildings.bmvbs.custom.institute4 import Institute4
from teaser.logic.archetypebuildings.bmvbs.custom.institute8 import Institute8
from teaser.logic.archetypebuildings.bmvbs.singlefamilydwelling import (
    SingleFamilyDwelling,
)
from teaser.logic.buildingobjects.thermalzone import ThermalZone
from teaser.logic.buildingobjects.useconditions import UseConditions
from teaser.logic.buildingobjects.buildingsystems.buildingahu import BuildingAHU
from teaser.logic.buildingobjects.buildingphysics.outerwall import OuterWall
from teaser.logic.buildingobjects.buildingphysics.rooftop import Rooftop
from teaser.logic.buildingobjects.buildingphysics.groundfloor import GroundFloor
from teaser.logic.buildingobjects.buildingphysics.innerwall import InnerWall
from teaser.logic.buildingobjects.buildingphysics.floor import Floor
from teaser.logic.buildingobjects.buildingphysics.ceiling import Ceiling
from teaser.logic.buildingobjects.buildingphysics.door import Door
from teaser.logic.buildingobjects.buildingphysics.window import Window
from teaser.logic.buildingobjects.buildingphysics.layer import Layer
from teaser.logic.buildingobjects.buildingphysics.material import Material
import django

django.setup()
from teaser_citydb.models import BWZKMapping

BUILDING_CLASS = {
    "Office": {"method": "bmvbs", "teaser_class": Office},
    "Institute": {"method": "bmvbs", "teaser_class": Institute},
    "Institute4": {"method": "bmvbs", "teaser_class": Institute4},
    "Institute8": {"method": "bmvbs", "teaser_class": Institute8},
    "Building": {"method": "undefined", "teaser_class": Building},
    "SingleFamilyDwelling": {"method": "iwu", "teaser_class": SingleFamilyDwelling},
    "SingleFamilyHouse": {"method": "tabula_de", "teaser_class": SingleFamilyHouse},
    "TerracedHouse": {"method": "tabula_de", "teaser_class": TerracedHouse},
    "MultiFamilyHouse": {"method": "tabula_de", "teaser_class": MultiFamilyHouse},
    "ApartmentBlock": {"method": "tabula_de", "teaser_class": ApartmentBlock},
}


def to_teaser_archetype(city_model, buildings=None):

    prj = Project(load_data=True)
    prj.name = city_model.name
    buildings_not_generated = []
    if buildings is None:
        for building in city_model.city_object_member.filter(
            objectclass=ObjectClass.objects.get(classname="Building")
        ):
            buildings_not_generated = _import_building_archetype(
                building_energy=building.building_obj.building_energy_obj,
                project=prj,
                buildings_not_generated=buildings_not_generated,
            )
    else:
        for building in buildings:
            buildings_not_generated = _import_building_archetype(
                building_energy=building.building_obj.building_energy_obj,
                project=prj,
                buildings_not_generated=buildings_not_generated,
            )

    return prj, buildings_not_generated


def _import_building_archetype(building_energy, project, buildings_not_generated):
    """Doc is missing."""
    try:
        round(
            building_energy.measured_height / int(building_energy.storeys_above_ground),
            2,
        ),
    except ZeroDivisionError:
        buildings_not_generated.append(building_energy.gmlid)
        return buildings_not_generated

    if BWZKMapping.objects.get(bwzk=building_energy.function).archetype is not None:
        print("Import {} to Teaser".format(building_energy.gmlid))
        bl_class = BUILDING_CLASS[
            BWZKMapping.objects.get(bwzk=building_energy.function).archetype
        ]["teaser_class"]
        bldg = bl_class(
            parent=project,
            name=building_energy.gmlid,
            year_of_construction=building_energy.year_of_construction.year,
            net_leased_area=round(building_energy.floor_area, 0),
            number_of_floors=int(building_energy.storeys_above_ground),
            height_of_floors=round(
                building_energy.measured_height
                / int(building_energy.storeys_above_ground),
                2,
            ),
            internal_gains_mode=2,
        )
        bldg.generate_archetype()

        return buildings_not_generated
    else:
        buildings_not_generated.append(building_energy.gmlid)
        return buildings_not_generated


def to_teaser(city_model):

    prj = Project()
    prj.name = city_model.name
    for building in city_model.city_object_member.filter(
        objectclass=ObjectClass.objects.get(classname="Building")
    ):
        _import_building(
            building_energy=building.building_obj.building_energy_obj, project=prj
        )
    return prj


def _import_building(building_energy, project):
    bl_class = BUILDING_CLASS[building_energy.building_type]["teaser_class"]
    bldg = bl_class(parent=project)
    bldg.name = building_energy.gmlid
    bldg.year_of_construction = building_energy.year_of_construction.year
    bldg.number_of_floors = float(building_energy.storeys_above_ground)
    bldg.height_of_floors = float(building_energy.storey_heights_above_ground)

    try:
        _import_central_ahu(building_teaser=bldg, building_sql=building_energy)
    except:
        pass
    for zone_sql in building_energy.thermal_zones.all():
        zone = _import_thermal_zone(zone_sql, bldg)
        _import_use_conditions(zone_sql=zone_sql, zone_teaser=zone)


def _import_thermal_zone(zone_sql, bldg):

    zone = ThermalZone(parent=bldg)
    zone.name = zone_sql.name
    zone.area = float(zone_sql.floor_area)
    zone.volume = float(zone_sql.volume)
    for wall_sql in zone_sql.thermal_boundary_obj.filter(
        thermal_boundary_type="outerWall"
    ):
        out_wall = OuterWall(parent=zone)
        _import_building_element(out_wall, zone, wall_sql)
    for wall_sql in zone_sql.thermal_boundary_obj.filter(thermal_boundary_type="roof"):
        out_wall = Rooftop(parent=zone)
        _import_building_element(out_wall, zone, wall_sql)
    for wall_sql in zone_sql.thermal_boundary_obj.filter(
        thermal_boundary_type="groundSlab"
    ):
        out_wall = GroundFloor(parent=zone)
        _import_building_element(out_wall, zone, wall_sql)
    for wall_sql in zone_sql.thermal_boundary_obj.filter(
        thermal_boundary_type="interiorWall"
    ):
        out_wall = InnerWall(parent=zone)
        _import_building_element(out_wall, zone, wall_sql)
    for wall_sql in zone_sql.thermal_boundary_obj.filter(
        thermal_boundary_type="intermediateFloor"
    ):
        out_wall = Floor(parent=zone)
        _import_building_element(out_wall, zone, wall_sql)
    for wall_sql in zone_sql.thermal_boundary_obj.filter(
        thermal_boundary_type="intermediateCeiling"
    ):
        out_wall = Ceiling(parent=zone)
        _import_building_element(out_wall, zone, wall_sql)
    for wall_sql in zone_sql.thermal_boundary_obj.filter(thermal_boundary_type="door"):
        out_wall = Door(parent=zone)
        _import_building_element(out_wall, zone, wall_sql)

    return zone


def _import_building_element(out_wall, zone, wall_sql):

    out_wall.area = wall_sql.area
    out_wall.name = wall_sql.name
    out_wall.orientation = float(wall_sql.azimuth)
    out_wall.tilt = float(wall_sql.inclination)

    for lay_sql in wall_sql.construction.layer.all():
        _import_layer(out_wall, lay_sql)

    _import_window(wall_sql, zone)


def _import_layer(wall, lay_sql):
    lay = Layer(parent=wall)
    lay_temp = lay_sql.layer_component.first()
    lay.thickness = lay_temp.thickness
    lay.material = Material(parent=lay)
    lay.material.name = lay_temp.material.solid_material_abstract.name
    lay.material.material_id = lay_temp.material.solid_material_abstract.gmlid
    lay.material.density = float(lay_temp.material.solid_material_abstract.density)
    lay.material.thermal_conduc = float(
        lay_temp.material.solid_material_abstract.conductivity
    )
    lay.material.heat_capac = float(
        lay_temp.material.solid_material_abstract.specific_heat
    )


def _import_window(wall_sql, zone):
    for win_sql in wall_sql.contains.all():
        win = Window(parent=zone)
        win.area = win_sql.area
        win.name = win_sql.name
        win.orientation = float(wall_sql.azimuth)
        win.tilt = float(wall_sql.inclination)

        for lay_sql in win_sql.construction.layer.all():
            _import_layer(win, lay_sql)


def _import_use_conditions(zone_sql, zone_teaser):

    zone_teaser.use_conditions = UseConditions(parent=zone_teaser)
    usage_sql = zone_sql.usage_zone.first()
    zone_teaser.use_conditions.usage = usage_sql.usage_zone_type
    zone_teaser.use_conditions.with_heating = zone_sql.is_heated
    zone_teaser.use_conditions.with_cooling = zone_sql.is_cooled
    zone_teaser.use_conditions.with_ahu = zone_sql.is_ventilated
    occupants = usage_sql.occupants.first()

    zone_teaser.use_conditions.persons = occupants.number_of_occupants
    zone_teaser.use_conditions.fixed_heat_flow_rate_persons = float(
        occupants.heat_dissipation.total_value
    )
    zone_teaser.use_conditions.ratio_conv_rad_persons = float(
        occupants.heat_dissipation.convective_fraction
    )

    series = occupants.occupancy_rate.time_depending_values.time_series_file
    series.get_values(
        start=dt(2014, 1, 1, 0, 0, 0),
        end=dt(2014, 12, 31, 23, 55, 0),
        mean="1h",
        query=None,
    )
    zone_teaser.use_conditions.persons_profile = series.values[
        "mean_persons_profile"
    ].tolist()

    machines = usage_sql.facilities.get(
        objectclass=ObjectClass.objects.get(classname="ElectricalAppliances")
    )
    zone_teaser.use_conditions.machines = float(machines.heat_dissipation.total_value)
    zone_teaser.use_conditions.ratio_conv_rad_machines = float(
        machines.heat_dissipation.convective_fraction
    )
    series = machines.operation_schedule.time_depending_values.time_series_file
    series.get_values(
        start=dt(2014, 1, 1, 0, 0, 0),
        end=dt(2014, 12, 31, 23, 55, 0),
        mean="1h",
        query=None,
    )
    zone_teaser.use_conditions.machines_profile = series.values[
        "mean_machines_profile"
    ].tolist()

    lighting = usage_sql.facilities.get(
        objectclass=ObjectClass.objects.get(classname="LightingFacilities")
    )
    zone_teaser.use_conditions.ratio_conv_rad_lighting = float(
        lighting.heat_dissipation.convective_fraction
    )
    zone_teaser.use_conditions.lighting_power = lighting.electrical_power
    series = lighting.operation_schedule.time_depending_values.time_series_file
    series.get_values(
        start=dt(2014, 1, 1, 0, 0, 0),
        end=dt(2014, 12, 31, 23, 55, 0),
        mean="1h",
        query=None,
    )
    zone_teaser.use_conditions.lighting_profile = series.values[
        "mean_lighting_profile"
    ].tolist()

    zone_teaser.use_conditions.infiltration_rate = float(zone_sql.infiltration_rate)

    heating_series = usage_sql.heating_schedule.time_depending_values.time_series_file
    heating_series.get_values(
        start=dt(2014, 1, 1, 0, 0, 0),
        end=dt(2014, 12, 31, 23, 55, 0),
        mean="1h",
        query=None,
    )
    zone_teaser.use_conditions.heating_profile = heating_series.values[
        "mean_heating_profile"
    ].tolist()
    cooling_series = usage_sql.cooling_schedule.time_depending_values.time_series_file
    cooling_series.get_values(
        start=dt(2014, 1, 1, 0, 0, 0),
        end=dt(2014, 12, 31, 23, 55, 0),
        mean="1h",
        query=None,
    )
    zone_teaser.use_conditions.cooling_profile = cooling_series.values[
        "mean_cooling_profile"
    ].tolist()


def _import_central_ahu(building_teaser, building_sql):
    """Documentation missing."""
    mech_vent_sql = building_sql.energy_system.filter(
        objectclass=ObjectClass.objects.get(classname="MechanicalVentilation")
    )[0].energy_conversion_system_obj.mechanical_ventilation_obj
    if mech_vent_sql is not None:
        building_teaser.with_ahu = True
        building_teaser.central_ahu = BuildingAHU(parent=building_teaser)
        building_teaser.central_ahu.heat_recovery = mech_vent_sql.has_heat_recovery
        building_teaser.central_ahu.efficiency_recovery = float(
            mech_vent_sql.recuperation_factor
        )

    else:
        building_teaser.with_ahu = True
        building_teaser.central_ahu = None
