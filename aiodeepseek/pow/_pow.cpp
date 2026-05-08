#include <pybind11/pybind11.h>
#include <cstdint>
#include <cstring>
#include <string>
#include <atomic>
#include <thread>
#include <vector>
#include <algorithm>
#include <immintrin.h>

namespace py = pybind11;

static constexpr size_t RATE    = 136;
static constexpr size_t RATE_W  = RATE / 8;
static constexpr size_t MAX_NONCE_DEC = 20;

static const uint64_t RC[24] = {
    0x0000000000000001ULL, 0x0000000000008082ULL, 0x800000000000808AULL,
    0x8000000080008000ULL, 0x000000000000808BULL, 0x0000000080000001ULL,
    0x8000000080008081ULL, 0x8000000000008009ULL, 0x000000000000008AULL,
    0x0000000000000088ULL, 0x0000000080008009ULL, 0x000000008000000AULL,
    0x000000008000808BULL, 0x800000000000008BULL, 0x8000000000008089ULL,
    0x8000000000008003ULL, 0x8000000000008002ULL, 0x8000000000000080ULL,
    0x000000000000800AULL, 0x800000008000000AULL, 0x8000000080008081ULL,
    0x8000000000008080ULL, 0x0000000080000001ULL, 0x8000000080008008ULL,
};

static constexpr char DIGITS_00_99[] =
    "00010203040506070809"
    "10111213141516171819"
    "20212223242526272829"
    "30313233343536373839"
    "40414243444546474849"
    "50515253545556575859"
    "60616263646566676869"
    "70717273747576777879"
    "80818283848586878889"
    "90919293949596979899";

static inline int hex_nibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return 0;
}

static inline int fast_u64_to_dec(uint64_t v, char* out) {
    char tmp[20];
    char* p = tmp + sizeof(tmp);
    while (v >= 100) {
        uint64_t q = v / 100;
        uint64_t r = v - q * 100;
        p -= 2;
        p[0] = DIGITS_00_99[r * 2];
        p[1] = DIGITS_00_99[r * 2 + 1];
        v = q;
    }
    if (v < 10) {
        *--p = static_cast<char>('0' + v);
    } else {
        p -= 2;
        p[0] = DIGITS_00_99[v * 2];
        p[1] = DIGITS_00_99[v * 2 + 1];
    }
    int len = static_cast<int>((tmp + sizeof(tmp)) - p);
    memcpy(out, p, static_cast<size_t>(len));
    return len;
}

struct PowCtx {
    uint64_t static_state[25];
    uint64_t target4[4];
    uint8_t  dyn_tpl[24];
    size_t   base_len;
    size_t   dyn_word_start;
    size_t   dyn_word_count;
    size_t   dyn_offset;
};

static PowCtx build_ctx(const std::string& base, const std::string& hex) {
    PowCtx ctx = {};
    ctx.base_len = base.size();

    for (int j = 0; j < 4; ++j) {
        uint64_t v = 0;
        for (int k = 0; k < 8; ++k) {
            int p = (j * 8 + k) * 2;
            uint8_t b = static_cast<uint8_t>((hex_nibble(hex[p]) << 4) | hex_nibble(hex[p + 1]));
            v |= static_cast<uint64_t>(b) << (k * 8);
        }
        ctx.target4[j] = v;
    }

    ctx.dyn_word_start = ctx.base_len / 8;
    ctx.dyn_offset     = ctx.base_len % 8;
    size_t dyn_last      = ctx.base_len + MAX_NONCE_DEC;
    size_t dyn_word_end  = dyn_last / 8 + 1;
    ctx.dyn_word_count   = dyn_word_end - ctx.dyn_word_start;
    if (ctx.dyn_word_start + ctx.dyn_word_count > RATE_W)
        ctx.dyn_word_count = RATE_W - ctx.dyn_word_start;

    memset(ctx.dyn_tpl, 0, sizeof(ctx.dyn_tpl));
    size_t dyn_byte_start = ctx.dyn_word_start * 8;
    if (ctx.base_len > dyn_byte_start)
        memcpy(ctx.dyn_tpl, base.data() + dyn_byte_start, ctx.base_len - dyn_byte_start);

    alignas(8) uint8_t blk[RATE] = {};
    memcpy(blk, base.data(), ctx.base_len);
    blk[RATE - 1] = 0x80;

    memset(ctx.static_state, 0, sizeof(ctx.static_state));
    for (size_t j = 0; j < RATE_W; ++j) {
        if (j >= ctx.dyn_word_start && j < ctx.dyn_word_start + ctx.dyn_word_count)
            continue;
        uint64_t v;
        memcpy(&v, &blk[j * 8], 8);
        ctx.static_state[j] ^= v;
    }

    return ctx;
}

#define R4(x, n) _mm256_or_si256(_mm256_slli_epi64((x), (n)), _mm256_srli_epi64((x), 64-(n)))

