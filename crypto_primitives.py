import math
import random
# crypto_primitives.py  (Demo-friendly, Shamir t-of-n threshold version)

import math
import random
import secrets
from typing import List, Dict, Tuple, Optional

# --- Cryptographic Constants and Utilities ---

# Simplified prime for demonstration only (NOT secure for production)
P_PRIME = 10007  # prime modulus for ElGamal components (c1, c2, h)
G_GENERATOR = 5  # generator g for ElGamal operations

# --- Correct modular inverse (Extended Euclidean Algorithm) ---
def mod_inverse(a: int, m: int) -> Optional[int]:
    a = a % m
    if a == 0:
        return None
    t, new_t = 0, 1
    r, new_r = m, a
    while new_r != 0:
        q = r // new_r
        t, new_t = new_t, t - q * new_t
        r, new_r = new_r, r - q * new_r
    if r != 1:
        return None
    return t % m

def mod_exp(base: int, exponent: int, modulus: int) -> int:
    return pow(base, exponent, modulus)

# --- Threshold "Key Setup" (Shamir secret sharing over F_p) ---
def generate_threshold_keys(n: int, t: int, p: int) -> Tuple[int, Dict[int, int], int]:
    """
    Keygen using Shamir t-of-n secret sharing over F_p:
      - joint_private_key_x in [1, p-2]
      - create polynomial f(z) = a0 + a1 z + ... + a_{t-1} z^{t-1} (mod p), with a0 = x
      - shares[i] = f(i) for i=1..n
      - joint_public_key_h = g^x mod p
    Returns (x, {i: share_i}, h)
    """
    if not (1 <= t <= n):
        raise ValueError("Threshold 't' must satisfy 1 <= t <= n")

    # Choose secret exponent x in 1..p-2
    x = secrets.randbelow(p - 2) + 1

    # Random coefficients for degree-(t-1) polynomial over F_p
    coeffs = [x] + [secrets.randbelow(p) for _ in range(t - 1)]

    def poly_eval(i: int) -> int:
        acc = 0
        pow_i = 1
        for a in coeffs:
            acc = (acc + a * pow_i) % p
            pow_i = (pow_i * i) % p
        return acc

    shares: Dict[int, int] = {i: poly_eval(i) for i in range(1, n + 1)}

    h = mod_exp(G_GENERATOR, x, p)
    return x, shares, h

# --- Hybrid Encryption / Decryption Primitives (SIMULATION) ---

class SymmetricKey:
    def __init__(self):
        self.key = secrets.token_hex(16)
        self.iv = secrets.token_hex(8)

# Fixed simulation key (deterministic demo)
# Ensure < P_PRIME so ElGamal recovers exactly without modulo surprises
FIXED_SIMULATION_KEY_INT = 2345
FIXED_SIMULATION_KEY_HEX = "0123456789abcdef0123456789abcdef"

def aes_encrypt(data: str, key: SymmetricKey) -> str:
    encrypted_data = "".join(chr(ord(c) + 1) for c in data)
    return f"AES_CXT({encrypted_data})"

def aes_decrypt(ciphertext: str, key: SymmetricKey) -> str:
    if not ciphertext.startswith("AES_CXT("):
        raise ValueError("Invalid ciphertext format")
    encrypted_data = ciphertext[8:-1]
    decrypted_data = "".join(chr(ord(c) - 1) for c in encrypted_data)
    return decrypted_data

def elgamal_encrypt_symmetric_key(symkey_obj: SymmetricKey, joint_public_key_h: int) -> Tuple[int, int]:
    message_int = FIXED_SIMULATION_KEY_INT
    # k random in 1..p-2
    k = secrets.randbelow(P_PRIME - 2) + 1
    c1 = mod_exp(G_GENERATOR, k, P_PRIME)
    h_k = mod_exp(joint_public_key_h, k, P_PRIME)
    c2 = (message_int * h_k) % P_PRIME
    return c1, c2

def hash_vote(vote: str) -> str:
    # Python's built-in hash is salted per process; for demo, keep as-is.
    return str(hash(vote))

def hybrid_encrypt_vote(vote_data: str, joint_public_key_h: int) -> Dict:
    symkey = SymmetricKey()
    symkey.key = FIXED_SIMULATION_KEY_HEX
    enc_vote = aes_encrypt(vote_data, symkey)
    c1, c2 = elgamal_encrypt_symmetric_key(symkey, joint_public_key_h)
    vote_hash = hash_vote(vote_data)
    msg_package = {
        "Enc_Vote": enc_vote,
        "IV": symkey.iv,
        "Enc_C1": c1,
        "Enc_C2": c2,
        "Hash": vote_hash,
        "Timestamp": random.randint(1000000000, 2000000000),
    }
    return {"Message": msg_package, "Original_SymKey_Int": FIXED_SIMULATION_KEY_INT}

# --- Threshold Decryption Helpers (Shamir t-of-n reconstruction) ---

