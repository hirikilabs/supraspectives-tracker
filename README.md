# supraspectives-tracker

"Spy" satellite tracker

(C) David Pello for Tabakalera Medialab
Using pysattracker library: https://github.com/cubehub/pysattracker

This program is free software under the GNU GPL License:
https://www.gnu.org/licenses/gpl-3.0.html

This program expects a satdata.py file with an array of dictionaries
containing satellite data. Dictionary keys are "name", "tle1", "tle2"
and "freqs" for name, TLE lines and downlink frequencies.
Then it listens in port 7777 for a satellite name from that array, and
tracks it if it's visible. For tracking it connects to rotctld to move
the antenna and to gqrx to adjust frequency.
