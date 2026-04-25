// HYBRID ENCRYPTION MODULE - Compatible with Ring Signature & Threshold Systems
// Compile: clang hybrid_encryption.c -o hybrid_encryption
// Run: ./hybrid_encryption
//
// NOTE: Uses toy parameters (P=23) to match ring signature & threshold code
// For real systems: use OpenSSL with proper key sizes

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>


#define P 23              // prime modulus (toy - use large prime in production)
#define G 5               // generator
#define Q (P - 1)         // group order for exponents

#define AES_BLOCK_SIZE 16 // simplified block size
#define MAX_MSG_LEN 256

// DATA STRUCTURES

// RSA-like key pair (simplified ElGamal-style for compatibility)
typedef struct {
    int private_key;      // x
    int public_key;       // h = g^x mod P
} KeyPair;

// Symmetric key for AES
typedef struct {
    unsigned char key[16];
    unsigned char iv[16];
} SymmetricKey;

// Hybrid encrypted package
typedef struct {
    int encrypted_sym_key;           // RSA/ElGamal encrypted symmetric key
    int encrypted_sym_key_c1;        // ElGamal c1 component
    unsigned char iv[16];            // AES IV
    unsigned char ciphertext[MAX_MSG_LEN];  // AES encrypted data
    int ciphertext_len;
    int metadata_hash;               // integrity check
    long timestamp;
} HybridPackage;

// MODULAR ARITHMETIC (same as your other files)

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
    a = a % m;
    if (a < 0) a += m;
    long long g = egcd(a, m, &x, &y);
    if (g != 1) return -1;
    x %= m;
    if (x < 0) x += m;
    return x;
}

// KEY GENERATION

// Generate asymmetric key pair (ElGamal style - compatible with threshold)
void generate_keypair(KeyPair *kp) {
    kp->private_key = rand() % Q;
    if (kp->private_key == 0) kp->private_key = 1;
    kp->public_key = (int)modpow(G, kp->private_key, P);
}

// Generate random symmetric key and IV
// NOTE: For toy P=23, we use small key values that survive ElGamal
void generate_symmetric_key(SymmetricKey *sk) {
    // Key value must be < P and > 0 for ElGamal to work with toy params
    int key_val = (rand() % (P - 2)) + 1;  // 1 to P-2
    sk->key[0] = key_val;  // Store the actual key value here
    for (int i = 1; i < 16; i++) {
        sk->key[i] = 0;
    }
    for (int i = 0; i < 16; i++) {
        sk->iv[i] = rand() % 256;
    }
}

// SIMPLE AES-LIKE SYMMETRIC ENCRYPTION (TOY VERSION)
// For production: replace with actual AES from OpenSSL

// Simple XOR-based stream cipher (toy - NOT SECURE)
// Mimics AES-CTR mode behavior for demonstration
void aes_encrypt(const unsigned char *plaintext, int len,
                 const SymmetricKey *sk,
                 unsigned char *ciphertext) {
    unsigned char keystream[16];
    int block = 0;
    
    for (int i = 0; i < len; i++) {
        if (i % 16 == 0) {
            // Generate keystream block (toy version)
            for (int j = 0; j < 16; j++) {
                keystream[j] = (sk->key[j] + sk->iv[j] + block) % 256;
            }
            block++;
        }
        ciphertext[i] = plaintext[i] ^ keystream[i % 16];
    }
}

void aes_decrypt(const unsigned char *ciphertext, int len,
                 const SymmetricKey *sk,
                 unsigned char *plaintext) {
    // XOR is symmetric - same operation
    aes_encrypt(ciphertext, len, sk, plaintext);
}

// ASYMMETRIC KEY ENCRYPTION (ElGamal - compatible with threshold)

