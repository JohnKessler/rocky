// =====================================================================
// Rocky | PART 04 | yoke
// Single U-frame bolted to the turntable hub. The left arm takes the
// tilt servo horn, the right arm takes a 623ZZ bearing. Printing it in
// one piece keeps the tilt axis square without any alignment jig.
// Local origin: pan axis, z = 0 at the yoke UNDERSIDE.
// PRINT: lay it on its back (rotate 90 deg about X) so the U sits flat
//        on the bed. 137 x 97 footprint, 26mm tall. No supports.
// =====================================================================
include <rocky_params.scad>
use     <rocky_lib.scad>

arm_in   = head_d/2 + yoke_clear;      // inner face of each arm
arm_out  = arm_in + yoke_arm_t;
piv_z    = tilt_axis_z - yoke_base_z;  // pivot height in local coords
cap_r    = yoke_depth/2;               // rounded arm top
stop_pin_r = 45;                       // tilt hard-stop pin radius
stop_pin_d = 5;

module arm(side) {                      // side = -1 left, +1 right
    hull() {
        translate([side * (arm_in + yoke_arm_t/2), 0, piv_z/2])
            cube([yoke_arm_t, yoke_depth, piv_z], center = true);
        translate([side * (arm_in + yoke_arm_t/2), 0, piv_z])
            rotate([0, 90, 0]) cylinder(d = yoke_depth, h = yoke_arm_t, center = true);
    }
}

module gusset(side) {
    // triangular brace from the crossbar into the arm
    translate([side * arm_in, yoke_depth/2, 0]) rotate([90, 0, 0])
        scale([side < 0 ? -1 : 1, 1, 1])
            linear_extrude(yoke_depth) polygon([[0, 0], [-16, 0], [0, 26]]);
}

module crossbar() {
    translate([0, 0, yoke_bar_h/2])
        cube([2*arm_out, yoke_depth, yoke_bar_h], center = true);
}

module tilt_stop_pin(side) {
    translate([side * arm_in, 0, piv_z - stop_pin_r])
        rotate([0, -side * 90, 0]) cylinder(d = stop_pin_d, h = 3.2);
}

module cable_channel() {
    // groove up the BACK face of the right arm for the pan-joint harness
    translate([arm_in + 0.5, -yoke_depth/2 - eps, -eps])
        cube([yoke_arm_t - 1, 3.5, piv_z - 18], center = false);
}

difference() {
    union() {
        crossbar();
        arm(-1);
        arm(+1);
        gusset(-1);
        gusset(+1);
        tilt_stop_pin(-1);
        tilt_stop_pin(+1);
    }

    // --- bolts down into the turntable hub ------------------------------
    for (x = [-22, 22], y = [-9, 9]) translate([x, y, 0]) {
        translate([0, 0, -eps]) cylinder(d = m3_free, h = yoke_bar_h + 2*eps);
        translate([0, 0, yoke_bar_h - m3_head_h]) cylinder(d = m3_head, h = m3_head_h + eps);
    }

    // --- LEFT arm: tilt servo horn ---------------------------------------
    translate([-arm_in - eps, 0, piv_z]) rotate([0, -90, 0]) {
        cylinder(d = sv_horn_d + slop, h = sv_horn_t + 0.5);      // horn disc
        cylinder(d = sv_shaft_d + 3.0, h = sv_boss_h + 1.0);      // spline boss
        translate([0, 0, -1]) cylinder(d = 11, h = yoke_arm_t + 3); // clearance
        polar(4, 8, 45) translate([0, 0, -1]) cylinder(d = 2.3, h = yoke_arm_t + 3);
    }

    // --- RIGHT arm: 623ZZ bearing ----------------------------------------
    translate([arm_in - eps, 0, piv_z]) rotate([0, 90, 0]) {
        cylinder(d = brg_od - press_slop, h = brg_t + 0.2);        // press fit
        cylinder(d = m3_free, h = yoke_arm_t + 2);                 // pivot screw
        translate([0, 0, yoke_arm_t - m3_head_h])
            cylinder(d = m3_head, h = m3_head_h + 2);              // screw head
    }

    cable_channel();

    // --- cable tie slots on the crossbar ---------------------------------
    for (x = [-34, 34]) translate([x, 0, yoke_bar_h/2])
        for (y = [-5, 5]) translate([0, y, 0])
            cube([4.2, 1.6, yoke_bar_h + 4], center = true);
}
