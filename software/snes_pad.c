/*
 * snes_pad.c - up to two original SNES controllers wired straight to a
 *              Raspberry Pi 4's GPIO, exposed to Linux/RetroArch as virtual
 *              gamepads (uinput).
 *
 * Build:  gcc -O2 -Wall -o snes_pad snes_pad.c
 * Run:    sudo ./snes_pad [-n pads] [-r poll_hz] [-t half_period_us] [-a cpu] [-v]
 *
 *   -n  number of pads, 1 or 2          (default 2)
 *   -r  polling rate in Hz              (default 1000)
 *   -t  half clock period in microsec   (default 6 = original SNES timing;
 *                                        2-3 works with most pads/short cables)
 *   -a  pin the daemon to this CPU core (use with isolcpus=<n> for best jitter)
 *   -v  print raw button state on every change (debugging)
 *
 * Wiring (BCM numbers; pads powered from 3.3 V, NOT 5 V).
 * LATCH and CLOCK are shared by both pads, like on a real SNES; each pad has
 * its own DATA line, so both are read in the same 160 us pass.
 *   LATCH (both pads) -> GPIO22 (header pin 15)
 *   CLOCK (both pads) -> GPIO27 (header pin 13)
 *   DATA  pad 1       -> GPIO17 (header pin 11)
 *   DATA  pad 2       -> GPIO10 (header pin 19)
 *   VCC   (both pads) -> 3V3    (header pin 17)
 *   GND   (both pads) -> GND    (header pin 9)
 *
 * All six wires sit on ONE row of the header, so a single 1x6 connector fits:
 *   pins  9    11     13     15     17    19
 *         GND  DATA1  CLOCK  LATCH  3V3   DATA2
 * GPIO10 is SPI0 MOSI: keep SPI disabled (raspi-config -> Interface -> SPI -> No).
 *
 * Raspberry Pi 4 (BCM2711) only: uses /dev/gpiomem register access.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <sched.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/file.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <linux/uinput.h>

#define PIN_CLOCK  27
#define PIN_LATCH  22
#define MAX_PADS   2
static const int PIN_DATA[MAX_PADS] = { 17, 10 };

/* ---- GPIO (BCM2711 registers, word offsets) ------------------------------ */
#define GPSET0   7      /* 0x1C */
#define GPCLR0   10     /* 0x28 */
#define GPLEV0   13     /* 0x34 */
#define PUPPDN0  57     /* 0xE4: GPIO_PUP_PDN_CNTRL_REG0 (BCM2711 only) */

static volatile uint32_t *gpio;

static int gpio_open(void)
{
    int fd = open("/dev/gpiomem", O_RDWR | O_SYNC);
    if (fd < 0) return -1;
    void *m = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    close(fd);
    if (m == MAP_FAILED) return -1;
    gpio = (volatile uint32_t *)m;
    return 0;
}

static void gpio_mode(int pin, int out)
{
    volatile uint32_t *r = &gpio[pin / 10];
    int sh = (pin % 10) * 3;
    uint32_t v = *r;
    v &= ~(7u << sh);
    v |= (uint32_t)(out ? 1 : 0) << sh;
    *r = v;
}

static void gpio_pull_up(int pin)
{
    volatile uint32_t *r = &gpio[PUPPDN0 + pin / 16];
    int sh = (pin % 16) * 2;
    uint32_t v = *r;
    v &= ~(3u << sh);
    v |= 1u << sh;                      /* 01 = pull-up */
    *r = v;
}

static inline void hi(int pin)  { gpio[GPSET0] = 1u << pin; }
static inline void lo(int pin)  { gpio[GPCLR0] = 1u << pin; }

