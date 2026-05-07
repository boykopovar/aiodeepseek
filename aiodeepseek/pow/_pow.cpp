#include <pybind11/pybind11.h>
#include <cstdint>
#include <cstring>
#include <string>
#include <array>
#include <vector>

namespace py = pybind11;

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
    { 0, 36,  3, 41, 18},
    { 1, 44, 10, 45,  2},
    {62,  6, 43, 15, 61},
    {28, 55, 25, 21, 56},
    {27, 20, 39,  8, 14},
};

static inline uint64_t rotl64(uint64_t x, int n) {
    return (x << n) | (x >> (64 - n));
}

static void keccak_f(uint64_t A[25]) {
    uint64_t C[5], D[5], B[25];

    for (int i = 1; i < 24; ++i) {
        for (int x = 0; x < 5; ++x)
            C[x] = A[x] ^ A[x+5] ^ A[x+10] ^ A[x+15] ^ A[x+20];

        for (int x = 0; x < 5; ++x)
            D[x] = C[(x+4)%5] ^ rotl64(C[(x+1)%5], 1);

        for (int y = 0; y < 5; ++y)
            for (int x = 0; x < 5; ++x)
                A[x + 5*y] ^= D[x];

        for (int y = 0; y < 5; ++y)
            for (int x = 0; x < 5; ++x)
                B[y + 5*((2*x + 3*y) % 5)] = rotl64(A[x + 5*y], ROT[x][y]);

        for (int y = 0; y < 5; ++y)
            for (int x = 0; x < 5; ++x)
                A[x + 5*y] = B[x + 5*y] ^ (~B[(x+1)%5 + 5*y] & B[(x+2)%5 + 5*y]);

        A[0] ^= RC[i];
    }
}

static std::array<uint8_t, 32> keccak256_deepseek(const uint8_t* msg, size_t len) {
    const size_t R = 136;
    size_t pad = R - len % R;

    std::vector<uint8_t> m(msg, msg + len);
    if (pad == 1) {
        m.push_back(0x86);
    } else {
        m.push_back(0x06);
        for (size_t i = 0; i < pad - 2; ++i) m.push_back(0x00);
        m.push_back(0x80);
    }

    uint64_t S[25] = {};

    for (size_t i = 0; i < m.size(); i += R) {
        for (int j = 0; j < 17; ++j) {
            uint64_t v;
            memcpy(&v, &m[i + j*8], 8);
            S[j] ^= v;
        }
        keccak_f(S);
    }

    std::array<uint8_t, 32> out;
    for (int i = 0; i < 4; ++i)
        memcpy(&out[i*8], &S[i], 8);
    return out;
}

static int hex_nibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return 0;
}

static std::array<uint8_t, 32> parse_hex32(const std::string& s) {
    std::array<uint8_t, 32> out{};
    for (int i = 0; i < 32; ++i)
        out[i] = (uint8_t)((hex_nibble(s[2*i]) << 4) | hex_nibble(s[2*i+1]));
    return out;
}

static int64_t solve(const std::string& base, const std::string& challenge_hex, int64_t difficulty) {
    if (challenge_hex.size() != 64) return -1;

    auto target = parse_hex32(challenge_hex);

    std::string buf = base;
    const size_t base_len = base.size();

    char nonce_buf[22];

    for (int64_t nonce = 0; nonce < difficulty; ++nonce) {
        int nlen = snprintf(nonce_buf, sizeof(nonce_buf), "%lld", (long long)nonce);
        buf.resize(base_len);
        buf.append(nonce_buf, nlen);

        auto digest = keccak256_deepseek(
            reinterpret_cast<const uint8_t*>(buf.data()), buf.size()
        );

        if (digest == target) return nonce;
    }
    return -1;
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
