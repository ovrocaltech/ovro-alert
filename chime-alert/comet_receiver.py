# Run this from the command line to setup a comet receiver as a daemon in whatever directory you're in
# From here, all CHIME/FRB VOEvent XML files will be sent to the directory in which the daemon is initiated
twistd -n comet -v --remote=chimefrb.physics.mcgill.ca --print-event --local-ivo=ivo://caltech/comet_broker
