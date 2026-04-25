from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import secrets
from typing import List, Dict
import sys

# Import your existing modules
try:
    from crypto_primitives import (
        generate_threshold_keys, 
        hybrid_encrypt_vote, 
        hybrid_decrypt_vote, 
        P_PRIME
    )
    from schulze_method_base import calculate_schulze_winner, print_matrix
except ImportError:
    print("Error: Required files not found. Ensure crypto_primitives.py and schulze_method_base.py are in the same folder.")
    sys.exit(1)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
CORS(app)

# Global election state
election_state = {
    'setup_complete': False,
    'voting_active': False,
    'results_available': False,
    'candidates': [],
    'n_candidates': 0,
    'n_authorities': 0,
    'threshold': 0,
    'n_voters': 0,
    'encrypted_votes': [],
    'authority_shares': {},
    'joint_public_key': 0,
    'votes_cast': 0,
    'decrypted_votes': [],
    'winner': None,
    'd_matrix': [],
    'p_matrix': [],
    #edited
    'voter_keys': {},            # voter_id → {sk, pk}
    'rings': {},                 # ring_id → list of public keys
    'voter_ring_id': {},         # voter_id → ring_id
    'used_key_images': set(),    # for double-vote detection
#edited
}


@app.route('/')
def index():
    return render_template('index.html')
