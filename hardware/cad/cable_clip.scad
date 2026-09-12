// =====================================================================
// Rocky | PART 09 | cable_clip
// P-clip for the pan-joint harness. Print four.
// PRINT: flat, as modelled.
// =====================================================================
include <rocky_params.scad>
use     <rocky_lib.scad>

clip_id = harness_d + 1.5;
clip_t  = 2.2;
h       = 7;

difference() {
    union() {
        difference() {
            cylinder(d = clip_id + 2*clip_t, h = h);
            translate([0, 0, -eps]) cylinder(d = clip_id, h = h + 2*eps);
            // opening so the harness can be pressed in
            translate([0, clip_id, h/2]) cube([clip_id * 0.55, clip_id * 2, h + 2], center = true);
        }
        translate([-(clip_id/2 + clip_t + 4), -4.5, 0]) cube([9, 9, h]);
    }
    translate([-(clip_id/2 + clip_t + 4.5), 0, -eps]) cylinder(d = m3_free, h = h + 2*eps);
}
