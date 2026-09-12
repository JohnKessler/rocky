// =====================================================================
// Rocky - shared dimension library
// ---------------------------------------------------------------------
// EVERY printable part in hardware/cad/ includes this file. Change a
// number here and re-run ./build_all.sh to regenerate the whole robot.
//
// UNITS: millimetres, degrees.
//
// !! BEFORE YOU PRINT !!
// Three groups of numbers below are marked MEASURE. They describe parts
// that ship in slightly different revisions from different vendors (the
// round display module especially). Put calipers on your actual parts
// and correct them, then rebuild. Everything else keys off these.
// =====================================================================

// ---------------------------------------------------------------------
// Print / fit tolerances
// ---------------------------------------------------------------------
wall        = 2.6;   // nominal shell wall (3 perimeters at 0.4mm nozzle)
thin_wall   = 1.8;   // internal ribs and webs
slop        = 0.30;  // clearance on sliding / mating fits
press_slop  = 0.05;  // interference fit (bearings, dowels)
eps         = 0.01;  // co-planar face nudge for clean CSG

// Fastener system: M3 with brass heat-set inserts (M3 x 5.0mm OD x 4.0 long)
m3_free     = 3.4;   // M3 clearance hole
m3_head     = 6.2;   // M3 socket-head cap diameter
m3_head_h   = 3.2;
m3_insert_d = 4.2;   // heat-set pilot bore (melt-in; 4.2 for 5.0 OD inserts)
m3_insert_h = 5.0;
m2_free     = 2.4;   // M2 clearance (display + camera + Pi hardware)
m2_insert_d = 3.2;
m25_free    = 2.9;   // M2.5 clearance (Raspberry Pi mounting)
m25_insert_d= 3.6;

// ---------------------------------------------------------------------
// Overall envelope  (design target: well under 1 cubic foot)
// ---------------------------------------------------------------------
base_d        = 162;   // base outer diameter
base_h        = 62;    // base wall height (desk to turntable underside)
base_floor_t  = 3.0;   // bottom plate thickness

leg_count     = 5;     // Rocky's five limbs
leg_reach     = 13;    // how far a leg sticks out past the base wall
leg_h         = 16;

// ---------------------------------------------------------------------
// Slewing ring: 6 mm balls running in a printed race
// ---------------------------------------------------------------------
ball_d        = 6.0;   // 6mm chrome steel balls (or 6mm airsoft BBs in a pinch)
ball_count    = 24;
race_d        = 128;   // pitch circle the ball centres ride on
// A 90-degree V groove, not a semicircle: it is self-supporting in both
// print orientations and it self-centres the balls on two contact lines.
race_groove_d = 2.2;   // groove depth below the race face
// Ball centre sits ball_d/2/sin(45) above the apex, so the two race faces
// must end up 2*(that - groove depth) apart:
race_gap      = 4.1;   // 2 * (6/2/0.7071 - 2.2) = 4.09

turntable_d   = 150;
turntable_t   = 5.0;

// ---------------------------------------------------------------------
// Servos  -- MEASURE. Standard-size hobby servo, the universal footprint.
// (Hitec HS-5485HB / Savox SH-0255MG / MG996R all match this.)
// ---------------------------------------------------------------------
sv_body_l     = 40.6;  // body length
sv_body_w     = 20.0;  // body width
sv_body_h     = 37.0;  // body height, underside to top of case
sv_flange_l   = 54.5;  // tip to tip across the mounting ears
sv_flange_t   = 2.7;   // ear thickness
sv_flange_z   = 27.2;  // underside of body to underside of ears
sv_hole_dx    = 49.5;  // mounting hole spacing along the long axis
sv_hole_dy    = 10.0;  // hole spacing across
sv_hole_d     = 2.6;   // self-tapping M2.5 into plastic
sv_shaft_off  = 10.2;  // body centre to output shaft centre, along length
sv_shaft_d    = 6.0;   // spline boss outer diameter
sv_boss_h     = 4.0;   // spline boss height above case
sv_horn_d     = 22;    // round horn disc diameter
sv_horn_t     = 2.0;

// ---------------------------------------------------------------------
// Micro servo (tilt axis) -- MEASURE. MG90S / HS-5065MG class.
// A standard-size servo will not fit beside the Pi inside the head, and
// with the head trimmed to balance on its tilt axis a micro has ample
// torque: the servo only fights inertia and friction, never gravity.
// ---------------------------------------------------------------------
msv_body_l    = 23.0;
msv_body_w    = 12.2;
msv_body_h    = 22.5;  // underside of body to top of case
msv_flange_l  = 32.2;
msv_flange_t  = 2.5;
msv_flange_z  = 16.0;  // body underside to underside of the ears
msv_hole_dx   = 27.9;  // single pair of ear holes
msv_hole_d    = 2.2;
msv_shaft_off = 5.9;
msv_shaft_d   = 4.8;
msv_boss_h    = 4.0;
msv_horn_d    = 20.0;
msv_horn_t    = 1.8;

// ---------------------------------------------------------------------
// Sensor brow: the camera pod above the face. Free-standing, so the
// camera board is not fighting the display for room inside the face.
// Its underside is a 45 degree ramp, which keeps it support-free.
// ---------------------------------------------------------------------
pod_w         = 46;    // across X: camera alongside the microphone
pod_z0        = 68;    // where the ramp leaves the head shell
pod_z1        = 100;    // top of the pod
pod_y_front   = 26;    // front face of the pod
pod_wall      = 2.4;