// Encrypt symmetric key using recipient's public key
// Returns c1, c2 where: c1 = g^k, c2 = m * h^k (ElGamal)
void encrypt_symmetric_key(const SymmetricKey *sk, int recipient_public_key,
                           int *c1, int *c2) {
    // Use key[0] directly as the symmetric key value (already < P)
    int sym_key_int = sk->key[0];
    if (sym_key_int == 0) sym_key_int = 1;
    
    // ElGamal encryption
    int k = rand() % Q;
    if (k == 0) k = 1;
    
    *c1 = (int)modpow(G, k, P);
    int hk = (int)modpow(recipient_public_key, k, P);
    *c2 = (sym_key_int * hk) % P;
}

// Decrypt symmetric key using private key
int decrypt_symmetric_key(int c1, int c2, int private_key) {
    // m = c2 * (c1^x)^(-1) mod P
    long long c1_pow_x = modpow(c1, private_key, P);
    long long inv = modinv(c1_pow_x, P);
    if (inv == -1) return -1;
    return (int)((c2 * inv) % P);
}


// THRESHOLD DECRYPTION INTEGRATION
// (Uses Lagrange interpolation from your threshold code)


// Lagrange coefficient at x=0 for threshold reconstruction
long long lagrange_coeff(int i_idx, int indices[], int k) {
    long long xi = indices[i_idx] + 1;
    long long num = 1, den = 1;
    
    for (int j = 0; j < k; ++j) {
        if (j == i_idx) continue;
        long long xj = indices[j] + 1;
        num = (num * ((Q - (xj % Q)) % Q)) % Q;
        long long diff = (xi - xj) % Q;
        if (diff < 0) diff += Q;
        den = (den * diff) % Q;
    }
    
    long long den_inv = modinv(den, Q);
    if (den_inv == -1) return 0;
    
    long long lambda = (num * den_inv) % Q;
    if (lambda < 0) lambda += Q;
    return lambda;
}

// Threshold decrypt c1 using shares
// partials[i] = c1^{share[i]} mod P
long long threshold_combine(int partials[], int indices[], int k) {
    long long prod = 1;
    for (int i = 0; i < k; ++i) {
        long long lambda = lagrange_coeff(i, indices, k);
        long long term = modpow(partials[i], lambda, P);
        prod = (prod * term) % P;
    }
    return prod;
}

// SIMPLE HASH FUNCTION (for integrity - toy version)

int simple_hash(const unsigned char *data, int len) {
    unsigned int h = 5381;
    for (int i = 0; i < len; i++) {
        h = ((h << 5) + h) + data[i];
    }
    return h % 65536;
}


// HYBRID ENCRYPTION - MAIN FUNCTIONS

// ENCRYPT: Vote/message encryption with hybrid scheme
HybridPackage hybrid_encrypt(const unsigned char *plaintext, int plaintext_len,
                              int recipient_public_key) {
    HybridPackage pkg;
    memset(&pkg, 0, sizeof(pkg));
    
    printf("\n=== HYBRID ENCRYPTION ===\n");
    
    // Step 1: Generate random symmetric key
    SymmetricKey sym_key;
    generate_symmetric_key(&sym_key);
    printf("[+] Generated symmetric key\n");
    
    // Step 2: Copy IV to package
    memcpy(pkg.iv, sym_key.iv, 16);
    
    // Step 3: Encrypt plaintext with symmetric key (AES)
    aes_encrypt(plaintext, plaintext_len, &sym_key, pkg.ciphertext);
    pkg.ciphertext_len = plaintext_len;
    printf("[+] Encrypted data with AES (%d bytes)\n", plaintext_len);
    
    // Step 4: Encrypt symmetric key with recipient's public key (ElGamal)
    encrypt_symmetric_key(&sym_key, recipient_public_key,
                          &pkg.encrypted_sym_key_c1,
                          &pkg.encrypted_sym_key);
    printf("[+] Encrypted symmetric key with ElGamal\n");
    printf("    c1 = %d, c2 = %d\n", pkg.encrypted_sym_key_c1, pkg.encrypted_sym_key);
    
    // Step 5: Add metadata
    pkg.metadata_hash = simple_hash(plaintext, plaintext_len);
    pkg.timestamp = time(NULL);
    printf("[+] Added integrity hash: %d\n", pkg.metadata_hash);
    
    // Clear sensitive data
    memset(&sym_key, 0, sizeof(sym_key));
    
    return pkg;
}

