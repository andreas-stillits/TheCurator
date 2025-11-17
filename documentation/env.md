### Reproducibility of environment

For every run, lock down the environment using the command:

$ conda env export --no-builds | grep -v "prefix:" > environment.lock

Canonicalize it to read only dependencies, sort them alphabetically and delete whitespaces/formatting
Include environment variables in canonical form somehow - hidden random seeds, etc. Anything that could change code outcome
Importantly there should be no reference to the users system (path names, builds, etc.)
Stream it into an environment hash.

environment.lock is stored as provenance along with the artifact for future rehydration.

NB: This solution hardcodes conda to be on the user system. Maybe go with pip or uv? In any case: code so that it can be changed modularly in one place


### Regarding external user packages (e.g. FreeCAD)

Require the user to document these: installation, version, modifications/settings, time stamp