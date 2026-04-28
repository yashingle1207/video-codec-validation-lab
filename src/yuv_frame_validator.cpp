/*
 * Author:  Yash Daniel Ingle
 * Email:   yashingle1207@gmail.com
 * GitHub:  github.com/yashingle1207
 * Project: Video Codec Validation Lab
 * File:    yuv_frame_validator.cpp
 * Purpose: Read a raw YUV420p file and emit per-frame pixel statistics and
 *          SHA-256 hashes as a JSON array to stdout for bitstream validation.
 *
 * Description:
 *   Parses a headerless YUV420p binary file frame-by-frame and computes Y-plane
 *   mean, min, max, and variance; U/V-plane means; and a SHA-256 hash of each
 *   frame's raw bytes.  Three anomaly flags are set per frame: black_frame
 *   (Y mean < 5), frozen_frame (hash identical to previous frame), and
 *   clipped_frame (Y max == 255 AND Y min == 0 simultaneously).  The SHA-256
 *   implementation is self-contained - no OpenSSL or other external library
 *   is required, making this binary portable across Linux, macOS, and Windows.
 *
 * Build:
 *   g++ -std=c++14 -O2 -Wall -Wextra -o yuv_frame_validator src/yuv_frame_validator.cpp
 *
 * Usage:
 *   ./yuv_frame_validator <yuv_file> <width> <height> <frame_count>
 */

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

// =============================================================================
// Self-contained SHA-256 implementation (FIPS 180-4)
// =============================================================================
// SHA-256 produces a 32-byte (256-bit) digest used here to fingerprint each
// raw YUV frame.  Identical digests across consecutive frames indicate a frozen
// encoder output - a common symptom of DMA stalls or encoder hang in HW bring-up.

namespace sha256 {

// Round constants - first 32 bits of the fractional parts of cube roots of
// the first 64 primes (FIPS 180-4, Section 4.2.2).
static const uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
    0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
    0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
    0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
};

// Circular right-rotate for uint32_t.
static inline uint32_t rotr(uint32_t x, int n) {
    return (x >> n) | (x << (32 - n));
}

// SHA-256 logical functions (FIPS 180-4, Section 4.1.2).
static inline uint32_t Ch (uint32_t x, uint32_t y, uint32_t z) { return (x & y) ^ (~x & z); }
static inline uint32_t Maj(uint32_t x, uint32_t y, uint32_t z) { return (x & y) ^ (x & z) ^ (y & z); }
static inline uint32_t S0 (uint32_t x) { return rotr(x, 2)  ^ rotr(x, 13) ^ rotr(x, 22); }
static inline uint32_t S1 (uint32_t x) { return rotr(x, 6)  ^ rotr(x, 11) ^ rotr(x, 25); }
static inline uint32_t s0 (uint32_t x) { return rotr(x, 7)  ^ rotr(x, 18) ^ (x >> 3);  }
static inline uint32_t s1 (uint32_t x) { return rotr(x, 17) ^ rotr(x, 19) ^ (x >> 10); }

struct Context {
    uint32_t h[8];      // Working hash state (8 x 32-bit words = 256 bits total).
    uint64_t bits;      // Total number of input bits processed.
    uint8_t  buf[64];   // Partial block buffer (SHA-256 processes 512-bit blocks).
    int      buf_len;   // Number of valid bytes currently in buf.

    Context() : bits(0), buf_len(0) {
        // Initial hash values - first 32 bits of fractional parts of sqrt of
        // the first 8 primes (FIPS 180-4, Section 5.3.3).
        h[0]=0x6a09e667; h[1]=0xbb67ae85; h[2]=0x3c6ef372; h[3]=0xa54ff53a;
        h[4]=0x510e527f; h[5]=0x9b05688c; h[6]=0x1f83d9ab; h[7]=0x5be0cd19;
    }

    // Process one 64-byte (512-bit) block through the SHA-256 compression function.
    void process_block(const uint8_t* b) {
        uint32_t w[64];
        // Load first 16 words from the block (big-endian).
        for (int i = 0; i < 16; ++i)
            w[i] = (uint32_t(b[i*4])   << 24) | (uint32_t(b[i*4+1]) << 16)
                 | (uint32_t(b[i*4+2]) <<  8) |  uint32_t(b[i*4+3]);
        // Expand to 64 words via the message schedule.
        for (int i = 16; i < 64; ++i)
            w[i] = s1(w[i-2]) + w[i-7] + s0(w[i-15]) + w[i-16];

        // Working variables - copies of the current hash state.
        uint32_t a=h[0], b2=h[1], c=h[2], d=h[3],
                 e=h[4], f=h[5], g=h[6], hh=h[7];

        // 64-round compression loop.
        for (int i = 0; i < 64; ++i) {
            uint32_t t1 = hh + S1(e) + Ch(e,f,g) + K[i] + w[i];
            uint32_t t2 = S0(a) + Maj(a,b2,c);
            hh=g; g=f; f=e; e=d+t1;
            d=c;  c=b2; b2=a; a=t1+t2;
        }
        // Add compressed chunk to current hash state.
        h[0]+=a; h[1]+=b2; h[2]+=c; h[3]+=d;
        h[4]+=e; h[5]+=f;  h[6]+=g; h[7]+=hh;
    }

