// Configuration
const API_BASE_URL = 'http://YOUR_SERVER_IP:8080/api';  // Replace with your server URL

// Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand();
tg.ready();

// Global state
let currentUser = null;
let currentGame = null;
let currentQuestionIndex = 0;
let score = 0;

// PRO games list
const PRO_GAMES = [
    'moto_tug', 'adventure', 'penguin_race', 'tractor_pull',
    'auto_racing', 'water_moto', 'swimming', 'memory_match',
    'word_search', 'hangman', 'flashcards', 'crossword',
    'hidden_object', 'categorization', 'sequence_order'
];

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    try {
        // Get user from Telegram WebApp
        const initData = tg.initDataUnsafe;
        if (initData.user) {
            await loadUser(initData.user.id);
        } else {
            showError('Please open this app from Telegram');
        }
    } catch (error) {
        console.error('Init error:', error);
        showError('Failed to initialize app');
    }
});

// Load user data
async function loadUser(userId) {
    try {
        const response = await fetch(`${API_BASE_URL}/user/${userId}`);
        const data = await response.json();
        
        if (data.error) {
            showError('User not registered. Please use /start command in bot first.');
            return;
        }
        
        currentUser = data;
        document.getElementById('userName').textContent = data.name;
        
        if (data.is_pro) {
            document.getElementById('proBadge').classList.remove('hidden');
        }
        
        // Check if admin
        const ADMIN_IDS = [123456789];  // Same as in bot.py
        if (ADMIN_IDS.includes(userId)) {
            document.getElementById('adminPanel').classList.remove('hidden');
            loadAdminStats();
        }
        
        hideLoading();
        showDashboard();
    } catch (error) {
        console.error('Load user error:', error);
        showError('Failed to load user data');
    }
}

// Navigation functions
function showDashboard() {
    hideAll();
    document.getElementById('dashboard').classList.remove('hidden');
}

function showMyGames() {
    hideAll();
    document.getElementById('myGamesView').classList.remove('hidden');
    loadMyGames();
}

function showCreateGame() {
    hideAll();
    document.getElementById('createGameView').classList.remove('hidden');
}

function hideAll() {
    document.querySelectorAll('.container').forEach(el => el.classList.add('hidden'));
}

function hideLoading() {
    document.getElementById('loading').classList.add('hidden');
}

function showError(message) {
    tg.showAlert(message);
}

// Check PRO access
function checkProAccess(gameType) {
    const proWarning = document.getElementById('proWarning');
    const gameForm = document.getElementById('gameForm');
    
    if (PRO_GAMES.includes(gameType) && !currentUser.is_pro) {
        proWarning.classList.remove('hidden');
        gameForm.classList.add('hidden');
    } else {
        proWarning.classList.add('hidden');
        gameForm.classList.remove('hidden');
    }
}

// Request PRO access
async function requestProAccess() {
    if (currentUser.pro_requested) {
        tg.showAlert('You have already requested PRO access. Please wait for admin approval.');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/request-pro`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: currentUser.user_id })
        });
        
        if (response.ok) {
            currentUser.pro_requested = 1;
            tg.showAlert('✅ PRO access request sent! Admin will review it soon.');
        }
    } catch (error) {
        console.error('Request PRO error:', error);
        showError('Failed to send request');
    }
}

// Load user's games
async function loadMyGames() {
    try {
        const response = await fetch(`${API_BASE_URL}/games/${currentUser.user_id}`);
        const games = await response.json();
        
        const gamesList = document.getElementById('gamesList');
        
        if (games.length === 0) {
            gamesList.innerHTML = '<p style="text-align: center; color: #666;">No games created yet</p>';
            return;
        }
        
        gamesList.innerHTML = games.map(game => `
            <div class="game-card">
                <div class="game-info">
                    <h3>${game.title}</h3>
                    <p>${game.game_type.replace('_', ' ')}</p>
                    <p style="font-size: 12px; color: #999;">${new Date(game.created_at).toLocaleDateString()}</p>
                </div>
                <div class="game-actions">
                    <button class="btn-small btn-play" onclick="playGame(${game.id})">▶ Play</button>
                    <button class="btn-small btn-share" onclick="shareGame('${game.share_link}')">📤 Share</button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Load games error:', error);
        showError('Failed to load games');
    }
}

// Create new game
async function createGame() {
    const gameType = document.getElementById('gameType').value;
    const title = document.getElementById('gameTitle').value.trim();
    const questionsText = document.getElementById('questions').value.trim();
    
    if (!title || !questionsText) {
        tg.showAlert('Please fill in all fields');
        return;
    }
    
    // Check PRO access
    if (PRO_GAMES.includes(gameType) && !currentUser.is_pro) {
        tg.showAlert('This is a PRO feature. Please request access first.');
        return;
    }
    
    // Parse questions
    const questions = questionsText.split('\n').map(line => {
        const parts = line.split('|').map(p => p.trim());
        return {
            question: parts[0],
            answers: [parts[1], parts[2], parts[3], parts[4]],
            correct: parseInt(parts[5]) - 1
        };
    });
    
    if (questions.length === 0) {
        tg.showAlert('Please add at least one question');
        return;
    }
    
    // Generate share link
    const shareLink = `https://t.me/MyEduGames_bot?start=game_${Date.now()}`;
    
    try {
        const response = await fetch(`${API_BASE_URL}/games`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                creator_id: currentUser.user_id,
                game_type: gameType,
                title: title,
                questions: questions,
                share_link: shareLink
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            tg.showAlert('✅ Game created successfully!');
            document.getElementById('gameTitle').value = '';
            document.getElementById('questions').value = '';
            showMyGames();
        }
    } catch (error) {
        console.error('Create game error:', error);
        showError('Failed to create game');
    }
}

// Share game
function shareGame(link) {
    tg.openTelegramLink(link);
}

// Play game
async function playGame(gameId) {
    // This would load the game and start playing
    // Implement game logic based on game type
    tg.showAlert('Game play feature coming soon!');
}

// Admin functions
async function loadAdminStats() {
    // Load admin statistics from API
    // This is a placeholder - implement based on your needs
    document.getElementById('totalUsers').textContent = '0';
    document.getElementById('totalGames').textContent = '0';
}

// Telegram WebApp theme
tg.setHeaderColor('secondary_bg_color');
tg.setBackgroundColor('#667eea');