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

## What it found, vehicle by vehicle

The counts are what the first run of the audit reported and what the last one reports on the delivered file. (The first run
didn't yet check wheels and loads at rest or the off-road angles; those checks found more, listed under each vehicle.)

### M1151A1 HMMWV: 8 issues, now 0
- Four doors swung into the mirrors and each other (their hinges sat inside the door's skin): hinged on the outer skin now.
- Full lock drove the front tyres through the frame: the portal hubs steer with the wheel and the lock is the inner wheel's for the published 25 ft turning radius.
- The rear tyres stood inside the cargo shell (found by the wheels-at-rest check): the shell has open wheel wells.
- The M2 went through the roof and the turret's shields touched its own ring: the gun's slot runs up to the window and the ring is clear.
- Approach, departure and clearance (48.7° / 37.2° / 0.442 m) now match the published 48.8° / 37° / 17.2 in.

### M1A2 SEPv3 Abrams: 4 issues, now 0
- The gun sank into the engine deck at the rear (-9° at traverse 180): the table of limits keeps it above the deck and the fittings.
- The driver's hatch swung into the glacis fittings; the commander's into its own ring: the driver's hatch swings right on a corner post in the glacis' plane, and the hinges sit higher.
- 180 in of track now lies on the ground (the published figure).

### M2A3 Bradley: 3 issues, now 0
- The squad's roof hatch opened down into the hull (its axis was reversed).
- The commander's hatch opened into the CIV's head: the CIV moved back so the hatch stands open clear of it.
- The Bushmaster went through the troop hatch lid at the rear: it has its table of limits.

### M1126 Stryker: 7 issues, now 0
- The first two axles were closer together than the tyres are tall, so their tyres overlapped: the pairs are respaced, and the differentials sit at the published 0.53 m clearance.
- The front tyres couldn't reach the published 52 ft turning circle's lock without going through the hull: the lower hull narrows to its belly and the struts move inboard.
- The troop hatches' hinges ran across their axes, and the RWS's cradle swung into its own yoke: the bridge sits lower and the gun further forward, for the full +60°.
- The remote weapon station swept through the commander's hatch and the roof fittings: it moves 16 cm forward.
- The published approach and departure angles don't exist (only the clearance does); they're measured and reported.

### T-72B3: 3 issues, now 0
- The commander's hatch went into its cupola; the driver's into the glacis armour; the gun into the rear drums and log: the Kord moves to the cupola's edge, the driver's hatch swings back, and the gun has its table of limits.

### HEMTT M977A4 cargo truck: 0 issues in the first run, now 0
The wheels-at-rest and loads-at-rest checks found tyres in the fenders and a boom rest standing through a pallet; the crane
had no slew limits.
- Fenders raised clear of the tyres; the front springs sit under the frame rails and the tie rods are shorter, so the front tyres steer clear.
- The crane's boom has `limits_by_traverse`: how high it has to be to slew over the load. Its rest moves to the side rail; the hook stows under the sheave and hangs plumb when let down (`gravity`).
- The bumper is raised for the 40.8° approach angle (published 41°). The departure angle can't match: Oshkosh quotes 45° for the family, but the published length and the 18 ft body leave the body's back end over 2 m behind the last axle, which gives about 22°.

### HEMTT M978A4 tanker: 10 issues, now 0
- Both cab doors and all four pump doors swung into the trim and the pump enclosure: hinged on their outer skins.
- All four steering wheels drove through the frame and the mirrors at lock: springs under the rails, shorter tie rods, steering locks from the published 100 ft turning circle.
- The suction-hose tubes ran through the rear tyres and the tool box into the third axle.

### M1083A1P2 FMTV: 4 issues, now 0
- Both doors' hinges sat inside the cab shell, and the front tyres at lock went through the frame and the fenders.
- The steps stood in the front tyres and the fuel tank in the rear pair's: moved clear. The spare tyre stood sideways through the cab's back and the front pallet: it faces rearward in the gap.
- The bumpers' heights now give the published 40.2° / 49.2° approach and departure angles.

### AH-64D Apache
- The audit's ground check was the only complaint: the aircraft's origin isn't on the ground (its lowest point is 0.95 m below it), which suits the cockpit viewer.
- The M230 chain gun met the belly from 22° down: its trunnions hang lower, the turret drive is a ring for the breech to swing up into, and the ammunition runs along the belly to a rotary joint and down a feed chute that turns with the turret, so it reaches the full 60° round its ±86° traverse; its measured limits are in its extras and the viewer clamps to them. The swashplate turns with the rotor.

<!-- per-vehicle findings and the final results table follow -->
