import collections
from teaser.project import Project
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
from teaser_citydb.models import BWZKMapping
from django.contrib.gis.geos import LineString
from citydb.models import ObjectClass
from teaser_citydb.models import UsageMapping
import teaser_citydb.teaser_api.to_teaser_geometry as tt_geom

BUILDING_CLASS = {
    "Office": {"method": "bmvbs", "teaser_class": Office},
    "Institute": {"method": "bmvbs", "teaser_class": Institute},
    "Institute4": {"method": "bmvbs", "teaser_class": Institute4},
    "Institute8": {"method": "bmvbs", "teaser_class": Institute8},
    "Building": {"method": "undefined", "teaser_class": Building},
    "SingleFamilyDwelling": {"method": "iwu", "teaser_class": SingleFamilyDwelling},
    "SingleFamilyHouse": {"method": "tabula_de", "teaser_class": SingleFamilyDwelling},
    "TerracedHouse": {"method": "tabula_de", "teaser_class": SingleFamilyDwelling},
    "MultiFamilyHouse": {"method": "tabula_de", "teaser_class": SingleFamilyDwelling},
    "ApartmentBlock": {"method": "tabula_de", "teaser_class": SingleFamilyDwelling},
}


def to_teaser_usage_zone(city_model, buildings):

    prj = Project(load_data=True)
    prj.name = city_model.name
    buildings_not_generated = []
    if buildings is None:
        for building in city_model.city_object_member.filter(
            objectclass=ObjectClass.objects.get(classname="Building")
        ):
            buildings_not_generated = _import_building_usage_zone(
                building_energy=building.building_obj.building_energy_obj,
                project=prj,
                buildings_not_generated=buildings_not_generated,
            )
    else:
        for building in buildings:
            buildings_not_generated = _import_building_usage_zone(
                building_energy=building.building_obj.building_energy_obj,
                project=prj,
                buildings_not_generated=buildings_not_generated,
            )
    return prj, buildings_not_generated


def _import_building_usage_zone(building_energy, project, buildings_not_generated):
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
        outer_wall_gml = {}
        window_gml = {}
        for i, line in enumerate(multi_line):

            outer_wall_gml["Wall_{}".format(i)] = {
                "area": (line.length * building_energy.measured_height)
                * (1 - bldg.factor_win_gml),
                "orientation": tt_geom._get_orientation(line),
                "tilt": 90,
            }
            window_gml["Window_{}".format(i)] = {
                "area": (line.length * building_energy.measured_height)
                * bldg.factor_win_gml,
                "orientation": tt_geom._get_orientation(line),
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

        temp_sum_zones = collections.defaultdict(float)
        for zone_sql in building_energy.thermal_zones.all():
            temp_sum_zones[
                UsageMapping.objects.get(
                    din_277=zone_sql.usage_zone.first().usage_zone_type
                ).usage_zone
            ] += zone_sql.floor_area
        bldg.zone_area_factors = collections.OrderedDict()
        for key, value in temp_sum_zones.items():
            bldg.zone_area_factors[key] = [(value / building_energy.floor_area), key]

        bldg.generate_gml()
        bldg.calc_building_parameter()

        return buildings_not_generated
    else:
        buildings_not_generated.append(building_energy.gmlid)
        return buildings_not_generated
