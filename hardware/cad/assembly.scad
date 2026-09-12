// =====================================================================
// Rocky | assembly preview
// Imports the exported STLs and places them in the robot's own frame,
// z = 0 at the desk surface. Set pan / tilt to check clearances through
// the full range of motion before you print anything.
//
//   openscad -o preview.png --camera=0,0,130,65,0,25,700 assembly.scad
// =====================================================================
include <rocky_params.scad>
use     <rocky_lib.scad>

pan  = 0;    // degrees, +/- pan_range
tilt = 0;    // degrees, +/- tilt_range
show_balls = true;

S = "../stl/";

color("#3b4252") import(str(S, "base_shell.stl"));
color("#4c566a") translate([0, 0, deck_z]) import(str(S, "base_deck.stl"));

rotate([0, 0, pan]) {
    color("#4c566a") translate([0, 0, turn_z]) import(str(S, "turntable.stl"));
    color("#3b4252") translate([0, 0, yoke_base_z]) import(str(S, "yoke.stl"));

    translate([0, 0, tilt_axis_z]) rotate([tilt, 0, 0]) {
        color("#3b4252") import(str(S, "head_back.stl"));
        color("#d8dee9") import(str(S, "faceplate.stl"));
        color("#2e3440") translate([0, pod_y_front + 1.6, pod_z1 - 13])
            rotate([0, 0, 0]) import(str(S, "pod_window.stl"));
        // the display itself, so the face reads at a glance
        color("#88c0d0") translate([0, head_depth/2 - 2.4 - disp_glass_t/2, 0])
            rotate([-90, 0, 0]) cylinder(d = disp_active_d, h = 0.8, center = true);
    }
}

if (show_balls)
    color("#bf616a") translate([0, 0, race_z + race_gap/2]) race_balls();
