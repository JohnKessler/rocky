// =====================================================================
// Rocky | PART 10 | ball_cage
// Keeps the 24 bearing balls evenly spaced so they cannot bunch up and
// bind the slew ring. Thinner than the race gap, so it floats free.
// PRINT: flat. 0.2mm layers, no supports. PETG preferred.
// =====================================================================
include <rocky_params.scad>
use     <rocky_lib.scad>

cage_t = race_gap - 1.1;

difference() {
    cylinder(d = race_d + ball_d + 5, h = cage_t);
    translate([0, 0, -eps]) cylinder(d = race_d - ball_d - 5, h = cage_t + 2*eps);
    polar(ball_count, race_d/2) translate([0, 0, -eps])
        cylinder(d = ball_d + 0.6, h = cage_t + 2*eps);
}
