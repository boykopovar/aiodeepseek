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

static constexpr size_t RATE   = 136;
static constexpr size_t RATE_W = RATE / 8;

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

static const int ROT[5][5] = {
    { 0, 36, 3, 41, 18},
    { 1, 44, 10, 45,  2},
    {62,  6, 43, 15, 61},
    {28, 55, 25, 21, 56},
    {27, 20, 39,  8, 14},
};

static inline uint64_t rotl64(uint64_t x, int n) {
    return n ? ((x << n) | (x >> (64 - n))) : x;
}

static void keccak_f(uint64_t A[25]) {
    uint64_t C[5], D[5], B[25];
    for (int i = 1; i < 24; ++i) {
        for (int x = 0; x < 5; ++x)
            C[x] = A[x] ^ A[x+5] ^ A[x+10] ^ A[x+15] ^ A[x+20];
        for (int x = 0; x < 5; ++x)
            D[x] = C[(x+4)%5] ^ rotl64(C[(x+1)%5], 1);
        for (int j = 0; j < 25; ++j)
            A[j] ^= D[j % 5];
        for (int y = 0; y < 5; ++y)
            for (int x = 0; x < 5; ++x)
                B[y + 5*((2*x + 3*y) % 5)] = rotl64(A[x + 5*y], ROT[x][y]);
        for (int y = 0; y < 5; ++y)
            for (int x = 0; x < 5; ++x)
                A[x + 5*y] = B[x + 5*y] ^ (~B[(x+1)%5 + 5*y] & B[(x+2)%5 + 5*y]);
        A[0] ^= RC[i];
    }
}

static inline int fast_itoa(int64_t v, char* buf) {
    if (v == 0) { buf[0] = '0'; return 1; }
    char tmp[20];
    int n = 0;
    for (uint64_t u = (uint64_t)v; u; u /= 10)
        tmp[n++] = (char)('0' + u % 10);
    for (int i = 0; i < n; ++i)
        buf[i] = tmp[n - 1 - i];
    return n;
}

static inline int hex_nibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return 0;
}

struct PowCtx {
    uint64_t static_state[25];
    uint64_t target4[4];
    uint8_t dyn_tpl[24];
    size_t base_len;
    size_t dyn_word_start;
    size_t dyn_word_count;
    size_t dyn_offset;
};

