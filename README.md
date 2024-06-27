# TEASER extension for django-citydb Application

## Introduction

This app adds interface between `TEASER` and `django-citydb` Application to conduct
usage of `TEASER` in combination with `3DCityDB`. It adds models and scripts for import
and export to databases as well as for automated simulation.

This repository is currently mainted by the [Institute for Digital Networking of Buildings, Energy Supply Systems and Users](mailto:info@dvg.tu-berlin.de) , if you have any questions don't hesitate to contact us.

We've set up this repository for testing and learning purposes. However, first you need
to learn how to configure your databases and the Django settings.


## Install `django-teaser`

        $ pip install -e [Path/to/this/Readme]

## Quick start to use `django-teaser` in your personal Django project

1. Add `teaser_citydb` to your INSTALLED_APPS setting like this::

        INSTALLED_APPS = [
        ...
        'teaser_citydb',
        ]

2. Include the polls URLconf in your project urls.py like this::

        url(r'^teaser_citydb/', include('teaser_citydb.urls')),

3. Run `python manage.py migrate` to create the `teaser_citydb` models.

5. Visit http://127.0.0.1:8000/teaser_citydb/ to test if installation worked

## Version

This is version 0.1.0. In development phase we will not guarantee to use strict semantic
versioning.

## How to cite?


    (1) Remmen, P. Automated Calibration of Non-Residential Urban Building Energy Modeling = Automatisierte Kalibrierung von Simulationsmodellen Für Nichtwohngebäude Im Städtischen Maßstab, 1. Auflage.; E.ON Energy Research Center, RWTH Aachen University: Aachen, 2022. [Link](https://publications.rwth-aachen.de/record/843586/files/843586.pdf)


## Contact 

Code is maintained by TU Berlin Institute for Digital Networking of Buildings, Energy Supply Systems and Users. [Contact Us](mailto:info@dvg.tu-berlin.de)


## License

[MIT](LICENSE)


## Acknowledgements

`django-teaser` has been developed within public funded projects
and with financial support by BMWK (Federal Ministry for Economics and Climate Action)

<img src="img\bmwk-logo-2022-en-web-transparent.gif" width="200">
