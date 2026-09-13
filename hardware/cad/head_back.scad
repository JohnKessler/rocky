// =====================================================================
// Rocky | PART 05 | head_back
// The main head shell: Pi, tilt servo, tilt pivot, faceplate posts,
// trim-weight post, and the sensor brow that carries camera and mic.
// Local origin: the TILT AXIS (head centre). Rocky faces +Y.
// PRINT: rear face down, open side up. Every overhang on the shell is a 45
//        degree chamfer or better, but the brow is not: its front wall is a
//        ceiling over the brow cavity in this orientation, so it wants light
//        supports under the brow, as PRINTING.md says.
// =====================================================================
include <rocky_params.scad>
use     <rocky_lib.scad>

y_rear    = -head_depth/2;
inner_d   = head_d - 2*wall;
inner_r   = inner_d/2;
rear_d    = head_d - 2*rear_ch;

// --- tilt servo (micro, left cheek) -----------------------------------
sv_wall_x = -(head_d/2 - wall);                       // inner face of the cheek
sv_pad_t  = msv_body_h - msv_flange_z - msv_flange_t; // 4.0mm stand-off
// --- Pi 5, portrait, shifted +X so the tilt servo clears it ------------
pi_cx     = -10;
pi_holes_x= [pi_cx - pi_hole_dy/2, pi_cx + pi_hole_dy/2];
pi_holes_z= [-pi_hole_dx/2, pi_hole_dx/2];
pi_y      = -22;                                      // PCB plane
// --- faceplate posts: a tripod clear of both Pi and servo --------------
// Three posts at r = 60 on the 3, 9 and 6 o'clock rays. The display's
// square carrier reaches r = 64 on the diagonals, so the diagonals are
// unusable; these three rays clear the carrier, the Pi, the tilt servo
// and the sensor brow simultaneously.
fp_r      = 60;
fp_posts  = [[fp_r, 0], [-fp_r, 0], [0, -fp_r]];
fp_y0     = 8;    // forward of the tilt servo's front face
fp_y      = 19;
// --- sensor brow -------------------------------------------------------
// The brow's outline, its 45 degree rear ramp and the microphone's slot are
// all in rocky_params.scad: pod_window and components.scad need the same
// numbers, and the mic cradle here has to agree with the port there.
cam_cx    = cam_lens_x;
cam_cz    = cam_lens_z;

// =====================================================================
module shell_solid() {
    translate([0, y_rear, 0]) rotate([-90, 0, 0]) union() {
        hull() {
            cylinder(d = rear_d, h = 0.4);
            translate([0, 0, rear_ch]) cylinder(d = head_d, h = 0.4);
        }
        translate([0, 0, rear_ch])
            cylinder(d = head_d, h = (y_split - y_rear) - rear_ch);
    }
}

module shell_cavity() {
    translate([0, y_rear + wall, 0]) rotate([-90, 0, 0]) union() {
        hull() {
            cylinder(d = rear_d - 2*wall, h = 0.4);
            translate([0, 0, rear_ch]) cylinder(d = inner_d, h = 0.4);
        }
        translate([0, 0, rear_ch]) cylinder(d = inner_d, h = head_depth);
    }
}

// --- sensor brow ------------------------------------------------------
// Built as a stack of thin slabs so the rear face follows a true 45 degree
// ramp - which is the print-downward face, the head going on the bed rear
// first. The cavity is open at the TOP, at z = pod_z1: the front wall is
// solid, carrying the lens and mic bores, so the camera and the microphone go
// in from above and pod_window is a bezel over the front rather than a lid.
module pod_profile(inset = 0) {
    steps = 40;
    for (i = [0 : steps - 1]) {
        z0 = pod_z0 + i * (pod_z1 - pod_z0) / steps;
        z1 = pod_z0 + (i + 1) * (pod_z1 - pod_z0) / steps;
        y0 = pod_ramp_y(z1) + inset;
        if (pod_y_front - inset > y0)
            translate([0, (y0 + pod_y_front - inset)/2, (z0 + z1)/2])
                cube([pod_w - 2*inset, pod_y_front - inset - y0, z1 - z0 + 0.02],
                     center = true);
    }
}

