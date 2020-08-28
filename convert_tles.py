#!/usr/bin/env python3

# (C) David Pello for Tabakalera Medialab
# This program is free software under the GNU GPL License:
# https://www.gnu.org/licenses/gpl-3.0.html
#
# This program creates a satdata.py file with an array of dictionaries
# in the format expected by the tracker program.
# it also creates a TLE txt file for use with Gpredict.


import sys
import csv

SEPARATOR = ";"

input_csv = open(sys.argv[1], "r")
csv_data = csv.reader(input_csv, delimiter=SEPARATOR)

sat_data = "sat_data = [\n"
line_count = 0

for line in csv_data:
    tles = line[0]
    freqs = line[1]
        
    # format data
    sat = "    {\n    'name' : '"
    sat = sat + tles.split("\n")[0] + "', \n"
    sat = sat + "    'tle1' : '"
    sat = sat + tles.split("\n")[1] + "', \n"
    sat = sat + "    'tle2' : '"
    sat = sat + tles.split("\n")[2] + "', \n"
    sat = sat + "    'freqs' : '"
    ls = freqs.split("\n")
    for l in ls:
        sat = sat + l + ';'
    sat = sat + "'\n    }"

    sat_data = sat_data + sat + ", \n"
    line_count = line_count + 1
sat_data = sat_data + "]"
print(sat_data)






