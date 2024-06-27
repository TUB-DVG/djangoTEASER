"""Little helpfer function to rename all TEASER buildings."""
import string
import random


def random_choice(k=4):
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choices(alphabet, k=k))


def rename_teaser_buildings(prj):
    """Rename all building in teaser to be unique in database.

    Parameters
    ----------
    prj : teaser.Project()
        Project instance of TEASER to be uploaded in the database.

    Returns
    --------
    prj : teaser.Project()
        Project instance of TEASER with renamed building names.

    """
    for bldg in prj.buildings:
        bldg.name = "{}_{}".format(bldg.name, random_choice(k=4))

    return prj