module pod_solid()  { pod_profile(0); }
module pod_cavity() { pod_profile(pod_wall); }

module camera_posts() {
    for (x = [cam_cx - cam_hole_dx/2, cam_cx + cam_hole_dx/2],
         z = [cam_cz - cam_hole_dy/2, cam_cz + cam_hole_dy/2])
        translate([x, 0, z]) {
            base = pod_ramp_y(z) + pod_wall;
            difference() {
                translate([0, base, 0]) rotate([-90, 0, 0])
                    cylinder(d = 7, h = 18 - base);
                translate([0, 18 - 4.2, 0]) rotate([-90, 0, 0])
                    cylinder(d = m2_insert_d, h = 4.4);
            }
        }
}

// Window fixings: M2.5 self-tappers, not heat-set inserts.
//
// The bore used to run y = 21.4..25.8 and stop 0.2 mm short of the front face,
// leaving a membrane over both holes that no insert could be pressed through.
// Opening it at the face exposes the other half of the problem: the brow's
// front wall is 2.4 mm and an M2.5 insert wants 4.4, and there is no printable
// way to thicken it from inside - in this print orientation anything added to
// that wall's inner face is an overhang over open cavity. A thread-forming
// screw into 2.4 mm of PETG holds far more than a 10 g cover plate needs, and
// the tilt servo's ears already go in the same way.
module pod_window_screws() {
    for (x = [-pod_w/2 + 6, pod_w/2 - 6])
        translate([x, pod_cav_y1 - 2, pod_z1 - 7]) rotate([-90, 0, 0])
            cylinder(d = 2.1, h = pod_wall + 3);
}

// The microphone: a cradle, not a bracket.
//
// What was here before were two M2 insert bores at y = 11.8..16 - open cavity
// at that height, so they cut nothing and the brow shipped with no mic
// mounting at all. Screwing a bracket in is not the fix: the free slot beside
// the camera is 13.6 mm wide (the camera's mounting bosses reach x = +7, the
// brow's inner wall is at +20.6), the stick on edge eats 7.3 of that, and an
// M2 boss needs 5.6 mm more than is left. There is also nowhere to put a
// screwdriver - the brow's front is walled and its only opening is the top.
//
// So the stick drops in from above into a slot moulded into the brow, trapped
// forward by the front wall it speaks through, sideways between the inner wall
// and one rib, and downward by the slot floor. A chamfered nub at the mouth
// cams aside as it goes in and keeps it from shaking back out. No fasteners,
// and the one thing the pocket costs - you reprint the head to fit a
// different microphone - is why mic_body_* are parameters.
module mic_pocket() {
    translate([mic_x0, mic_y0, mic_z0])
        cube([mic_body_x + slop + 2, mic_body_y + slop + 3, mic_body_z + slop]);
}

module mic_cradle() {
    difference() {
        union() {
            // Clipped to the brow's cavity, so the back of the block IS the
            // 45 degree ramp and nothing can poke out through a wall. The rib
            // runs a little higher than the pocket to carry the nub.
            intersection() {
                union() {
                    translate([mic_x0 - thin_wall, pod_y_rear, pod_z0])
                        cube([thin_wall, pod_y_front - pod_y_rear,
                              mic_z1 + 1.6 - pod_z0]);
                    translate([mic_x0, pod_y_rear, pod_z0])
                        cube([mic_body_x + slop + 1, pod_y_front - pod_y_rear,
                              mic_z1 - pod_z0]);
                }
                pod_cavity();
            }
            // retaining nub, thickest at the mouth and tapering upward
            translate([mic_x0, mic_y0 + 5, mic_z1]) rotate([-90, 0, 0])
                linear_extrude(10) polygon([[0, 0], [0.5, 0], [0, -1.6]]);
        }
        mic_pocket();
    }
}

