// =====================================================================
// Rocky | component stand-ins
//
// Simplified models of the bought-in parts, at their real sizes and in
// their real places. They are not accurate models and are not meant to
// be printed - they exist so the assembly renders show where a board
// actually goes, which a picture of empty printed shells does not.
//
// Dimensions come from rocky_params.scad where the printed parts care
// about them, and from the datasheets otherwise.
// =====================================================================
include <rocky_params.scad>

// Palette, shared with the exploded views so a colour means the same
// thing in every picture.
C_PCB      = "#1f6f3f";   // circuit boards
C_PCB_DARK = "#14532b";
C_METAL    = "#9aa4b2";   // connectors, shields, heatsinks
C_PLASTIC  = "#22262e";   // servo cases, speaker frames
C_SCREEN   = "#0b1622";   // display glass
C_COPPER   = "#b87333";
C_WIRE_RED = "#d94b3c";
C_WIRE_BLK = "#31363f";

module pcb(w, d, t = 1.6, colour = C_PCB) {
    color(colour) cube([w, d, t], center = true);
}

// --- Raspberry Pi 5 with the official Active Cooler ---------------------
// Origin at the centre of the PCB, component side +Z.
module raspberry_pi_5() {
    pcb(pi_w, pi_h, pi_pcb_t);
    // active cooler: finned block plus fan
    color(C_METAL) translate([-2, 0, pi_pcb_t/2 + 9]) cube([58, 38, 18], center = true);
    color("#3a3f48") translate([22, 0, pi_pcb_t/2 + 19.5]) cylinder(d = 30, h = 3, center = true);
    // USB-A stack and Ethernet on one long edge
    color(C_METAL) {
        translate([-27, pi_h/2 - 4, pi_pcb_t/2 + 8]) cube([17, 14, 16], center = true);
        translate([-4, pi_h/2 - 4, pi_pcb_t/2 + 8]) cube([17, 14, 16], center = true);
        translate([21, pi_h/2 - 4, pi_pcb_t/2 + 7]) cube([16, 14, 14], center = true);
    }
    // USB-C power and the two micro-HDMI on the other
    color(C_METAL) {
        translate([-31, -pi_h/2 + 2, pi_pcb_t/2 + 1.7]) cube([9, 7, 3.5], center = true);
        translate([-14, -pi_h/2 + 2, pi_pcb_t/2 + 1.6]) cube([8, 7, 3.2], center = true);
        translate([ 2, -pi_h/2 + 2, pi_pcb_t/2 + 1.6]) cube([8, 7, 3.2], center = true);
    }
    // GPIO header
    color("#1a1d23") translate([-8, pi_h/2 - 3.5, pi_pcb_t/2 + 4.2]) cube([51, 5, 8.5], center = true);
}

// --- PCA9685 16-channel servo driver -----------------------------------
module pca9685() {
    pcb(62.5, 25.4);
    color("#1a1d23") translate([0, 7, 4.3]) cube([58, 7.6, 8.5], center = true);   // servo headers
    color("#2f6fb5") translate([-26, -7, 4]) cube([10, 9, 8], center = true);      // screw terminal
    color(C_METAL) translate([26, -7, 3]) cube([8, 8, 6], center = true);          // I2C header
}

// --- Pololu step-down regulator ----------------------------------------
module buck_regulator(label_h = 0) {
    pcb(43.2, 20.3, 1.6, C_PCB_DARK);
    color("#3a3f48") translate([4, 0, 6]) cube([18, 14, 11], center = true);       // inductor
    color(C_METAL) translate([-17, 0, 3]) cube([6, 12, 5], center = true);
}

// --- MAX98357A I2S amplifier -------------------------------------------
module max98357a() {
    pcb(20.5, 16.4, 1.6, C_PCB_DARK);
    color("#1a1d23") translate([0, -6, 3]) cube([18, 3, 5], center = true);
    color("#c0c4cc") translate([0, 2, 1.6]) cube([5, 5, 1.2], center = true);
}

// --- 40mm speaker, magnet up -------------------------------------------
module speaker_40mm() {
    color(C_PLASTIC) cylinder(d = spk_d, h = 2.5);
    color("#4a4f58") translate([0, 0, 2.5]) cylinder(d = 30, h = 3);
    color("#6b7280") translate([0, 0, 5.5]) cylinder(d = 26, h = 8.5);             // magnet
}

