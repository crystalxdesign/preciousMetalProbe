// Original LC ring-down acquisition firmware for Raspberry Pi Pico / RP2040.
// GP15 -> TMUX1101 SEL; buffered TANK voltage -> GP26 / ADC0.
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "pico/stdlib.h"
#include "pico/stdio_usb.h"
#include "hardware/adc.h"
#include "hardware/dma.h"
#include "hardware/pio.h"
#include "hardware/clocks.h"
#include "hardware/sync.h"
#include "hardware/regs/adc.h"
#include "excite.pio.h"

#define ADC_PIN 26u
#define EXCITE_PIN 15u
#define SAMPLE_COUNT 2048u
#define PRE_DELAY_US 128u
#define PULSE_US 5u // must match the PIO instruction's [4] delay
#define CAPTURE_TIMEOUT_US 20000u
#define SETTLE_MS 20u

static uint16_t samples[SAMPLE_COUNT];
static PIO pulse_pio = pio0;
static uint pulse_sm, pulse_offset;
static int capture_dma, stop_dma;
static uint32_t stop_cs;
static uint32_t sequence;

typedef struct {
    bool timeout, fifo_over, fifo_under, pulse_done;
    uint32_t adc_errors, rail_samples;
    double rise_us_est, fall_us_est;
    uint32_t launch_bracket_us;
} capture_info;

static void pulse_reset(void) {
    pio_sm_set_enabled(pulse_pio, pulse_sm, false);
    pio_sm_clear_fifos(pulse_pio, pulse_sm);
    pio_sm_restart(pulse_pio, pulse_sm);
    pio_sm_clkdiv_restart(pulse_pio, pulse_sm);
    pio_sm_exec(pulse_pio, pulse_sm, pio_encode_jmp(pulse_offset));
    pio_sm_set_pins_with_mask(pulse_pio, pulse_sm, 0, 1u << EXCITE_PIN);
    pio_interrupt_clear(pulse_pio, 0);
}

static void hardware_init(void) {
    // Safe low immediately; the external 100k pulldown also covers reset/boot.
    gpio_init(EXCITE_PIN);
    gpio_put(EXCITE_PIN, false);
    gpio_set_dir(EXCITE_PIN, GPIO_OUT);
    adc_init();
    adc_gpio_init(ADC_PIN);
    adc_select_input(0);
    adc_set_round_robin(0);
    adc_set_clkdiv(0); // 48MHz / 96 = 500000 samples/s
    // Retain all 12 data bits, plus the per-conversion error in bit 15.
    adc_fifo_setup(true, true, 1, true, false);
    capture_dma = dma_claim_unused_channel(true);
    stop_dma = dma_claim_unused_channel(true);

    pulse_sm = pio_claim_unused_sm(pulse_pio, true);
    pulse_offset = pio_add_program(pulse_pio, &excite_program);
    pio_sm_config c = excite_program_get_default_config(pulse_offset);
    sm_config_set_set_pins(&c, EXCITE_PIN, 1);
    sm_config_set_out_shift(&c, true, false, 32);
    sm_config_set_clkdiv(&c, (float)clock_get_hz(clk_sys) / 1000000.0f);
    pio_gpio_init(pulse_pio, EXCITE_PIN);
    pio_sm_init(pulse_pio, pulse_sm, pulse_offset, &c);
    pio_sm_set_consecutive_pindirs(pulse_pio, pulse_sm, EXCITE_PIN, 1, true);
    pulse_reset();
}

