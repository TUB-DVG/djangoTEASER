"""This module contains the mapping class for TEASER."""

from django.contrib.gis.db import models


class UsageMapping(models.Model):
    """ORM class for usage zone mapping.

    This class contains the corresponding Mapping between TEASER usage zones
    and DIN - 277 -2 classification


    Parameters
    ----------
    din_277 : string
        DIN - 277 - 2 classification, which can also be a collection of number
        divided by a forward slash ('/')
    usage_zone : str
        Name of usage_zone in TEASER.

    """

    din_277 = models.CharField(max_length=4000, blank=True, null=True)
    usage_zone = models.CharField(max_length=4000, blank=True, null=True)

    class Meta:
        """Meta Class from Django."""

        managed = True
        db_table = "teas_mapping_din"
