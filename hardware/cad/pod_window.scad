// =====================================================================
// Rocky | PART 07 | pod_window
// Closes the sensor brow once the camera and mic are inside. Carries the
// lens aperture and the microphone port.
//
// Local frame: origin at the centre of the plate. X across the brow,
// Y through the plate thickness, OUTWARD IS +Y, Z up the brow.
// In head coordinates the plate centre sits at y = pod_y_front + plate_t/2,
// z = pod_z1 - 13, so the plate's -Y face lands on the brow's front face.
//
// The outward direction used to be -Y, which put the screw counterbores on the
// face that beds against the brow and pointed the locating spigot out into
// free air. Worse, being built from that face outward, all three counterbores
// landed just clear of the plate and removed nothing at all, so the screw heads
// stood proud of a plate that was meant to be flush. The spigot is gone with
// them: it was there to drop into an opening in the brow's front, and there is
// no opening - that wall is solid, with the lens and mic bores in head_back
// lining up behind this plate's apertures.
//
// PRINT: outside face (+Y) down. Two M2.5 self-tappers into the brow.
// =====================================================================
include <rocky_params.scad>
use     <rocky_lib.scad>

plate_t   = 3.2;
plate_h   = 26;
plate_z   = pod_z1 - 13;     // plate centre in head coordinates
cam_pos   = [cam_lens_x, cam_lens_z - plate_z];   // [x, z] from the plate centre
mic_pos   = [mic_port_x, mic_port_z - plate_z];
screw_x   = pod_w/2 - 6;
screw_z   = 6;

module thru(d, x, z) {
    translate([x, 0, z]) rotate([-90, 0, 0])
        cylinder(d = d, h = plate_t * 4, center = true);
}

// counterbore opening on the outside (+Y) face
module cbore(d, depth, x, z) {
    translate([x, plate_t/2 + eps - depth, z]) rotate([-90, 0, 0])
        cylinder(d = d, h = depth + eps);
}

// Named rather than inlined so check_features.py can assert each one removes
// material. That is not hypothetical tidiness: the counterbores this part used
// to have cut nothing, and nothing in the build noticed.
module camera_aperture() {
    thru(cam_lens_d + 1.0, cam_pos[0], cam_pos[1]);
    // The relief keeps the printed surface off the lens barrel. +3, not +5:
    // the lens sits 10 mm above the plate's lower edge, and a 20 mm recess
    // there runs exactly tangent to it, which leaves a knife edge and a
    // non-manifold solid.
    cbore(cam_lens_d + 3.0, 1.2, cam_pos[0], cam_pos[1]);
}

// A rosette breathes better than one hole. Sized to sit inside the mic_port_d
// bore behind it, so no part of it opens onto solid brow wall:
// ring radius + hole/2 < mic_port_d/2.
module mic_rosette() {
    thru(2.4, mic_pos[0], mic_pos[1]);
    for (i = [0 : 7])
        thru(1.8, mic_pos[0] + 2.8 * cos(i * 45), mic_pos[1] + 2.8 * sin(i * 45));
}

module screw_holes() {
    for (x = [-screw_x, screw_x]) {
        thru(m25_free, x, screw_z);
        cbore(5.4, 1.8, x, screw_z);
    }
}

difference() {
    cube([pod_w, plate_t, plate_h], center = true);
    camera_aperture();
    mic_rosette();
    screw_holes();
}
