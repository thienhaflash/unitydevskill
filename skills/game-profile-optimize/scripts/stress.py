#!/usr/bin/env python3
"""Print the scale multiplier the next build will carry (the profile's stressScale.key serialized in its scene), or 1 if the game has none.
usage: stress.py <game> <project folder>"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gameprofile as P

prof = P.load(sys.argv[1])
s = prof.get("stressScale")
value = 1.0
if s:
    try:
        for line in open(os.path.join(sys.argv[2], s["file"])):
            if f"{s['key']}:" in line:
                value = float(line.split(":")[1])
                break
    except OSError:
        pass
print(value)