// ---------------------------------------------------------------------
// Round display  -- MEASURE. Waveshare 4" DSI Round, 720x720.
// disp_glass_d : outer diameter of the cover glass
// disp_active_d: the lit circle (4" diagonal on a round panel = the dia)
// disp_pcb_*   : the carrier PCB behind the glass
// ---------------------------------------------------------------------
disp_glass_d   = 110.0;
disp_active_d  = 101.6;
disp_glass_t   = 2.2;
disp_pcb_w     = 91.0;
disp_pcb_h     = 91.0;
disp_pcb_t     = 1.6;
disp_stack_t   = 11.5; // glass front face to deepest component on the back
disp_hole_dx   = 81.0; // carrier PCB mounting holes (M2.5, 4 off)
disp_hole_dy   = 81.0;
disp_bezel_ov  = 3.0;  // how far the printed bezel laps over the glass

// ---------------------------------------------------------------------
// Head
// ---------------------------------------------------------------------
y_split       = 21;    // faceplate takes over forward of this plane
rear_ch       = 8;     // 45 degree rear chamfer run
front_ch      = 2;     // chamfer breaking the faceplate rim
head_d        = 140;
head_depth    = 62;
head_face_tilt= 6;     // face tips back this many degrees: reads as "attentive"
// Head coordinate convention: Rocky faces +Y. The face is a circle of
// head_d in the XZ plane; head_depth runs along Y; the tilt axis runs
// along X through the head's centre of mass.
tilt_axis_z   = 170;   // height of the tilt pivot above the desk
yoke_arm_t    = 7.0;   // arm plate thickness, along X
yoke_depth    = 26.0;  // arm / crossbar depth, along Y
yoke_bar_h    = 12.0;  // crossbar height
yoke_clear    = 1.6;   // air gap between head cheek and yoke arm
tilt_range    = 26;    // +/- degrees of mechanical travel
pan_range     = 100;   // +/- degrees; hard stop in the base limits it

// Tilt pivot hardware: 623ZZ bearing (3 x 10 x 4) on the idler side
brg_od        = 10.0;
brg_id        = 3.0;
brg_t         = 4.0;

// ---------------------------------------------------------------------
// Camera  -- Raspberry Pi Camera Module 3 (Wide). 25 x 24 mm PCB.
// ---------------------------------------------------------------------
cam_pcb_w     = 25.0;
cam_pcb_h     = 24.0;
cam_pcb_t     = 1.1;
cam_hole_dx   = 21.0;
cam_hole_dy   = 12.5;
cam_lens_d    = 15.0;  // lens barrel clearance
cam_lens_h    = 6.5;
cam_ffc_w     = 16.0;

// ---------------------------------------------------------------------
// Raspberry Pi 5 + Active Cooler
// ---------------------------------------------------------------------
pi_w          = 85.0;
pi_h          = 56.0;
pi_hole_inset = 3.5;
pi_hole_dx    = 58.0;
pi_hole_dy    = 49.0;
pi_pcb_t      = 1.4;
pi_stack_h    = 32.0;  // PCB bottom to top of the Active Cooler fan
pi_standoff   = 5.0;   // clearance under the board for solder tails

// ---------------------------------------------------------------------
// Speaker: 40 mm round, 4 ohm 3 W
// ---------------------------------------------------------------------
// Mounted in the floor of the base, firing downward; the leg clearance
// under the base acts as the slot load. Keeps it out of the head entirely.
spk_d         = 40.0;  // frame outer diameter
spk_depth     = 5.5;   // frame thickness (magnet stands proud above this)
spk_magnet_h  = 14.0;  // total height including the magnet
spk_hole_pcd  = 46.0;  // mounting hole pitch circle
spk_cone_d    = 34.0;  // radiating area to leave clear

// ---------------------------------------------------------------------
// Misc hardware
// ---------------------------------------------------------------------
barrel_d      = 8.2;   // 2.1mm DC barrel jack panel cutout
switch_d      = 12.2;  // 12mm latching rocker/pushbutton cutout
harness_d     = 16.0;  // bore the pan-joint wire bundle passes through
harness_r     = 30.0;  // radius from pan axis where the harness crosses
usb_mic_d     = 14.0;  // USB gooseneck/stick mic body

// ---------------------------------------------------------------------
// Cosmetics
// ---------------------------------------------------------------------
vent_w        = 3.0;
vent_gap      = 3.4;
carapace_ribs = 24;    // ridge count around the head shell
rib_depth     = 0.9;

$fn = 96;

// ---------------------------------------------------------------------
// Derived heights -- do not edit directly, these fall out of the above.
// ---------------------------------------------------------------------
deck_t         = 6.0;                     // race deck plate thickness
deck_od        = base_d - 2*wall - 1.0;   // drops inside the base wall
race_z         = base_h - 6;              // fixed race face, z from base floor
deck_z         = race_z - deck_t;         // underside of the deck
turn_z         = race_z + race_gap;       // turntable underside
// The pan servo hangs from the underside of the deck by its mounting ears,
// so its height is fixed by the deck rather than by a separate bracket.
pan_servo_z    = deck_z - sv_flange_z;    // servo body underside, from base floor
boss_top_z     = pan_servo_z + sv_body_h + sv_boss_h;  // top of the spline boss
hub_d          = 56;                      // turntable centre hub, houses the horn
hub_h          = 10;                      // hub height above the turntable face
yoke_base_z    = turn_z + turntable_t + hub_h;   // underside of the yoke
yoke_rise      = tilt_axis_z - yoke_base_z;

// PCA9685 16-channel servo driver breakout (Adafruit 815 footprint)
pca_hole_dx    = 57.9;
pca_hole_dy    = 20.3;
// Pololu step-down regulator boards (2 mounting holes)
buck_hole_dx   = 38.1;   // 1.5in between the two mounting holes

// Camera Module 3 FPC tail width, used only by the component stand-ins.
cam_ffc_w_render = 16.0;