/* ---- timing -------------------------------------------------------------- */
static inline uint64_t now_ns(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

static inline void delay_ns(uint64_t ns)
{
    uint64_t end = now_ns() + ns;
    while (now_ns() < end) { }
}

/* ---- SNES protocol ------------------------------------------------------- */
/*
 * Serial order (active low): B Y Select Start Up Down Left Right A X L R
 * Latch idles low, clock idles high. The pad's 4021 shifts on the rising clock
 * edge, so we sample at the end of the low phase. One GPLEV0 read samples the
 * data lines of both pads at once.
 * A CPU preemption mid-read only stretches a clock phase, which the static
 * CMOS shift register tolerates - it can delay a sample, never corrupt it.
 */
#define NBITS 12

static void snes_read(uint64_t half_ns, int npads, uint16_t out[MAX_PADS])
{
    uint16_t raw[MAX_PADS] = { 0, 0 };

    hi(PIN_LATCH);
    delay_ns(2 * half_ns);              /* 12 us at default timing */
    lo(PIN_LATCH);
    delay_ns(half_ns);

    for (int i = 0; i < NBITS; i++) {
        lo(PIN_CLOCK);
        delay_ns(half_ns);
        uint32_t lev = gpio[GPLEV0];
        for (int p = 0; p < npads; p++)
            if ((lev >> PIN_DATA[p]) & 1) raw[p] |= (uint16_t)(1u << i);
        hi(PIN_CLOCK);
        delay_ns(half_ns);
    }
    for (int p = 0; p < npads; p++)
        out[p] = (uint16_t)(~raw[p] & 0x0FFF);   /* 1 = pressed */
}

/* ---- uinput -------------------------------------------------------------- */
static const struct { int bit; int code; } btn[] = {
    { 0, BTN_SOUTH },   /* B      */
    { 1, BTN_WEST  },   /* Y      */
    { 2, BTN_SELECT},
    { 3, BTN_START },
    { 8, BTN_EAST  },   /* A      */
    { 9, BTN_NORTH },   /* X      */
    { 10, BTN_TL   },   /* L      */
    { 11, BTN_TR   },   /* R      */
};
#define NBTN ((int)(sizeof btn / sizeof btn[0]))
#define DPAD_MASK 0x00F0u   /* bits 4..7: up down left right */

static int uinput_open(const char *name, uint16_t product)
{
    int fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK);
    if (fd < 0) fd = open("/dev/input/uinput", O_WRONLY | O_NONBLOCK);
    if (fd < 0) return -1;

    ioctl(fd, UI_SET_EVBIT, EV_KEY);
    for (int i = 0; i < NBTN; i++) ioctl(fd, UI_SET_KEYBIT, btn[i].code);
    ioctl(fd, UI_SET_EVBIT, EV_ABS);
    ioctl(fd, UI_SET_ABSBIT, ABS_X);
    ioctl(fd, UI_SET_ABSBIT, ABS_Y);

    struct uinput_user_dev u;
    memset(&u, 0, sizeof u);
    snprintf(u.name, UINPUT_MAX_NAME_SIZE, "%s", name);
    u.id.bustype = BUS_VIRTUAL;
    u.id.vendor  = 0x1209;              /* pid.codes test VID/PID */
    u.id.product = product;
    u.id.version = 1;
    u.absmin[ABS_X] = -1; u.absmax[ABS_X] = 1;
    u.absmin[ABS_Y] = -1; u.absmax[ABS_Y] = 1;

    if (write(fd, &u, sizeof u) != (ssize_t)sizeof u || ioctl(fd, UI_DEV_CREATE) < 0) {
        close(fd);
        return -1;
    }
    return fd;
}

static void emit(int fd, uint16_t prev, uint16_t cur)
{
    struct input_event ev[16];
    int n = 0;
    uint16_t diff = prev ^ cur;

    memset(ev, 0, sizeof ev);
    for (int i = 0; i < NBTN; i++) {
        if ((diff >> btn[i].bit) & 1) {
            ev[n].type  = EV_KEY;
            ev[n].code  = btn[i].code;
            ev[n].value = (cur >> btn[i].bit) & 1;
            n++;
        }
    }
    if (diff & DPAD_MASK) {
        ev[n].type = EV_ABS; ev[n].code = ABS_X;
        ev[n].value = ((cur >> 7) & 1) - ((cur >> 6) & 1);   /* right - left */
        n++;
        ev[n].type = EV_ABS; ev[n].code = ABS_Y;
        ev[n].value = ((cur >> 5) & 1) - ((cur >> 4) & 1);   /* down - up */
        n++;
    }
    if (!n) return;
    ev[n].type = EV_SYN; ev[n].code = SYN_REPORT; n++;
    if (write(fd, ev, (size_t)n * sizeof ev[0]) < 0 && errno != EAGAIN)
        perror("uinput write");
}

/* ---- main ---------------------------------------------------------------- */
static volatile sig_atomic_t running = 1;
static void on_sig(int s) { (void)s; running = 0; }

static void usage(const char *p)
{
    fprintf(stderr, "usage: %s [-n pads(1-2)] [-r poll_hz] [-t half_period_us] [-a cpu] [-v]\n", p);
    exit(2);
}