#define KF_ROUND4(i)                                                                                \
    do {                                                                                            \
        C[0] = _mm256_xor_si256(_mm256_xor_si256(_mm256_xor_si256(                                 \
                   _mm256_xor_si256(A[ 0], A[ 5]), A[10]), A[15]), A[20]);                         \
        C[1] = _mm256_xor_si256(_mm256_xor_si256(_mm256_xor_si256(                                 \
                   _mm256_xor_si256(A[ 1], A[ 6]), A[11]), A[16]), A[21]);                         \
        C[2] = _mm256_xor_si256(_mm256_xor_si256(_mm256_xor_si256(                                 \
                   _mm256_xor_si256(A[ 2], A[ 7]), A[12]), A[17]), A[22]);                         \
        C[3] = _mm256_xor_si256(_mm256_xor_si256(_mm256_xor_si256(                                 \
                   _mm256_xor_si256(A[ 3], A[ 8]), A[13]), A[18]), A[23]);                         \
        C[4] = _mm256_xor_si256(_mm256_xor_si256(_mm256_xor_si256(                                 \
                   _mm256_xor_si256(A[ 4], A[ 9]), A[14]), A[19]), A[24]);                         \
        D[0] = _mm256_xor_si256(C[4], R4(C[1], 1));                                                \
        D[1] = _mm256_xor_si256(C[0], R4(C[2], 1));                                                \
        D[2] = _mm256_xor_si256(C[1], R4(C[3], 1));                                                \
        D[3] = _mm256_xor_si256(C[2], R4(C[4], 1));                                                \
        D[4] = _mm256_xor_si256(C[3], R4(C[0], 1));                                                \
        for (int _j = 0; _j < 25; ++_j) A[_j] = _mm256_xor_si256(A[_j], D[_j % 5]);              \
        B[ 0] =        A[ 0];                                                                       \
        B[ 1] = R4(A[ 6], 44);                                                                     \
        B[ 2] = R4(A[12], 43);                                                                     \
        B[ 3] = R4(A[18], 21);                                                                     \
        B[ 4] = R4(A[24], 14);                                                                     \
        B[ 5] = R4(A[ 3], 28);                                                                     \
        B[ 6] = R4(A[ 9], 20);                                                                     \
        B[ 7] = R4(A[10],  3);                                                                     \
        B[ 8] = R4(A[16], 45);                                                                     \
        B[ 9] = R4(A[22], 61);                                                                     \
        B[10] = R4(A[ 1],  1);                                                                     \
        B[11] = R4(A[ 7],  6);                                                                     \
        B[12] = R4(A[13], 25);                                                                     \
        B[13] = R4(A[19],  8);                                                                     \
        B[14] = R4(A[20], 18);                                                                     \
        B[15] = R4(A[ 4], 27);                                                                     \
        B[16] = R4(A[ 5], 36);                                                                     \
        B[17] = R4(A[11], 10);                                                                     \
        B[18] = R4(A[17], 15);                                                                     \
        B[19] = R4(A[23], 56);                                                                     \
        B[20] = R4(A[ 2], 62);                                                                     \
        B[21] = R4(A[ 8], 55);                                                                     \
        B[22] = R4(A[14], 39);                                                                     \
        B[23] = R4(A[15], 41);                                                                     \
        B[24] = R4(A[21],  2);                                                                     \
        for (int _y = 0; _y < 5; ++_y)                                                             \
            for (int _x = 0; _x < 5; ++_x)                                                         \
                A[_x + 5*_y] = _mm256_xor_si256(                                                   \
                    B[_x + 5*_y],                                                                   \
                    _mm256_andnot_si256(B[(_x+1)%5 + 5*_y], B[(_x+2)%5 + 5*_y]));                \
        A[0] = _mm256_xor_si256(A[0],                                                              \
                   _mm256_set1_epi64x(static_cast<int64_t>(RC[i])));                               \
    } while(0)

static void keccak_f_4way(__m256i A[25]) {
    __m256i C[5], D[5], B[25];
    KF_ROUND4( 1); KF_ROUND4( 2); KF_ROUND4( 3); KF_ROUND4( 4);
    KF_ROUND4( 5); KF_ROUND4( 6); KF_ROUND4( 7); KF_ROUND4( 8);
    KF_ROUND4( 9); KF_ROUND4(10); KF_ROUND4(11); KF_ROUND4(12);
    KF_ROUND4(13); KF_ROUND4(14); KF_ROUND4(15); KF_ROUND4(16);
    KF_ROUND4(17); KF_ROUND4(18); KF_ROUND4(19); KF_ROUND4(20);
    KF_ROUND4(21); KF_ROUND4(22); KF_ROUND4(23);
}

#undef KF_ROUND4
#undef R4

