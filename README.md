[![Travis CI](https://travis-ci.org/PyBossa/pybossa.png?branch=master)](https://travis-ci.org/#!/PyBossa/pybossa)  [![Coverage Status](https://coveralls.io/repos/PyBossa/pybossa/badge.png)](https://coveralls.io/r/PyBossa/pybossa?branch=master)

![GeoTagX](http://geotagx.org/static/img/default_logo.png) ![PyBossa] (http://pybossa.com/assets/img/pybossa_badge_light_small.png)

[GeotagX] (http://geotagx.org/) is built on PyBossa. PyBossa is an open source platform for crowdsourcing volunteer tasks that require human cognition, knowledge or intelligence. GeoTagX uses PyBossa for crowdsourcing analyses of media emerging from disasters, leading to datasets for humanitarian response efforts.  

[GeotagX] (http://geotagx.org/) is led by [UNITAR-UNOSAT], (http://www.unitar.org/unosat/) based inside [CERN] (http://home.web.cern.ch/). It is part of [Citizen Cyberlab] (http://citizencyberlab.eu/), a collection of citizen science projects funded by the European Commission 7th Framework Programme for Research and Technological Development. Within Citizen Cyberlab,  GeoTagX is unique for its humanitarian focus. 

We're at an early beta testing stage. You can help as a volunteer by [trying out analysing some photos with our prototype modules] (http://geotagx.org/analyse_photos) and giving us feedback about bugs or suggestions in the [issues section here] (https://github.com/geotagx/pybossa/issues). You can also [email your feedback] (mailto: cobi.smith@unitar.org) rather than share on GitHub if you prefer, though our first preference is the issues section so other volunteers to learn from your experience. 

![GeoTagX](http://geotagx.org/static/img/default_logo.png) 
![Citizen Cyberlab] (http://geotagx.org/static/img/footer/CCLlogo.jpg) 
![UNOSAT] (http://geotagx.org/static/img/footer/logo_unitar.png) 
![FP7] (http://geotagx.org/static/img/footer/FP7-logo%20coulor.jpg) 
![Citizen Cyberscience Centre] (http://geotagx.org/static/img/footer/image_gallery.jpg)   

PyBossa was inspired by the [BOSSA](http://bossa.berkeley.edu/) crowdsourcing engine but is written in
python (hence the name!). It can be used for any distributed tasks project
but was initially developed to help scientists and other researchers
crowd-source human problem-solving skills!

# Installing and Upgrading

**Important: if you are updating a server, please, be sure to check the
Database Migration scripts, as new changes could introduce new tables,
columns, etc, in the DB model. See the [Migration Section](http://docs.pybossa.com/en/latest/install.html#migrating-the-database-table-structure) from the
documentation**

See [installation instructions](http://docs.pybossa.com/en/latest/install.html).

# Running Tests

Just run the following command:

```
  nosetests test/
```

# Useful Links

* [Documentation](http://docs.pybossa.com/)
* [Mailing List](http://lists.okfn.org/mailman/listinfo/open-science-dev)

# Contributing

If you want to contribute to the project, please, check the
[CONTRIBUTING file](CONTRIBUTING.md).

It has the instructions to become a contributor.

## Authors

* [Daniel Lombraña González](http://daniellombrana.es) - [Citizen Cyberscience Centre](http://citizencyberscience.net/), [Shuttleworth Fellow](http://www.shuttleworthfoundation.org/fellows/daniel-lombrana/)
* Rufus Pollock - [Open Knowledge Foundation](http://okfn.org/)

* [FontAwesome fonts](http://fortawesome.github.com/Font-Awesome/)
* [GeoLite data by MaxMind](http://www.maxmind.com)
* 

![Shuttleworth Foundation Funded](http://pybossa.com/assets/img/shuttleworth-funded.png)

## Copyright / License

Copyright 2014 SF Isle of Man Limited. 

Source Code License: The GNU Affero General Public License, either version 3 of the License
or (at your option) any later version. (see COPYING file)

The GNU Affero General Public License is a free, copyleft license for
software and other kinds of works, specifically designed to ensure
cooperation with the community in the case of network server software.

Documentation and media is under a Creative Commons Attribution License version
3.
