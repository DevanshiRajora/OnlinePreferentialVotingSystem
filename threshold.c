// Compile:
//   clang threshold_elgamal_demo.c -o threshold_elgamal
// Run:
//   ./threshold_elgamal
//
// Notes: NOT secure. Uses small integers. For real systems use big ints, safe primes, secure RNG, ZK proofs.

#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define TTRUSTEES 4        // total trustees
#define THRESHOLD 3        // threshold needed to decrypt (t <= TTRUSTEES)
#define P 23               // prime modulus (toy)
#define G 5                // generator
// Group order Q = P-1 for exponent arithmetic
#define Q (P - 1)

// ---------- modular arithmetic helpers ----------
long long modmul(long long a, long long b, long long m) {
    return (a * b) % m;
}
long long modpow(long long a, long long e, long long m) {
    long long res = 1 % m;
    a %= m;
    if (a < 0) a += m;
    while (e > 0) {
        if (e & 1) res = (res * a) % m;
        a = (a * a) % m;
        e >>= 1;
    }
    return res;
}

// extended gcd for modular inverse
long long egcd(long long a, long long b, long long *x, long long *y) {
    if (b == 0) { *x = 1; *y = 0; return a; }
    long long x1, y1;
    long long g = egcd(b, a % b, &x1, &y1);
    *x = y1;
    *y = x1 - (a / b) * y1;
    return g;
}
long long modinv(long long a, long long m) {
    long long x, y;
    long long g = egcd(a < 0 ? a + m : a, m, &x, &y);
    if (g != 1) return -1; // no inverse
    x %= m;
    if (x < 0) x += m;
    return x;
}

// ---------- Shamir secret sharing (split + eval) ----------
// We'll use x-coordinates 1..TTRUSTEES (public indices)
void shamir_split(int secret, int shares[], int n) {
    // Build random polynomial f(0)=secret, f(1)=..., deg = THRESHOLD-1
    int deg = THRESHOLD - 1;
    int coeffs[THRESHOLD]; // coeffs[0]=secret
    coeffs[0] = secret % Q;
    for (int i = 1; i <= deg; ++i) coeffs[i] = rand() % Q;
    // evaluate f at x = 1..n
    for (int i = 0; i < n; ++i) {
        int x = i + 1;
        long long val = 0;
        long long powx = 1;
        for (int j = 0; j <= deg; ++j) {
            val = (val + coeffs[j] * powx) % Q;
            powx = (powx * x) % Q;
        }
        shares[i] = (int)val;
    }
}

// Lagrange coefficient lambda_i at 0 using x-coords (1..n) but only for selected indices
// We compute lambda_i modulo Q (since exponents live mod Q)
long long lagrange_coefficient_at_0(int i_idx, int indices[], int k) {
    // i_idx is index in indices[] (0..k-1)
    long long xi = indices[i_idx] + 1; // x coordinate (1..)
    long long num = 1;
    long long den = 1;
    for (int j = 0; j < k; ++j) {
        if (j == i_idx) continue;
        long long xj = indices[j] + 1;
        // num *= (0 - xj) = -xj
        num = (num * ((Q - (xj % Q)) % Q)) % Q;
        // den *= (xi - xj)
        long long diff = (xi - xj) % Q;
        if (diff < 0) diff += Q;
        den = (den * diff) % Q;
    }
    long long den_inv = modinv(den, Q);
    if (den_inv == -1) {
        // fallback (shouldn't happen for small primes)
        return 0;
    }
    long long lambda = (num * den_inv) % Q;
    if (lambda < 0) lambda += Q;
    return lambda;
}

// ---------- ElGamal keygen, encrypt, partial decrypt, combine ----------
// Key generation: secret x in Z_Q, public h = g^x mod P
void elgamal_keygen(int *x, int *h) {
    *x = rand() % Q;
    *h = (int)modpow(G, *x, P);
}

// ElGamal encrypt a small message m (1..P-1)
void elgamal_encrypt(int m, int *c1, int *c2) {
    int k = rand() % Q;
    if (k == 0) k = 1;
    *c1 = (int)modpow(G, k, P);
    int hk = (int)modpow((long long)/*h placeholder*/G, k, P); // overwritten below by proper h
    // Note: caller should provide correct h; simplified below by passing h in caller
    // We'll implement a wrapper that takes h.
}

// Better encrypt that takes public h
void elgamal_encrypt_with_h(int m, int h, int *c1, int *c2) {
    int k = rand() % Q;
    if (k == 0) k = 1;
    *c1 = (int)modpow(G, k, P);
    int hk = (int)modpow(h, k, P);
    *c2 = (int)((m * hk) % P);
}

// Each trustee with share s_i computes partial = c1^{s_i} mod P
int trustee_partial_decrypt(int c1, int share) {
    return (int)modpow(c1, share, P);
}

// Combine partial decryptions using Lagrange coefficients to obtain c1^{x}
// partials[] correspond to trustees at indices[]
long long combine_partials(int partials[], int indices[], int k) {
    long long prod = 1;
    for (int i = 0; i < k; ++i) {
        long long lambda = lagrange_coefficient_at_0(i, indices, k); // in Z_Q
        // compute partials[i]^{lambda} mod P
        long long term = modpow(partials[i], lambda, P);
        prod = (prod * term) % P;
    }
    return prod; // this should equal c1^{x}
}

// Modular inverse in modulus P
long long modinvP(long long a) {
    return modinv(a, P);
}

// ---------- Demo flow ----------
int main() {
    srand(time(NULL));

    // 1) Master key (election key)
    int x_master;
    int h;
    elgamal_keygen(&x_master, &h);
    printf("Master private x = %d\n", x_master);
    printf("Public h = %d (g^x mod P)\n", h);

    // 2) Split private key x_master into shares for trustees
    int shares[TTRUSTEES];
    shamir_split(x_master, shares, TTRUSTEES);
    printf("\nShamir shares (for trustees):\n");
    for (int i = 0; i < TTRUSTEES; ++i) {
        printf(" trustee %d (x=%d) share s = %d\n", i+1, i+1, shares[i]);
    }

    // 3) Voter encrypts message m under public h
    int m = 7; // vote (toy)
    int c1, c2;
    elgamal_encrypt_with_h(m, h, &c1, &c2);
    printf("\nEncrypted vote: m=%d -> c1=%d, c2=%d\n", m, c1, c2);

    // 4) Trustees produce partial decryptions.
    //   Choose any THRESHOLD trustees (here we pick first THRESHOLD)
    int indices[THRESHOLD];
    int partials[THRESHOLD];
    for (int i = 0; i < THRESHOLD; ++i) {
        indices[i] = i; // trustee index (0-based); x-coordinate = i+1
        partials[i] = trustee_partial_decrypt(c1, shares[i]);
        printf(" trustee %d partial = %d\n", i+1, partials[i]);
    }

    // 5) Combine partials to get c1^x
    long long c1powx = combine_partials(partials, indices, THRESHOLD);
    printf("\nCombined value c1^x = %lld\n", c1powx);

    // 6) Recover message: m = c2 * inv(c1^x) mod P
    long long inv = modinvP(c1powx);
    if (inv == -1) { printf("No inverse for combine value!\n"); return 1; }
    long long recovered = (c2 * inv) % P;
    printf("Recovered message = %lld\n", recovered);

    if (recovered == m) printf("Decryption SUCCESS\n");
    else printf("Decryption FAILED\n");

    return 0;
}