    // Feed len bytes of data into the hash context.
    void update(const uint8_t* data, size_t len) {
        bits += uint64_t(len) * 8;  // track total bit count for the length field
        for (size_t i = 0; i < len; ++i) {
            buf[buf_len++] = data[i];
            if (buf_len == 64) { process_block(buf); buf_len = 0; }
        }
    }

    // Finalise: apply padding and write the 32-byte digest to out[].
    void finalise(uint8_t out[32]) {
        // Append the mandatory 0x80 padding byte.
        buf[buf_len++] = 0x80;
        // If the buffer is too full for the 8-byte length field, flush it first.
        if (buf_len > 56) {
            while (buf_len < 64) buf[buf_len++] = 0;
            process_block(buf); buf_len = 0;
        }
        // Zero-pad up to byte 56, then append 64-bit big-endian bit count.
        while (buf_len < 56) buf[buf_len++] = 0;
        for (int i = 7; i >= 0; --i) buf[buf_len++] = uint8_t(bits >> (i * 8));
        process_block(buf);
        // Write 8 x 32-bit hash words as big-endian bytes (32 bytes total).
        for (int i = 0; i < 8; ++i) {
            out[i*4+0] = uint8_t(h[i] >> 24);
            out[i*4+1] = uint8_t(h[i] >> 16);
            out[i*4+2] = uint8_t(h[i] >>  8);
            out[i*4+3] = uint8_t(h[i]);
        }
    }
};

// Compute SHA-256 of data[0..len-1] and return the digest as a 64-char hex string.
// SHA-256 digest length is always exactly 32 bytes = 64 hexadecimal characters.
static std::string hash_hex(const uint8_t* data, size_t len) {
    Context ctx;
    ctx.update(data, len);
    uint8_t digest[32];  // 32 bytes = 256 bits = SHA-256 output length
    ctx.finalise(digest);
    std::ostringstream oss;
    oss << std::hex << std::setfill('0');
    for (int i = 0; i < 32; ++i)
        oss << std::setw(2) << unsigned(digest[i]);
    return oss.str();
}

} // namespace sha256

// =============================================================================
// YUV plane statistics
// =============================================================================

struct PlaneStat {
    double mean  = 0.0;
    double min_v = 255.0;
    double max_v = 0.0;
    double var   = 0.0;
};

// Compute mean, min, max, and population variance for a plane of n_pixels bytes.
static PlaneStat compute_plane_stat(const uint8_t* plane, size_t n_pixels)
{
    PlaneStat s;
    double sum = 0.0;
    uint8_t pmin = 255, pmax = 0;

    // Single pass: accumulate sum and track extrema simultaneously.
    for (size_t i = 0; i < n_pixels; ++i) {
        uint8_t v = plane[i];
        sum += v;
        if (v < pmin) pmin = v;
        if (v > pmax) pmax = v;
    }
    s.mean  = sum / double(n_pixels);
    s.min_v = pmin;
    s.max_v = pmax;

    // Second pass: compute population variance = E[(X - Î¼)²].
    double var_acc = 0.0;
    for (size_t i = 0; i < n_pixels; ++i) {
        double diff = double(plane[i]) - s.mean;
        var_acc += diff * diff;
    }
    s.var = var_acc / double(n_pixels);
    return s;
}

// Compute mean pixel value of a chroma plane (U or V).
static double plane_mean(const uint8_t* plane, size_t n_pixels)
{
    double sum = 0.0;
    for (size_t i = 0; i < n_pixels; ++i) sum += plane[i];
    return sum / double(n_pixels);
}

// =============================================================================
// Minimal JSON helpers (avoids any external JSON library dependency)
// =============================================================================

static std::string fmt_dbl(double v, int prec = 4)
{
    std::ostringstream o;
    o << std::fixed << std::setprecision(prec) << v;
    return o.str();
}

static const char* fmt_bool(bool v) { return v ? "true" : "false"; }

// =============================================================================
// main
// =============================================================================

