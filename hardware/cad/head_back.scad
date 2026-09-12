// =====================================================================
// Rocky | PART 05 | head_back
// The main head shell: Pi, tilt servo, tilt pivot, faceplate posts,
// trim-weight post, and the sensor brow that carries camera and mic.
// Local origin: the TILT AXIS (head centre). Rocky faces +Y.
// PRINT: rear face down, open side up. Every overhang is a 45 degree
//        chamfer or better, so no supports are required.
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
ramp_z    = 75;                                       // ramp leaves the shell here
pod_y0    = -16;
cam_cx    = -7;
cam_cz    = 84;
mic_cx    = 15;

function ramp_y(z) = pod_y0 + max(0, z - ramp_z);     // 45 degree underside

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
// Built as a stack of thin slabs so the underside follows a true 45
// degree ramp; the cavity is open at the front for assembly.
module pod_profile(inset = 0) {
    steps = 40;
    for (i = [0 : steps - 1]) {
        z0 = pod_z0 + i * (pod_z1 - pod_z0) / steps;
        z1 = pod_z0 + (i + 1) * (pod_z1 - pod_z0) / steps;
        y0 = ramp_y(z1) + inset;
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
            base = ramp_y(z) + pod_wall;
            difference() {
                translate([0, base, 0]) rotate([-90, 0, 0])
                    cylinder(d = 7, h = 18 - base);
                translate([0, 18 - 4.2, 0]) rotate([-90, 0, 0])
                    cylinder(d = m2_insert_d, h = 4.4);
            }
        }
}

module pod_window_inserts() {
    for (x = [-pod_w/2 + 6, pod_w/2 - 6])
        translate([x, pod_y_front - 4.6, pod_z1 - 7]) rotate([-90, 0, 0])
            cylinder(d = m25_insert_d, h = 4.4);
}

module mic_inserts() {
    for (z = [cam_cz - 9, cam_cz + 9])
        translate([mic_cx, 16 - 4.2, z]) rotate([-90, 0, 0])
            cylinder(d = m2_insert_d, h = 4.4);
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

module tilt_servo_pad()  { cheek_pad(-1, 0, -6, 26, 46, sv_pad_t); }
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

module tilt_stop_slots() {
    span = 2 * tilt_range + 8;
    for (side = [-1, 1])
        for (i = [0 : 40])
            rotate([180 - span/2 + i * span/40, 0, 0])
                translate([side * (head_d/2 - wall - 2), 0, 45])
                    rotate([0, side * 90, 0]) cylinder(d = 6.2, h = wall + 5, $fn = 16);
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
    }
    tilt_servo_negatives();
    tilt_pivot_negative();
    tilt_stop_slots();
    pod_window_inserts();
    mic_inserts();
    rear_vents();
    // microphone port through the brow's front rim is cut by pod_window
    // harness entry, low on the right cheek
    translate([0, -14, 0]) rotate([0, 45, 0])
        translate([0, 0, -head_d/2 - 4]) cylinder(d = 14, h = wall + 8);
}