// --- round display module ----------------------------------------------
// Origin at the centre of the glass, viewer side +Z.
module round_display() {
    color(C_SCREEN) translate([0, 0, -disp_glass_t/2]) cylinder(d = disp_glass_d, h = disp_glass_t);
    color("#0d2b3a") translate([0, 0, -disp_glass_t - 0.2]) cylinder(d = disp_active_d, h = 0.4);
    color(C_PCB) translate([0, 0, -disp_glass_t - 1.6/2 - 0.4])
        cube([disp_pcb_w, disp_pcb_w, 1.6], center = true);
    color("#1a1d23") translate([0, -30, -disp_glass_t - 4]) cube([30, 12, 5], center = true);
    color("#c8a24a") translate([0, -46, -disp_glass_t - 2.5]) cube([16, 24, 0.3], center = true);  // FPC tail
}

// --- Camera Module 3 ----------------------------------------------------
// Origin at the centre of the PCB, lens facing +Z.
module camera_module_3() {
    pcb(cam_pcb_w, cam_pcb_h, cam_pcb_t);
    color(C_PLASTIC) translate([0, 0, cam_pcb_t/2 + 3]) cube([16, 16, 6], center = true);
    color("#12161c") translate([0, 0, cam_pcb_t/2 + 6.2]) cylinder(d = cam_lens_d, h = 1.4);
    color("#c8a24a") translate([0, -14, -cam_pcb_t/2 - 0.2]) cube([cam_ffc_w, 10, 0.3], center = true);
}

// --- servos -------------------------------------------------------------
// Origin at the OUTPUT SHAFT, on the underside of the body, matching the
// servo_pocket convention in rocky_lib.scad.
module standard_servo() {
    dx = sv_shaft_off;
    color(C_PLASTIC) {
        translate([-dx, 0, sv_body_h/2]) cube([sv_body_l, sv_body_w, sv_body_h], center = true);
        translate([-dx, 0, sv_flange_z + sv_flange_t/2])
            cube([sv_flange_l, sv_body_w, sv_flange_t], center = true);
    }
    color("#c8c8c8") translate([0, 0, sv_body_h]) cylinder(d = sv_shaft_d + 2, h = sv_boss_h);
    color(C_WIRE_BLK) translate([-dx - sv_body_l/2 - 5, 0, sv_body_h * 0.45])
        cube([12, 6, 4], center = true);
}

module micro_servo() {
    dx = msv_shaft_off;
    color(C_PLASTIC) {
        translate([-dx, 0, msv_body_h/2]) cube([msv_body_l, msv_body_w, msv_body_h], center = true);
        translate([-dx, 0, msv_flange_z + msv_flange_t/2])
            cube([msv_flange_l, msv_body_w, msv_flange_t], center = true);
    }
    color("#c8c8c8") translate([0, 0, msv_body_h]) cylinder(d = msv_shaft_d + 2, h = msv_boss_h);
    color(C_WIRE_BLK) translate([-dx - msv_body_l/2 - 4, 0, msv_body_h * 0.45])
        cube([10, 5, 3.5], center = true);
}

module servo_horn(d = sv_horn_d) {
    color("#e8e8e8") cylinder(d = d, h = sv_horn_t);
}

// --- misc ---------------------------------------------------------------
module bearing_623() {
    color(C_METAL) difference() {
        cylinder(d = brg_od, h = brg_t);
        translate([0, 0, -0.1]) cylinder(d = brg_id, h = brg_t + 0.2);
    }
}

// Flat USB stick microphone, stood on edge. Origin at its minimum corner, so
// it drops straight onto mic_x0 / mic_y0 / mic_z0 with no arithmetic at the
// call site. Capsule forward, USB plug back, right-angle adapter on the plug.
module usb_microphone() {
    color(C_PLASTIC) cube([mic_body_x, mic_body_y, mic_body_z]);
    color("#3a3f4b") translate([mic_body_x/2, mic_body_y - 0.4, mic_body_z/2])
        rotate([-90, 0, 0]) cylinder(d = 4, h = 1.0, $fn = 16);
    color(C_METAL) translate([mic_body_x/2 - 6, -11, mic_body_z/2 - 2.3])
        cube([12, 11, 4.6]);
    color("#1a1d23") translate([mic_body_x/2 - 7, -19, mic_body_z/2 - 4])
        cube([14, 8, 8]);
}

// A short run of wire between two points, for the harness illustrations.
module wire(p0, p1, d = 1.8, colour = C_WIRE_RED) {
    color(colour) hull() {
        translate(p0) sphere(d = d, $fn = 10);
        translate(p1) sphere(d = d, $fn = 10);
    }
}

// Floating caption, always facing the camera's default view.
module caption(text_string, size = 6, colour = "#e8eef7") {
    color(colour) rotate([90, 0, 0]) linear_extrude(0.6)
        text(text_string, size = size, font = "Liberation Sans:style=Bold",
             halign = "center", valign = "center");
}
