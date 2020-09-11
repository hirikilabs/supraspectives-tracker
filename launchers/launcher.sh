#!/bin/bash
tmux \
	new-session "/home/pi/rotor.sh; read" \; \
	new-window "cd /home/pi/quadrature/; ./quadrature_tracker.py ; read" \; \
	new-window "/home/pi/videoserver.sh; read"