static capture_info capture(void) {
    capture_info info = {0};
    sleep_ms(SETTLE_MS);
    adc_run(false);
    while (!(adc_hw->cs & ADC_CS_READY_BITS)) tight_loop_contents();
    adc_fifo_drain();
    // W1C flags: clear before arming so errors belong to this capture.
    adc_hw->cs |= ADC_CS_ERR_STICKY_BITS;
    adc_hw->fcs |= ADC_FCS_OVER_BITS | ADC_FCS_UNDER_BITS;
    memset(samples, 0, sizeof samples);
    pulse_reset();
    pio_sm_put_blocking(pulse_pio, pulse_sm, PRE_DELAY_US - 3u);

    // A second DMA channel stops the ADC in hardware after the last sample.
    // This avoids false FIFO overflow if a USB interrupt delays the CPU.
    stop_cs = adc_hw->cs & ~(ADC_CS_START_MANY_BITS | ADC_CS_START_ONCE_BITS |
                            ADC_CS_ERR_STICKY_BITS);
    dma_channel_config s = dma_channel_get_default_config(stop_dma);
    channel_config_set_transfer_data_size(&s, DMA_SIZE_32);
    channel_config_set_read_increment(&s, false);
    channel_config_set_write_increment(&s, false);
    dma_channel_configure(stop_dma, &s, &adc_hw->cs, &stop_cs, 1, false);

    dma_channel_config c = dma_channel_get_default_config(capture_dma);
    channel_config_set_transfer_data_size(&c, DMA_SIZE_16);
    channel_config_set_read_increment(&c, false);
    channel_config_set_write_increment(&c, true);
    channel_config_set_dreq(&c, DREQ_ADC);
    channel_config_set_chain_to(&c, stop_dma);
    channel_config_set_high_priority(&c, true);
    dma_channel_configure(capture_dma, &c, samples, &adc_hw->fifo,
                          SAMPLE_COUNT, true);

    // Disable interrupts only over the launch sequence (a few us).
    // ADC and PIO have different clocks: this is NOT exact sample-edge sync.
    uint32_t irq_state = save_and_disable_interrupts();
    uint64_t a0 = time_us_64();
    adc_run(true);
    uint64_t a1 = time_us_64();
    uint64_t p0 = time_us_64();
    pio_sm_set_enabled(pulse_pio, pulse_sm, true);
    uint64_t p1 = time_us_64();
    restore_interrupts(irq_state);
    info.rise_us_est = (double)((int64_t)(p0 + p1) - (int64_t)(a0 + a1)) / 2.0
                       + PRE_DELAY_US;
    info.fall_us_est = info.rise_us_est + PULSE_US;
    info.launch_bracket_us = (uint32_t)((a1 - a0) + (p1 - p0));

    uint64_t deadline = a0 + CAPTURE_TIMEOUT_US;
    while (dma_channel_is_busy(capture_dma) ||
           (adc_hw->cs & ADC_CS_START_MANY_BITS)) {
        if (time_us_64() >= deadline) {
            info.timeout = true;
            break;
        }
        tight_loop_contents();
    }
    adc_run(false);
    if (info.timeout) {
        dma_channel_abort(capture_dma);
        dma_channel_abort(stop_dma);
    } else {
        dma_channel_wait_for_finish_blocking(stop_dma);
    }
    while (!(adc_hw->cs & ADC_CS_READY_BITS)) tight_loop_contents();
    info.fifo_over = (adc_hw->fcs & ADC_FCS_OVER_BITS) != 0;
    info.fifo_under = (adc_hw->fcs & ADC_FCS_UNDER_BITS) != 0;
    info.pulse_done = pio_interrupt_get(pulse_pio, 0);
    pulse_reset();
    adc_fifo_drain();
    for (uint i = 0; i < SAMPLE_COUNT; ++i) {
        if (samples[i] & 0x8000u) ++info.adc_errors;
        uint16_t raw = samples[i] & 0x0fffu;
        if (raw <= 16u || raw >= 4079u) ++info.rail_samples;
    }
    return info;
}

static uint32_t crc32_samples(void) {
    // Standard CRC-32/ISO-HDLC, over little-endian uint16 samples incl ERR.
    uint32_t crc = 0xffffffffu;
    for (uint i = 0; i < SAMPLE_COUNT; ++i) {
        for (uint b = 0; b < 2; ++b) {
            crc ^= (samples[i] >> (8u * b)) & 0xffu;
            for (uint k = 0; k < 8; ++k)
                crc = (crc >> 1) ^ ((crc & 1u) ? 0xedb88320u : 0u);
        }
    }
    return crc ^ 0xffffffffu;
}

static void send_frame(capture_info info) {
    uint32_t id = ++sequence;
    uint32_t fs = clock_get_hz(clk_adc) / 96u;
    printf("FRAME {\"protocol\":1,\"id\":%lu,\"n\":%u,\"fs_hz\":%lu,"
           "\"pulse_us\":%u,\"rise_us_est\":%.2f,\"fall_us_est\":%.2f,"
           "\"launch_bracket_us\":%lu,\"timeout\":%u,\"fifo_over\":%u,"
           "\"fifo_under\":%u,\"pulse_done\":%u,\"adc_errors\":%lu,"
           "\"rail_samples\":%lu,\"crc32\":%lu}\n",
           (unsigned long)id, SAMPLE_COUNT, (unsigned long)fs, PULSE_US,
           info.rise_us_est, info.fall_us_est, (unsigned long)info.launch_bracket_us,
           info.timeout, info.fifo_over, info.fifo_under, info.pulse_done,
           (unsigned long)info.adc_errors, (unsigned long)info.rail_samples,
           (unsigned long)crc32_samples());
    // Chunked text is inspectable in a serial terminal and easy to recover.
    for (uint start = 0; start < SAMPLE_COUNT; start += 32u) {
        printf("DATA %u", start);
        for (uint i = start; i < start + 32u && i < SAMPLE_COUNT; ++i)
            printf(",%u", (unsigned)samples[i]);
        putchar('\n');
    }
    printf("END %lu\n", (unsigned long)id);
    fflush(stdout);
}

int main(void) {
    hardware_init();
    stdio_init_all();
    // No unsolicited captures. Host requests one frame at a time with 'c\n'.
    char command[16];
    uint pos = 0;
    bool overflow = false;
    while (true) {
        if (!stdio_usb_connected()) { pos = 0; overflow = false; sleep_ms(10); continue; }
        int ch = getchar_timeout_us(10000);
        if (ch == PICO_ERROR_TIMEOUT) continue;
        if (ch == '\r') continue;
        if (ch == '\n') {
            command[pos] = '\0';
            if (!overflow && strcmp(command, "c") == 0) send_frame(capture());
            else if (!overflow && strcmp(command, "h") == 0) {
                puts("INFO lc_metal_capture protocol=1 c=capture h=help GP15=pulse GP26=ADC0");
                fflush(stdout);
            } else puts("ERROR command; use c or h");
            pos = 0; overflow = false;
        } else if (pos + 1u < sizeof command) command[pos++] = (char)ch;
        else overflow = true;
    }
}
