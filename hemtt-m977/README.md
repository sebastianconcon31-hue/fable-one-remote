# HEMTT M977A4 cargo truck

A game-ready US Army HEMTT M977A4: the 8×8 Heavy Expanded Mobility Tactical Truck with its 18 ft cargo body and rear material-handling crane, carrying eight pallets of resources. Outside only, at 1:1 scale.

![The HEMTT on the pad](docs/hero.jpg)

| Side | Rear and crane |
| --- | --- |
| ![Side view](docs/side.jpg) | ![Rear three-quarter view with the crane](docs/rear.jpg) |
| **Cab** | **Running gear** |
| ![Cab, grille, bumper and winch](docs/cab.jpg) | ![16.00R20 XZL tyres and the front axles](docs/wheels.jpg) |

## Files

| File | What it is |
| --- | --- |
| `hemtt_m977a4.glb` | **The truck.** Textured, with every wheel, the steering, the doors, the crane and each pallet load its own node. TBD |
| `hemtt_m977a4_web.glb` | A lighter copy with half-size WebP textures, for browsers and phones. TBD |
| `hemtt_viewer.html` | Opens the truck in your browser with a double-click: orbit round it, open the doors, drive the wheels, work the crane, unload the cargo. |
| `measurements.json` | The finished model measured against the published dimensions. |
| `build.py`, `truck.py`, `markings.py`, `m977.py` | The Blender build (it uses the shared `../modelkit`). |

## Scale: 1:1 with the real truck

Built to Oshkosh's published M977A4 figures; `build.py` measures the finished geometry against them on every build:

TBD

- **Units and axes:** metres, glTF axes. +Y is up, +Z points to the front, and +X is the driver's left.
- **Origin:** on the ground, on the centreline, midway between the front and rear axle pairs. The tyres stand on y = 0.

## Moving parts

Each is its own node, pivoted where the real part turns, and its glTF extras say how it moves (`drive`, `axis`, `limits`):

| Node | Moves |
| --- | --- |
| `Wheel_{1-4}_{Left,Right}` | spin about local X; + rolls forward (radius 0.62 m) |
| `Steer_{1,2}_{Left,Right}` | steer about local Y; + turns left. Axle 1 up to ±0.62 rad, axle 2 up to ±0.42 rad. The wheels sit inside these nodes. |
| `Door_Left`, `Door_Right` | swing about `axis` on the front hinge; + opens (up to 1.4 rad) |
| `Crane` | slews about local Y |
| `Crane_Boom` | luffs about local X; − raises it (to −1.3 rad) |
| `Crane_Boom_Extension` | telescopes along local +Z, up to 2.3 m |
| `Crane_Hook` | hangs from the boom tip; lower it along local −Y |
| `Cargo_Pallet_1` … `_8` | the resources, one pallet load each: drums of fuel, ammunition cans, crates and rations |
| `Spare_Tire` | on its carrier behind the cab |
| `Light_*` | head, turn, tail, reverse, clearance lights and the amber beacon. Their lens materials `Light_White`, `Light_Amber` and `Light_Red` are emissive, so scale the emission to switch them. |

## Look

- **Paint:** CARC green with the panel seams and bolt rows of its cab, engine bay and body.
- **Stencils:** a black registration number, the CTIS tyre pressures, the weight class, JP-8 and NO SMOKING, the crane's load chart and DANGER, and bumper codes.
- **Hazard stripes:** yellow and black on both bumpers and the crane boom.
- **Weathering:** mud thrown up by every wheel, dust settling low down and on top, exhaust soot round the stack, grime in the corners and worn edges.
- **Textures:** the look is built procedurally in Blender, then baked into standard PBR textures:

| Texture set | Size | Covers |
| --- | --- | --- |
| `HEMTT_Paint_Front` | 4096² | Cab, doors, front end, fenders, engine bay, wheels' paint |
| `HEMTT_Paint_Back` | 4096² | Cargo body, rear end, crane, fuel tank and boxes |
| `HEMTT_Chassis` | 2048² | Frame, axles and springs, tyres, exhaust, steel |
| `HEMTT_Cargo` | 2048² | Pallets, drums, ammunition cans, crates, straps, ration cases |

Each set has a base colour, an occlusion-roughness-metallic map and a normal map. Glass, mirrors and light lenses use plain material values.

## Rebuilding

```sh
pip install bpy==5.0.1 pillow                 # once, with Python 3.11
python3.11 hemtt-m977/build.py --glb hemtt-m977/hemtt_m977a4.glb --textures 4096
python3.11 hemtt-m977/build.py --preview out --lookdev   # quick look at the paint, without baking
```

## Accuracy

The truck is modelled on the M977A4 from its published figures and general knowledge of the vehicle, not from manufacturer drawings.

- **Published dimensions:** the overall length, width and height, wheelbase, track, tyre size and cargo body length match exactly.
- **Estimated:** the spacing within each axle pair, the cab and body heights, and the layout behind the cab.
- **Markings:** plausible but made up; the registration and unit codes aren't a real vehicle's.
