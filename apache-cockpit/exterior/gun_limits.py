"""Measures the M230's elevation limits round its turret's traverse against the
airframe, from the merged aircraft, into exterior/m230_limits.json; merge.mjs
puts them in the gun's extras (`limits_by_traverse`). Run it after merge.mjs,
then run merge.mjs again.

    python exterior/gun_limits.py apache_ah64d.glb"""
import sys
import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "modelkit"))
import bpy
import clearance

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=sys.argv[1])
O = bpy.data.objects
O["M230_Turret"]["control"] = "traverse"
gun = O["M230_Gun"]
gun["control"] = "elevate"
table = clearance.table_for(gun, log=print)
json.dump({"traverse_step": clearance.STEP, "limits_by_traverse": table}, open(os.path.join(HERE, "m230_limits.json"), "w"))
print("wrote", os.path.join(HERE, "m230_limits.json"))
