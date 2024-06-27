from teaser.project import Project
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
import django

django.setup()
from django.contrib.gis.geos import LineString
from teaser_citydb.models import BWZKMapping
from citydb.models import ObjectClass
import teaser_citydb.teaser_api.to_teaser_geometry as tt_geom

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


def to_teaser_window(city_model, buildings=None):

    prj = Project(load_data=True)
    prj.name = city_model.name
    buildings_not_generated = []
    e_win_all = []

    if buildings is None:
        for building in city_model.city_object_member.filter(
            objectclass=ObjectClass.objects.get(classname="Building")
        ):
            buildings_not_generated, e_win = _import_building_window(
                building_energy=building.building_obj.building_energy_obj,
                project=prj,
                buildings_not_generated=buildings_not_generated,
            )
            e_win_all.append(e_win)

    else:
        for building in buildings:
            buildings_not_generated, e_win = _import_building_window(
                building_energy=building.building_obj.building_energy_obj,
                project=prj,
                buildings_not_generated=buildings_not_generated,
            )
            e_win_all.append(e_win)

    return prj, buildings_not_generated, e_win_all


def _import_building_window(building_energy, project, buildings_not_generated):
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
            net_leased_area=None,
            number_of_floors=int(building_energy.storeys_above_ground),
            height_of_floors=round(
                building_energy.measured_height
                / int(building_energy.storeys_above_ground),
                2,
            ),
            internal_gains_mode=2,
        )

        footprint = (
            building_energy.bldg_thematic_surface.first()
            .thematic_surface_geom.first()
            .geometry
        )
        bldg.net_leased_area = (
            footprint.area * int(building_energy.storeys_above_ground) * 0.85
        )

        multi_line = []
        for ring in footprint:
            for i, point in enumerate(ring):
                try:
                    multi_line.append(LineString(point, ring[i + 1]))
                except IndexError:
                    pass
        facade = {}
        total_area = 0.0
        for i, line in enumerate(multi_line):

            if tt_geom._get_orientation(line) in facade.keys():
                facade[tt_geom._get_orientation(line)] += (
                    line.length * building_energy.measured_height
                )
            else:
                facade[tt_geom._get_orientation(line)] = (
                    line.length * building_energy.measured_height
                )
            total_area += line.length * building_energy.measured_height

        outer_wall_gml = {}
        window_gml = {}
        no_orientation = True
        for orientation, facade_area in facade.items():
            window_gml["Win_{}".format(orientation)] = {
                "area": 0.0,
                "orientation": orientation,
                "tilt": 90,
            }
            for zone in building_energy.thermal_zones.all():
                try:
                    for bound in zone.thermal_boundary_obj.all():
                        for win in bound.contains.all():
                            if orientation == float(bound.azimuth):
                                window_gml["Win_{}".format(orientation)][
                                    "area"
                                ] += float(win.area)
                except TypeError:
                    no_orientation = True

            if no_orientation is False:
                outer_wall_gml["Wall_{}".format(orientation)] = {
                    "area": facade_area
                    - window_gml["Win_{}".format(orientation)]["area"],
                    "orientation": orientation,
                    "tilt": 90,
                }
        total_win_area = 0
        if no_orientation is True:
            for zone in building_energy.thermal_zones.all():
                for bound in zone.thermal_boundary_obj.all():

                    for win in bound.contains.all():

                        total_win_area += float(win.area)

        for orientation, facade_area in facade.items():
            window_gml["Win_{}".format(orientation)] = {
                "area": facade_area / total_area * total_win_area,
                "orientation": orientation,
                "tilt": 90,
            }
            factor_win_gml = total_win_area / total_area
            outer_wall_gml["Wall_{}".format(orientation)] = {
                "area": facade_area - window_gml["Win_{}".format(orientation)]["area"],
                "orientation": orientation,
                "tilt": 90,
            }

        if sum([value["area"] for key, value in window_gml.items()]) == 0:
            for key, value in facade.items():
                outer_wall_gml["Wall_{}".format(key)] = {
                    "area": value * (1 - bldg.factor_win_gml),
                    "orientation": key,
                    "tilt": 90,
                }
                window_gml["Win_{}".format(key)] = {
                    "area": value * bldg.factor_win_gml,
                    "orientation": key,
                    "tilt": 90,
                }
                factor_win_gml = bldg.factor_win_gml

        roof_gml = {"Roof": {"area": footprint.area, "orientation": -1, "tilt": 0}}
        ground_floor_gml = {
            "Ground Floor": {"area": footprint.area, "orientation": -2, "tilt": 0}
        }

        bldg.outer_wall_gml = outer_wall_gml
        bldg.window_gml = window_gml
        bldg.roof_gml = roof_gml
        bldg.ground_floor_gml = ground_floor_gml

        bldg.generate_gml()

        return buildings_not_generated, factor_win_gml
    else:
        buildings_not_generated.append(building_energy.gmlid)
        return buildings_not_generated, factor_win_gml