// Port through the brow's front wall, behind pod_window's rosette. Without it
// the microphone is sealed into a closed box: the wall here is solid 2.4 mm.
module mic_port() {
    translate([mic_port_x, pod_cav_y1 - 1, mic_port_z]) rotate([-90, 0, 0])
        cylinder(d = mic_port_d, h = pod_wall + 2);
}

// And the camera's, for the same reason - the lens was looking at 2.4 mm of
// PETG. The barrel reaches y = 25.6, so it sits inside this bore rather than
// behind it.
module cam_aperture() {
    translate([cam_cx, pod_cav_y1 - 1, cam_cz]) rotate([-90, 0, 0])
        cylinder(d = cam_lens_d + 1.0, h = pod_wall + 2);
}

// The brow's floor is a closed web: nothing joined its cavity to the head's,
// so neither the camera's ribbon nor the mic's lead had a way down to the Pi.
//
// Placed under the camera, not under the microphone. The Camera Module 3's
// FFC leaves the top edge of the board, folds back on itself and comes down
// behind it at y = 8..17, so the slot sits where the ribbon actually falls and
// is cam_ffc_w wide to match it. The mic's lead crosses to the same slot under
// the camera board, which clears the brow floor by 4 mm.
module brow_cable_slot() {
    translate([-13, 2, pod_z0 - 6]) cube([cam_ffc_w, 15, 8]);
}

// --- tilt axis --------------------------------------------------------
module cheek_pad(side, cx, cz, w, h, t) {
    // slab on the inside of a cheek, chamfered on its print-underside
    x_wall = side * (head_d/2 - wall);
    hull() {
        translate([x_wall + side * 0.3, 0, cz]) cube([0.6, w, h], center = true);
        translate([x_wall - side * t, t/2, cz]) cube([0.6, w - t, h - 2*t], center = true);
    }
}

// 34 tall, not 46: the stop slot sweeps up to z = -24.6 at one end of its
// arc, and the pad used to reach -29. Still 3 mm of pad beyond each ear screw.
module tilt_servo_pad()  { cheek_pad(-1, 0, -6, 26, 34, sv_pad_t); }
module tilt_pivot_pad()  { cheek_pad(+1, 0,  0, 26, 26, 6); }

module tilt_servo_negatives() {
    // spline boss through the cheek
    translate([-head_d/2 - 3, 0, 0]) rotate([0, 90, 0]) cylinder(d = 10, h = wall + 4);
    // two ear screws: M2 self-tappers straight into the pad
    for (z = [-msv_shaft_off + msv_hole_dx/2, -msv_shaft_off - msv_hole_dx/2])
        translate([sv_wall_x + sv_pad_t + 0.5, 0, z]) rotate([0, -90, 0])
            cylinder(d = 1.7, h = sv_pad_t + wall);
}

module tilt_pivot_negative() {
    translate([head_d/2 - wall - 6, 0, 0]) rotate([0, 90, 0]) {
        cylinder(d = m3_insert_d, h = m3_insert_h);
        translate([0, 0, m3_insert_h]) cylinder(d = 3.8, h = wall + 8);
    }
}

// The mechanical tilt end stop: the arc each yoke pin sweeps through the
// cheek. One of the three layers meant to bound tilt, and until now the only
// one that did not exist - it was anchored at x = 65.4, z = 45, which is
// 79.4 mm from the head's axis while the shell reaches 70, so all 41 cuts
// fell 9.4 mm outside the material and the software limits were alone.
//
// The cheek is a cylinder about Y, so the surface is 4 mm deeper at the middle
// of the sweep than at its ends: the cut starts inside the shell and runs out
// past the outer face to cover both.
module tilt_stop_slots() {
    span  = tilt_range + tilt_stop_over;     // +/- degrees
    steps = 40;
    x0    = tilt_stop_surface_x(tilt_stop_z) - 5;
    len   = head_d/2 + 2 - x0;
    for (side = [-1, 1])
        for (i = [0 : steps])
            rotate([-span + i * 2 * span / steps, 0, 0])
                translate([side * x0, tilt_stop_y, tilt_stop_z])
                    rotate([0, side * 90, 0])
                        cylinder(d = tilt_stop_d + 1.2, h = len, $fn = 16);
}

