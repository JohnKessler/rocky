// =====================================================================
// Rocky | PART 11 | speaker_gasket
// Seals the speaker frame against the base floor so the enclosure does
// not leak and chuff. PRINT IN TPU (95A), 100% infill, no supports.
// =====================================================================
include <rocky_params.scad>
use     <rocky_lib.scad>

difference() {
    cylinder(d = spk_hole_pcd + 8, h = 1.6);
    translate([0, 0, -eps]) cylinder(d = spk_cone_d + 2, h = 1.6 + 2*eps);
    polar(4, spk_hole_pcd/2, 45) translate([0, 0, -eps])
        cylinder(d = m25_free + 0.4, h = 1.6 + 2*eps);
}
