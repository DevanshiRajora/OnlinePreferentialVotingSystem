import secrets
import json
from crypto_primitives import P_PRIME, G_GENERATOR, mod_exp

# -----------------------------------------
# Stable hash function
# -----------------------------------------
# def hash_mod_p(*args):
#     data = json.dumps(args, sort_keys=True)
#     return abs(hash(data)) % P_PRIME
import hashlib

def hash_mod_p(*args):
    data = json.dumps(args, sort_keys=True).encode()
    digest = hashlib.sha256(data).hexdigest()
    return int(digest, 16) % P_PRIME


# -----------------------------------------
# Key generation
# -----------------------------------------
def generate_voter_keypair():
    sk = secrets.randbelow(P_PRIME - 2) + 1
    pk = mod_exp(G_GENERATOR, sk, P_PRIME)
    return sk, pk


# -----------------------------------------
# Ring Sign (Stable Demo Version)
# -----------------------------------------
def ring_sign(message_hash, ring_public_keys, my_index, my_secret_key):

    # Random nonce
    nonce = secrets.randbelow(P_PRIME - 1)

    # Commitment
    commitment = mod_exp(G_GENERATOR, nonce, P_PRIME)

    # Challenge
    challenge = hash_mod_p(message_hash, commitment)

    # Response = nonce - sk * challenge mod (p-1)
    response = (nonce - my_secret_key * challenge) % (P_PRIME - 1)

    # Key image (prevents double voting)
    key_image = mod_exp(G_GENERATOR, my_secret_key, P_PRIME)

    return {
        "commitment": commitment,
        "challenge": challenge,
        "response": response,
        "key_image": key_image
    }


# -----------------------------------------
# Ring Verify
# -----------------------------------------
def ring_verify(message_hash, signature, ring_public_keys):

    commitment = signature["commitment"]
    challenge = signature["challenge"]
    response = signature["response"]

    # Check against ALL public keys in ring
    for pk in ring_public_keys:

        # Compute expected commitment:
        # g^response * pk^challenge mod p
        left = (
            mod_exp(G_GENERATOR, response, P_PRIME) *
            mod_exp(pk, challenge, P_PRIME)
        ) % P_PRIME

        # Recompute challenge
        computed_challenge = hash_mod_p(message_hash, left)

        if computed_challenge == challenge:
            return True

    return False
