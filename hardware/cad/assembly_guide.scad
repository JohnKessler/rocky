// =====================================================================
// Rocky | assembly figures
//
// Renders the pictures used in docs/ASSEMBLY.md. One file so that every
// figure is drawn from the same part positions - if a dimension changes
// in rocky_params.scad, every figure moves with it.
//
//   openscad -o out.png -D 'VIEW="exploded"' assembly_guide.scad
//
// render_figures.sh drives it for all views.
// =====================================================================
include <rocky_params.scad>
use     <rocky_lib.scad>
use     <components.scad>

VIEW    = "exploded";
EXPLODE = 1.0;        // 0 is fully assembled
SHOW_COMPONENTS = true;
CAM_RX  = 62;         // must match the camera the shell script uses,
CAM_RZ  = 205;        // so the labels face the viewer
LABEL_D = 150;        // callout length, scaled per figure so labels stay in frame

S = "../stl/";

// Printed parts keep the colours used in the rest of the documentation.
C_SHELL = "#3b4252";
C_DECK  = "#4c566a";
C_FACE  = "#d8dee9";
C_BALL  = "#bf616a";

// ---------------------------------------------------------------------
// labels
// ---------------------------------------------------------------------

module billboard(txt, size = 7, colour = "#e5e9f0") {
    color(colour) rotate([0, 0, CAM_RZ]) rotate([CAM_RX, 0, 0])
        linear_extrude(0.8)
            text(txt, size = size, font = "Liberation Sans:style=Bold",
                 halign = "left", valign = "center");
}

// The world direction that appears to run left-to-right on screen, given
// the camera's Z rotation. Callouts travel along it so their leader lines
// look horizontal in the rendered image rather than diving into the page.
SCREEN_X = [cos(CAM_RZ), sin(CAM_RZ), 0];

function screen_offset(d) = [SCREEN_X[0] * d, SCREEN_X[1] * d, 0];

// A numbered callout with a leader line back to the part it names.
//
// Only the NUMBER is drawn. Long labels ran off the edge of every figure at
// small scales, and a number plus a legend is how technical illustration
// solves that anyway. The caption text is echoed instead, and the render
// script captures it into a legend file beside the image - so the figure and
// its caption come from this one place and cannot drift apart.
//
// Positive `side` puts the number to the right of the part, negative to left.
module callout(n, txt, at, side = 1, rise = 0, size = 0) {
    echo(str("LEGEND|", n, "|", txt));
    d = side * LABEL_D;
    r = LABEL_D * 0.105;                       // number disc scales with the figure
    tip = [at[0] + SCREEN_X[0] * d, at[1] + SCREEN_X[1] * d, at[2] + rise];
    color("#88c0d0") hull() {
        translate(at) sphere(d = r * 0.36, $fn = 8);
        translate(tip) sphere(d = r * 0.22, $fn = 8);
    }
    color("#88c0d0") translate(at) sphere(d = r * 0.52, $fn = 14);
    translate(tip) rotate([0, 0, CAM_RZ]) rotate([CAM_RX, 0, 0]) {
        color("#88c0d0") cylinder(r = r, h = 0.6, $fn = 32);
        translate([0, 0, 0.6]) color("#111820") linear_extrude(0.6)
            text(str(n), size = r * 1.25, font = "Liberation Sans:style=Bold",
                 halign = "center", valign = "center");
    }
}

module title(txt, at = [0, 0, 0]) {
    translate(at) rotate([0, 0, CAM_RZ]) rotate([CAM_RX, 0, 0])
        color("#eceff4") linear_extrude(0.8)
            text(txt, size = 15, font = "Liberation Sans:style=Bold",
                 halign = "center", valign = "center");
}

// ---------------------------------------------------------------------
// printed parts, each at its assembled height plus an explode offset
// ---------------------------------------------------------------------

function ex(d) = d * EXPLODE;

module p_base()      { color(C_SHELL) import(str(S, "base_shell.stl")); }
module p_deck()      { color(C_DECK)  translate([0,0,deck_z + ex(46)])  import(str(S, "base_deck.stl")); }
module p_turntable() { color(C_DECK)  translate([0,0,turn_z + ex(96)]) import(str(S, "turntable.stl")); }
module p_cage()      { color("#5e81ac") translate([0,0,race_z - 0.5 + ex(74)]) import(str(S, "ball_cage.stl")); }
module p_balls()     { color(C_BALL)  translate([0,0,race_z + race_gap/2 + ex(74)]) race_balls(); }
module p_yoke()      { color(C_SHELL) translate([0,0,yoke_base_z + ex(132)]) import(str(S, "yoke.stl")); }

module head_group(tilt = 0) {
    translate([0, 0, tilt_axis_z + ex(178)]) rotate([tilt, 0, 0]) children();
}