// --- interior mounts --------------------------------------------------
module pi_posts() {
    for (x = pi_holes_x, z = pi_holes_z)
        translate([x, y_rear + wall - eps, z]) rotate([-90, 0, 0])
            difference() {
                union() {
                    cylinder(d = 7.5, h = pi_y - (y_rear + wall));
                    cylinder(d1 = 11, d2 = 7.5, h = 2.4);
                }
                translate([0, 0, pi_y - (y_rear + wall) - 4.2])
                    cylinder(d = m25_insert_d, h = 4.4);
            }
}

module faceplate_posts() {
    for (p = fp_posts) {
        ur = [p[0], p[1]] / fp_r;
        wr = head_d/2 - wall - 1.2;          // nub lands on the inner wall
        difference() {
            hull() {
                // tapers to a nub against the wall at its low end, so the
                // print-downward face never exceeds 45 degrees
                translate([ur[0] * wr, fp_y0, ur[1] * wr]) sphere(d = 3.5, $fn = 16);
                translate([p[0], fp_y - 5.4, p[1]]) rotate([-90, 0, 0])
                    cylinder(d = 10, h = 5.4);
            }
            translate([p[0], fp_y - m3_insert_h, p[1]]) rotate([-90, 0, 0])
                cylinder(d = m3_insert_d, h = m3_insert_h + eps);
        }
    }
}

// The I2S amplifier, on the rear wall above the Pi.
//
// It started in the base next to the speaker, which meant BCLK, LRC and DIN
// had to cross the rotating pan joint. Putting it here sends two analogue
// speaker conductors across instead of five digital ones, and keeps 3MHz
// square waves off a harness that flexes every time Rocky turns.
module amp_pads() {
    for (x = [-7.62, 7.62])
        translate([x, y_rear + wall - eps, 47]) rotate([-90, 0, 0])
            difference() {
                union() {
                    cylinder(d = 6.5, h = 6);
                    cylinder(d1 = 9.5, d2 = 6.5, h = 2.2);
                }
                translate([0, 0, 6 - 4.2]) cylinder(d = m2_insert_d, h = 4.4);
            }
}

module trim_post() {
    translate([0, y_rear + wall - eps, -50]) rotate([-90, 0, 0])
        difference() {
            union() {
                cylinder(d = 10, h = 6);
                cylinder(d1 = 14, d2 = 10, h = 2.6);
            }
            translate([0, 0, 6 - m3_insert_h]) cylinder(d = m3_insert_d, h = m3_insert_h + eps);
        }
}

// --- cosmetics and cooling -------------------------------------------
module carapace() {
    polar_y(carapace_ribs, 0)
        hull() for (y = [y_rear + 14, y_split - 6])
            translate([head_d/2 - rib_depth, y, 0])
                rotate([0, 90, 0]) cylinder(d = 3.0, h = rib_depth * 2, $fn = 12);
}

module rear_vents() {
    for (i = [0 : 5], j = [0 : 2])
        translate([-30 + i * 12, y_rear - 2, -34 + j * 9])
            cube([4, wall + 4, 5]);
}

// =====================================================================
difference() {
    union() {
        difference() {
            union() { shell_solid(); carapace(); pod_solid(); }
            shell_cavity();
            pod_cavity();
        }
        tilt_servo_pad();
        tilt_pivot_pad();
        pi_posts();
        faceplate_posts();
        trim_post();
        camera_posts();
        amp_pads();
        mic_cradle();
    }
    tilt_servo_negatives();
    tilt_pivot_negative();
    tilt_stop_slots();
    pod_window_screws();
    mic_port();
    cam_aperture();
    brow_cable_slot();
    rear_vents();
    // harness entry, low on the right cheek
    translate([0, -14, 0]) rotate([0, 45, 0])
        translate([0, 0, -head_d/2 - 4]) cylinder(d = 14, h = wall + 8);
}