int main(int argc, char **argv)
{
    double hz = 1000.0, half_us = 6.0;
    int cpu = -1, verbose = 0, npads = 2, c;

    while ((c = getopt(argc, argv, "n:r:t:a:v")) != -1) {
        switch (c) {
        case 'n': npads = atoi(optarg); break;
        case 'r': hz = atof(optarg); break;
        case 't': half_us = atof(optarg); break;
        case 'a': cpu = atoi(optarg); break;
        case 'v': verbose = 1; break;
        default: usage(argv[0]);
        }
    }
    if (npads < 1 || npads > MAX_PADS || hz < 10 || hz > 8000 ||
        half_us < 0.5 || half_us > 20) usage(argv[0]);

    /* Only one daemon may drive CLOCK/LATCH; two at once scramble every read. */
    int lockfd = open("/run/snes_pad.lock", O_CREAT | O_RDWR, 0644);
    if (lockfd < 0) lockfd = open("/tmp/snes_pad.lock", O_CREAT | O_RDWR, 0644);
    if (lockfd >= 0 && flock(lockfd, LOCK_EX | LOCK_NB) < 0) {
        fprintf(stderr, "snes_pad: another instance is already running "
                        "(try: sudo systemctl stop snes-pad)\n");
        return 1;
    }

    uint64_t half_ns  = (uint64_t)(half_us * 1000.0);
    uint64_t period_ns = (uint64_t)(1e9 / hz);
    uint64_t read_ns   = half_ns * (2 + 1 + 2 * NBITS);
    if (read_ns * 12 / 10 > period_ns)
        fprintf(stderr, "warning: a read takes ~%.0f us, poll period is %.0f us\n",
                read_ns / 1e3, period_ns / 1e3);

    if (gpio_open() < 0) { perror("/dev/gpiomem (run as root or join 'gpio' group)"); return 1; }

    int ufd[MAX_PADS] = { -1, -1 };
    for (int p = 0; p < npads; p++) {
        char name[32];
        snprintf(name, sizeof name, "SNES GPIO Pad %d", p + 1);
        ufd[p] = uinput_open(name, (uint16_t)(p + 1));
        if (ufd[p] < 0) { perror("/dev/uinput (run as root)"); return 1; }
    }

    gpio_mode(PIN_LATCH, 1); lo(PIN_LATCH);
    gpio_mode(PIN_CLOCK, 1); hi(PIN_CLOCK);
    for (int p = 0; p < npads; p++) {
        gpio_mode(PIN_DATA[p], 0);
        gpio_pull_up(PIN_DATA[p]);      /* unplugged pad reads as "nothing pressed" */
    }

    if (cpu >= 0) {
        cpu_set_t set; CPU_ZERO(&set); CPU_SET(cpu, &set);
        if (sched_setaffinity(0, sizeof set, &set) < 0) perror("sched_setaffinity");
    }
    struct sched_param sp = { .sched_priority = 80 };
    if (sched_setscheduler(0, SCHED_FIFO, &sp) < 0) perror("SCHED_FIFO (continuing without RT)");
    mlockall(MCL_CURRENT | MCL_FUTURE);

    signal(SIGINT, on_sig);
    signal(SIGTERM, on_sig);

    fprintf(stderr, "snes_pad: %d pad(s), %.0f Hz, half period %.1f us, read ~%.0f us\n",
            npads, hz, half_us, read_ns / 1e3);
    usleep(200000);                     /* let udev/RetroArch notice the new devices */

    uint16_t prev[MAX_PADS] = { 0, 0 }, cur[MAX_PADS] = { 0, 0 };
    struct timespec next;
    clock_gettime(CLOCK_MONOTONIC, &next);

    while (running) {
        next.tv_nsec += (long)period_ns;
        while (next.tv_nsec >= 1000000000L) { next.tv_nsec -= 1000000000L; next.tv_sec++; }
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &next, NULL);

        snes_read(half_ns, npads, cur);
        for (int p = 0; p < npads; p++) {
            if (cur[p] != prev[p]) {
                emit(ufd[p], prev[p], cur[p]);
                if (verbose) printf("pad%d %03x\n", p + 1, cur[p]), fflush(stdout);
                prev[p] = cur[p];
            }
        }
    }

    for (int p = 0; p < npads; p++) { ioctl(ufd[p], UI_DEV_DESTROY); close(ufd[p]); }
    gpio_mode(PIN_LATCH, 0); gpio_mode(PIN_CLOCK, 0);
    return 0;
}
