import math
import sys
from typing import List, Dict, Tuple, Optional

# IMPORTANT: You must have 'crypto_primitives.py' and 'schulze_method_base.py' 
# (the functional version, saved from previous steps) in the same folder.
try:
    from crypto_primitives import (
        generate_threshold_keys, 
        hybrid_encrypt_vote, 
        hybrid_decrypt_vote, 
        P_PRIME
    )
    # The functional Schulze method is imported here
    from schulze_method_base import calculate_schulze_winner, print_matrix
except ImportError:
    print("Error: Required files (crypto_primitives.py and schulze_method_base.py) not found.")
    print("Please ensure all three files are saved in the same folder.")
    sys.exit(1)


# --- GLOBAL ELECTION DATA STORAGE ---
ENCRYPTED_VOTES = []
AUTHORITY_SHARES: Dict[int, int] = {}
JOINT_PUBLIC_KEY: int = 0
CANDIDATES: List[str] = []
N_CANDIDATES: int = 0
N_AUTHORITIES: int = 0
THRESHOLD: int = 0
N_VOTERS: int = 0


# --- ELECTION SETUP PHASE (Interactive) ---

def interactive_setup():
    """Gathers all necessary election parameters from the user."""
    global CANDIDATES, N_CANDIDATES, N_AUTHORITIES, THRESHOLD, N_VOTERS, AUTHORITY_SHARES, JOINT_PUBLIC_KEY
    
    print("--- 1. ELECTION SETUP ---")
    
    # 1. Candidate Setup
    try:
        C = int(input("Enter number of candidates: "))
        if C <= 1:
            print("Must have at least two candidates.")
            return False
    except ValueError:
        print("Invalid number entered for candidates.")
        return False
    
    CANDIDATES = []
    print("\nEnter candidate names:")
    for i in range(C):
        name = input(f"Candidate {i+1}: ").strip()
        if not name:
            print("Candidate name cannot be empty.")
            return False
        CANDIDATES.append(name)
    N_CANDIDATES = C

    # 2. Authority Setup
    try:
        N_AUTHORITIES = int(input("\nEnter total number of decryption authorities (N): "))
        THRESHOLD = int(input("Enter minimum threshold for decryption (t): "))
        if THRESHOLD > N_AUTHORITIES or THRESHOLD <= 0:
            print("Invalid Threshold. Must be 1 <= t <= N.")
            return False
    except ValueError:
        print("Invalid number entered for authorities/threshold.")
        return False
        
    # 3. Voter Count
    try:
        N_VOTERS = int(input("\nEnter number of voters (V): "))
        if N_VOTERS < 1:
            print("Must have at least one voter.")
            return False
    except ValueError:
        print("Invalid number entered for voters.")
        return False
        
    # 4. Generate Keys
    print("\n--- Key Generation ---")
    print(f"Generating Threshold ElGamal key shares for N={N_AUTHORITIES}, t={THRESHOLD}...")
    try:
        # Note: Joint private key (JOINT_PRIVATE_KEY) is not stored globally for security simulation, but generated.
        _, AUTHORITY_SHARES, JOINT_PUBLIC_KEY = generate_threshold_keys(
            N_AUTHORITIES, THRESHOLD, P_PRIME
        )
        print("  Success: Threshold ElGamal Public Key Generated and Shares Distributed.")
    except ValueError as e:
        print(f"  FATAL ERROR during key setup: {e}")
        return False
        
    print("-" * 30)
    return True

# --- VOTE CASTING & ENCRYPTION PHASE (Interactive) ---

def interactive_voting():
    """Allows user to enter rankings, which are then encrypted."""
    print("--- 2. INTERACTIVE VOTE CASTING (Hybrid Encryption) ---")
    print("\nEnter each voter's ranking from 1st to last:")
    print(f"Example: Enter ranking as a single line, separated by spaces (e.g., {' '.join(CANDIDATES)})")

    candidate_names_set = set(CANDIDATES)

    for v in range(N_VOTERS):
        while True:
            print(f"\nVoter {v+1}:")
            ranking = input().split()
            
            # Input validation (must match candidate list exactly)
            if len(ranking) != N_CANDIDATES:
                print(f"Error: Ranking must contain exactly {N_CANDIDATES} candidates.")
                continue
            
            # Check for unknown or duplicate names
            if set(ranking) != candidate_names_set:
                print("Error: Invalid candidates or duplicates found in ranking. Try again.")
                continue

            break # Exit the loop if input is valid

        # Convert list of candidates to a string for encryption (e.g., "Earth,Mars,Venus,Mercury")
        vote_data_str = ",".join(ranking)
        
        # Hybrid Encryption: AES encrypts data, Threshold ElGamal encrypts the AES key
        encrypted_package = hybrid_encrypt_vote(vote_data_str, JOINT_PUBLIC_KEY)
        
        # Store the encrypted package (simulates transmission to the server/blockchain)
        ENCRYPTED_VOTES.append(encrypted_package)
    
    print(f"\n  Total encrypted votes stored: {len(ENCRYPTED_VOTES)}")
    print("-" * 30)

# --- DECRYPTION & TALLYING PHASE ---

def tally_votes():
    """Orchestrates the collaborative decryption and final vote counting."""
    print("--- 3. COLLABORATIVE DECRYPTION (Threshold ElGamal) ---")
    
    decrypted_rankings: List[List[str]] = []
    
    # 1. Select the minimum required shares (t) from the available authorities
    # We use shares from authorities 1 up to the threshold 't'
    selected_authority_shares = {
        idx: AUTHORITY_SHARES[idx] 
        for idx in range(1, THRESHOLD + 1)
    }
    
    print(f"  Decryption requires {THRESHOLD} shares. Using shares from authorities 1-{THRESHOLD}.")
    
    # 2. Iterate through all encrypted votes and decrypt them
    print(f"  Attempting to decrypt {len(ENCRYPTED_VOTES)} votes...")
    successful_decryptions = 0
    
    for encrypted_pkg in ENCRYPTED_VOTES:
        
        # The core step: collaborative threshold decryption
        decrypted_vote = hybrid_decrypt_vote(
            encrypted_pkg, 
            selected_authority_shares, 
            THRESHOLD,
            CANDIDATES
        )
        
        if decrypted_vote:
            decrypted_rankings.append(decrypted_vote)
            successful_decryptions += 1
            
    print(f"\n  Decryption Complete: {successful_decryptions} / {N_VOTERS} votes successfully recovered.")
    
    # Print the decrypted votes for verification
    if decrypted_rankings:
        print("\n--- Decrypted Votes ---")
        for i, ranking in enumerate(decrypted_rankings):
            print(f"Vote {i+1}: {' > '.join(ranking)}")
    
    print("-" * 30)
    
    # 3. Final Vote Counting (Schulze Method)
    print("--- 4. FINAL COUNTING (SCHULZE METHOD) ---")
    
    if not decrypted_rankings:
        print("No valid votes to count. Election result is undefined.")
        return

    # Use the imported functional Schulze method
    winner, d_matrix, p_matrix = calculate_schulze_winner(CANDIDATES, decrypted_rankings)
    
    print("\nPairwise Preference Matrix d[i][j]:")
    print_matrix(d_matrix, CANDIDATES)
    
    print("\nStrongest Path Matrix p[i][j]:")
    print_matrix(p_matrix, CANDIDATES)

    print("\n--- ELECTION RESULT (SCHULZE WINNER) ---")
    print(f"The final winner of the election is: {winner}")
    print("-" * 30)


# --- MAIN EXECUTION ---
if __name__ == '__main__':
    if interactive_setup():
        interactive_voting()
        tally_votes()