static void worker_avx2(const PowCtx& ctx, uint64_t from, uint64_t to,
                         std::atomic<int64_t>& result) {
    const __m256i t0 = _mm256_set1_epi64x(static_cast<int64_t>(ctx.target4[0]));
    const __m256i t1 = _mm256_set1_epi64x(static_cast<int64_t>(ctx.target4[1]));
    const __m256i t2 = _mm256_set1_epi64x(static_cast<int64_t>(ctx.target4[2]));
    const __m256i t3 = _mm256_set1_epi64x(static_cast<int64_t>(ctx.target4[3]));

    alignas(32) uint8_t dyn[4][24];
    char nbuf[4][21];

    const size_t dyn_offset     = ctx.dyn_offset;
    const size_t dyn_word_start = ctx.dyn_word_start;
    const size_t dyn_word_count = ctx.dyn_word_count;

    for (uint64_t nonce = from; nonce < to; nonce += 4) {
        if ((nonce & 0xFFFu) == 0 && result.load(std::memory_order_relaxed) >= 0)
            return;

        uint64_t lanes = to - nonce;
        if (lanes > 4) lanes = 4;

        for (uint64_t l = 0; l < lanes; ++l) {
            memcpy(dyn[l], ctx.dyn_tpl, sizeof(ctx.dyn_tpl));
            int nlen = fast_u64_to_dec(nonce + l, nbuf[l]);
            memcpy(dyn[l] + dyn_offset, nbuf[l], static_cast<size_t>(nlen));
            dyn[l][dyn_offset + static_cast<size_t>(nlen)] = 0x06;
        }
        for (uint64_t l = lanes; l < 4; ++l)
            memcpy(dyn[l], dyn[0], sizeof(dyn[0]));

        alignas(32) __m256i A[25];
        for (int j = 0; j < 25; ++j)
            A[j] = _mm256_set1_epi64x(static_cast<int64_t>(ctx.static_state[j]));

        for (size_t w = 0; w < dyn_word_count; ++w) {
            uint64_t v0, v1, v2, v3;
            memcpy(&v0, &dyn[0][w * 8], 8);
            memcpy(&v1, &dyn[1][w * 8], 8);
            memcpy(&v2, &dyn[2][w * 8], 8);
            memcpy(&v3, &dyn[3][w * 8], 8);
            __m256i vv = _mm256_set_epi64x(
                static_cast<int64_t>(v3), static_cast<int64_t>(v2),
                static_cast<int64_t>(v1), static_cast<int64_t>(v0));
            A[dyn_word_start + w] = _mm256_xor_si256(A[dyn_word_start + w], vv);
        }

        keccak_f_4way(A);

        int mask = _mm256_movemask_pd(_mm256_castsi256_pd(_mm256_cmpeq_epi64(A[0], t0)));
        if (!mask) continue;
        mask &= _mm256_movemask_pd(_mm256_castsi256_pd(_mm256_cmpeq_epi64(A[1], t1)));
        if (!mask) continue;
        mask &= _mm256_movemask_pd(_mm256_castsi256_pd(_mm256_cmpeq_epi64(A[2], t2)));
        if (!mask) continue;
        mask &= _mm256_movemask_pd(_mm256_castsi256_pd(_mm256_cmpeq_epi64(A[3], t3)));
        if (!mask) continue;

        mask &= static_cast<int>((1u << lanes) - 1u);

        for (int l = 0; l < static_cast<int>(lanes); ++l) {
            if (mask & (1 << l)) {
                int64_t expected = -1;
                result.compare_exchange_strong(expected, static_cast<int64_t>(nonce) + l,
                                               std::memory_order_relaxed);
                return;
            }
        }
    }
}

static int64_t solve(const std::string& base, const std::string& challenge_hex,
                     int64_t difficulty) {
    if (challenge_hex.size() != 64 || difficulty <= 0 ||
        base.size() > RATE - MAX_NONCE_DEC)
        return -1;

    PowCtx ctx = build_ctx(base, challenge_hex);
    std::atomic<int64_t> result{-1};

    unsigned nthreads = std::thread::hardware_concurrency();
    if (nthreads < 1) nthreads = 1;
    if (static_cast<int64_t>(nthreads) > difficulty)
        nthreads = static_cast<unsigned>(difficulty);

    const uint64_t udiff = static_cast<uint64_t>(difficulty);
    const uint64_t chunk = (udiff + nthreads - 1u) / nthreads;

    std::vector<std::thread> threads;
    threads.reserve(nthreads);

    for (unsigned t = 0; t < nthreads; ++t) {
        uint64_t from = static_cast<uint64_t>(t) * chunk;
        uint64_t to   = std::min(from + chunk, udiff);
        threads.emplace_back(worker_avx2, std::cref(ctx), from, to, std::ref(result));
    }

    for (auto& th : threads)
        th.join();

    return result.load(std::memory_order_relaxed);
}

PYBIND11_MODULE(_pow, m) {
    m.doc() = "C++ Keccak-based PoW solver for DeepSeek (23-round variant).";
    m.def("solve", &solve,
        py::arg("base"),
        py::arg("challenge_hex"),
        py::arg("difficulty"),
        "Brute-force a PoW nonce.\n\n"
        "Args:\n"
        "    base: Salt prefix string.\n"
        "    challenge_hex: Expected 32-byte digest as 64-char hex string.\n"
        "    difficulty: Maximum iterations.\n\n"
        "Returns:\n"
        "    Matching nonce >= 0, or -1 if not found."
    );
}