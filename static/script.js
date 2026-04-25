// Global state
let electionState = {
    candidates: [],
    currentRanking: [],
    setupComplete: false,
    ringInfo: null,
    votingActive: false
};

// Initialize page
document.addEventListener('DOMContentLoaded', () => {
    checkElectionStatus();
});

// API Helper
async function apiCall(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    const response = await fetch(`/api/${endpoint}`, options);
    return await response.json();
}

// Check election status on load
async function checkElectionStatus() {
    try {
        const result = await apiCall('status');
        if (result.setup_complete) {
            electionState.candidates = result.candidates;
            electionState.setupComplete = true;
            
            if (result.voting_active) {
                showSection('voting-section');
                updatePhase('voting');
                updateVoteStatus(result.votes_cast, result.n_voters);
                setupRankingUI(result.candidates);
            } else if (result.results_available) {
                showSection('results-section');
                updatePhase('results');
                displayResults();
            } else {
                showSection('decrypt-section');
                updatePhase('decrypt');
            }
        }
    } catch (error) {
        console.log('Starting fresh election');
    }
}

// Setup Election
async function setupElection() {
    const candidatesText = document.getElementById('candidates-input').value.trim();
    const nAuthorities = parseInt(document.getElementById('n-authorities').value);
    const threshold = parseInt(document.getElementById('threshold').value);
    const nVoters = parseInt(document.getElementById('n-voters').value);
    
    if (!candidatesText) {
        alert('Please enter at least 2 candidates');
        return;
    }
    
    const candidates = candidatesText.split('\n')
        .map(c => c.trim())
        .filter(c => c.length > 0);
    
    if (candidates.length < 2) {
        alert('Please enter at least 2 candidates');
        return;
    }
    
    try {
        const result = await apiCall('setup', 'POST', {
            candidates,
            n_authorities: nAuthorities,
            threshold,
            n_voters: nVoters
        });
        
        if (result.success) {
            electionState.ringInfo = result.ring_info;
            displayRingInfo(result.ring_info);
            electionState.candidates = candidates;
            electionState.setupComplete = true;
            showSection('voting-section');
            updatePhase('voting');
            setupRankingUI(candidates);
            updateVoteStatus(0, nVoters);
            alert(`Election initialized!\n\n${candidates.length} candidates\n${nVoters} voters\nThreshold: ${threshold} of ${nAuthorities} authorities`);
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        alert('Setup failed: ' + error.message);
    }
}

// Setup Ranking UI with drag and drop
function setupRankingUI(candidates) {
    const container = document.getElementById('ranking-container');
    container.innerHTML = '';
    
    electionState.currentRanking = [...candidates];
    
    candidates.forEach((candidate, index) => {
        const item = document.createElement('div');
        item.className = 'rank-item';
        item.draggable = true;
        item.dataset.candidate = candidate;
        
        item.innerHTML = `
            <div class="rank-number">${index + 1}</div>
            <div class="rank-name">${candidate}</div>
        `;
        
        item.addEventListener('dragstart', handleDragStart);
        item.addEventListener('dragover', handleDragOver);
        item.addEventListener('drop', handleDrop);
        item.addEventListener('dragend', handleDragEnd);
        
        container.appendChild(item);
    });
}

// Drag and Drop Handlers
let draggedElement = null;

function handleDragStart(e) {
    draggedElement = this;
    this.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}

function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleDrop(e) {
    if (e.stopPropagation) {
        e.stopPropagation();
    }
    
    if (draggedElement !== this) {
        const container = document.getElementById('ranking-container');
        const items = Array.from(container.children);
        const draggedIndex = items.indexOf(draggedElement);
        const targetIndex = items.indexOf(this);
        
        if (draggedIndex < targetIndex) {
            this.parentNode.insertBefore(draggedElement, this.nextSibling);
        } else {
            this.parentNode.insertBefore(draggedElement, this);
        }
        
        updateRankNumbers();
    }
    
    return false;
}

function handleDragEnd() {
    this.classList.remove('dragging');
    updateCurrentRanking();
}

function updateRankNumbers() {
    const items = document.querySelectorAll('.rank-item');
    items.forEach((item, index) => {
        item.querySelector('.rank-number').textContent = index + 1;
    });
}

function updateCurrentRanking() {
    const items = document.querySelectorAll('.rank-item');
    electionState.currentRanking = Array.from(items).map(
        item => item.dataset.candidate
    );
}

// Cast Vote
async function castVote() {
    updateCurrentRanking();
    
    try {
        // const result = await apiCall('vote', 'POST', {
        //     ranking: electionState.currentRanking
        // });
        const voterId = document.getElementById('voter-id-input').value.trim();

// Frontend validation
        const errorBox = document.getElementById('voter-id-error');
        errorBox.textContent = "";

        if (!/^\d{5}$/.test(voterId)) {
            errorBox.textContent = "Voter ID must be exactly 5 digits.";
            return;
        }

        if (voterId[2] !== '0') {
            errorBox.textContent = "Invalid Voter ID. 3rd digit must be 0.";
            return;
        }

        const result = await apiCall('vote', 'POST', {
            ranking: electionState.currentRanking,
            voter_id: voterId
        });



        if (!result.success) {
            errorBox.textContent = result.error;
            return;
        }
        // ✅ Vote successful

        errorBox.textContent = "";

        // Show confirmation
        alert(`✅ Vote ${result.vote_number} encrypted and cast successfully!`);

        // Shuffle ranking for next voter
        shuffleRanking();

        // Clear voter ID field
        document.getElementById('voter-id-input').value = "";

        // Update vote counter from backend
        const status = await apiCall('status');
        updateVoteStatus(status.votes_cast, status.n_voters);
        
        // if (result.success) {
        //     alert(`✅ Vote ${result.vote_number} encrypted and cast successfully!`);
            
        //     // Shuffle ranking for next voter
        //     shuffleRanking();
            
        //     // Update status
        //     const status = await apiCall('status');
        //     updateVoteStatus(status.votes_cast, status.n_voters);
        // } else {
        //     alert('Error: ' + result.error);
        // }
    } catch (error) {
        alert('Vote casting failed: ' + error.message);
    }
}

function shuffleRanking() {
    const candidates = [...electionState.candidates];
    for (let i = candidates.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [candidates[i], candidates[j]] = [candidates[j], candidates[i]];
    }
    setupRankingUI(candidates);
}

function updateVoteStatus(cast, total) {
    const statusBox = document.getElementById('vote-status');
    statusBox.innerHTML = `<strong>Votes Cast:</strong> ${cast} / ${total}`;
    statusBox.className = 'status-box' + (cast >= total ? ' success' : '');
}

// Close Voting
async function closeVoting() {
    if (!confirm('Are you sure you want to close voting? This cannot be undone.')) {
        return;
    }
    
    try {
        const result = await apiCall('close-voting', 'POST');
        if (result.success) {
            alert(`Voting closed. ${result.total_votes} votes recorded.`);
            showSection('decrypt-section');
            updatePhase('decrypt');
            
            const info = document.getElementById('decrypt-info');
            info.innerHTML = `<strong>Total Encrypted Votes:</strong> ${result.total_votes}`;
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

// Decrypt Votes
async function decryptVotes() {
    try {
        const result = await apiCall('decrypt', 'POST');
        
        if (result.success) {
            displayDecryptedVotes(result.votes);
            alert(`✅ Successfully decrypted ${result.decrypted_count} votes!`);
            
            setTimeout(() => {
                showSection('results-section');
                updatePhase('results');
            }, 2000);
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        alert('Decryption failed: ' + error.message);
    }
}

function displayDecryptedVotes(votes) {
    const container = document.getElementById('decrypted-votes');
    container.innerHTML = '<h3 style="margin-top: 20px;">Decrypted Votes:</h3>';
    
    votes.forEach((vote, index) => {
        const item = document.createElement('div');
        item.className = 'vote-item';
        item.innerHTML = `<strong>Vote ${index + 1}:</strong> ${vote}`;
        container.appendChild(item);
    });
}

// Tally Votes
async function tallyVotes() {
    try {
        const result = await apiCall('tally', 'POST');
        
        if (result.success) {
            displayResults();
            alert('🎉 Winner calculated using Schulze Method!');
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        alert('Tallying failed: ' + error.message);
    }
}

// Display Results
async function displayResults() {
    try {
        const result = await apiCall('results');
        
        if (result.success) {
            // Winner announcement
            const winnerDiv = document.getElementById('winner-announcement');
            winnerDiv.innerHTML = `
                <h3>🏆 Election Winner</h3>
                <p style="font-size: 2.5em; margin: 15px 0;">${result.winner}</p>
                <p>Based on ${result.total_votes} votes using the Schulze Method</p>
            `;
            
            // Matrices
            displayMatrix('d-matrix', result.d_matrix, result.candidates, 'Pairwise Preferences');
            displayMatrix('p-matrix', result.p_matrix, result.candidates, 'Strongest Paths');
        }
    } catch (error) {
        console.error('Error displaying results:', error);
    }
}

function displayMatrix(elementId, matrix, candidates, title) {
    const container = document.getElementById(elementId);
    
    let html = '<table><thead><tr><th></th>';
    candidates.forEach(c => {
        html += `<th>${c}</th>`;
    });
    html += '</tr></thead><tbody>';
    
    matrix.forEach((row, i) => {
        html += `<tr><th>${candidates[i]}</th>`;
        row.forEach(val => {
            html += `<td>${val > 0 ? val : '-'}</td>`;
        });
        html += '</tr>';
    });
    
    html += '</tbody></table>';
    container.innerHTML = html;
}

// Reset Election
async function resetElection() {
    if (!confirm('Reset the entire election? All data will be lost.')) {
        return;
    }
    
    try {
        await apiCall('reset', 'POST');
        location.reload();
    } catch (error) {
        alert('Reset failed: ' + error.message);
    }
}

// UI Helpers
function showSection(sectionId) {
    document.querySelectorAll('.section').forEach(section => {
        section.classList.remove('active');
    });
    document.getElementById(sectionId).classList.add('active');
}

function updatePhase(phase) {
    const phases = ['setup', 'voting', 'decrypt', 'results'];
    const currentIndex = phases.indexOf(phase);
    
    phases.forEach((p, index) => {
        const element = document.getElementById(`phase-${p}`);
        element.classList.remove('active', 'completed');
        
        if (index < currentIndex) {
            element.classList.add('completed');
        } else if (index === currentIndex) {
            element.classList.add('active');
        }
    });
}

function displayRingInfo(ringInfo) {
    const container = document.getElementById('ring-info-container');

    let html = `
        <div class="card" style="margin-top:20px;">
            <h3>🔐 Ring Signature Layer Active</h3>
            <p><strong>Total Voters:</strong> ${ringInfo.total_voters}</p>
            <p><strong>Ring Size Limit:</strong> ${ringInfo.ring_size_limit}</p>
            <p><strong>Number of Rings Formed:</strong> ${ringInfo.number_of_rings}</p>

            <h4>Ring Distribution:</h4>
    `;

    for (let ringId in ringInfo.distribution) {
        html += `<p>Ring ${ringId} → ${ringInfo.distribution[ringId]} voters</p>`;
    }

    html += `
            <button onclick="toggleRingDetails()">View Ring Structure</button>
            <div id="ring-details" style="display:none; margin-top:15px;"></div>
        </div>
    `;

    container.innerHTML = html;

    // Populate hidden details
    const details = document.getElementById('ring-details');
    let detailHTML = "";

    for (let ringId in ringInfo.public_keys) {
        detailHTML += `<h4>Ring ${ringId}</h4><ul>`;
        ringInfo.public_keys[ringId].forEach(pk => {
            detailHTML += `<li>${pk}</li>`;
        });
        detailHTML += "</ul>";
    }

    details.innerHTML = detailHTML;
}

function toggleRingDetails() {
    const details = document.getElementById('ring-details');
    details.style.display = details.style.display === 'none' ? 'block' : 'none';
}