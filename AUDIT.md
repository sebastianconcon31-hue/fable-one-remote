# Vehicle audit: do they work in a game, and are they 1:1?

Every model was put through `modelkit/audit.py`, which loads the delivered glTF
and checks what a game engine will run into, then measured against the
published figures. This is what it found and what changed.

```sh
python3.11 modelkit/audit.py m1151-hmmwv/m1151_hmmwv.glb --json out.json
```

## What the audit checks

- **Scale and placement:** the model stands on its ground reference, is centred
  across, has one root.
- **Wheels at rest:** no tyre inside bodywork, another tyre or a load.
- **Loads at rest:** every pallet clear of the bed and of each other.
- **Every hinge at its limit and half way:** doors, hatches, ramps, tailgates
  checked for new collisions with the rest of the vehicle and with the ground.
- **Steering at full lock** both ways: tyres clear of frame, springs, fenders,
  steps and each other.
- **Guns round the traverse:** each gun at its lowest and highest elevation all
  the way round, and each turret swept round, checked against the hull.
- **Wheels' `radius` against their tyres, tracks' links against their loop.**
- **Off-road geometry** (wheeled vehicles): approach and departure angles (rubber
  mud flaps left out, as the published figures do), ground clearance under the
  axles, and what limits each.

Collisions are counted as triangle pairs that overlap in a pose but not at rest,
named by the meshes involved, so the cause is clear.

## New in every model

- **`limits_by_traverse` on every gun** (and the M977's crane boom): the lowest
  and highest elevation every 5° of the turret's traverse, measured against the
  hull by `modelkit/clearance.py`. A game clamps the gun to it and the gun lifts
  over the engine deck or the load instead of sinking through. The viewer does.
- **Steering locks from the published turning circles** (Ackermann, inner wheel),
  where they're published.
- **The 1:1 table includes the off-road figures** where they're published:
  approach and departure angles, ground clearance.
- **The M977 HEMTT** has the same `control` tags as the others, so one game
  integration drives all eight.

<!-- per-vehicle findings and the final results table follow -->
