// =====================================================================
// Rocky | PART 01 | base_shell
// The load-bearing tub: floor, outer wall, five legs, panel cutouts,
// ballast trough, and the bosses that carry the race deck.
// PRINT: as modelled, floor down. No supports needed.
// =====================================================================
include <rocky_params.scad>
use     <rocky_lib.scad>

boss_od     = 9.5;
boss_r      = base_d/2 - wall - boss_od/2 - 1.2;   // boss centres
boss_n      = 6;

module legs() {
    polar(leg_count, 0, 90) {
        hull() {
            translate([base_d/2 - 8, 0, 0]) cylinder(d = 26, h = leg_h - 4);
            translate([base_d/2 + leg_reach - 11, 0, 0]) cylinder(d = 20, h = 2.5);
            // 45-degree shoulder back into the wall so nothing overhangs
            translate([base_d/2 - 16, 0, 0]) cylinder(d = 30, h = leg_h + 6);
        }
    }
}

module shell_solid() {
    union() {
        cylinder(d = base_d, h = base_h);
        legs();
    }
}

module shell_hollow() {
    // main cavity (open topped - no trapped voids anywhere in this part)
    translate([0, 0, base_floor_t])
        cylinder(d = base_d - 2*wall, h = base_h);
}

module deck_bosses() {
    polar(boss_n, boss_r, 30) difference() {
        union() {
            cylinder(d = boss_od, h = deck_z);
            // web tying the boss back to the wall, keeps it from wobbling
            translate([0, -thin_wall/2, 0])
                cube([boss_od/2 + 2.2, thin_wall, deck_z]);
        }
        translate([0, 0, deck_z - m3_insert_h]) heatset();
    }
}

// Down-firing speaker: seats against the inside of the floor on the base
// axis, radiating through a grille into the gap the legs hold open.
module speaker_mount() {
    translate([0, 0, base_floor_t - eps])
        difference() {
            cylinder(d = spk_hole_pcd + 9, h = 3.2);
            translate([0, 0, -eps]) cylinder(d = spk_d + slop, h = 3.2 + 2*eps);
        }
    polar(4, spk_hole_pcd/2, 45) translate([0, 0, base_floor_t - eps])
        difference() {
            cylinder(d = 7, h = 5);
            translate([0, 0, 1]) heatset(d = m25_insert_d, h = 4 + eps);
        }
}

module pca_pads() {
    // servo driver board, tucked against the wall opposite the connectors
    translate([0, -46, base_floor_t - eps]) rotate([0, 0, 0])
        for (x = [-pca_hole_dx/2, pca_hole_dx/2], y = [-pca_hole_dy/2, pca_hole_dy/2])
            translate([x, y, 0]) difference() {
                cylinder(d = 7, h = 6);
                translate([0, 0, 6 - 4]) heatset(d = m25_insert_d, h = 4 + eps);
            }
}

module buck_pads() {
    // two step-down regulators: 5V for the Pi, 6V for the servo rail.
    // Each board is held by a pair of pads on a common y line.
    for (x0 = [-42, 6])
        for (x = [x0, x0 + buck_hole_dx])
            translate([x, 36, base_floor_t - eps]) difference() {
                cylinder(d = 6.5, h = 6);
                translate([0, 0, 2]) heatset(d = m25_insert_d, h = 4 + eps);
            }
}

module panel_cutouts() {
    // DC input barrel jack
    translate([0, 0, 22]) rotate([0, 0, 180])
        translate([0, 0, 0]) rotate([0, 90, 0])
            translate([0, 0, -base_d/2 - 2]) cylinder(d = barrel_d, h = 14);
    // power switch, 20mm to one side of the jack
    rotate([0, 0, 195]) translate([0, 0, 22]) rotate([0, 90, 0])
        translate([0, 0, -base_d/2 - 2]) cylinder(d = switch_d, h = 14);
    // service slot: reach in for the servo connector without disassembly
    rotate([0, 0, 90]) hull() for (z = [16, 40])
        translate([base_d/2 - 6, 0, z]) rotate([0, 90, 0]) cylinder(d = 9, h = 12);
}

difference() {
    union() {
        difference() {
            shell_solid();
            shell_hollow();
        }
        deck_bosses();
        speaker_mount();
        pca_pads();
        buck_pads();
    }
    // cooling / acoustic vents, two bands
    vent_ring(base_d, 26, 46, 28, w = 3.0, ang_span = 150, ang_start = -75);
    vent_ring(base_d, 26, 46, 28, w = 3.0, ang_span = 110, ang_start = 125);
    panel_cutouts();
    // speaker grille through the floor
    translate([0, 0, -eps]) speaker_grille(spk_cone_d, base_floor_t + 2*eps);
    // keep the very top of the wall clear so the turntable can seat
    translate([0, 0, base_h - 0.6]) cylinder(d1 = base_d - 2*wall, d2 = base_d - 2*wall + 1.4, h = 0.8);
}
