// f310_bridge.m — F310 D-mode USB HID → stdout JSON for DeepSight Host
//
// Captures the F310 via IOUSBHostDevice (needs root or setuid) and outputs
// one JSON line per poll interval at ~250Hz.
//
// Build:
//   clang -framework Foundation -framework IOUSBHost -framework IOKit \
//         -Os -o scripts/f310_bridge scripts/f310_bridge.m
//
// Setup (one-time):
//   sudo cp scripts/f310_bridge /usr/local/bin/deepsight_f310_bridge
//   sudo chown root:wheel /usr/local/bin/deepsight_f310_bridge
//   sudo chmod 4755 /usr/local/bin/deepsight_f310_bridge
//
// Usage:
//   /usr/local/bin/deepsight_f310_bridge [--debug]

#import <Foundation/Foundation.h>
#import <IOUSBHost/IOUSBHost.h>
#import <IOKit/IOKitLib.h>
#import <signal.h>
#import <stdio.h>
#import <stdlib.h>
#import <string.h>
#import <unistd.h>

static volatile int running = 1;

static void on_signal(int sig) {
    (void)sig;
    running = 0;
}

static void eprint(NSString *msg) {
    const char *s = [msg UTF8String];
    write(STDERR_FILENO, s, strlen(s));
    write(STDERR_FILENO, "\n", 1);
}

// Walk the IORegistry tree and fix HIDRM properties on all HID-related nodes.
// Must run as root (setuid) to set properties on AppleUserUSBHostHIDDevice.
static void fixHidrmProperties(io_registry_entry_t entry) {
    io_name_t name;
    IORegistryEntryGetName(entry, name);

    // Fix HIDRM properties on HID-related nodes
    if (strstr(name, "HID") || strstr(name, "AppleUserUSB")) {
        IORegistryEntrySetCFProperty(entry,
            CFSTR("HIDRMDeviceState"), CFSTR("Allowed"));
        IORegistryEntrySetCFProperty(entry,
            CFSTR("RegisterService"), kCFBooleanTrue);
        IORegistryEntrySetCFProperty(entry,
            CFSTR("HIDRMOverride"), CFSTR("Register"));
        char msg[256];
        snprintf(msg, sizeof(msg), "  fixed: %s", name);
        eprint(@(msg));
    }

    // Recurse into children
    io_iterator_t citer = 0;
    IORegistryEntryGetChildIterator(entry, "IOService", &citer);
    io_service_t child;
    while ((child = IOIteratorNext(citer))) {
        fixHidrmProperties(child);
        IOObjectRelease(child);
    }
    IOObjectRelease(citer);
}

