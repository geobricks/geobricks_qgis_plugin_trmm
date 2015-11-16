[![License](http://img.shields.io/:license-GPL2-green.svg)](http://doge.mit-license.org)
[![volkswagen status](https://auchenberg.github.io/volkswagen/volkswargen_ci.svg?v=1)](https://github.com/auchenberg/volkswagen)

# TRMM Data Downloader for QGIS
Download TRMM rainfall estimates data and create thematic maps.

|Plugin|Output|
|------|------|
|![TRMM Data Downloader](images/screenshot.png)|![TRMM Data Downloader](images/screenshot2.png)|

# Data Availability
Daily data are available from January 1st 1998 to July 31st 2015.

# User Interface

* **Username:** your PPS username, please visit [this link](http://registration.pps.eosdis.nasa.gov/registration/) to request an account
* **Password:** your PPS password, please visit [this link](http://registration.pps.eosdis.nasa.gov/registration/) to request an account
* **Data Frequency:** original layers are produced every 3 hours. when the *Daily* options is selected all the layers of each day are aggregated as an average layer
* **From Date:** starting date of the period of interest
* **To Date:** ending date of the period of interest
* **Download Path:** the local folder where the layers must be downloaded. The plugin will generate a subfolder system at this path to organize the layers in order to be divided by year, month and date.
* **Open in QGIS when the download is completed:** when this flag is checked the layers will be added to the QGIS canvas.

# Multilanguage
The plugin is currently available in English and Italian. A project on [Transifex](https://www.transifex.com/) has been added at [this URL](https://www.transifex.com/geobricks/trmm-data-downloader/dashboard/). Anyone can contribute to add more languages.

# Developed with
![IntelliJ](http://www.jetbrains.com/idea/docs/logo_intellij_idea.png)
