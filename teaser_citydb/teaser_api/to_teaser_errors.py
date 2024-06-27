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
import collections

django.setup()
from django.contrib.gis.geos import LineString
from teaser_citydb.models import BWZKMapping
from citydb.models import ObjectClass
import teaser_citydb.teaser_api.to_teaser_geometry as tt_geom
import warnings

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


def to_teaser_element(city_model, buildings=None):

    prj = Project(load_data=True)
    prj.name = city_model.name
    buildings_not_generated = []

    if buildings is None:
        for building in city_model.city_object_member.filter(
            objectclass=ObjectClass.objects.get(classname="Building")
        ):
            buildings_not_generated = _import_building_element(
                building_energy=building.building_obj.building_energy_obj,
                project=prj,
                buildings_not_generated=buildings_not_generated,
            )

    else:
        for building in buildings:
            # try:
            buildings_not_generated = _import_building_element(
                building_energy=building.building_obj.building_energy_obj,
                project=prj,
                buildings_not_generated=buildings_not_generated,
            )
            # except:
            #     print(building)

    return prj, buildings_not_generated


def _import_building_element(building_energy, project, buildings_not_generated):
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
        total_line_length = footprint.length
        multi_line = []
        for ring in footprint:
            for i, point in enumerate(ring):
                try:
                    multi_line.append(LineString(point, ring[i + 1]))
                except IndexError:
                    pass

        bldg.net_leased_area = (
            footprint.area * int(building_energy.storeys_above_ground) * 0.85
        )

        zone = building_energy.thermal_zones.all().order_by("pk").first()
        outer_wall_gml = {}
        window_gml = {}
        roof_gml = {}
        ground_floor_gml = {}

        for b, bound in enumerate(
            zone.thermal_boundary_obj.filter(thermal_boundary_type="OuterWall")
        ):
            # if float(bound.construction.u_value) == 4.0:
            #     bound.thermal_boundary_type = "GroundSlab"
            #     bound.save()

            if bound.azimuth is None:

                for i, line in enumerate(multi_line):

                    outer_wall_gml["bound_{}".format(i)] = collections.OrderedDict(
                        {
                            "area": (
                                float(bound.area)
                                / float(zone.floor_area / building_energy.floor_area)
                            )
                            * line.length
                            / total_line_length,
                            "orientation": tt_geom._get_orientation(line),
                            "tilt": float(bound.inclination),
                            "u_value": float(bound.construction.u_value),
                            "layer": collections.OrderedDict(),
                        }
                    )
                    if len(bound.construction.layer.all()) == 0:
                        outer_wall_gml["bound_{}".format(i)]["layer"] = None
                    for l, layer in enumerate(
                        bound.construction.layer.all().order_by("ordered_position")
                    ):

                        info_layer = layer.layer_component.first()
                        outer_wall_gml["bound_{}".format(i)]["layer"][
                            l
                        ] = collections.OrderedDict(
                            {
                                "position": int(layer.ordered_position),
                                "thickness": float(info_layer.thickness),
                                "material": info_layer.material.solid_material_abstract.name,
                                "density": float(
                                    info_layer.material.solid_material_abstract.density
                                ),
                                "thermal_conduc": float(
                                    info_layer.material.solid_material_abstract.conductivity
                                ),
                                "heat_capac": float(
                                    info_layer.material.solid_material_abstract.specific_heat
                                    / 1000
                                ),
                            }
                        )
                    for window in bound.contains.all():
                        window_gml["window_{}".format(i)] = collections.OrderedDict(
                            {
                                "area": (
                                    float(window.area)
                                    / float(
                                        zone.floor_area / building_energy.floor_area
                                    )
                                )
                                * line.length
                                / total_line_length,
                                "type": "Window",
                                "orientation": tt_geom._get_orientation(line),
                                "tilt": float(bound.inclination),
                                "u_value": float(window.construction.u_value),
                            }
                        )
            else:

                outer_wall_gml["bound_{}".format(b)] = collections.OrderedDict(
                    {
                        "area": float(bound.area)
                        / float(zone.floor_area / building_energy.floor_area),
                        "orientation": float(bound.azimuth),
                        "tilt": float(bound.inclination),
                        "u_value": float(bound.construction.u_value),
                        "layer": collections.OrderedDict(),
                    }
                )

                if len(bound.construction.layer.all()) == 0:
                    outer_wall_gml["bound_{}".format(b)]["layer"] = None
                for l, layer in enumerate(
                    bound.construction.layer.all().order_by("ordered_position")
                ):

                    info_layer = layer.layer_component.first()
                    outer_wall_gml["bound_{}".format(b)]["layer"][
                        l
                    ] = collections.OrderedDict(
                        {
                            "position": int(layer.ordered_position),
                            "thickness": float(info_layer.thickness),
                            "material": info_layer.material.solid_material_abstract.name,
                            "density": float(
                                info_layer.material.solid_material_abstract.density
                            ),
                            "thermal_conduc": float(
                                info_layer.material.solid_material_abstract.conductivity
                            ),
                            "heat_capac": float(
                                info_layer.material.solid_material_abstract.specific_heat
                                / 1000
                            ),
                        }
                    )

                for window in bound.contains.all():
                    window_gml["window_{}".format(b)] = collections.OrderedDict(
                        {
                            "area": float(window.area)
                            / float(zone.floor_area / building_energy.floor_area),
                            "type": "Window",
                            "orientation": float(bound.azimuth),
                            "tilt": float(bound.inclination),
                            "u_value": float(window.construction.u_value),
                        }
                    )

        for b, bound in enumerate(
            zone.thermal_boundary_obj.filter(thermal_boundary_type="Roof")
        ):

            if bound.azimuth is None:
                bound.azimuth = 0.0
                bound.save()
            roof_gml["bound_{}".format(b)] = collections.OrderedDict(
                {
                    "area": float(bound.area)
                    / float(zone.floor_area / building_energy.floor_area),
                    "orientation": float(bound.azimuth),
                    "tilt": float(bound.inclination),
                    "u_value": float(bound.construction.u_value),
                    "layer": collections.OrderedDict(),
                }
            )

            if len(bound.construction.layer.all()) == 0:
                roof_gml["bound_{}".format(b)]["layer"] = None
            for l, layer in enumerate(
                bound.construction.layer.all().order_by("ordered_position")
            ):

                info_layer = layer.layer_component.first()
                roof_gml["bound_{}".format(b)]["layer"][l] = collections.OrderedDict(
                    {
                        "position": int(layer.ordered_position),
                        "thickness": float(info_layer.thickness),
                        "material": info_layer.material.solid_material_abstract.name,
                        "density": float(
                            info_layer.material.solid_material_abstract.density
                        ),
                        "thermal_conduc": float(
                            info_layer.material.solid_material_abstract.conductivity
                        ),
                        "heat_capac": float(
                            info_layer.material.solid_material_abstract.specific_heat
                            / 1000
                        ),
                    }
                )
        for b, bound in enumerate(
            zone.thermal_boundary_obj.filter(thermal_boundary_type="GroundSlab")
        ):
            if bound.azimuth is None:
                bound.azimuth = 0.0
                bound.save()
            ground_floor_gml["bound_{}".format(b)] = collections.OrderedDict(
                {
                    "area": float(bound.area)
                    / float(zone.floor_area / building_energy.floor_area),
                    "orientation": float(bound.azimuth),
                    "tilt": float(bound.inclination),
                    "u_value": float(bound.construction.u_value),
                    "layer": collections.OrderedDict(),
                }
            )
            if len(bound.construction.layer.all()) == 0:
                ground_floor_gml["bound_{}".format(b)]["layer"] = None
            for l, layer in enumerate(
                bound.construction.layer.all().order_by("ordered_position")
            ):

                info_layer = layer.layer_component.first()
                ground_floor_gml["bound_{}".format(b)]["layer"][
                    l
                ] = collections.OrderedDict(
                    {
                        "position": int(layer.ordered_position),
                        "thickness": float(info_layer.thickness),
                        "material": info_layer.material.solid_material_abstract.name,
                        "density": float(
                            info_layer.material.solid_material_abstract.density
                        ),
                        "thermal_conduc": float(
                            info_layer.material.solid_material_abstract.conductivity
                        ),
                        "heat_capac": float(
                            info_layer.material.solid_material_abstract.specific_heat
                            / 1000
                        ),
                    }
                )

        bldg.outer_wall_gml = outer_wall_gml
        bldg.window_gml = window_gml
        bldg.roof_gml = roof_gml
        bldg.ground_floor_gml = ground_floor_gml

        if (
            bool(outer_wall_gml) is False
            or bool(roof_gml) is False
            or bool(ground_floor_gml) is False
        ):
            try:
                bldg.parent.buildings.remove(bldg)
                buildings_not_generated = tt_geom._import_building_geometry(
                    building_energy, project, buildings_not_generated
                )

                warnings.warn(
                    "Building {} is simulated without Building Element information".format(
                        building_energy.gmlid
                    )
                )
                return buildings_not_generated
            except:
                bldg.parent.buildings.remove(bldg)
                buildings_not_generated.append(building_energy.gmlid)
                return buildings_not_generated
        else:
            bldg.generate_info()
            return buildings_not_generated
    else:
        buildings_not_generated.append(building_energy.gmlid)
        return buildings_not_generated
