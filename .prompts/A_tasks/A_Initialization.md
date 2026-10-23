Port to uv 

Port the plugin to QGIS 4

see https://plugins.qgis.org/docs/migrate-qgis4

do not maintain compatibility with QGIS 3.

You can use the notes in /Users/guilhem/dev/projects/github/qgis_simple_browse/PORTING.md. Update that file if needed (only general notes that can be used for porting other projects)

Create a submodule name fhrgr that will have the code + metadata (similar to /Users/guilhem/dev/projects/github/qgis_simple_browse/). If needed for organization, you may create submodules

Currently the .ui are ransformed into derived .py using a QT tool : this may not actually necessary. You may keep the ui and use it in the reset of the code

Also make a build for building the plugin, using well known package for that. you may use taskipy. Remove the .bat and .sh if not needed 

transform the azure-pipelines.yml to instad use github workflow : to perform the build + upload. 

if you need tests, you may use pytest.