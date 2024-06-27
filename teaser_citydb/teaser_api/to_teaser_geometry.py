import math
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


def to_teaser_geometry(city_model, buildings=None):

    prj = Project(load_data=True)
    prj.name = city_model.name
    buildings_not_generated = []

    if buildings is None:
        for building in city_model.city_object_member.filter(
            objectclass=ObjectClass.objects.get(classname="Building")
        ):
            buildings_not_generated = _import_building_geometry(
                building_energy=building.building_obj.building_energy_obj,
                project=prj,
                buildings_not_generated=buildings_not_generated,
            )

    else:
        for building in buildings:
            buildings_not_generated = _import_building_geometry(
                building_energy=building.building_obj.building_energy_obj,
                project=prj,
                buildings_not_generated=buildings_not_generated,
            )

    return prj, buildings_not_generated


def _get_orientation(line):

    normal = round(
        math.atan2((line[1][1] - line[0][1]), (line[1][0] - line[0][0]))
        * (180 / math.pi),
        0,
    )

    # very Juelich specific

    if -180.0 <= normal < 0.0:
        orientation = -normal
        if 1.0 < orientation < 10.0:
            return 0.0
        elif 35.0 < orientation < 55.0:
            return 45.0
        elif 80.0 < orientation < 110.0:
            return 90.0
        elif 125.0 < orientation < 145.0:
            return 135.0
        elif 170.0 < orientation < 179.0:
            return 180.0
        else:
            return orientation
    elif 0.0 < normal < 180.0:
        orientation = 360.0 - normal
        if 181.0 < orientation < 190.0:
            return 180.0
        elif 215.0 < orientation < 235.0:
            return 225.0
        elif 260.0 < orientation < 280.0:
            return 270.0
        elif 305.0 < orientation < 325.0:
            return 315.0
        elif 350.0 < orientation < 369.0:
            return 0.0
        else:
            return orientation
    elif normal == 0 or normal == 180:
        return round(normal, 0)


def _import_building_geometry(building_energy, project, buildings_not_generated):
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
        for i, line in enumerate(multi_line):

            if _get_orientation(line) in facade.keys():
                facade[_get_orientation(line)] += (
                    line.length * building_energy.measured_height
                )
            else:
                facade[_get_orientation(line)] = (
                    line.length * building_energy.measured_height
                )

        outer_wall_gml = {}
        window_gml = {}
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

        roof_gml = {"Roof": {"area": footprint.area, "orientation": -1, "tilt": 0}}
        ground_floor_gml = {
            "Ground Floor": {"area": footprint.area, "orientation": -2, "tilt": 0}
        }

        bldg.outer_wall_gml = outer_wall_gml
        bldg.window_gml = window_gml
        bldg.roof_gml = roof_gml
        bldg.ground_floor_gml = ground_floor_gml

        bldg.generate_gml()

        return buildings_not_generated
    else:
        buildings_not_generated.append(building_energy.gmlid)
        return buildings_not_generated
