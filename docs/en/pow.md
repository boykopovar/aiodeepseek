# Proof-of-Work

DeepSeek requires a Proof-of-Work challenge to be solved before every chat completion API request and before registration. The client does this automatically, with no user intervention required.

---

## What PoW means in DeepSeek

Before sending a request, the client receives a **challenge** object from the server with these fields:

| Field        | Description                   |
|--------------|-------------------------------|
| `salt`       | Salt string                   |
| `expire_at`  | Expiration time               |
| `difficulty` | Maximum number of iterations  |
| `challenge`  | Expected hash (32 bytes, hex) |
| `algorithm`  | Algorithm (`DeepSeekHashV1`)  |
| `signature`  | Challenge signature           |

The task is to find an integer `nonce` from `0` to `difficulty` such that:

```
Keccak-256(f"{salt}_{expire_at}_{nonce}") == challenge
```

The found `nonce` is packed into JSON and encoded in base64, then sent in the `X-DS-PoW-Response` header.

---

## Typical difficulty

The typical `difficulty` value is **144,000**.

That means up to 144,000 Keccak-256 hashes may need to be computed in the worst case. In practice, the required `nonce` is found after about half that many iterations on average.

---

## Performance

### C++ extension

The calculations are implemented in `aiodeepseek/pow/_pow.cpp` - C++17 using:

- **AVX2** - Intel/AMD SIMD instructions for computing 4 hashes in parallel
- **Multithreading** - the task is split across all CPU cores via `std::thread`
- **23-round Keccak** - a non-standard variant with 23 rounds instead of 24
- **Partial static hash** - the immutable part of the input (without the nonce) is hashed once and reused

On a modern CPU with 8+ cores, the computation takes **3–15 milliseconds**. A custom pure-Python `Keccak` implementation took ~30 seconds (~10 s with `multiprocessing`).

### Building the extension

```bash
pip install git+ssh://git@github.com/boykopovar/aiodeepseek.git -U
```

Build requirements:
- C++17 compiler (GCC 7+, Clang 5+, MSVC 2017+)
- CPU with AVX2 support (Intel Haswell 2013+, AMD Ryzen 2017+)
- `pybind11 >= 2.12`

On Windows, the compiler must support `/arch:AVX2`. On Linux/macOS, the flags `-mavx2 -march=native` are used.

---

## Possible issues

### PoW is not solved (`-1`)

If no solution is found within `difficulty`, `PowNotSolvedError("PoW not solved within difficulty limit")` is raised.

### High CPU load

Every `ask` / `ask_stream` starts a parallel nonce search on all cores. These are short load spikes (milliseconds). If that is critical, use `timeout` to control waiting.

---

## See also

- [DeepSeekClient](client.md)
- [Exceptions](exceptions.md)
