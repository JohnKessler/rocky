// =====================================================================
// Rocky | PART 02 | base_deck
// Structural plate that closes the base. Its top face is the fixed half
// of the slewing ring; the pan servo hangs underneath it by its ears.
// Local origin: centre of the deck, z = 0 at the UNDERSIDE.
// PRINT: as modelled, flat on the bed, race groove upward. No supports.
//        4 perimeters / 40% infill - this plate carries the whole head.
// =====================================================================
include <rocky_params.scad>
use     <rocky_lib.scad>

boss_od  = 9.5;
boss_r   = base_d/2 - wall - boss_od/2 - 1.2;   // must match base_shell
stop_r   = 44;                                  // pan hard-stop post radius
stop_w   = 8;
stop_h   = 5;

module deck_plate() {
    dx = sv_shaft_off;
    difference() {
        cylinder(d = deck_od, h = deck_t);

        // --- slewing ring, fixed half (V groove opening upward) ---------
        translate([0, 0, deck_t]) race_groove(dir = -1);

        // --- servo body drops through; ears land on the underside -------
        translate([-dx, 0, deck_t/2])
            cube([sv_body_l + slop, sv_body_w + slop, deck_t + 2*eps], center = true);

        // --- heat-set inserts for the four servo ear screws -------------
        for (x = [-sv_hole_dx/2, sv_hole_dx/2], y = [-sv_hole_dy/2, sv_hole_dy/2])
            translate([-dx + x, y, 4.2]) rotate([180, 0, 0])
                cylinder(d = m25_insert_d, h = 4.2 + eps);

        // --- wiring harness riser ---------------------------------------
        translate([harness_r, 0, -eps]) cylinder(d = harness_d, h = deck_t + 2*eps);

        // --- mounting to the base shell bosses --------------------------
        polar(6, boss_r, 30) {
            translate([0, 0, -eps]) cylinder(d = m3_free, h = deck_t + 2*eps);
            translate([0, 0, deck_t - m3_head_h]) cylinder(d = m3_head, h = m3_head_h + eps);
        }

        // --- airflow, clear of the race and the servo -------------------
        polar(12, 46, 15) translate([0, 0, -eps]) cylinder(d = 6, h = deck_t + 2*eps);
    }
}

// Post that the turntable's arc rib runs into. This caps pan travel
// mechanically, so a bad software limit cannot wring the wiring harness.
module pan_stop() {
    rotate([0, 0, 180]) translate([stop_r, 0, deck_t - eps]) hull() {
        cylinder(d = stop_w, h = stop_h);
        cylinder(d = stop_w + 3, h = 1.5);
    }
}

union() {
    deck_plate();
    pan_stop();
}