def _lagrange_interpolate_at_zero(points: List[Tuple[int, int]], p: int) -> int:
    """
    Reconstruct f(0) from t points (i, f(i)) using Lagrange interpolation over F_p.
    points: list of (x_i, y_i) with distinct x_i in 1..p-1
    """
    total = 0
    for j, (xj, yj) in enumerate(points):
        num = 1
        den = 1
        for m, (xm, _ym) in enumerate(points):
            if m == j:
                continue
            num = (num * xm) % p
            den = (den * ((xm - xj) % p)) % p
        inv_den = mod_inverse(den, p)
        if inv_den is None:
            raise ValueError("Interpolation failed: denominator not invertible.")
        lambda_j = (num * inv_den) % p
        total = (total + yj * lambda_j) % p
    return total

def threshold_elgamal_decrypt_key(c1: int, c2: int, authority_shares: Dict[int, int], threshold: int) -> int:
    """
    Reconstruct x via Shamir (t-of-n), then compute:
      D = c1^x mod P_PRIME
      m = c2 * D^{-1} mod P_PRIME
    """
    if len(authority_shares) < threshold:
        raise ValueError(f"Insufficient shares: need {threshold}, got {len(authority_shares)}")

    # Deterministic selection: first `threshold` indices sorted
    selected_indices = sorted(list(authority_shares.keys()))[:threshold]
    selected_points = [(i, authority_shares[i]) for i in selected_indices]

    # Reconstruct secret x = f(0) over F_p
    reconstructed_x = _lagrange_interpolate_at_zero(selected_points, P_PRIME)

    D = mod_exp(c1, reconstructed_x, P_PRIME)
    invD = mod_inverse(D, P_PRIME)
    if invD is None:
        raise ValueError("Modular inverse of D does not exist; decryption failed.")
    recovered_message_int = (c2 * invD) % P_PRIME
    return recovered_message_int

def hybrid_decrypt_vote(
    encrypted_pkg: Dict,
    authority_shares: Dict[int, int],
    threshold: int,
    candidates: List[str],
) -> Optional[List[str]]:
    msg = encrypted_pkg["Message"]
    c1 = msg["Enc_C1"]
    c2 = msg["Enc_C2"]
    try:
        recovered_key_int = threshold_elgamal_decrypt_key(c1, c2, authority_shares, threshold)
    except Exception as e:
        print(f"Symmetric Key Decryption Failed (Threshold ElGamal): {e}")
        return None

    if recovered_key_int != FIXED_SIMULATION_KEY_INT:
        print("Symmetric Key Decryption Failed: Recovered key does not match expected key.")
        return None

    symkey_obj = SymmetricKey()
    symkey_obj.key = FIXED_SIMULATION_KEY_HEX
    symkey_obj.iv = msg.get("IV", symkey_obj.iv)

    try:
        decrypted_vote_str = aes_decrypt(msg["Enc_Vote"], symkey_obj)
    except Exception as e:
        print(f"AES decryption failed: {e}")
        return None

    try:
        decrypted_ranking = [name.strip() for name in decrypted_vote_str.split(",")]
    except Exception:
        print("Decryption succeeded but vote format invalid.")
        return None

    computed_hash = hash_vote(decrypted_vote_str)
    if computed_hash != msg["Hash"]:
        print("Integrity check failed! Hash mismatch.")
        return None

    if not all(c in candidates for c in decrypted_ranking) or len(decrypted_ranking) != len(candidates):
        print(f"Decrypted vote is invalid (bad candidates or length mismatch): {decrypted_ranking}")
        return None

    return decrypted_ranking

# --- Demo block ---
if __name__ == "__main__":
    print("--- Threshold ElGamal Primitives Demo (crypto_primitives.py) ---")
    N_AUTHORITIES = 5
    THRESHOLD = 3

    x_secret, shares, h_public = generate_threshold_keys(N_AUTHORITIES, THRESHOLD, P_PRIME)
    print(f"Generated secret x: {x_secret}")
    print(f"Generated shares (sample): { {k: shares[k] for k in sorted(shares)[:THRESHOLD]} }")
    print(f"Joint public key h: {h_public}")

    # Encrypt a vote
    VOTE = "Mars,Earth,Venus"
    encrypted_pkg = hybrid_encrypt_vote(VOTE, h_public)
    c1 = encrypted_pkg["Message"]["Enc_C1"]
    c2 = encrypted_pkg["Message"]["Enc_C2"]
    expected_m = encrypted_pkg["Original_SymKey_Int"]
    print(f"Ciphertext (c1,c2): ({c1}, {c2}) - expected m: {expected_m}")

    # Use first THRESHOLD shares for decryption demo (sorted deterministic)
    t_shares = {i: shares[i] for i in sorted(list(shares.keys()))[:THRESHOLD]}
    try:
        recovered = threshold_elgamal_decrypt_key(c1, c2, t_shares, THRESHOLD)
        print(f"Recovered message int: {recovered} (match? {recovered == expected_m})")
    except Exception as e:
        print(f"Threshold decryption failed: {e}")

    # Full hybrid decrypt
    result = hybrid_decrypt_vote(encrypted_pkg, t_shares, THRESHOLD, ["Mars", "Earth", "Venus"])
    print(f"Decrypted ranking: {result}")