// DECRYPT: Standard decryption with single private key
int hybrid_decrypt(const HybridPackage *pkg, int private_key,
                   unsigned char *plaintext) {
    printf("\n=== HYBRID DECRYPTION ===\n");
    
    // Step 1: Decrypt symmetric key using ElGamal
    int sym_key_int = decrypt_symmetric_key(pkg->encrypted_sym_key_c1,
                                             pkg->encrypted_sym_key,
                                             private_key);
    if (sym_key_int == -1) {
        printf("[-] Failed to decrypt symmetric key\n");
        return -1;
    }
    printf("[+] Decrypted symmetric key value: %d\n", sym_key_int);
    
    // Step 2: Reconstruct symmetric key structure
    SymmetricKey sym_key;
    sym_key.key[0] = sym_key_int;  // Direct value (no conversion needed for toy)
    for (int i = 1; i < 16; i++) sym_key.key[i] = 0;
    memcpy(sym_key.iv, pkg->iv, 16);
    
    // Step 3: Decrypt ciphertext with AES
    aes_decrypt(pkg->ciphertext, pkg->ciphertext_len, &sym_key, plaintext);
    printf("[+] Decrypted data with AES\n");
    
    // Step 4: Verify integrity
    int computed_hash = simple_hash(plaintext, pkg->ciphertext_len);
    if (computed_hash != pkg->metadata_hash) {
        printf("[-] Integrity check FAILED\n");
        return -1;
    }
    printf("[+] Integrity check PASSED\n");
    
    memset(&sym_key, 0, sizeof(sym_key));
    return pkg->ciphertext_len;
}

// THRESHOLD DECRYPT: Decrypt using threshold key shares
int hybrid_decrypt_threshold(const HybridPackage *pkg,
                              int shares[], int indices[], int threshold,
                              unsigned char *plaintext) {
    printf("\n=== THRESHOLD HYBRID DECRYPTION ===\n");
    
    // Step 1: Each trustee computes partial decryption
    int partials[threshold];
    printf("[+] Computing partial decryptions:\n");
    for (int i = 0; i < threshold; i++) {
        partials[i] = (int)modpow(pkg->encrypted_sym_key_c1, shares[indices[i]], P);
        printf("    Trustee %d: partial = %d\n", indices[i] + 1, partials[i]);
    }
    
    // Step 2: Combine partials using Lagrange interpolation
    long long c1_pow_x = threshold_combine(partials, indices, threshold);
    printf("[+] Combined c1^x = %lld\n", c1_pow_x);
    
    // Step 3: Recover symmetric key: m = c2 * (c1^x)^(-1)
    long long inv = modinv(c1_pow_x, P);
    if (inv == -1) {
        printf("[-] Failed to compute inverse\n");
        return -1;
    }
    int sym_key_int = (int)((pkg->encrypted_sym_key * inv) % P);
    printf("[+] Recovered symmetric key value: %d\n", sym_key_int);
    
    // Step 4: Reconstruct symmetric key and decrypt
    SymmetricKey sym_key;
    sym_key.key[0] = sym_key_int;  // Direct value
    for (int i = 1; i < 16; i++) sym_key.key[i] = 0;
    memcpy(sym_key.iv, pkg->iv, 16);
    
    aes_decrypt(pkg->ciphertext, pkg->ciphertext_len, &sym_key, plaintext);
    printf("[+] Decrypted data with AES\n");
    
    // Verify integrity
    int computed_hash = simple_hash(plaintext, pkg->ciphertext_len);
    if (computed_hash != pkg->metadata_hash) {
        printf("[-] Integrity check FAILED\n");
        return -1;
    }
    printf("[+] Integrity check PASSED\n");
    
    return pkg->ciphertext_len;
}


