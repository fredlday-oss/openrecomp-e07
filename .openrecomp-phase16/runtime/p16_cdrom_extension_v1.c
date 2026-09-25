/*
 * OpenRecomp Phase 16 - deterministic CD-ROM sector delivery extension (OpenRecomp-authored).
 *
 * Provides a bounds-checked, read-only sector delivery service sourcing authentic
 * Mode 2 Form 1 sectors directly from the private disc image file.
 *
 * Conforms to fail-closed discipline:
 * - Out-of-bounds LBA fails closed (returns P9_RT_UNSUPPORTED_OPERATION).
 * - Invalid sync pattern fails closed.
 * - Missing or unreadable file fails closed.
 * - Destination outside valid guest RAM fails closed.
 * - Records non-reconstructive operational counters.
 */

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define P16_CD_RAW_SECTOR_SIZE 2352u
#define P16_CD_USER_DATA_OFFSET 24u
#define P16_CD_USER_DATA_SIZE 2048u
#define P16_CD_MAX_LBA 174087u

static char g_p16_disc_path[1024];
static uint64_t g_p16_cdrom_read_calls;
static uint64_t g_p16_cdrom_sectors_delivered;
static uint64_t g_p16_cdrom_bytes_delivered;
static uint64_t g_p16_cdrom_read_failures;
static uint32_t g_p16_cdrom_last_lba;
static uint32_t g_p16_cdrom_last_count;

static const unsigned char g_p16_sync_pattern[12] = {
    0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00
};

void p16_cdrom_set_disc_path(const char *path)
{
    if (path != NULL && strlen(path) < sizeof(g_p16_disc_path)) {
        strncpy(g_p16_disc_path, path, sizeof(g_p16_disc_path) - 1);
        g_p16_disc_path[sizeof(g_p16_disc_path) - 1] = '\0';
    }
}

const char *p16_cdrom_get_disc_path(void)
{
    return g_p16_disc_path;
}

uint64_t p16_cdrom_read_calls(void) { return g_p16_cdrom_read_calls; }
uint64_t p16_cdrom_sectors_delivered(void) { return g_p16_cdrom_sectors_delivered; }
uint64_t p16_cdrom_bytes_delivered(void) { return g_p16_cdrom_bytes_delivered; }
uint64_t p16_cdrom_read_failures(void) { return g_p16_cdrom_read_failures; }
uint32_t p16_cdrom_last_lba(void) { return g_p16_cdrom_last_lba; }
uint32_t p16_cdrom_last_count(void) { return g_p16_cdrom_last_count; }

int p16_cdrom_read_user_sectors(uint32_t start_lba, uint32_t count, uint32_t dest_address)
{
    FILE *fp;
    uint32_t ram_offset = 0u;
    uint32_t i;
    unsigned char sector_buf[P16_CD_RAW_SECTOR_SIZE];
    uint64_t total_bytes;

    ++g_p16_cdrom_read_calls;

    total_bytes = (uint64_t)count * P16_CD_USER_DATA_SIZE;
    if (count == 0u || start_lba >= P16_CD_MAX_LBA || start_lba + count > P16_CD_MAX_LBA) {
        ++g_p16_cdrom_read_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }

    if (!p9_translate_ram((uint64_t)dest_address, total_bytes, &ram_offset)) {
        ++g_p16_cdrom_read_failures;
        return P9_RT_MEMORY_OUT_OF_RANGE;
    }

    if (g_p16_disc_path[0] == '\0') {
        ++g_p16_cdrom_read_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }

    fp = fopen(g_p16_disc_path, "rb");
    if (fp == NULL) {
        ++g_p16_cdrom_read_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }

#if defined(_WIN32)
    if (_fseeki64(fp, (int64_t)start_lba * P16_CD_RAW_SECTOR_SIZE, SEEK_SET) != 0) {
#else
    if (fseeko(fp, (off_t)start_lba * P16_CD_RAW_SECTOR_SIZE, SEEK_SET) != 0) {
#endif
        fclose(fp);
        ++g_p16_cdrom_read_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }

    for (i = 0u; i < count; ++i) {
        if (fread(sector_buf, 1, P16_CD_RAW_SECTOR_SIZE, fp) != P16_CD_RAW_SECTOR_SIZE) {
            fclose(fp);
            ++g_p16_cdrom_read_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        if (memcmp(sector_buf, g_p16_sync_pattern, sizeof(g_p16_sync_pattern)) != 0) {
            fclose(fp);
            ++g_p16_cdrom_read_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        memcpy(g_p9_ram + ram_offset + (i * P16_CD_USER_DATA_SIZE),
               sector_buf + P16_CD_USER_DATA_OFFSET,
               P16_CD_USER_DATA_SIZE);
    }

    fclose(fp);

    g_p16_cdrom_sectors_delivered += count;
    g_p16_cdrom_bytes_delivered += total_bytes;
    g_p16_cdrom_last_lba = start_lba;
    g_p16_cdrom_last_count = count;

    return P9_RT_OK;
}
