#!/bin/sh

. /home/jbroda/Web/water/venv/bin/activate

python3 /home/jbroda/Web/water/check_water.py > /tmp/water_usage.txt