int main(int argc, char* argv[])
{
    if (argc != 5) {
        std::cerr << "Usage: " << argv[0]
                  << " <yuv_file> <width> <height> <frame_count>\n"
                  << "  yuv_file    : raw YUV420p binary file\n"
                  << "  width       : frame width in pixels\n"
                  << "  height      : frame height in pixels\n"
                  << "  frame_count : number of frames to validate\n";
        return 1;
    }

    const std::string path  = argv[1];
    const int width         = std::atoi(argv[2]);
    const int height        = std::atoi(argv[3]);
    const int nframes       = std::atoi(argv[4]);

    if (width <= 0 || height <= 0 || nframes <= 0) {
        std::cerr << "Error: width, height, and frame_count must be positive integers.\n";
        return 1;
    }

    // YUV420p (4:2:0 planar) layout: Y plane = W*H bytes, each chroma plane = W*H/4 bytes.
    // Total frame size = W*H + W*H/4 + W*H/4 = 3/2 * W * H bytes.
    const size_t y_n  = size_t(width) * size_t(height);        // luma pixels
    const size_t uv_n = y_n / 4;                               // each chroma plane (2x sub-sampled in each dimension)
    const size_t fsz  = y_n + 2 * uv_n;                        // 1.5 bytes per pixel

    std::ifstream fin(path, std::ios::binary);
    if (!fin) {
        std::cerr << "Error: cannot open file '" << path << "'\n";
        return 1;
    }

    std::vector<uint8_t> buf(fsz);
    std::string prev_hash;
    bool first = true;

    std::cout << "[\n";  // begin JSON array

    for (int fn = 0; fn < nframes; ++fn) {
        fin.read(reinterpret_cast<char*>(buf.data()),
                 static_cast<std::streamsize>(fsz));

        // Short read = file is shorter than the declared frame count.
        if (static_cast<size_t>(fin.gcount()) != fsz) {
            std::cerr << "Warning: short read at frame " << fn
                      << " (got " << fin.gcount() << " bytes, expected " << fsz << ")\n";
            break;
        }

        // Pointers into the frame buffer for each YUV plane.
        const uint8_t* y_plane = buf.data();
        const uint8_t* u_plane = y_plane + y_n;    // U plane starts after Y
        const uint8_t* v_plane = u_plane + uv_n;   // V plane starts after U

        // Compute Y-plane statistics (mean, min, max, variance).
        PlaneStat ys = compute_plane_stat(y_plane, y_n);
        // For chroma planes we only need the mean for anomaly detection.
        double um = plane_mean(u_plane, uv_n);
        double vm = plane_mean(v_plane, uv_n);

        // SHA-256 the entire frame (Y + U + V planes concatenated).
        std::string h = sha256::hash_hex(buf.data(), fsz);

        // --- Anomaly detection flags ---

        // Black frame: Y mean < 5 (near-black; 0 = pure black in 8-bit YUV).
        bool black_frame = (ys.mean < 5.0);

        // Frozen frame: same raw bytes as the previous frame.
        // Indicates the encoder outputted a duplicate frame (DMA stall / hang).
        bool frozen_frame = (!first && h == prev_hash);

        // Clipped frame: Y spans the full [0, 255] range simultaneously.
        // Indicates the encoder exceeded the codec's dynamic range on both ends.
        bool clipped_frame = (static_cast<uint8_t>(ys.max_v) == 255 &&
                              static_cast<uint8_t>(ys.min_v) == 0);

        // Emit JSON object for this frame.
        if (fn > 0) std::cout << ",\n";
        std::cout << "  {\n"
                  << "    \"frame\": "         << fn                        << ",\n"
                  << "    \"y_mean\": "        << fmt_dbl(ys.mean)          << ",\n"
                  << "    \"y_min\": "         << int(ys.min_v)             << ",\n"
                  << "    \"y_max\": "         << int(ys.max_v)             << ",\n"
                  << "    \"y_variance\": "    << fmt_dbl(ys.var)           << ",\n"
                  << "    \"u_mean\": "        << fmt_dbl(um)               << ",\n"
                  << "    \"v_mean\": "        << fmt_dbl(vm)               << ",\n"
                  << "    \"sha256\": \""      << h                         << "\",\n"
                  << "    \"black_frame\": "   << fmt_bool(black_frame)     << ",\n"
                  << "    \"frozen_frame\": "  << fmt_bool(frozen_frame)    << ",\n"
                  << "    \"clipped_frame\": " << fmt_bool(clipped_frame)   << "\n"
                  << "  }";

        prev_hash = h;
        first = false;
    }

    std::cout << "\n]\n";  // end JSON array
    return 0;
}
