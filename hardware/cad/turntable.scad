// =====================================================================
// Rocky | PART 03 | turntable
// Rotating half of the slewing ring. Bolts to the pan servo horn from
// below and carries the yoke on its hub.
// Local origin: pan axis, z = 0 at the UNDERSIDE (the race face).
// PRINT: as modelled, race face down. The V groove self-supports at 45
//        degrees, so no supports are needed. 4 perimeters, 40% infill.
// =====================================================================
include <rocky_params.scad>
use     <rocky_lib.scad>

horn_recess_z = boss_top_z - turn_z;          // how far the spline boss intrudes
stop_slot_r   = 44;
stop_slot_w   = 11;                           // deck post is 8mm across
// The slot's arc IS the travel, not the material left over between its ends:
// this was 360 - 2*pan_range - 9 = 151 degrees, which let the post move only
// +/-77 while the software limit is +/-100, so every large pan command drove a
// standard servo into a printed post and stalled it. The post's 1.5 mm of
// side clearance adds about 2 degrees at each end, so a 2*pan_range + 9 arc
// catches at roughly +/-106 - outside the software limit, the same way round
// as the tilt stop.
stop_span     = 2*pan_range + 9;              // +/- pan_range, plus a margin

module stop_slot() {
    // arc slot the deck's stop post rides in; its ends are the hard stops
    rotate([0, 0, 180 - stop_span/2])
        for (i = [0 : 63])
            rotate([0, 0, i * stop_span / 63])
                translate([stop_slot_r, 0, -eps])
                    cylinder(d = stop_slot_w, h = turntable_t + 2*eps, $fn = 16);
}

module body() {
    union() {
        cylinder(d = turntable_d, h = turntable_t);
        translate([0, 0, turntable_t - eps]) cylinder(d = hub_d, h = hub_h + eps);
        // gentle fillet where the hub meets the plate
        translate([0, 0, turntable_t - eps])
            cylinder(d1 = hub_d + 5, d2 = hub_d, h = 2.5);
    }
}

difference() {
    body();

    // --- slewing ring, rotating half (V groove opening downward) --------
    race_groove(dir = +1);

    // --- servo horn pocket ----------------------------------------------
    // spline boss first, then the round horn disc it sits on
    translate([0, 0, -eps]) cylinder(d = sv_shaft_d + 3.0, h = horn_recess_z + eps);
    translate([0, 0, horn_recess_z - eps])
        cylinder(d = sv_horn_d + slop, h = sv_horn_t + 0.4 + eps);
    // driver access to the horn's centre retaining screw
    cylinder(d = 6.5, h = turntable_t + hub_h + 1);
    // four screws pulling the horn up into the hub
    polar(4, 8, 45) translate([0, 0, horn_recess_z + sv_horn_t])
        cylinder(d = 2.2, h = 9);

    // --- yoke mounting, from the hub top --------------------------------
    for (x = [-22, 22], y = [-9, 9])
        translate([x, y, turntable_t + hub_h - m3_insert_h]) heatset();

    // --- wiring harness riser, rotates with the head --------------------
    translate([harness_r, 0, -eps]) cylinder(d = harness_d, h = turntable_t + 2*eps);

    // --- mechanical pan limit -------------------------------------------
    stop_slot();

    // --- lighten the disc, and let air out of the base -------------------
    polar(6, 34, 30) translate([0, 0, -eps]) cylinder(d = 11, h = turntable_t + 2*eps);
}