// DEMO / TEST

int main() {
    srand(time(NULL));
    
    printf("========================================\n");
    printf(" HYBRID ENCRYPTION DEMO\n");
    printf(" (Compatible with Ring Sig & Threshold)\n");
    printf("========================================\n");
    
    // ----- SETUP: Generate server keypair -----
    KeyPair server;
    generate_keypair(&server);
    printf("\nServer Key Pair:\n");
    printf("  Private key (x): %d\n", server.private_key);
    printf("  Public key (h):  %d\n", server.public_key);
    
    // ----- TEST 1: Basic Hybrid Encryption -----
    printf("\n--- TEST 1: Basic Hybrid Encryption ---\n");
    
    unsigned char vote[] = "VOTE:Alice";
    int vote_len = strlen((char*)vote);
    
    printf("Original vote: %s\n", vote);
    
    // Encrypt
    HybridPackage encrypted = hybrid_encrypt(vote, vote_len, server.public_key);
    
    // Decrypt
    unsigned char decrypted[MAX_MSG_LEN] = {0};
    int dec_len = hybrid_decrypt(&encrypted, server.private_key, decrypted);
    
    if (dec_len > 0) {
        decrypted[dec_len] = '\0';
        printf("\nDecrypted vote: %s\n", decrypted);
        if (strcmp((char*)vote, (char*)decrypted) == 0)
            printf("SUCCESS: Decryption matched!\n");
        else
            printf("FAILED: Decryption mismatch!\n");
    }
    
    // ----- TEST 2: Threshold Decryption -----
    printf("\n--- TEST 2: Threshold Hybrid Decryption ---\n");
    
    #define TRUSTEES 4
    #define THRESHOLD 3
    
    // Split private key using Shamir (from threshold code)
    int shares[TRUSTEES];
    int deg = THRESHOLD - 1;
    int coeffs[THRESHOLD];
    coeffs[0] = server.private_key;
    for (int i = 1; i <= deg; i++) coeffs[i] = rand() % Q;
    
    for (int i = 0; i < TRUSTEES; i++) {
        int x = i + 1;
        long long val = 0, powx = 1;
        for (int j = 0; j <= deg; j++) {
            val = (val + coeffs[j] * powx) % Q;
            powx = (powx * x) % Q;
        }
        shares[i] = (int)val;
    }
    
    printf("\nTrustee shares:\n");
    for (int i = 0; i < TRUSTEES; i++)
        printf("  Trustee %d: share = %d\n", i + 1, shares[i]);
    
    // Encrypt new vote
    unsigned char vote2[] = "VOTE:Bob";
    int vote2_len = strlen((char*)vote2);
    printf("\nOriginal vote: %s\n", vote2);
    
    HybridPackage encrypted2 = hybrid_encrypt(vote2, vote2_len, server.public_key);
    
    // Threshold decrypt using first 3 trustees
    int indices[THRESHOLD] = {0, 1, 2};
    unsigned char decrypted2[MAX_MSG_LEN] = {0};
    
    int dec_len2 = hybrid_decrypt_threshold(&encrypted2, shares, indices, 
                                             THRESHOLD, decrypted2);
    
    if (dec_len2 > 0) {
        decrypted2[dec_len2] = '\0';
        printf("\nDecrypted vote: %s\n", decrypted2);
        if (strcmp((char*)vote2, (char*)decrypted2) == 0)
            printf("SUCCESS: Threshold decryption matched!\n");
        else
            printf("FAILED: Threshold decryption mismatch!\n");
    }
    
    printf("\n========================================\n");
    printf(" DEMO COMPLETE\n");
    printf("========================================\n");
    
    return 0;
}