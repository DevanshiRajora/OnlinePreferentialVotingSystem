
from typing import List, Dict, Tuple, Optional

def print_matrix(matrix: List[List[int]], candidates: List[str]):
    """Helper function to print matrices with labels."""
    C = len(candidates)
    # Adjust spacing for matrix output
    print("      " + "  ".join(f"{c:>5}" for c in candidates))
    for i in range(C):
        row_str = f"{candidates[i]:>5} "
        for j in range(C):
            # Use ' - ' for cells that should be empty (like diagonal or 0 initial path strength)
            val = matrix[i][j]
            display_val = str(val) if val > 0 else ' - ' 
            row_str += f"{display_val:>5} "
        print(row_str)

def calculate_schulze_winner(candidates: List[str], rankings: List[List[str]]) -> Tuple[str, List[List[int]], List[List[int]]]:
    """
    Core Schulze method logic to calculate the winner based on provided candidate list and rankings.

    Args:
        candidates: List of candidate names.
        rankings: List of votes, where each vote is a list of candidate names ranked from 1st to last.

    Returns:
        Tuple of (winner_name: str, d_matrix: List[List[int]], p_matrix: List[List[int]])
    """
    C = len(candidates)
    if C <= 1:
        return "Not enough candidates", [], []

    # Mapping name → index for easy use
    index = {candidates[i]: i for i in range(C)}
    
    # 1. Initialize pairwise preference matrix d[i][j]
    # d[i][j] = number of voters preferring i over j
    d = [[0] * C for _ in range(C)]

    # 2. Process rankings to fill d (Pairwise Preference Matrix)
    for ranking in rankings:
        # Skip invalid rankings (should be caught by the calling function, but safe to check)
        if len(ranking) != C or set(ranking) != set(candidates):
             continue 

        # Convert ranking (list of names) to indices
        ranking_idx = [index[name] for name in ranking]
        
        # --- Update the pairwise preference matrix d ---
        # Iterate over all possible pairs (i, j)
        for i_pos in range(C):
            i_idx = ranking_idx[i_pos] 
            for j_pos in range(i_pos + 1, C):
                j_idx = ranking_idx[j_pos] 
                
                # Since i_pos < j_pos, candidate i_idx is preferred over j_idx
                d[i_idx][j_idx] += 1
                
    # 3. STEP 1: INITIALIZE PATH STRENGTH (p) 
    # p[i][j] = d[i][j] if d[i][j] > d[j][i], else 0
    p = [[0] * C for _ in range(C)]

    for i in range(C):
        for j in range(C):
            if i != j and d[i][j] > d[j][i]:
                # The initial path strength is the number of voters preferring i over j
                p[i][j] = d[i][j] 
            # Otherwise, p[i][j] remains 0
    
    # 4. STEP 2: COMPUTE STRONGEST PATHS (Floyd-Warshall variant for Widest Path)
    for k in range(C):
        for i in range(C):
            for j in range(C):
                if i != j and i != k and j != k:
                    # p[i][j] = max(current_path, path_via_k)
                    # Path strength via k is limited by the weakest link: min(p[i][k], p[k][j])
                    p[i][j] = max(p[i][j], min(p[i][k], p[k][j]))

    # 5. DETERMINE WINNER 
    # Candidate X wins if p[X][Y] >= p[Y][X] for every Y
    possible_winners = []
    
    for i in range(C):
        wins_all = True
        for j in range(C):
            if i != j and p[i][j] < p[j][i]:
                wins_all = False
                break
        if wins_all:
            possible_winners.append(candidates[i])
            
    # 6. Format Winner Output
    winner_name: str
    if len(possible_winners) == 1:
        winner_name = possible_winners[0]
    elif len(possible_winners) > 1:
        # The Schulze method is designed to always produce a single winner or a tie set
        winner_name = "Tied Winners: " + ", ".join(possible_winners)
    else:
        # This case is extremely rare for Schulze unless there are no valid votes
        winner_name = "No single winner (Cycle/Undefined)"
            
    return winner_name, d, p

# If this file is run directly, it still executes the original interactive calculator logic
if __name__ == '__main__':
    # Simple example to demonstrate the core function without full input loop
    
    # Example data from Wikipedia Schulze Method page (5 voters, 3 candidates: A, B, C)
    example_candidates = ['A', 'B', 'C']
    example_rankings = [
        ['A', 'C', 'B'], # Voter 1
        ['A', 'C', 'B'], # Voter 2
        ['B', 'A', 'C'], # Voter 3
        ['C', 'A', 'B'], # Voter 4
        ['C', 'B', 'A'], # Voter 5
    ]
    
    print("\n" + "="*50)
    print("--- Schulze Method Calculator (Module Test) ---")
    print("="*50)

    winner, d_matrix, p_matrix = calculate_schulze_winner(example_candidates, example_rankings)

    print("\nPairwise Preference Matrix d[i][j]: (i preferred over j)")
    print_matrix(d_matrix, example_candidates)

    print("\nStrongest Path Matrix p[i][j]: (Path strength from i to j)")
    print_matrix(p_matrix, example_candidates)
    print("="*40)

    print("\n🏆 Final Winner of the election:", winner)

