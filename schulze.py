# Schulze Method Implementation in Python


def schulze_method():
    
    # ---------------------INPUT SECTION------------------------------------

    # Number of candidates
    C = int(input("Enter number of candidates: "))

    # Candidate names
    candidates = []
    print("\nEnter candidate names:")
    for _ in range(C):
        candidates.append(input())

    # Mapping name → index for easy use
    index = {candidates[i]: i for i in range(C)}

    # Number of voters
    V = int(input("\nEnter number of voters: "))

    # Initialize pairwise preference matrix d[i][j]
    # d[i][j] = number of voters preferring i over j
    d = [[0] * C for _ in range(C)]

    # ----------------------COLLECT VOTES-----------------------------------
    
    print("\nEnter each voter's ranking from 1st to last:")
    print("Example: If candidates are A, B, C, enter: A B C")

    for v in range(V):
        print(f"\nVoter {v+1}:")
        ranking = input().split()

        # Convert ranking (list of names) to indices
        ranking_idx = [index[name] for name in ranking]

        # For every pair (i, j), if ranking_idx[i] is above ranking_idx[j],
        # increase d[i][j]
        for i in range(C):
            for j in range(i + 1, C):
                higher = ranking_idx[i]
                lower = ranking_idx[j]
                d[higher][lower] += 1

    # ------------------------      STEP 1: INITIALIZE p[i][j] = d[i][j] - d[j][i]            ---------------------------------
    
    p = [[0] * C for _ in range(C)]

    for i in range(C):
        for j in range(C):
            if i != j:
                p[i][j] = d[i][j] - d[j][i]
            if i==j:
                p[i][j]=0

    # ------------------------ STEP 2: COMPUTE STRONGEST PATHS (WIDEST PATH PROBLEM)  ---------------------------------
    # ---------------------------- Using Floyd–Warshall-style dynamic programming  ----------------------------
    for k in range(C):
        for i in range(C):
            if i != k:
                for j in range(C):
                    if j != k and j != i:
                        # p[i][j] = max(p[i][j], min(p[i][k], p[k][j]))
                        p[i][j] = max(p[i][j], min(p[i][k], p[k][j]))

    # ----------------------- OUTPUT THE MATRICES ---------------------------------- 

    print("\nPairwise Preference Matrix d[i][j]:")
    print_matrix(d, candidates)

    print("\nStrongest Path Matrix p[i][j]:")
    print_matrix(p, candidates)

    # ----------------------  DETERMINE WINNER    ----------------------------------- 
    # -----------------------  Candidate X wins if p[X][Y] >= p[Y][X] for every Y   ----------------------------------
    winner = None

    for i in range(C):
        wins_all = True
        for j in range(C):
            if i != j and p[i][j] < p[j][i]:
                wins_all = False
                break
        if wins_all:
            winner = candidates[i]
            break

    print("\nWinner of the election:", winner)


# ------------------------  Helper function to print matrices with labels    ---------------------------------

def print_matrix(matrix, candidates):
    C = len(candidates)
    print("      " + "  ".join(f"{c:>5}" for c in candidates))
    for i in range(C):
        row_str = f"{candidates[i]:>5} "
        for j in range(C):
            row_str += f"{matrix[i][j]:>5} "
        print(row_str)


# ---------------------- RUN THE PROGRAM -----------------------------------

schulze_method()
