"""This module contains the mapping class for TEASER."""

from django.contrib.gis.db import models


class BWZKMapping(models.Model):
    """ORM class for BWZK mapping.

    This class contains the corresponding Mapping between archetype buildings
    and BWZK number


    Parameters
    ----------
    bwzk : string
        BWZK Number, which can also be a collection of number dividid by a
        forward slash ('/')
    archetype : str
        Name of archetype building in TEASER. Allowed: 'Office', 'Institute',
        'Instistue4', 'Institute8'

    """

    bwzk = models.CharField(max_length=4000, blank=True, null=True)
    archetype = models.CharField(max_length=4000, blank=True, null=True)

    class Meta:
        """Meta Class from Django."""

        managed = True
        db_table = "teas_mapping_bwzk"
