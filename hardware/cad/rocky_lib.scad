// =====================================================================
// Rocky - reusable geometry helpers
// =====================================================================
include <rocky_params.scad>

// ---- primitives ------------------------------------------------------

// Cylinder with a rounded (filleted) top edge.
module round_top_cyl(d, h, r) {
    hull() {
        cylinder(d = d, h = h - r);
        translate([0, 0, h - r]) rotate_extrude()
            translate([d/2 - r, 0]) circle(r = r);
        translate([0, 0, h - r]) cylinder(d = d - 2*r, h = r);
    }
}

// A 90-degree V ball race, cut into a flat face lying at z = 0.
//   dir = -1  groove sinks below the face  (use on an upward-facing race)
//   dir = +1  groove rises above the face  (use on a downward-facing race)
// Either way the flanks sit at 45 degrees, so it prints without support.
module race_groove(pitch_d = race_d, depth = race_groove_d, dir = -1) {
    rotate_extrude($fn = 200)
        polygon([[pitch_d/2 - depth, 0],
                 [pitch_d/2 + depth, 0],
                 [pitch_d/2,         dir * depth]]);
}

// The balls themselves, for assembly renders / interference checking.
module race_balls(pitch_d = race_d, n = ball_count, d = ball_d) {
    polar(n, pitch_d/2) sphere(d = d, $fn = 24);
}

// Countersunk / counterbored clearance hole for an M3 cap screw,
// drilled downward from z=0.
module m3_cbore(depth = 20, head_up = true) {
    translate([0, 0, -depth]) cylinder(d = m3_free, h = depth + eps);
    if (head_up) cylinder(d = m3_head, h = m3_head_h + eps);
}

// Blind pilot bore for a brass heat-set insert, opening upward from z=0.
module heatset(d = m3_insert_d, h = m3_insert_h) {
    cylinder(d = d, h = h);
    // lead-in chamfer so the insert starts straight
    translate([0, 0, -eps]) cylinder(d1 = d + 1.0, d2 = d, h = 0.8);
}

// A boss with a heat-set insert in the top.
module insert_boss(h, od = 8, d = m3_insert_d, ih = m3_insert_h) {
    difference() {
        cylinder(d = od, h = h);
        translate([0, 0, h - ih]) heatset(d, ih + eps);
    }
}

// ---- patterns --------------------------------------------------------

// Polar array about the Y axis, for anything arranged around Rocky's
// face (the face lies in the XZ plane, so Z-axis polar is wrong there).
module polar_y(n, r = 0, start = 0) {
    for (i = [0 : n - 1])
        rotate([0, start + i * 360 / n, 0]) translate([r, 0, 0]) children();
}

module polar(n, r = 0, start = 0) {
    for (i = [0 : n - 1])
        rotate([0, 0, start + i * 360 / n]) translate([r, 0, 0]) children();
}

// Vertical louvre slots cut through a cylindrical wall, as radial capsules.
// The cut starts just inside the wall's inner face and runs outward, so it
// pierces the wall without chewing into bosses standing behind it.
module vent_ring(d, z0, z1, count, w = vent_w, ang_span = 360, ang_start = 0,
                 t = wall) {
    r0 = d/2 - t - 0.6;   // stays inside the wall, clear of bosses behind it
    len = t + 4;
    for (i = [0 : count - 1])
        rotate([0, 0, ang_start + i * ang_span / count])
            hull() {
                translate([r0, 0, z0 + w/2]) rotate([0, 90, 0])
                    cylinder(d = w, h = len, $fn = 20);
                translate([r0, 0, z1 - w/2]) rotate([0, 90, 0])
                    cylinder(d = w, h = len, $fn = 20);
            }
}

// Radial grille of round holes, for the speaker.
module speaker_grille(d_open, t) {
    hole  = 2.6;
    pitch = 4.4;
    n = floor(d_open / pitch / 2);
    translate([0, 0, -eps]) cylinder(d = hole, h = t + 2*eps);
    for (ring = [1 : n]) {
        r = ring * pitch;
        cnt = max(6, floor(2 * 3.14159 * r / pitch));
        for (i = [0 : cnt - 1])
            rotate([0, 0, i * 360 / cnt]) translate([r, 0, -eps])
                if (r + hole/2 < d_open/2) cylinder(d = hole, h = t + 2*eps);
    }
}

// ---- component negatives --------------------------------------------

// Negative volume for a standard-size servo dropped in from above.
// Origin sits at the OUTPUT SHAFT AXIS, on the underside of the body.
// Set `ears` to also cut the mounting-ear pocket.
module servo_pocket(ears = true, lead_in = 30) {
    dx = sv_shaft_off;             // shaft is offset from the body centre
    // body, plus a lead-in column above it so the servo can drop in
    translate([-dx, 0, (sv_body_h + lead_in)/2 - eps])
        cube([sv_body_l + slop, sv_body_w + slop, sv_body_h + lead_in], center = true);
    if (ears)
        translate([-dx, 0, sv_flange_z + sv_flange_t/2])
            cube([sv_flange_l + slop, sv_body_w + slop, sv_flange_t + slop], center = true);
    // cable exit
    translate([-dx - sv_body_l/2 - 4, 0, sv_body_h * 0.45])
        cube([10, 8, 10], center = true);
}

// The two M2.5 screw holes in each servo mounting ear.
module servo_ear_holes(h = 10) {
    dx = sv_shaft_off;
    translate([-dx, 0, 0])
        for (x = [-sv_hole_dx/2, sv_hole_dx/2], y = [-sv_hole_dy/2, sv_hole_dy/2])
            translate([x, y, -h/2]) cylinder(d = sv_hole_d, h = h);
}

// Clearance for the servo output boss + a round horn recessed into a part.
module servo_horn_pocket(depth = sv_horn_t + 0.4) {
    cylinder(d = sv_horn_d + slop, h = depth);
    translate([0, 0, -sv_boss_h]) cylinder(d = sv_shaft_d + 2.5, h = sv_boss_h + eps);
    // four screw holes to bolt the horn to the driven part
    polar(4, 8) translate([0, 0, -8]) cylinder(d = 2.2, h = 20);
}

// Raspberry Pi 5 mounting hole pattern, centred on the board outline.
module pi_holes(h = 12, d = m25_insert_d) {
    for (x = [-pi_hole_dx/2, pi_hole_dx/2], y = [-pi_hole_dy/2, pi_hole_dy/2])
        translate([x, y, 0]) cylinder(d = d, h = h);
}

// Camera Module 3 hole pattern.
module cam_holes(h = 10, d = m2_insert_d) {
    for (x = [-cam_hole_dx/2, cam_hole_dx/2], y = [-cam_hole_dy/2, cam_hole_dy/2])
        translate([x, y, 0]) cylinder(d = d, h = h);
}

// Display carrier PCB hole pattern.
module disp_holes(h = 12, d = m25_insert_d) {
    for (x = [-disp_hole_dx/2, disp_hole_dx/2], y = [-disp_hole_dy/2, disp_hole_dy/2])
        translate([x, y, 0]) cylinder(d = d, h = h);
}
