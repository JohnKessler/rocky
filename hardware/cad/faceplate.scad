// =====================================================================
// Rocky | PART 06 | faceplate
// Bezel and display carrier in one piece: the round panel drops in from
// behind, screws to four bosses, and the lip traps its cover glass.
// Three M3 screws through the rim hold the faceplate to head_back.
// Local origin: the TILT AXIS. Rocky faces +Y.
// PRINT: front face DOWN. The rim chamfer is the only overhang and it
//        is 45 degrees. Print in the colour you want Rocky's face framed
//        in - this is the part people look at.
// =====================================================================
include <rocky_params.scad>
use     <rocky_lib.scad>

y_back    = y_split;                       // mates against head_back's posts
y_face    = head_depth/2;                  // +31, the front-most surface
lip_t     = 2.4;                           // bezel lip over the glass
y_glass_f = y_face - lip_t;                // glass front face
y_glass_b = y_glass_f - disp_glass_t;      // glass back / carrier front
// swallows the square carrier corner-to-corner, with rim left over
pocket_d  = sqrt(2) * disp_pcb_w + 1.5;
fp_r      = 60;
fp_posts  = [[fp_r, 0], [-fp_r, 0], [0, -fp_r]];

module ring_solid() {
    translate([0, y_back, 0]) rotate([-90, 0, 0]) union() {
        cylinder(d = head_d, h = (y_face - front_ch) - y_back);
        translate([0, 0, (y_face - front_ch) - y_back])
            cylinder(d1 = head_d, d2 = head_d - 2*front_ch, h = front_ch);
    }
}

module pockets() {
    // 1. window the viewer actually sees
    translate([0, y_glass_f, 0]) rotate([-90, 0, 0])
        cylinder(d = disp_active_d + 2.4, h = lip_t + 1);
    // 2. seat for the cover glass
    translate([0, y_glass_b, 0]) rotate([-90, 0, 0])
        cylinder(d = disp_glass_d + 2*slop, h = disp_glass_t + eps);
    // 3. relief for the carrier PCB and everything on it. Round, not
    //    square: it swallows any carrier whose diagonal fits, without
    //    driving thin corners into the rim.
    translate([0, y_back - eps, 0]) rotate([-90, 0, 0])
        cylinder(d = pocket_d, h = y_glass_b - y_back + 2*eps);
}

module panel_screw_bosses() {
    // M2.5 inserts, bored forward from the carrier seat
    for (x = [-disp_hole_dx/2, disp_hole_dx/2], z = [-disp_hole_dy/2, disp_hole_dy/2])
        translate([x, y_glass_b, z]) rotate([-90, 0, 0])
            cylinder(d = m25_insert_d, h = 3.6);
}

module frame_screws() {
    for (p = fp_posts) translate([p[0], 0, p[1]]) rotate([-90, 0, 0]) {
        translate([0, 0, y_back - eps]) cylinder(d = m3_free, h = head_depth);
        translate([0, 0, y_face - 3.0]) cylinder(d = m3_head, h = 4);
    }
}

// Shallow facets around the rim, echoing the carapace on head_back.
module rim_facets() {
    polar_y(carapace_ribs, 0)
        hull() for (y = [y_back + 3, y_face - 4])
            translate([head_d/2 - rib_depth, y, 0])
                rotate([0, 90, 0]) cylinder(d = 3.0, h = rib_depth * 2, $fn = 12);
}

difference() {
    union() { ring_solid(); rim_facets(); }
    pockets();
    panel_screw_bosses();
    frame_screws();
}