static PowCtx build_ctx(const std::string& base, const std::string& hex) {
    PowCtx ctx = {};
    ctx.base_len = base.size();

    for (int j = 0; j < 4; ++j) {
        uint64_t v = 0;
        for (int k = 0; k < 8; ++k) {
            int p = (j * 8 + k) * 2;
            uint8_t b = (uint8_t)((hex_nibble(hex[p]) << 4) | hex_nibble(hex[p+1]));
            v |= (uint64_t)b << (k * 8);
        }
        ctx.target4[j] = v;
    }

    ctx.dyn_word_start = ctx.base_len / 8;
    ctx.dyn_offset = ctx.base_len % 8;
    size_t dyn_last = ctx.base_len + 6;
    size_t dyn_word_end = dyn_last / 8 + 1;
    ctx.dyn_word_count = dyn_word_end - ctx.dyn_word_start;
    if (ctx.dyn_word_start + ctx.dyn_word_count > RATE_W)
        ctx.dyn_word_count = RATE_W - ctx.dyn_word_start;

    memset(ctx.dyn_tpl, 0, sizeof(ctx.dyn_tpl));
    size_t dyn_byte_start = ctx.dyn_word_start * 8;
    if (ctx.base_len > dyn_byte_start)
        memcpy(ctx.dyn_tpl, base.data() + dyn_byte_start, ctx.base_len - dyn_byte_start);

    uint8_t blk[RATE] = {};
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

static inline __m256i rotl64x4(__m256i x, int n) {
    if (n == 0) return x;
    return _mm256_or_si256(_mm256_slli_epi64(x, n), _mm256_srli_epi64(x, 64 - n));
}
static void keccak_f_4way(__m256i A[25]) {
    __m256i C[5], D[5], B[25];
    for (int i = 1; i < 24; ++i) {
        for (int x = 0; x < 5; ++x)
            C[x] = _mm256_xor_si256(
                    _mm256_xor_si256(
                     _mm256_xor_si256(
                      _mm256_xor_si256(A[x], A[x+5]), A[x+10]), A[x+15]), A[x+20]);
        for (int x = 0; x < 5; ++x)
            D[x] = _mm256_xor_si256(C[(x+4)%5], rotl64x4(C[(x+1)%5], 1));
        for (int j = 0; j < 25; ++j)
            A[j] = _mm256_xor_si256(A[j], D[j % 5]);
        for (int y = 0; y < 5; ++y)
            for (int x = 0; x < 5; ++x)
                B[y + 5*((2*x + 3*y) % 5)] = rotl64x4(A[x + 5*y], ROT[x][y]);
        for (int y = 0; y < 5; ++y)
            for (int x = 0; x < 5; ++x)
                A[x + 5*y] = _mm256_xor_si256(B[x + 5*y],
                    _mm256_andnot_si256(B[(x+1)%5 + 5*y], B[(x+2)%5 + 5*y]));
        A[0] = _mm256_xor_si256(A[0], _mm256_set1_epi64x((int64_t)RC[i]));
    }
}

static void worker_avx2(const PowCtx& ctx, int64_t from, int64_t to,
                         std::atomic<int64_t>& result) {
    alignas(32) uint64_t lo[4][4];
    char nbuf[4][20];
    uint8_t dyn[4][24];

    const __m256i t0 = _mm256_set1_epi64x((int64_t)ctx.target4[0]);
    const __m256i t1 = _mm256_set1_epi64x((int64_t)ctx.target4[1]);
    const __m256i t2 = _mm256_set1_epi64x((int64_t)ctx.target4[2]);
    const __m256i t3 = _mm256_set1_epi64x((int64_t)ctx.target4[3]);

    for (int64_t nonce = from; nonce < to; nonce += 4) {
        if ((nonce & 0xFF) == 0 && result.load(std::memory_order_relaxed) >= 0) return;

        int64_t lanes = to - nonce < 4 ? to - nonce : 4;

        for (int l = 0; l < 4; ++l) {
            int64_t n = (l < lanes) ? nonce + l : nonce;
            memcpy(dyn[l], ctx.dyn_tpl, ctx.dyn_word_count * 8);
            int nlen = fast_itoa(n, nbuf[l]);
            memcpy(dyn[l] + ctx.dyn_offset, nbuf[l], (size_t)nlen);
            dyn[l][ctx.dyn_offset + nlen] = 0x06;
        }

        __m256i A[25];
        for (int j = 0; j < 25; ++j)
            A[j] = _mm256_set1_epi64x((int64_t)ctx.static_state[j]);

        for (size_t w = 0; w < ctx.dyn_word_count; ++w) {
            uint64_t v[4];
            for (int l = 0; l < 4; ++l)
                memcpy(&v[l], &dyn[l][w * 8], 8);
            __m256i vv = _mm256_set_epi64x(
                (int64_t)v[3], (int64_t)v[2], (int64_t)v[1], (int64_t)v[0]);
            A[ctx.dyn_word_start + w] = _mm256_xor_si256(A[ctx.dyn_word_start + w], vv);
        }

        keccak_f_4way(A);

        __m256i cmp = _mm256_cmpeq_epi64(A[0], t0);
        if (_mm256_testz_si256(cmp, cmp)) continue;

        _mm256_store_si256((__m256i*)lo[0], A[0]);
        _mm256_store_si256((__m256i*)lo[1], A[1]);
        _mm256_store_si256((__m256i*)lo[2], A[2]);
        _mm256_store_si256((__m256i*)lo[3], A[3]);

        for (int l = 0; l < lanes; ++l) {
            if (lo[0][l] == ctx.target4[0] && lo[1][l] == ctx.target4[1] &&
                lo[2][l] == ctx.target4[2] && lo[3][l] == ctx.target4[3]) {
                int64_t expected = -1;
                result.compare_exchange_strong(expected, nonce + l,
                                               std::memory_order_relaxed);
                return;
            }
        }
    }
}


static int64_t solve(const std::string& base, const std::string& challenge_hex,
                     int64_t difficulty) {
    if (challenge_hex.size() != 64 || difficulty <= 0) return -1;

    PowCtx ctx = build_ctx(base, challenge_hex);

    std::atomic<int64_t> result{-1};

    unsigned nthreads = std::thread::hardware_concurrency();
    if (nthreads < 1) nthreads = 1;
    if ((int64_t)nthreads > difficulty) nthreads = (unsigned)difficulty;

    std::vector<std::thread> threads;
    threads.reserve(nthreads);

    int64_t chunk = (difficulty + (int64_t)nthreads - 1) / (int64_t)nthreads;

    for (unsigned t = 0; t < nthreads; ++t) {
    int64_t from = (int64_t)t * chunk;
    int64_t to = std::min(from + chunk, difficulty);
    threads.emplace_back(worker_avx2, std::cref(ctx), from, to, std::ref(result));
}

    for (auto& th : threads) th.join();
    return result.load();
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