module p_head_back()  { color(C_SHELL) import(str(S, "head_back.stl")); }
module p_faceplate()  { color(C_FACE)  translate([0, ex(62), 0]) import(str(S, "faceplate.stl")); }
module p_pod_window() { color("#2e3440") translate([0, pod_y_front + 1.6 + ex(86), pod_z1 - 13]) import(str(S, "pod_window.stl")); }

// ---------------------------------------------------------------------
// bought-in parts, in their real places
// ---------------------------------------------------------------------

module c_base_electronics() {
    // speaker, magnet up, firing down through the floor grille
    translate([0, 0, base_floor_t]) speaker_40mm();
    translate([0, -46, base_floor_t + 6]) pca9685();
    translate([-23, 36, base_floor_t + 6]) buck_regulator();
    translate([25, 36, base_floor_t + 6]) buck_regulator();
}

module c_pan_servo() {
    translate([0, 0, pan_servo_z]) standard_servo();
    translate([0, 0, boss_top_z - sv_horn_t]) servo_horn();
}

module c_head_internals() {
    // Pi 5, portrait, component side forward, shifted +X to clear the tilt servo
    translate([-10, -22, 0]) rotate([-90, 0, 0]) rotate([0, 0, 90]) raspberry_pi_5();
    // tilt servo on the left cheek, shaft outward through the wall
    translate([-(head_d/2 - wall), 0, 0]) rotate([0, -90, 0]) rotate([0, 0, -90]) micro_servo();
    // camera and microphone in the sensor brow
    translate([-7, 18, 84]) rotate([-90, 0, 0]) camera_module_3();
    translate([mic_x0, mic_y0, mic_z0]) usb_microphone();
    // I2S amplifier on the rear wall, above the Pi
    translate([0, -22, 47]) rotate([-90, 0, 0]) max98357a();
    // the pivot bearing on the right cheek
    translate([head_d/2 + yoke_clear + 1, 0, 0]) rotate([0, 90, 0]) bearing_623();
}

module c_display() {
    translate([0, head_depth/2 - 2.4, 0]) rotate([-90, 0, 0]) round_display();
}

// ---------------------------------------------------------------------
// figures
// ---------------------------------------------------------------------

module fig_exploded() {
    callout(1, "base_shell", [0, 0, 34], -1);
    callout(2, "base electronics", [0, -30, 12], 1, 16);
    callout(3, "pan servo", [0, 0, pan_servo_z + 20], 1, -36);
    callout(4, "base_deck (fixed race)", [0, 0, deck_z + ex(46) + 3], -1);
    callout(5, "ball cage + 24 balls", [60, 0, race_z + ex(74)], -1, -6);
    callout(6, "turntable (rotating race)", [0, 0, turn_z + ex(96) + 8], -1, 16);
    callout(7, "yoke", [66, 0, yoke_base_z + ex(132) + 40], 1);
    callout(8, "head_back + Pi + tilt servo", [0, -40, tilt_axis_z + ex(178)], 1, 46);
    callout(9, "display + faceplate", [0, 40, tilt_axis_z + ex(178) - 20], -1, -8);

    p_base();
    if (SHOW_COMPONENTS) { c_base_electronics(); c_pan_servo(); }
    p_deck();
    p_cage();
    p_balls();
    p_turntable();
    p_yoke();
    head_group() {
        p_head_back();
        if (SHOW_COMPONENTS) { c_head_internals(); c_display(); }
        p_faceplate();
        p_pod_window();
    }
}

module fig_assembled(tilt = 0, pan = 0) {
    p_base();
    p_deck();
    p_balls();
    rotate([0, 0, pan]) {
        p_turntable();
        p_yoke();
        head_group(tilt) { p_head_back(); p_faceplate(); p_pod_window(); }
    }
}

// One point along the harness service loop: a slack helix that winds and
// unwinds as the head turns. Functions cannot be declared inside a for body
// in OpenSCAD, so it lives here.
function harness_point(t) =
    let (a = 40 + t * 640, rr = 34 - 6 * sin(t * 360))
        [rr * cos(a), rr * sin(a), 16 + t * 30];

// --- stage figures, one per step in docs/ASSEMBLY.md ------------------

module fig_stage2() {                       // base electronics, looking in
    callout(1, "speaker, magnet up", [0, 0, 14], -1, 0);
    callout(2, "PCA9685 servo driver", [0, -46, 12], 1, 0);
    callout(3, "5.1V regulator, feeds the Pi", [-23, 36, 14], -1, 0);
    callout(4, "6.0V regulator, feeds the servos", [25, 36, 14], 1, 0);
    p_base();
    c_base_electronics();
}