@app.route('/api/setup', methods=['POST'])
def setup_election():
    """Initialize election with candidates and cryptographic parameters"""
    try:
        data = request.json
        candidates = data.get('candidates', [])
        n_authorities = int(data.get('n_authorities', 5))
        threshold = int(data.get('threshold', 3))
        n_voters = int(data.get('n_voters', 10))
        
        # Validation
        if len(candidates) < 2:
            return jsonify({'success': False, 'error': 'At least 2 candidates required'}), 400
        
        if threshold > n_authorities or threshold <= 0:
            return jsonify({'success': False, 'error': 'Invalid threshold'}), 400
        
        if n_voters < 1:
            return jsonify({'success': False, 'error': 'At least 1 voter required'}), 400
        
        # Generate threshold keys
        _, authority_shares, joint_public_key = generate_threshold_keys(
            n_authorities, threshold, P_PRIME
        )
        
        # Update base election state
        election_state.update({
            'setup_complete': True,
            'voting_active': True,
            'candidates': candidates,
            'n_candidates': len(candidates),
            'n_authorities': n_authorities,
            'threshold': threshold,
            'n_voters': n_voters,
            'authority_shares': authority_shares,
            'joint_public_key': joint_public_key,
            'encrypted_votes': [],
            'used_voter_ids': set(),  # added
            'votes_cast': 0
        })

        # -----------------------------------------------------
        # RING SIGNATURE INITIALIZATION
        # -----------------------------------------------------

        from ring_signature import generate_voter_keypair

        # 1️⃣ Generate keypairs per voter
        voter_keys = {}
        for vid in range(1, n_voters + 1):
            sk, pk = generate_voter_keypair()
            voter_keys[vid] = {"sk": sk, "pk": pk}

        # 2️⃣ Create rings (size ≤ 10)
        RING_SIZE = 10
        rings = {}
        voter_ring_id = {}

        ring_id = 1
        current_ring = []

        for vid in range(1, n_voters + 1):
            current_ring.append(voter_keys[vid]["pk"])
            voter_ring_id[vid] = ring_id

            if len(current_ring) == RING_SIZE:
                rings[ring_id] = current_ring
                ring_id += 1
                current_ring = []

        # leftover
        if current_ring:
            rings[ring_id] = current_ring

        # store in election state
        election_state['voter_keys'] = voter_keys
        election_state['rings'] = rings
        election_state['voter_ring_id'] = voter_ring_id
        election_state['used_key_images'] = set()
        election_state['used_voter_ids'] = set() #added

        # -----------------------------------------------------

        # Prepare ring metadata for frontend
        ring_metadata = {
            "total_voters": n_voters,
            "ring_size_limit": RING_SIZE,
            "number_of_rings": len(rings),
            "distribution": {
                ring_id: len(rings[ring_id]) for ring_id in rings
            },
            "public_keys": rings
        }

        return jsonify({
            'success': True,
            'message': 'Election setup complete',
            'candidates': candidates,
            'n_voters': n_voters,
            'crypto_info': {
                'n_authorities': n_authorities,
                'threshold': threshold,
                'public_key': joint_public_key
            },
            'ring_info': ring_metadata
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current election status"""
    return jsonify({
        'setup_complete': election_state['setup_complete'],
        'voting_active': election_state['voting_active'],
        'results_available': election_state['results_available'],
        'candidates': election_state['candidates'],
        'votes_cast': election_state['votes_cast'],
        'n_voters': election_state['n_voters']
    })

#edited
@app.route('/api/vote', methods=['POST'])
def cast_vote():
    """Cast an encrypted vote with ring signature"""
    try:
        if not election_state['voting_active']:
            return jsonify({'success': False, 'error': 'Voting is not active'}), 400
        
        data = request.json
        ranking = data.get('ranking', [])
        voter_id_input = data.get('voter_id', '').strip()

        # Must exist
        if not voter_id_input:
            return jsonify({'success': False, 'error': 'Voter ID required'}), 400

        # Must be exactly 5 digits
        if not voter_id_input.isdigit() or len(voter_id_input) != 5:
            return jsonify({'success': False, 'error': 'Voter ID must be exactly 5 digits'}), 400

        # 3rd digit must be 0
        if voter_id_input[2] != '0':
            return jsonify({'success': False, 'error': '3rd digit must be 0'}), 400

        # First digit cannot be 0
        if voter_id_input[0] == '0':
            return jsonify({'success': False, 'error': 'Cannot start with 0'}), 400

        # Last digit must be even
        if int(voter_id_input[-1]) % 2 != 0:
            return jsonify({'success': False, 'error': 'Last digit must be even'}), 400

     
        #added
        # Prevent double voting using same voter ID
        if voter_id_input in election_state['used_voter_ids']:
            return jsonify({'success': False, 'error': 'This Voter ID has already voted'}), 400

        # Validation susss
        if len(ranking) != election_state['n_candidates']:
            return jsonify({'success': False, 'error': 'Invalid ranking length'}), 400
        
        if set(ranking) != set(election_state['candidates']):
            return jsonify({'success': False, 'error': 'Invalid candidates in ranking'}), 400
        
    
        # Check if max votes reached
        if election_state['votes_cast'] >= election_state['n_voters']:
            return jsonify({'success': False, 'error': 'Maximum votes reached'}), 400
        
        # Encrypt the vote
        vote_data_str = ",".join(ranking)
        encrypted_package = hybrid_encrypt_vote(
            vote_data_str, 
            election_state['joint_public_key']
        )

        # ---------------------------------------------------------
        # RING SIGNATURE INTEGRATION (Option A: voter = vote number)
        # ---------------------------------------------------------

        from ring_signature import ring_sign, hash_mod_p

        # 1️⃣ Determine voter ID based on vote count
        voter_id = election_state['votes_cast'] + 1  # 1st vote = voter 1, etc.

        # 2️⃣ Load voter's secret & public key
        my_sk = election_state['voter_keys'][voter_id]["sk"]
        my_pk = election_state['voter_keys'][voter_id]["pk"]

        # 3️⃣ Determine their ring
        ring_id = election_state['voter_ring_id'][voter_id]
        ring_public_keys = election_state['rings'][ring_id]

        # 4️⃣ Identify my index in the ring
        my_index = ring_public_keys.index(my_pk)

        # 5️⃣ Compute message hash for signing
        # msg_hash = hash_mod_p(str(encrypted_package))
        import json
        msg_hash = hash_mod_p(json.dumps(encrypted_package, sort_keys=True))

        # 6️⃣ Generate ring signature
        signature = ring_sign(msg_hash, ring_public_keys, my_index, my_sk)

        # 7️⃣ Build final ballot object
        ballot = {
            "encrypted_package": encrypted_package,
            "ring_id": ring_id,
            "signature": signature,
            "key_image": signature["key_image"]
        }

        # ---------------------------------------------------------

        # Store final signed ballot
        election_state['encrypted_votes'].append(ballot)
        election_state['votes_cast'] += 1
        
        # added !!
        # Mark voter ID as used ONLY after successful vote
        election_state['used_voter_ids'].add(voter_id_input)

        return jsonify({
            'success': True,
            'message': 'Vote cast successfully',
            'vote_number': election_state['votes_cast'],
            'encrypted': True
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

#edited-

@app.route('/api/close-voting', methods=['POST'])
def close_voting():
    """Close voting period"""
    election_state['voting_active'] = False
    return jsonify({
        'success': True,
        'message': 'Voting closed',
        'total_votes': election_state['votes_cast']
    })
@app.route('/api/decrypt', methods=['POST'])
def decrypt_votes():
    """Decrypt all votes using threshold cryptography + ring signature verification"""
    try:
        if election_state['voting_active']:
            return jsonify({'success': False, 'error': 'Close voting first'}), 400
        
        # Select threshold shares
        selected_shares = {
            idx: election_state['authority_shares'][idx] 
            for idx in range(1, election_state['threshold'] + 1)
        }

        # -----------------------------
        # RING SIGNATURE VERIFICATION
        # -----------------------------
        from ring_signature import ring_verify, hash_mod_p

        used_images = election_state['used_key_images']
        decrypted_rankings = []

        for ballot in election_state['encrypted_votes']:

            encrypted_pkg = ballot["encrypted_package"]
            ring_id = ballot["ring_id"]
            signature = ballot["signature"]
            key_image = ballot["key_image"]

            # 1) Compute message hash
            # msg_hash = hash_mod_p(str(encrypted_pkg))
            import json
            msg_hash = hash_mod_p(json.dumps(encrypted_pkg, sort_keys=True))

            # 2) Load ring public keys
            ring_public_keys = election_state['rings'][ring_id]

            # 3) Verify ring signature
            if not ring_verify(msg_hash, signature, ring_public_keys):
                print("❌ Invalid ring signature. Ballot rejected.")
                continue

            # 4) Double vote detection
            if key_image in used_images:
                print("❌ Double vote detected (key image reused). Ballot rejected.")
                continue

            used_images.add(key_image)

            # 5) Decrypt vote
            decrypted_vote = hybrid_decrypt_vote(
                encrypted_pkg,
                selected_shares,
                election_state['threshold'],
                election_state['candidates']
            )

            if decrypted_vote:
                decrypted_rankings.append(decrypted_vote)

        # Save results
        election_state['used_key_images'] = used_images
        election_state['decrypted_votes'] = decrypted_rankings

        return jsonify({
            'success': True,
            'message': f'Decrypted {len(decrypted_rankings)} votes',
            'decrypted_count': len(decrypted_rankings),
            'votes': [' > '.join(v) for v in decrypted_rankings]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tally', methods=['POST'])
def tally_votes():
    """Calculate results using Schulze method"""
    try:
        if not election_state['decrypted_votes']:
            return jsonify({'success': False, 'error': 'No decrypted votes available'}), 400
        
        winner, d_matrix, p_matrix = calculate_schulze_winner(
            election_state['candidates'],
            election_state['decrypted_votes']
        )
        
        election_state.update({
            'results_available': True,
            'winner': winner,
            'd_matrix': d_matrix,
            'p_matrix': p_matrix
        })
        
        return jsonify({
            'success': True,
            'winner': winner,
            'd_matrix': d_matrix,
            'p_matrix': p_matrix,
            'candidates': election_state['candidates']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/results', methods=['GET'])
def get_results():
    """Get election results"""
    if not election_state['results_available']:
        return jsonify({'success': False, 'error': 'Results not available yet'}), 400
    
    return jsonify({
        'success': True,
        'winner': election_state['winner'],
        'd_matrix': election_state['d_matrix'],
        'p_matrix': election_state['p_matrix'],
        'candidates': election_state['candidates'],
        'total_votes': len(election_state['decrypted_votes'])
    })

@app.route('/api/reset', methods=['POST'])
def reset_election():
    """Reset election state"""
    election_state.update({
        'setup_complete': False,
        'voting_active': False,
        'results_available': False,
        'candidates': [],
        'encrypted_votes': [],
        'votes_cast': 0,
        'decrypted_votes': [],
        'winner': None
    })
    return jsonify({'success': True, 'message': 'Election reset'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)