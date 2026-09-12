// =====================================================================
// Rocky | PART 07 | pod_window
// Closes the sensor brow once the camera and mic are inside. Carries the
// lens aperture and the microphone port.
//
// Local frame: origin at the centre of the plate. X across the brow,
// Y through the plate thickness (outward is -Y), Z up the brow.
// In head coordinates the plate centre sits at y = pod_y_front,
// z = pod_z1 - 13.
//
// PRINT: outside face (-Y) down. Two M2.5 screws into the brow.
// =====================================================================
include <rocky_params.scad>
use     <rocky_lib.scad>

plate_t   = 3.2;
plate_h   = 26;
cam_pos   = [-7, -3];        // [x, z] relative to the plate centre
mic_pos   = [15, -3];
screw_x   = pod_w/2 - 6;
screw_z   = 6;

module thru(d, x, z) {
    translate([x, 0, z]) rotate([-90, 0, 0])
        cylinder(d = d, h = plate_t * 4, center = true);
}

// counterbore opening on the outside face
module cbore(d, depth, x, z) {
    translate([x, -plate_t/2 - eps, z]) rotate([-90, 0, 0])
        translate([0, 0, -depth]) cylinder(d = d, h = depth + eps);
}

difference() {
    union() {
        cube([pod_w, plate_t, plate_h], center = true);
        // spigot locating the plate inside the brow opening; it starts
        // inside the plate so the two solids interpenetrate cleanly, and
        // stops short of the screw counterbores
        translate([-(pod_w - 2*pod_wall - 2*slop)/2, -1.0, -12])
            cube([pod_w - 2*pod_wall - 2*slop, plate_t + 1.0, 14]);
    }

    // --- camera aperture ------------------------------------------------
    thru(cam_lens_d + 1.0, cam_pos[0], cam_pos[1]);
    cbore(cam_lens_d + 5.0, 1.2, cam_pos[0], cam_pos[1]);

    // --- microphone port: a rosette breathes better than one hole -------
    thru(2.4, mic_pos[0], mic_pos[1]);
    for (i = [0 : 7])
        thru(2.0, mic_pos[0] + 3.4 * cos(i * 45), mic_pos[1] + 3.4 * sin(i * 45));

    // --- fixings ---------------------------------------------------------
    for (x = [-screw_x, screw_x]) {
        thru(m25_free, x, screw_z);
        cbore(5.4, 1.8, x, screw_z);
    }
}