module fig_stage3() {                       // pan servo hung from the deck
    callout(1, "servo ears bolt UP into the deck", [-18, 0, deck_z - 4], -1, 16);
    callout(2, "body passes through the cutout", [-10, 0, 40], 1, -12);
    callout(3, "spline boss, horn goes here", [0, 0, boss_top_z], 1, 26);
    difference() {
        color(C_DECK) translate([0, 0, deck_z]) import(str(S, "base_deck.stl"));
        // half section, so you can see the servo hanging underneath
        translate([0, 120, deck_z + 6]) cube([400, 200, 40], center = true);
    }
    c_pan_servo();
}

module fig_stage4() {                       // the slew ring
    callout(1, "grease the V groove, thinly", [59, 0, race_z], -1, 22);
    callout(2, "cage sets the ball spacing", [-59, 0, race_z + ex(30)], -1, -6);
    callout(3, "24 x 6mm steel balls", [0, -59, race_z + ex(30)], 1, 16);
    callout(4, "horn screws up into the hub", [0, 0, turn_z + ex(60)], 1, 30);
    color(C_DECK) translate([0, 0, deck_z]) import(str(S, "base_deck.stl"));
    p_cage();
    p_balls();
    color(C_DECK) translate([0, 0, turn_z + ex(60)]) import(str(S, "turntable.stl"));
    translate([0, 0, turn_z + ex(60) - 3]) servo_horn();
}

module fig_stage5() {                       // yoke onto the turntable
    callout(1, "4 x M3 x 16 into the hub", [0, 0, yoke_base_z + 8], 1, 26);
    callout(2, "623ZZ bearing, press fit", [head_d/2 + yoke_clear + 4, 0, tilt_axis_z], 1);
    callout(3, "tilt servo horn fits here", [-(head_d/2 + yoke_clear + 4), 0, tilt_axis_z], -1);
    color(C_DECK) translate([0, 0, turn_z]) import(str(S, "turntable.stl"));
    color(C_SHELL) translate([0, 0, yoke_base_z]) import(str(S, "yoke.stl"));
    translate([head_d/2 + yoke_clear + 1, 0, tilt_axis_z]) rotate([0, 90, 0]) bearing_623();
}

module fig_stage6() {                       // head internals
    callout(1, "Pi 5, portrait, offset right", [6, -18, 0], 1, 34);
    callout(2, "tilt servo, shaft through the cheek", [-52, 0, -6], -1, -20);
    callout(3, "camera in the brow", [-7, 18, 84], -1, 2);
    callout(4, "microphone", [15, 10, 84], 1, 6);
    callout(5, "trim weights balance the head", [0, -26, -50], 1, -26);
    callout(6, "I2S amplifier", [0, -22, 47], -1, 62);
    p_head_back();
    c_head_internals();
}

module fig_stage7() {                       // faceplate and display
    callout(1, "display drops in from behind", [0, 6, 30], -1, 30);
    callout(2, "4 x M2.5 into the faceplate", [40, 10, 40], -1, 46);
    callout(3, "3 x M3 through the rim", [58, 26, -20], -1, -62);
    translate([0, ex(55), 0]) { color(C_FACE) import(str(S, "faceplate.stl")); }
    translate([0, ex(20), 0]) c_display();
    p_head_back();
}

module fig_harness() {                      // the pan-joint wiring
    callout(1, "11 conductors cross the joint", [harness_r, 0, turn_z + 24], 1, 30);
    callout(2, "service loop, about 60mm slack", harness_point(0.12), -1, 0);
    callout(3, "16mm bore at 30mm radius", [harness_r, 0, turn_z], -1, 34);
    difference() {
        union() {
            p_base();
            color(C_DECK) translate([0, 0, deck_z]) import(str(S, "base_deck.stl"));
            color(C_DECK) translate([0, 0, turn_z]) import(str(S, "turntable.stl"));
        }
        // a quarter cut, not a half: enough to see the service loop while
        // the base still reads as a closed shell
        translate([-100, 0, -100]) cube([200, 200, 400]);
    }
    // The service loop: a slack helix in the base that winds and unwinds as
    // the head turns, rising through the bore in the turntable.
    steps = 90;
    for (i = [0 : steps - 1])
        wire(harness_point(i / steps), harness_point((i + 1) / steps), 4.5, "#d08770");
    wire([harness_r * cos(40), harness_r * sin(40), 46],
         [harness_r, 0, turn_z + 34], 4.5, "#d08770");
}

if      (VIEW == "exploded")  fig_exploded();
else if (VIEW == "assembled") fig_assembled();
else if (VIEW == "stage2")    fig_stage2();
else if (VIEW == "stage3")    fig_stage3();
else if (VIEW == "stage4")    fig_stage4();
else if (VIEW == "stage5")    fig_stage5();
else if (VIEW == "stage6")    fig_stage6();
else if (VIEW == "stage7")    fig_stage7();
else if (VIEW == "harness")   fig_harness();
else                          fig_exploded();
