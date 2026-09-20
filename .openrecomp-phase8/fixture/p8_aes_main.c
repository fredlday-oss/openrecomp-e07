/*
 * OpenRecomp Phase 8 - original AES-128 ECB known-answer harness.
 *
 * Runs the FIPS-197 C.1 AES-128 known-answer vector through the upstream
 * tiny-AES-c implementation and emits the 16 ciphertext bytes as lowercase
 * hex over the fixture output window.  Returns 0 when the vector matches.
 */

#include "aes.h"

extern void p8_out_byte(char c);

static const unsigned char p8_key[16] = {
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
    0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f,
};

static const unsigned char p8_plaintext[16] = {
    0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77,
    0x88, 0x99, 0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff,
};

static const unsigned char p8_expected[16] = {
    0x69, 0xc4, 0xe0, 0xd8, 0x6a, 0x7b, 0x04, 0x30,
    0xd8, 0xcd, 0xb7, 0x80, 0x70, 0xb4, 0xc5, 0x5a,
};

static const char p8_hex_digits[16] = "0123456789abcdef";

static void p8_hex_byte(unsigned char value)
{
    p8_out_byte(p8_hex_digits[(value >> 4) & 0x0f]);
    p8_out_byte(p8_hex_digits[value & 0x0f]);
}

int p8_main(void)
{
    struct AES_ctx ctx;
    unsigned char buffer[16];
    int index;
    int status = 0;

    for (index = 0; index < 16; index++)
    {
        buffer[index] = p8_plaintext[index];
    }

    AES_init_ctx(&ctx, p8_key);
    AES_ECB_encrypt(&ctx, buffer);

    for (index = 0; index < 16; index++)
    {
        p8_hex_byte(buffer[index]);
        if (buffer[index] != p8_expected[index])
        {
            status = 1;
        }
    }
    p8_out_byte('\n');
    return status;
}