int main(int argc, char **argv) {
    @autoreleasepool {
        signal(SIGINT, on_signal);
        signal(SIGTERM, on_signal);

        bool debug = (argc > 1 && strcmp(argv[1], "--debug") == 0);
        bool fixHidrm = (argc > 1 && strcmp(argv[1], "--fix-hidrm") == 0);

        // ── Find F310 device ──────────────────────────────────────────
        CFMutableDictionaryRef dm = IOServiceMatching("IOUSBHostDevice");
        CFDictionarySetValue(dm, CFSTR("idVendor"),
                             (__bridge CFNumberRef)@(0x046d));
        CFDictionarySetValue(dm, CFSTR("idProduct"),
                             (__bridge CFNumberRef)@(0xc216));
        io_iterator_t it = 0;
        if (IOServiceGetMatchingServices(kIOMainPortDefault, dm, &it) != 0) {
            eprint(@"f310_bridge: IOServiceGetMatchingServices failed");
            return 1;
        }
        io_service_t ds = IOIteratorNext(it);
        IOObjectRelease(it);
        if (!ds) {
            eprint(@"f310_bridge: F310 (046d:c216) not found on USB bus");
            return 1;
        }

        // ── --fix-hidrm mode: set kernel properties to fix HIDRM approval ─
        if (fixHidrm) {
            eprint(@"f310_bridge: fixing HIDRM state (setuid root needed)...");
            fixHidrmProperties(ds);
            IOObjectRelease(ds);
            eprint(@"f310_bridge: HIDRM fix applied. Now try GCController/pygame.");
            return 0;
        }

        // ── Capture device (takes exclusive control from HID drivers) ─
        NSError *err = nil;
        IOUSBHostDevice *dev = [[IOUSBHostDevice alloc]
            initWithIOService:ds
                      options:IOUSBHostObjectInitOptionsDeviceCapture
                        queue:dispatch_get_global_queue(
                                  DISPATCH_QUEUE_PRIORITY_HIGH, 0)
                        error:&err
              interestHandler:nil];
        IOObjectRelease(ds);
        if (!dev) {
            eprint([NSString stringWithFormat:
                @"f310_bridge: device capture failed: %@",
                err.localizedDescription]);
            return 1;
        }

        // ── Re-find the interface after capture reset ─────────────────
        usleep(500000);  // 500ms settle (was 200ms, not enough for some states)
        CFMutableDictionaryRef dm2 = IOServiceMatching("IOUSBHostDevice");
        CFDictionarySetValue(dm2, CFSTR("idVendor"),
                             (__bridge CFNumberRef)@(0x046d));
        CFDictionarySetValue(dm2, CFSTR("idProduct"),
                             (__bridge CFNumberRef)@(0xc216));
        io_iterator_t it2 = 0;
        IOServiceGetMatchingServices(kIOMainPortDefault, dm2, &it2);
        io_service_t cd = IOIteratorNext(it2);
        IOObjectRelease(it2);
        if (!cd) {
            eprint(@"f310_bridge: device disappeared after capture");
            return 1;
        }

        // Walk children to find IOUSBHostInterface
        io_iterator_t citer = 0;
        IORegistryEntryGetChildIterator(cd, "IOService", &citer);
        io_service_t child, isvc = 0;
        while ((child = IOIteratorNext(citer))) {
            io_name_t name;
            IORegistryEntryGetName(child, name);
            if (strncmp(name, "IOUSBHostInterface", 18) == 0) {
                isvc = child;
                break;
            }
            IOObjectRelease(child);
        }
        IOObjectRelease(citer);
        IOObjectRelease(cd);
        if (!isvc) {
            eprint(@"f310_bridge: no IOUSBHostInterface found");
            return 1;
        }

        IOUSBHostInterface *iface = [[IOUSBHostInterface alloc]
            initWithIOService:isvc
                      options:0
                        queue:dispatch_get_global_queue(
                                  DISPATCH_QUEUE_PRIORITY_HIGH, 0)
                        error:&err
              interestHandler:nil];
        IOObjectRelease(isvc);
        if (!iface) {
            eprint([NSString stringWithFormat:
                @"f310_bridge: interface open failed: %@",
                err.localizedDescription]);
            return 1;
        }

        // ── Get interrupt IN pipe ─────────────────────────────────────
        IOUSBHostPipe *pipe = nil;
        for (int ep = 1; ep <= 8; ep++) {
            pipe = [iface copyPipeWithAddress:(0x80 | ep) error:&err];
            if (pipe) break;
        }
        if (!pipe) {
            eprint(@"f310_bridge: no interrupt IN pipe found");
            return 1;
        }

        // ── HID SET_IDLE — kickstart the interrupt endpoint ──────────────
        // The F310 may need a SET_IDLE request before it begins sending
        // HID reports via the interrupt IN pipe. Without this, the pipe
        // returns kIOReturnAborted.
        {
            IOUSBDeviceRequest req = {
                .bmRequestType = 0x21,   // HID class, Host→Device, Interface
                .bRequest = 0x0A,        // SET_IDLE
                .wValue = 0,             // duration=infinite, report=all
                .wIndex = 0,             // interface 0
                .wLength = 0             // no data phase
            };
            NSUInteger transferred = 0;
            BOOL ok = [dev sendDeviceRequest:req
                                        data:nil
                            bytesTransferred:&transferred
                           completionTimeout:1000  // 1 second timeout
                                       error:&err];
            if (ok) {
                eprint(@"f310_bridge: SET_IDLE ok");
            } else {
                char msg[256];
                snprintf(msg, sizeof(msg), "f310_bridge: SET_IDLE failed: %s",
                         err.localizedDescription.UTF8String ?: "?");
                eprint(@(msg));
            }
        }

        // Clear any stale stall on the interrupt pipe
        [pipe clearStallWithError:&err];

        eprint(@"f310_bridge: ready, outputting JSON to stdout");

        // ── Poll loop ─────────────────────────────────────────────────
        uint8_t   last[64] = {0};
        NSUInteger lastLen  = 0;

        int debugCount = 0;
        while (running) {
            NSMutableData *data = [NSMutableData dataWithLength:64];
            NSUInteger transferred = 0;
            if (![pipe sendIORequestWithData:data
                            bytesTransferred:&transferred
                           completionTimeout:0
                                       error:&err]) {
                if (debugCount < 10) {
                    char msg[256];
                    snprintf(msg, sizeof(msg), "  pipe read error: %s (domain=%s, code=%ld)",
                             err.localizedDescription.UTF8String ?: "?",
                             err.domain.UTF8String ?: "?",
                             (long)err.code);
                    eprint(@(msg));
                    debugCount++;
                }
                usleep(2000);
                continue;
            }

            if (transferred < 8) {
                if (debug && debugCount < 10) {
                    char msg[128];
                    snprintf(msg, sizeof(msg), "  got %zu bytes (need 8+)",
                             (unsigned long)transferred);
                    eprint(@(msg));
                    debugCount++;
                }
                usleep(2000);
                continue;
            }

            const uint8_t *b = data.bytes;

            // Debug: print raw hex on any change
            if (debug) {
                bool changed = (transferred != lastLen)
                               || (memcmp(b, last, transferred) != 0);
                if (changed) {
                    memcpy(last, b, transferred);
                    lastLen = transferred;
                    char hex[256];
                    int pos = 0;
                    for (NSUInteger i = 0; i < transferred && pos < 250; i++) {
                        pos += snprintf(hex + pos, sizeof(hex) - pos,
                                        "%02x ", b[i]);
                    }
                    fprintf(stderr, "[%zu] %s\n", transferred, hex);
                }
            }

            // ── Parse F310 D-mode HID report ──────────────────────────
            //
            // Standard 8-byte report:
            //   [0]   Left stick X    (0..255, center 127)
            //   [1]   Left stick Y    (0..255, center 127)
            //   [2]   Right stick X   (0..255, center 127)
            //   [3]   Right stick Y   (0..255, center 127)
            //   [4]   Hat (lo nibble) + extra btn (hi nibble/bit7)
            //   [5]   Buttons 1-8 (bits 0-7: X,A,B,Y,LB,RB,LT,RT)
            //   [6]   Buttons 9-12 (bits 0-3: Back,Start,L3,R3)
            //   [7]   Reserved or extra axis data
            //
            // If report > 8 bytes, bytes 8+ may contain analog triggers.

            // Axes: normalize 0..255 → -1.0..1.0
            double lx = (b[0] - 127.5) / 127.5;
            double ly = (b[1] - 127.5) / 127.5;
            double rx = (b[2] - 127.5) / 127.5;
            double ry = (b[3] - 127.5) / 127.5;

            // Analog triggers (if present in extended report)
            // Normalize to -1..1 (matching pygame/SDL2 convention):
            //   -1.0 = released, +1.0 = fully pulled
            double lt_analog = -1.0;
            double rt_analog = -1.0;
            if (transferred >= 10) {
                lt_analog = (b[8] - 127.5) / 127.5;
                rt_analog = (b[9] - 127.5) / 127.5;
            }

            // Hat switch: 4-bit value
            // 0=N,1=NE,2=E,3=SE,4=S,5=SW,6=W,7=NW,8=center
            int hatRaw = b[4] & 0x0f;
            int hatX = 0, hatY = 0;
            if (hatRaw <= 7) {
                if (hatRaw == 0 || hatRaw == 1 || hatRaw == 7) hatY = 1;
                if (hatRaw == 3 || hatRaw == 4 || hatRaw == 5) hatY = -1;
                if (hatRaw == 5 || hatRaw == 6 || hatRaw == 7) hatX = -1;
                if (hatRaw == 1 || hatRaw == 2 || hatRaw == 3) hatX = 1;
            }

            // Buttons: 16-bit bitmap from bytes 5-6, remapped to SDL2 order
            // HID report bits → SDL2 button numbers are identity-shifted:
            //   HID btn  (byte 5 bit N)   → SDL btn N
            //   HID btn  (byte 6 bit N-8) → SDL btn N
            uint16_t rawBits = b[5] | ((uint16_t)b[6] << 8);

            // Logo button: byte 4 bit 7 or byte 6 bit 4
            bool logo = (b[4] >> 7) & 1;
            if (!logo && transferred >= 7) {
                logo = (b[6] >> 4) & 1;
            }

            // Output SDL2-compatible button array (13 buttons)
            // [0]=X, [1]=A, [2]=B, [3]=Y, [4]=LB, [5]=RB,
            // [6]=LT(dig), [7]=RT(dig), [8]=Back, [9]=Start,
            // [10]=L3, [11]=R3, [12]=Logo
            int sdl[13];
            for (int i = 0; i < 12; i++) sdl[i] = (rawBits >> i) & 1;
            sdl[12] = logo ? 1 : 0;

            // ── JSON line to stdout ───────────────────────────────────
            // Raw hex for debugging button mapping (8 bytes)
            char rawHex[24];
            int rpos = 0;
            for (int i = 0; i < 8; i++) {
                rpos += snprintf(rawHex + rpos, sizeof(rawHex) - rpos,
                                 "%02x", b[i]);
            }

            char axesBuf[96];
            snprintf(axesBuf, sizeof(axesBuf),
                     "%.4f,%.4f,%.4f,%.4f,%.4f,%.4f",
                     lx, ly, rx, ry, lt_analog, rt_analog);

            char btnBuf[80];
            int pos = 0;
            for (int i = 0; i < 13; i++) {
                pos += snprintf(btnBuf + pos, sizeof(btnBuf) - pos,
                                "%s%d", i > 0 ? "," : "", sdl[i]);
            }

            double ts = [[NSDate date] timeIntervalSince1970];
            printf("{\"ts\":%.3f,\"raw\":\"%s\",\"axes\":[%s],\"buttons\":[%s],\"hat\":[%d,%d]}\n",
                   ts, rawHex, axesBuf, btnBuf, hatX, hatY);
            fflush(stdout);

            // 4ms ≈ 250Hz (matches F310 interrupt endpoint interval)
            usleep(4000);
        }

        eprint(@"f310_bridge: shutting down");
    }
    return 0;
}
