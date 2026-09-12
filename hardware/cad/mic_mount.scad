// =====================================================================
// Rocky | PART 08 | mic_mount
// Saddle clamp for the microphone module inside the sensor brow.
// Change mic_body_d to match whatever mic you actually fit.
// PRINT: flat back down. Two M2 screws into the pod's inserts.
// =====================================================================
include <rocky_params.scad>
use     <rocky_lib.scad>

mic_body_d = usb_mic_d;     // 14mm default
plate_t    = 3.0;
hole_pitch = 18.0;          // matches the inserts in head_back's pod
saddle_h   = mic_body_d/2 + 3;

difference() {
    union() {
        translate([0, 0, plate_t/2]) cube([12, hole_pitch + 11, plate_t], center = true);
        translate([0, 0, plate_t - eps]) hull() {
            cube([12, mic_body_d + 5, 0.4], center = true);
            translate([0, 0, saddle_h - 3])
                cube([12, mic_body_d + 5, 0.4], center = true);
        }
    }
    // the mic itself, with a flat-bottomed slot so it prints support-free
    translate([0, 0, plate_t + mic_body_d/2 + 1.0])
        rotate([0, 90, 0]) cylinder(d = mic_body_d + slop, h = 20, center = true);
    translate([0, 0, plate_t + mic_body_d/2 + 1.0])
        cube([20, mic_body_d + slop, mic_body_d], center = true);
    // fixings
    for (y = [-hole_pitch/2, hole_pitch/2]) translate([0, y, -eps]) {
        cylinder(d = m2_free, h = plate_t + 2*eps);
        translate([0, 0, plate_t - 1.6]) cylinder(d = 4.4, h = 2);
    }
}
