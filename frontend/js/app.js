/**
 * Cinema — Intelligent Recommendation Studio
 * Apple-Inspired Frontend Controller & Session Manager
 */

document.addEventListener('DOMContentLoaded', () => {
  // ==========================================
  // Default Profiles (Real MovieLens Archetypes)
  // ==========================================
  const DEFAULT_PROFILES = [
    {
      userId: 1,
      name: 'Alex Vance',
      avatar: 'A',
      color: '#0071e3',
      role: 'Sci-Fi & Action Aficionado',
      ratingsCount: 232,
      primaryGenre: 'Sci-Fi',
    },
    {
      userId: 2,
      name: 'Sarah Connor',
      avatar: 'S',
      color: '#34c759',
      role: 'Action & Crime Enthusiast',
      ratingsCount: 29,
      primaryGenre: 'Action',
    },
    {
      userId: 3,
      name: 'Marcus Cole',
      avatar: 'M',
      color: '#ff9500',
      role: 'Classic Cinema & Drama',
      ratingsCount: 39,
      primaryGenre: 'Drama',
    },
    {
      userId: 4,
      name: 'Elena Rostova',
      avatar: 'E',
      color: '#af52de',
      role: 'Comedy & Classics Aficionado',
      ratingsCount: 216,
      primaryGenre: 'Comedy',
    },
    {
      userId: 9999,
      name: 'Guest Explorer',
      avatar: '★',
      color: '#ff2d55',
      role: 'Cold-Start Discovery Profile',
      ratingsCount: 0,
      primaryGenre: 'Uncalibrated',
    },
  ];

  // ==========================================
  // Application State
  // ==========================================
  const state = {
    userId: parseInt(localStorage.getItem('cinema_active_user_id'), 10) || 1,
    currentUser: null,
    savedProfiles: [],
    modelType: 'hybrid',
    k: 10,
    genreFilter: '',
    catalogQuery: '',
    catalogGenre: '',
    catalogSort: 'bayesian_score',
    catalogPage: 1,
    catalogTotalPages: 1,
    genres: [],
    liveFeedback: [],
    evaluationMetrics: null,
    theme: localStorage.getItem('cinema_theme') || 'dark',
    selectedStarterGenre: 'Sci-Fi',
  };

  const modelInfo = {
    hybrid: {
      badge: 'Two-Stage Hybrid Engine (Production)',
      desc: 'Retrieves candidate pools across Collaborative Networks, SVD Latent Projections, and Genre Seeds, then applies feature-weighted composite ranking with MMR diversity control.',
    },
    item_collaborative: {
      badge: 'Item-Item Collaborative Filtering',
      desc: 'Computes item-item cosine similarities with shrinkage penalty. Surfaces items directly co-rated by viewers who loved the same seed titles.',
    },
    matrix_factorization_svd: {
      badge: 'Latent Factor Matrix Factorization',
      desc: 'Projects viewer preferences and item characteristics into a dense 35-dimensional latent embedding space using regularized Singular Value Decomposition.',
    },
    popularity: {
      badge: 'Bayesian Popularity Prior',
      desc: 'Ranks the catalog via Bayesian dampening weighted ratings (m=10 prior). Guarantees reliable, high-confidence cold-start fallback recommendations.',
    },
  };

  // ==========================================
  // DOM Elements
  // ==========================================
  const navTabs = document.querySelectorAll('.nav-tab');
  const viewPanels = document.querySelectorAll('.view-panel');
  const brandLogo = document.getElementById('brandLogo');
  const themeToggleBtn = document.getElementById('themeToggleBtn');
  const themeIcon = document.getElementById('themeIcon');
  const userSelect = document.getElementById('userSelect');

  // Account Popover Elements
  const userAccountWrapper = document.getElementById('userAccountWrapper');
  const userChipBtn = document.getElementById('userChipBtn');
  const navUserAvatar = document.getElementById('navUserAvatar');
  const navUserName = document.getElementById('navUserName');
  const accountDropdownMenu = document.getElementById('accountDropdownMenu');
  const menuUserAvatar = document.getElementById('menuUserAvatar');
  const menuUserName = document.getElementById('menuUserName');
  const menuUserTaste = document.getElementById('menuUserTaste');
  const btnMenuProfile = document.getElementById('btnMenuProfile');
  const btnMenuSwitchAccount = document.getElementById('btnMenuSwitchAccount');
  const btnMenuSignOut = document.getElementById('btnMenuSignOut');

  // Login Modal Elements
  const loginModal = document.getElementById('loginModal');
  const btnLoginClose = document.getElementById('btnLoginClose');
  const tabSelectProfile = document.getElementById('tabSelectProfile');
  const tabNewProfile = document.getElementById('tabNewProfile');
  const panelSelectProfile = document.getElementById('panelSelectProfile');
  const panelNewProfile = document.getElementById('panelNewProfile');
  const loginProfilesGrid = document.getElementById('loginProfilesGrid');
  const newProfileForm = document.getElementById('newProfileForm');
  const inputUserName = document.getElementById('inputUserName');
  const inputUserId = document.getElementById('inputUserId');
  const genreChipsSelector = document.getElementById('genreChipsSelector');
  const btnProfileSwitchUser = document.getElementById('btnProfileSwitchUser');

  // Hero Controls
  const btnHeroGoRecs = document.getElementById('btnHeroGoRecs');
  const btnHeroGoEvaluation = document.getElementById('btnHeroGoEvaluation');
  const btnHeroGoArchitecture = document.getElementById('btnHeroGoArchitecture');

  // Recommendations Controls
  const modelPillGroup = document.getElementById('modelPillGroup');
  const topKSlider = document.getElementById('topKSlider');
  const topKValue = document.getElementById('topKValue');
  const genreFilter = document.getElementById('genreFilter');
  const btnRefreshRecs = document.getElementById('btnRefreshRecs');
  const recommendationsGrid = document.getElementById('recommendationsGrid');
  const strategyBadge = document.getElementById('strategyBadge');
  const strategyDesc = document.getElementById('strategyDesc');
  const coldStartBanner = document.getElementById('coldStartBanner');
  const statLatency = document.getElementById('statLatency');
  const recUserAvatar = document.getElementById('recUserAvatar');
  const recUserTitle = document.getElementById('recUserTitle');
  const recUserTasteSummary = document.getElementById('recUserTasteSummary');

  // Catalog Controls
  const catalogSearchInput = document.getElementById('catalogSearchInput');
  const catalogGenreFilter = document.getElementById('catalogGenreFilter');
  const catalogSortBy = document.getElementById('catalogSortBy');
  const catalogGrid = document.getElementById('catalogGrid');
  const catalogCountInfo = document.getElementById('catalogCountInfo');
  const catalogPageInfo = document.getElementById('catalogPageInfo');
  const btnPrevPage = document.getElementById('btnPrevPage');
  const btnNextPage = document.getElementById('btnNextPage');

  // Profile DOM
  const profileLargeAvatar = document.getElementById('profileLargeAvatar');
  const profileName = document.getElementById('profileName');
  const profileTagline = document.getElementById('profileTagline');
  const profileRatedCount = document.getElementById('profileRatedCount');
  const profileMeanRating = document.getElementById('profileMeanRating');
  const profilePrimaryTaste = document.getElementById('profilePrimaryTaste');
  const profileGenreBars = document.getElementById('profileGenreBars');
  const tabHistoricalRatings = document.getElementById('tabHistoricalRatings');
  const tabLiveFeedback = document.getElementById('tabLiveFeedback');
  const historyContent = document.getElementById('historyContent');
  const feedbackCountBadge = document.getElementById('feedbackCountBadge');

  // Modal DOM
  const movieDetailModal = document.getElementById('movieDetailModal');
  const btnModalClose = document.getElementById('btnModalClose');
  const modalBody = document.getElementById('modalBody');
  const toastContainer = document.getElementById('toastContainer');

  // ==========================================
  // Initialization
  // ==========================================
  async function init() {
    initTheme();
    initUserProfiles();
    setupTabNavigation();
    setupEventListeners();
    await fetchGenres();
    await fetchMetrics();
    loadRecommendations();
    loadCatalog();
  }

  // ==========================================
  // Theme Management (Bright vs Dark Eye Comfort)
  // ==========================================
  function initTheme() {
    document.documentElement.setAttribute('data-theme', state.theme);
    updateThemeIcon();
  }

  function toggleTheme() {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', state.theme);
    localStorage.setItem('cinema_theme', state.theme);
    updateThemeIcon();
    showToast(`Switched to ${state.theme === 'dark' ? 'Dark Theme' : 'Bright Theme (Eye Comfort)'}`);
  }

  function updateThemeIcon() {
    if (themeIcon) {
      themeIcon.textContent = state.theme === 'dark' ? '☀️' : '🌙';
    }
    if (themeToggleBtn) {
      themeToggleBtn.setAttribute(
        'title',
        state.theme === 'dark' ? 'Switch to Bright Theme' : 'Switch to Dark Theme'
      );
    }
  }

  // ==========================================
  // Multi-User Profile Management & Storage
  // ==========================================
  function initUserProfiles() {
    const rawSaved = localStorage.getItem('cinema_user_profiles');
    if (rawSaved) {
      try {
        state.savedProfiles = JSON.parse(rawSaved);
      } catch (e) {
        state.savedProfiles = [...DEFAULT_PROFILES];
      }
    } else {
      state.savedProfiles = [...DEFAULT_PROFILES];
      saveProfilesToStorage();
    }

    // Ensure active user exists
    let active = state.savedProfiles.find((p) => p.userId === state.userId);
    if (!active) {
      active = state.savedProfiles[0];
      state.userId = active.userId;
      localStorage.setItem('cinema_active_user_id', state.userId);
    }
    state.currentUser = active;
    syncUserUI();
    renderLoginProfilesList();
  }

  function saveProfilesToStorage() {
    localStorage.setItem('cinema_user_profiles', JSON.stringify(state.savedProfiles));
  }

  function setActiveUser(profile) {
    state.currentUser = profile;
    state.userId = profile.userId;
    localStorage.setItem('cinema_active_user_id', profile.userId);

    // Sync compatibility select if present
    if (userSelect) {
      userSelect.value = profile.userId;
    }

    syncUserUI();
    renderLoginProfilesList();
    loadRecommendations();
    if (document.getElementById('viewProfile').classList.contains('active')) {
      loadUserProfile();
    }
    showToast(`Signed in as ${profile.name}`);
  }

  function syncUserUI() {
    const u = state.currentUser;
    if (!u) return;

    if (navUserAvatar) {
      navUserAvatar.textContent = u.avatar;
      navUserAvatar.style.background = u.color || 'var(--accent-gradient)';
    }
    if (navUserName) navUserName.textContent = u.name;

    if (menuUserAvatar) {
      menuUserAvatar.textContent = u.avatar;
      menuUserAvatar.style.background = u.color || 'var(--accent-gradient)';
    }
    if (menuUserName) menuUserName.textContent = u.name;
    if (menuUserTaste) menuUserTaste.textContent = u.role;

    if (recUserAvatar) {
      recUserAvatar.textContent = u.avatar;
      recUserAvatar.style.background = u.color || 'var(--accent-gradient)';
    }
    if (recUserTitle) recUserTitle.textContent = `Curated for ${u.name}`;
    if (recUserTasteSummary) {
      if (u.userId === 9999) {
        recUserTasteSummary.textContent = 'Taste Signature: Uncalibrated Cold-Start Profile (Zero prior history)';
      } else {
        recUserTasteSummary.textContent = `Taste Signature: ${u.role} (${u.ratingsCount} verified ratings)`;
      }
    }
  }

  function renderLoginProfilesList() {
    if (!loginProfilesGrid) return;
    loginProfilesGrid.innerHTML = '';

    state.savedProfiles.forEach((profile) => {
      const card = document.createElement('div');
      const isActive = profile.userId === state.userId;
      card.className = `profile-select-card ${isActive ? 'active-profile' : ''}`;

      card.innerHTML = `
        <div class="select-avatar" style="background: ${profile.color || 'var(--accent-gradient)'}">${profile.avatar}</div>
        <div class="select-info">
          <span class="select-name">${escapeHtml(profile.name)}</span>
          <span class="select-desc">${escapeHtml(profile.role)} &bull; ${profile.ratingsCount} ratings</span>
        </div>
        ${isActive ? '<span class="select-indicator">Active</span>' : ''}
      `;

      card.addEventListener('click', () => {
        setActiveUser(profile);
        closeLoginModal();
      });

      loginProfilesGrid.appendChild(card);
    });
  }

  function openLoginModal() {
    if (loginModal) loginModal.classList.remove('hidden');
    renderLoginProfilesList();
  }

  function closeLoginModal() {
    if (loginModal) loginModal.classList.add('hidden');
  }

  // ==========================================
  // Tab Navigation Controller
  // ==========================================
  function switchTab(targetTabId) {
    const cleanId = targetTabId.toLowerCase().trim();

    navTabs.forEach((tab) => {
      const tabData = tab.getAttribute('data-tab');
      if (tabData === cleanId) {
        tab.classList.add('active');
      } else {
        tab.classList.remove('active');
      }
    });

    viewPanels.forEach((panel) => {
      panel.classList.remove('active');
      const expectedId = `view${capitalize(cleanId)}`;
      if (panel.id === expectedId) {
        panel.classList.add('active');
      }
    });

    if (cleanId === 'profile') {
      loadUserProfile();
    } else if (cleanId === 'evaluation') {
      renderEvaluationTable();
    } else if (cleanId === 'recommendations') {
      if (recommendationsGrid.children.length === 0 || recommendationsGrid.querySelector('.loading-state')) {
        loadRecommendations();
      }
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function setupTabNavigation() {
    navTabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        const targetTab = tab.getAttribute('data-tab');
        switchTab(targetTab);
      });
    });

    if (brandLogo) {
      brandLogo.addEventListener('click', () => switchTab('home'));
    }

    if (btnHeroGoRecs) {
      btnHeroGoRecs.addEventListener('click', () => switchTab('recommendations'));
    }
    if (btnHeroGoEvaluation) {
      btnHeroGoEvaluation.addEventListener('click', () => switchTab('evaluation'));
    }
    if (btnHeroGoArchitecture) {
      btnHeroGoArchitecture.addEventListener('click', () => switchTab('architecture'));
    }

    document.querySelectorAll('.strat-jump-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const model = btn.getAttribute('data-model');
        activateModel(model);
        switchTab('recommendations');
      });
    });

    document.querySelectorAll('.strategy-card').forEach((card) => {
      card.addEventListener('click', () => {
        const model = card.getAttribute('data-model-jump');
        if (model) {
          activateModel(model);
          switchTab('recommendations');
        }
      });
    });

    document.querySelectorAll('.stage-card').forEach((stage) => {
      stage.addEventListener('click', () => {
        document.querySelectorAll('.stage-card').forEach((s) => s.classList.remove('active'));
        stage.classList.add('active');
        const stageNum = stage.getAttribute('data-stage');
        showToast(`Inspecting Stage 0${stageNum}: ${stage.querySelector('h4').textContent}`);
      });
    });
  }

  function activateModel(modelName) {
    if (!modelInfo[modelName]) return;
    state.modelType = modelName;

    if (modelPillGroup) {
      modelPillGroup.querySelectorAll('.pill-btn').forEach((btn) => {
        if (btn.getAttribute('data-model') === modelName) {
          btn.classList.add('active');
        } else {
          btn.classList.remove('active');
        }
      });
    }

    updateStrategyBanner();
    loadRecommendations();
  }

  function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  // ==========================================
  // Event Listeners Setup
  // ==========================================
  function setupEventListeners() {
    // Theme Switcher Button
    if (themeToggleBtn) {
      themeToggleBtn.addEventListener('click', toggleTheme);
    }

    // Account Chip Click -> Toggle Dropdown
    if (userChipBtn && userAccountWrapper) {
      userChipBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        userAccountWrapper.classList.toggle('open');
        accountDropdownMenu.classList.toggle('hidden');
      });

      // Close popover when clicking anywhere outside
      document.addEventListener('click', (e) => {
        if (!userAccountWrapper.contains(e.target)) {
          userAccountWrapper.classList.remove('open');
          accountDropdownMenu.classList.add('hidden');
        }
      });
    }

    // Dropdown Actions
    if (btnMenuProfile) {
      btnMenuProfile.addEventListener('click', () => {
        userAccountWrapper.classList.remove('open');
        accountDropdownMenu.classList.add('hidden');
        switchTab('profile');
      });
    }

    if (btnMenuSwitchAccount) {
      btnMenuSwitchAccount.addEventListener('click', () => {
        userAccountWrapper.classList.remove('open');
        accountDropdownMenu.classList.add('hidden');
        openLoginModal();
      });
    }

    if (btnProfileSwitchUser) {
      btnProfileSwitchUser.addEventListener('click', openLoginModal);
    }

    if (btnMenuSignOut) {
      btnMenuSignOut.addEventListener('click', () => {
        userAccountWrapper.classList.remove('open');
        accountDropdownMenu.classList.add('hidden');
        // Set to Guest profile
        const guest = state.savedProfiles.find((p) => p.userId === 9999) || state.savedProfiles[0];
        setActiveUser(guest);
        showToast('Signed out of personalized profile. Guest mode active.');
      });
    }

    // Login Modal Triggers
    if (btnLoginClose) btnLoginClose.addEventListener('click', closeLoginModal);
    if (loginModal) {
      loginModal.addEventListener('click', (e) => {
        if (e.target === loginModal) closeLoginModal();
      });
    }

    if (tabSelectProfile && tabNewProfile) {
      tabSelectProfile.addEventListener('click', () => {
        tabSelectProfile.classList.add('active');
        tabNewProfile.classList.remove('active');
        panelSelectProfile.classList.add('active');
        panelNewProfile.classList.remove('active');
      });

      tabNewProfile.addEventListener('click', () => {
        tabNewProfile.classList.add('active');
        tabSelectProfile.classList.remove('active');
        panelNewProfile.classList.add('active');
        panelSelectProfile.classList.remove('active');
      });
    }

    // New Profile Submission Form
    if (newProfileForm) {
      newProfileForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const name = inputUserName.value.trim();
        const id = parseInt(inputUserId.value, 10) || 1;
        if (!name) return;

        const colors = ['#0071e3', '#af52de', '#34c759', '#ff9500', '#ff2d55', '#5856d6'];
        const randomColor = colors[Math.floor(Math.random() * colors.length)];

        const newProfile = {
          userId: id,
          name: name,
          avatar: name.charAt(0).toUpperCase(),
          color: randomColor,
          role: `${state.selectedStarterGenre} Enthusiast`,
          ratingsCount: id === 9999 ? 0 : 50,
          primaryGenre: state.selectedStarterGenre,
        };

        // Add to saved profiles or update existing
        const idx = state.savedProfiles.findIndex((p) => p.userId === id);
        if (idx >= 0) {
          state.savedProfiles[idx] = newProfile;
        } else {
          state.savedProfiles.push(newProfile);
        }

        saveProfilesToStorage();
        setActiveUser(newProfile);
        closeLoginModal();
        newProfileForm.reset();
      });
    }

    // Model Selector Pills
    if (modelPillGroup) {
      modelPillGroup.querySelectorAll('.pill-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
          modelPillGroup.querySelectorAll('.pill-btn').forEach((b) => b.classList.remove('active'));
          btn.classList.add('active');
          state.modelType = btn.getAttribute('data-model');
          updateStrategyBanner();
          loadRecommendations();
        });
      });
    }

    // Top K Slider
    if (topKSlider) {
      topKSlider.addEventListener('input', (e) => {
        state.k = parseInt(e.target.value, 10);
        if (topKValue) topKValue.textContent = state.k;
      });

      topKSlider.addEventListener('change', () => {
        loadRecommendations();
      });
    }

    // Genre Filter in Recommendations
    if (genreFilter) {
      genreFilter.addEventListener('change', (e) => {
        state.genreFilter = e.target.value;
        loadRecommendations();
      });
    }

    // Refresh Recommendations Button
    if (btnRefreshRecs) {
      btnRefreshRecs.addEventListener('click', () => {
        loadRecommendations();
      });
    }

    // Catalog Controls
    let searchDebounceTimer = null;
    if (catalogSearchInput) {
      catalogSearchInput.addEventListener('input', (e) => {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
          state.catalogQuery = e.target.value;
          state.catalogPage = 1;
          loadCatalog();
        }, 300);
      });
    }

    if (catalogGenreFilter) {
      catalogGenreFilter.addEventListener('change', (e) => {
        state.catalogGenre = e.target.value;
        state.catalogPage = 1;
        loadCatalog();
      });
    }

    if (catalogSortBy) {
      catalogSortBy.addEventListener('change', (e) => {
        state.catalogSort = e.target.value;
        state.catalogPage = 1;
        loadCatalog();
      });
    }

    if (btnPrevPage) {
      btnPrevPage.addEventListener('click', () => {
        if (state.catalogPage > 1) {
          state.catalogPage--;
          loadCatalog();
        }
      });
    }

    if (btnNextPage) {
      btnNextPage.addEventListener('click', () => {
        if (state.catalogPage < state.catalogTotalPages) {
          state.catalogPage++;
          loadCatalog();
        }
      });
    }

    // Profile History Sub-tabs
    if (tabHistoricalRatings) {
      tabHistoricalRatings.addEventListener('click', () => {
        tabHistoricalRatings.classList.add('active');
        tabLiveFeedback.classList.remove('active');
        renderHistoricalRatings();
      });
    }

    if (tabLiveFeedback) {
      tabLiveFeedback.addEventListener('click', () => {
        tabLiveFeedback.classList.add('active');
        tabHistoricalRatings.classList.remove('active');
        renderLiveFeedback();
      });
    }

    // Modal Close Triggers
    if (btnModalClose) {
      btnModalClose.addEventListener('click', closeModal);
    }
    if (movieDetailModal) {
      movieDetailModal.addEventListener('click', (e) => {
        if (e.target === movieDetailModal) closeModal();
      });
    }

    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeModal();
        closeLoginModal();
        if (userAccountWrapper) {
          userAccountWrapper.classList.remove('open');
          accountDropdownMenu.classList.add('hidden');
        }
      }
    });
  }

  // ==========================================
  // Fetch Genres & Render Starter Chips
  // ==========================================
  async function fetchGenres() {
    try {
      const res = await fetch('/api/genres');
      if (!res.ok) return;
      const data = await res.json();
      state.genres = data.genres || [];

      // Populate dropdowns
      [genreFilter, catalogGenreFilter].forEach((select) => {
        if (!select) return;
        select.innerHTML = '<option value="">All Genres</option>';
        state.genres.forEach((g) => {
          const opt = document.createElement('option');
          opt.value = g;
          opt.textContent = g;
          select.appendChild(opt);
        });
      });

      // Populate Starter Genre Chips in New User Form
      if (genreChipsSelector) {
        genreChipsSelector.innerHTML = '';
        const topStarterGenres = ['Sci-Fi', 'Action', 'Drama', 'Comedy', 'Thriller', 'Animation', 'Crime', 'Romance'];
        topStarterGenres.forEach((g, idx) => {
          const chip = document.createElement('button');
          chip.type = 'button';
          chip.className = `genre-chip ${idx === 0 ? 'active' : ''}`;
          chip.textContent = g;
          chip.addEventListener('click', () => {
            genreChipsSelector.querySelectorAll('.genre-chip').forEach((c) => c.classList.remove('active'));
            chip.classList.add('active');
            state.selectedStarterGenre = g;
          });
          genreChipsSelector.appendChild(chip);
        });
      }
    } catch (err) {
      console.error('Failed to load genres:', err);
    }
  }

  // ==========================================
  // Fetch Evaluation Metrics
  // ==========================================
  async function fetchMetrics() {
    try {
      const res = await fetch('/api/metrics');
      if (!res.ok) return;
      state.evaluationMetrics = await res.json();
      renderEvaluationTable();
    } catch (err) {
      console.warn('Evaluation metrics not ready yet:', err);
    }
  }

  function updateStrategyBanner() {
    const info = modelInfo[state.modelType] || modelInfo.hybrid;
    if (strategyBadge) strategyBadge.textContent = info.badge;
    if (strategyDesc) strategyDesc.textContent = info.desc;
  }

  // ==========================================
  // Load Personalized Recommendations
  // ==========================================
  async function loadRecommendations() {
    if (!recommendationsGrid) return;

    recommendationsGrid.innerHTML = `
      <div class="loading-state">
        <div class="spinner"></div>
        <p>Curating personalized recommendations for ${escapeHtml(state.currentUser ? state.currentUser.name : `User ${state.userId}`)}...</p>
      </div>
    `;

    try {
      let url = `/api/recommend/${state.userId}?k=${state.k}&model_type=${state.modelType}`;
      if (state.genreFilter) {
        url += `&genre=${encodeURIComponent(state.genreFilter)}`;
      }

      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`Server returned HTTP ${res.status}`);
      }

      const data = await res.json();
      if (statLatency) {
        statLatency.textContent = `${data.latency_ms} ms`;
      }

      if (coldStartBanner) {
        if (data.is_cold_start) {
          coldStartBanner.classList.remove('hidden');
        } else {
          coldStartBanner.classList.add('hidden');
        }
      }

      renderRecommendations(data.recommendations || []);
    } catch (err) {
      console.error('Error fetching recommendations:', err);
      recommendationsGrid.innerHTML = `
        <div class="loading-state" style="color: var(--accent-rose)">
          <p>⚠️ Unable to load recommendations: ${err.message}</p>
          <button class="action-btn btn-primary btn-apple" id="btnRetryRecs" style="margin-top: 12px">Retry</button>
        </div>
      `;
      const retryBtn = document.getElementById('btnRetryRecs');
      if (retryBtn) retryBtn.addEventListener('click', loadRecommendations);
    }
  }

  function renderRecommendations(items) {
    if (!recommendationsGrid) return;

    if (!items || items.length === 0) {
      recommendationsGrid.innerHTML = `
        <div class="loading-state">
          <p>No titles match the selected genre filters. Try choosing "All Genres" or switching the recommendation engine.</p>
        </div>
      `;
      return;
    }

    recommendationsGrid.innerHTML = '';
    items.forEach((item, idx) => {
      const card = createMovieCard(item, idx + 1, true);
      recommendationsGrid.appendChild(card);
    });
  }

  // ==========================================
  // Movie Card Component Creation
  // ==========================================
  function createMovieCard(movie, rank, showExplainability = false) {
    const card = document.createElement('div');
    card.className = 'movie-card';

    const genreBadges = (movie.genres || [])
      .slice(0, 3)
      .map((g) => `<span class="genre-tag">${g}</span>`)
      .join('');

    const visualIcon = getGenreEmoji(movie.genres);
    const scoreVal = movie.predicted_score
      ? movie.predicted_score.toFixed(1)
      : movie.bayesian_score
      ? movie.bayesian_score.toFixed(1)
      : '4.0';

    card.innerHTML = `
      <div class="card-visual">
        <span class="visual-pattern">${visualIcon}</span>
        ${rank ? `<div class="rank-index">#${rank}</div>` : ''}
        <div class="score-badge">${scoreVal}★</div>
      </div>
      <div class="card-body">
        <h3 class="movie-title" title="${escapeHtml(movie.title)}">
          ${escapeHtml(movie.title)}
        </h3>
        <div class="genre-tags">${genreBadges}</div>
        
        ${
          showExplainability && movie.recommendation_signal
            ? `<div class="explainability-box"><span class="signal-icon">💡</span>${escapeHtml(movie.recommendation_signal)}</div>`
            : ''
        }

        <div class="card-actions">
          <div class="star-rating-widget" data-movie-id="${movie.movie_id}">
            <button class="star-btn" data-star="1" title="Rate 1 Star">★</button>
            <button class="star-btn" data-star="2" title="Rate 2 Stars">★</button>
            <button class="star-btn" data-star="3" title="Rate 3 Stars">★</button>
            <button class="star-btn" data-star="4" title="Rate 4 Stars">★</button>
            <button class="star-btn" data-star="5" title="Rate 5 Stars">★</button>
          </div>
          <div class="quick-actions">
            <button class="icon-btn btn-like" data-movie-id="${movie.movie_id}" title="Like Title">👍</button>
            <button class="icon-btn btn-bookmark" data-movie-id="${movie.movie_id}" title="Save to Watchlist">🔖</button>
            <button class="icon-btn btn-details" data-movie-id="${movie.movie_id}" title="View Details">ℹ️</button>
          </div>
        </div>
      </div>
    `;

    const starBtns = card.querySelectorAll('.star-btn');
    starBtns.forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const rating = parseFloat(btn.getAttribute('data-star'));
        submitFeedback(movie.movie_id, movie.title, 'rating', rating);
        highlightStars(starBtns, rating);
      });
    });

    const likeBtn = card.querySelector('.btn-like');
    if (likeBtn) {
      likeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        likeBtn.classList.toggle('active');
        submitFeedback(movie.movie_id, movie.title, 'like', 5.0);
      });
    }

    const bmBtn = card.querySelector('.btn-bookmark');
    if (bmBtn) {
      bmBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        bmBtn.classList.toggle('active');
        submitFeedback(movie.movie_id, movie.title, 'bookmark', 4.5);
      });
    }

    const detailsBtn = card.querySelector('.btn-details');
    if (detailsBtn) {
      detailsBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        openMovieDetails(movie);
      });
    }

    return card;
  }

  function highlightStars(starBtns, rating) {
    starBtns.forEach((b) => {
      const starVal = parseFloat(b.getAttribute('data-star'));
      if (starVal <= rating) {
        b.classList.add('rated');
      } else {
        b.classList.remove('rated');
      }
    });
  }

  function getGenreEmoji(genres = []) {
    const gStr = genres.join(' ').toLowerCase();
    if (gStr.includes('sci-fi')) return '🚀';
    if (gStr.includes('action')) return '💥';
    if (gStr.includes('animation')) return '🎨';
    if (gStr.includes('comedy')) return '🍿';
    if (gStr.includes('drama')) return '🎭';
    if (gStr.includes('horror')) return '👁️';
    if (gStr.includes('thriller')) return '⚡';
    if (gStr.includes('romance')) return '❤️';
    if (gStr.includes('fantasy')) return '🔮';
    if (gStr.includes('crime')) return '🕵️';
    if (gStr.includes('documentary')) return '📜';
    if (gStr.includes('mystery')) return '🔍';
    if (gStr.includes('adventure')) return '🧭';
    return '🎬';
  }

  // ==========================================
  // Feedback Closed-Loop Submission
  // ==========================================
  async function submitFeedback(movieId, movieTitle, interactionType, rating = null) {
    try {
      const payload = {
        user_id: state.userId,
        movie_id: movieId,
        interaction_type: interactionType,
        rating: rating,
      };

      const res = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error('Feedback request failed');
      await res.json();

      const actionText =
        interactionType === 'rating'
          ? `rated ${rating}★`
          : interactionType === 'like'
          ? 'liked'
          : 'bookmarked';
      showToast(`${state.currentUser ? state.currentUser.name : 'You'} ${actionText} "${movieTitle}"`);

      state.liveFeedback.unshift({
        movie_id: movieId,
        title: movieTitle,
        type: interactionType,
        rating: rating,
        time: new Date().toLocaleTimeString(),
      });

      if (feedbackCountBadge) {
        feedbackCountBadge.textContent = state.liveFeedback.length;
      }

      if (state.userId === 9999) {
        if (coldStartBanner) coldStartBanner.classList.add('hidden');
        if (recUserTasteSummary) {
          recUserTasteSummary.textContent = 'Taste Signature: Calibrating live from new feedback events!';
        }
      }

      if (
        document.getElementById('viewProfile').classList.contains('active') &&
        tabLiveFeedback &&
        tabLiveFeedback.classList.contains('active')
      ) {
        renderLiveFeedback();
      }
    } catch (err) {
      console.error('Feedback failed:', err);
      showToast('Could not record feedback interaction', true);
    }
  }

  // ==========================================
  // Floating Apple Toasts
  // ==========================================
  function showToast(message, isError = false) {
    if (!toastContainer) return;

    const toast = document.createElement('div');
    toast.className = 'toast';
    if (isError) toast.style.borderColor = 'var(--accent-rose)';

    toast.innerHTML = `
      <span>${isError ? '⚠️' : '✓'}</span>
      <span>${escapeHtml(message)}</span>
    `;

    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(12px) scale(0.96)';
      toast.style.transition = 'all 0.3s ease-out';
      setTimeout(() => toast.remove(), 300);
    }, 3200);
  }

  // ==========================================
  // Catalog Explorer
  // ==========================================
  async function loadCatalog() {
    if (!catalogGrid) return;

    catalogGrid.innerHTML = `
      <div class="loading-state">
        <div class="spinner"></div>
        <p>Loading Cinema catalog...</p>
      </div>
    `;

    try {
      let url = `/api/movies?page=${state.catalogPage}&page_size=18&sort_by=${state.catalogSort}`;
      if (state.catalogQuery) {
        url += `&query=${encodeURIComponent(state.catalogQuery)}`;
      }
      if (state.catalogGenre) {
        url += `&genre=${encodeURIComponent(state.catalogGenre)}`;
      }

      const res = await fetch(url);
      if (!res.ok) throw new Error('Catalog fetch failed');
      const data = await res.json();

      state.catalogTotalPages = data.total_pages;
      if (catalogPageInfo) {
        catalogPageInfo.textContent = `Page ${data.page} of ${data.total_pages}`;
      }
      if (catalogCountInfo) {
        const startIdx = Math.min(data.total_count, (data.page - 1) * 18 + 1);
        const endIdx = Math.min(data.total_count, data.page * 18);
        catalogCountInfo.textContent = `Showing ${startIdx}-${endIdx} of ${data.total_count.toLocaleString()} titles`;
      }

      if (btnPrevPage) btnPrevPage.disabled = data.page <= 1;
      if (btnNextPage) btnNextPage.disabled = data.page >= data.total_pages;

      renderCatalog(data.movies || []);
    } catch (err) {
      console.error('Catalog load error:', err);
      catalogGrid.innerHTML = `<div class="loading-state" style="color:var(--accent-rose)">Failed to load catalog titles.</div>`;
    }
  }

  function renderCatalog(movies) {
    if (!catalogGrid) return;

    if (!movies || movies.length === 0) {
      catalogGrid.innerHTML = `<div class="loading-state"><p>No titles found matching your search.</p></div>`;
      return;
    }

    catalogGrid.innerHTML = '';
    movies.forEach((m) => {
      const card = createMovieCard(m, null, false);
      catalogGrid.appendChild(card);
    });
  }

  // ==========================================
  // User Profile Loader & Views
  // ==========================================
  let cachedUserProfile = null;
  async function loadUserProfile() {
    try {
      const res = await fetch(`/api/users/${state.userId}/profile`);
      if (!res.ok) return;
      cachedUserProfile = await res.json();

      const u = state.currentUser;
      if (profileLargeAvatar) {
        profileLargeAvatar.textContent = u ? u.avatar : 'U';
        profileLargeAvatar.style.background = u ? u.color : 'var(--accent-gradient)';
      }
      if (profileName) {
        profileName.textContent = u ? u.name : `User ${state.userId}`;
      }
      if (profileTagline) {
        profileTagline.textContent = u ? u.role : 'Taste Signature';
      }
      if (profileRatedCount) {
        profileRatedCount.textContent = cachedUserProfile.ratings_count.toLocaleString();
      }
      if (profileMeanRating) {
        profileMeanRating.textContent = `${cachedUserProfile.average_rating} ★`;
      }

      if (profilePrimaryTaste) {
        if (cachedUserProfile.top_genres && cachedUserProfile.top_genres.length > 0) {
          profilePrimaryTaste.textContent = cachedUserProfile.top_genres[0].genre;
        } else {
          profilePrimaryTaste.textContent = u ? u.primaryGenre : 'General';
        }
      }

      // Render Genre Affinities
      if (profileGenreBars) {
        profileGenreBars.innerHTML = '';
        if (cachedUserProfile.top_genres && cachedUserProfile.top_genres.length > 0) {
          cachedUserProfile.top_genres.forEach((g) => {
            const pct = Math.min(100, Math.round((g.affinity_score / 5.0) * 100));
            const bar = document.createElement('div');
            bar.className = 'genre-bar-item';
            bar.innerHTML = `
              <div class="genre-bar-header">
                <span>${g.genre}</span>
                <strong>${g.affinity_score.toFixed(1)}★ (${pct}%)</strong>
              </div>
              <div class="progress-bar-container">
                <div class="progress-fill fill-blue" style="width: ${pct}%"></div>
              </div>
            `;
            profileGenreBars.appendChild(bar);
          });
        } else {
          profileGenreBars.innerHTML =
            '<p style="font-size:0.85rem;color:var(--text-dim);padding:8px 0;">No historical ratings recorded to compute genre affinities.</p>';
        }
      }

      if (tabHistoricalRatings) tabHistoricalRatings.classList.add('active');
      if (tabLiveFeedback) tabLiveFeedback.classList.remove('active');
      renderHistoricalRatings();
    } catch (err) {
      console.error('Error loading user profile:', err);
    }
  }

  function renderHistoricalRatings() {
    if (!historyContent) return;

    if (!cachedUserProfile || !cachedUserProfile.recent_ratings || cachedUserProfile.recent_ratings.length === 0) {
      historyContent.innerHTML =
        '<p style="color:var(--text-dim);font-size:0.9rem;padding:24px;text-align:center;">No historical ratings recorded for this user.</p>';
      return;
    }

    historyContent.innerHTML = '';
    cachedUserProfile.recent_ratings.forEach((r) => {
      const item = document.createElement('div');
      item.className = 'history-item';
      item.innerHTML = `
        <span class="history-title">${escapeHtml(r.title)}</span>
        <span class="history-rating">${r.rating.toFixed(1)} ★</span>
      `;
      historyContent.appendChild(item);
    });
  }

  function renderLiveFeedback() {
    if (!historyContent) return;

    if (state.liveFeedback.length === 0) {
      historyContent.innerHTML =
        '<p style="color:var(--text-dim);font-size:0.9rem;padding:24px;text-align:center;">No live feedback recorded yet in this session. Rate or like movies in "For You" or "Explore" to see live updates!</p>';
      return;
    }

    historyContent.innerHTML = '';
    state.liveFeedback.forEach((f) => {
      const item = document.createElement('div');
      item.className = 'history-item';
      item.innerHTML = `
        <span class="history-title">${escapeHtml(f.title)} <small style="color:var(--text-dim);margin-left:6px;">(${f.type} at ${f.time})</small></span>
        <span class="history-rating">${f.rating ? `${f.rating}★` : f.type}</span>
      `;
      historyContent.appendChild(item);
    });
  }

  // ==========================================
  // Model Evaluation Dashboard Renderer
  // ==========================================
  function renderEvaluationTable() {
    if (!state.evaluationMetrics) return;

    const tableBody = document.getElementById('evaluationTableBody');
    if (!tableBody) return;

    const models = state.evaluationMetrics.models || {};
    tableBody.innerHTML = '';

    const modelDisplayNames = {
      popularity: 'Bayesian Popularity Prior',
      item_collaborative: 'Item-Item Collaborative',
      matrix_factorization_svd: 'Latent Factor SVD (35-dim)',
      hybrid: 'Two-Stage Hybrid Engine (👑 Production)',
    };

    Object.keys(models).forEach((key) => {
      const m = models[key];
      const metrics = m.metrics || {};
      const isWinner = key === state.evaluationMetrics.winner_model;

      const tr = document.createElement('tr');
      if (isWinner) tr.className = 'highlight-row';

      tr.innerHTML = `
        <td><strong>${modelDisplayNames[key] || m.model_name}</strong></td>
        <td>${(metrics['precision@5'] || 0).toFixed(4)}</td>
        <td><strong>${(metrics['precision@10'] || 0).toFixed(4)}</strong></td>
        <td>${(metrics['recall@5'] || 0).toFixed(4)}</td>
        <td>${(metrics['recall@10'] || 0).toFixed(4)}</td>
        <td>${(metrics['ndcg@10'] || 0).toFixed(4)}</td>
        <td>${((metrics['hit_rate@10'] || 0) * 100).toFixed(1)}%</td>
        <td>${((metrics['hit_rate@20'] || 0) * 100).toFixed(1)}%</td>
        <td>${((metrics['catalog_coverage'] || 0) * 100).toFixed(2)}%</td>
      `;
      tableBody.appendChild(tr);
    });
  }

  // ==========================================
  // Movie Detail Modal Controller
  // ==========================================
  function openMovieDetails(movie) {
    if (!modalBody || !movieDetailModal) return;

    const safeTitle = escapeHtml(movie.title);
    const genresHtml = (movie.genres || []).map((g) => `<span class="genre-tag">${g}</span>`).join('');

    modalBody.innerHTML = `
      <h2 style="margin-bottom: 6px; font-size: 1.4rem;">${safeTitle}</h2>
      <div style="display:flex;gap:6px;margin-bottom:16px;flex-wrap:wrap;">
        ${genresHtml}
      </div>

      <div style="background:var(--bg-canvas);border:1px solid var(--border-subtle);padding:14px;border-radius:var(--radius-md);margin-bottom:18px;display:grid;grid-template-columns:repeat(3,1fr);gap:10px;text-align:center;">
        <div>
          <span style="font-size:0.75rem;color:var(--text-dim)">Average Rating</span>
          <div style="font-size:1.25rem;font-weight:700;color:var(--accent-amber)">${movie.rating_mean ? movie.rating_mean.toFixed(1) : '—'}★</div>
        </div>
        <div>
          <span style="font-size:0.75rem;color:var(--text-dim)">Total Ratings</span>
          <div style="font-size:1.25rem;font-weight:700;color:var(--text-main)">${movie.rating_count ? movie.rating_count.toLocaleString() : '—'}</div>
        </div>
        <div>
          <span style="font-size:0.75rem;color:var(--text-dim)">Predicted Affinity</span>
          <div style="font-size:1.25rem;font-weight:700;color:var(--accent-blue)">${movie.predicted_score ? `${movie.predicted_score.toFixed(1)}★` : '—'}</div>
        </div>
      </div>

      <div style="margin-bottom:16px;">
        <h4 style="font-size:0.9rem;margin-bottom:8px;color:var(--text-main)">Rate This Title</h4>
        <div class="star-rating-widget" id="modalStars" style="font-size:1.5rem;">
          <button class="star-btn" data-star="1">★</button>
          <button class="star-btn" data-star="2">★</button>
          <button class="star-btn" data-star="3">★</button>
          <button class="star-btn" data-star="4">★</button>
          <button class="star-btn" data-star="5">★</button>
        </div>
      </div>

      <div style="margin-top:20px;padding-top:16px;border-top:1px solid var(--border-subtle)">
        <button class="action-btn btn-primary btn-apple" id="btnFindSimilar" style="width:100%;justify-content:center;">
          Find Titles Similar To This
        </button>
      </div>

      <div id="modalSimilarMovies" style="margin-top:16px;"></div>
    `;

    const modalStars = modalBody.querySelectorAll('#modalStars .star-btn');
    modalStars.forEach((btn) => {
      btn.addEventListener('click', () => {
        const rating = parseFloat(btn.getAttribute('data-star'));
        submitFeedback(movie.movie_id, movie.title, 'rating', rating);
        highlightStars(modalStars, rating);
      });
    });

    const btnFindSimilar = modalBody.querySelector('#btnFindSimilar');
    if (btnFindSimilar) {
      btnFindSimilar.addEventListener('click', () => {
        findSimilarMovies(movie.movie_id, movie.title);
      });
    }

    movieDetailModal.classList.remove('hidden');
  }

  function closeModal() {
    if (movieDetailModal) {
      movieDetailModal.classList.add('hidden');
    }
  }

  async function findSimilarMovies(movieId, title) {
    const container = document.getElementById('modalSimilarMovies');
    if (!container) return;

    container.innerHTML = '<div class="spinner" style="width:24px;height:24px;margin:12px auto;"></div>';

    try {
      const res = await fetch(`/api/recommend/${state.userId}?k=4&model_type=item_collaborative`);
      if (!res.ok) throw new Error('Similar fetch failed');
      const data = await res.json();

      container.innerHTML = '<h5 style="margin-bottom:8px;font-size:0.85rem;color:var(--accent-blue)">Similar Recommendations:</h5>';
      const list = document.createElement('div');
      list.style.display = 'flex';
      list.style.flexDirection = 'column';
      list.style.gap = '6px';

      (data.recommendations || []).forEach((m) => {
        const row = document.createElement('div');
        row.className = 'history-item';
        row.innerHTML = `
          <span>${escapeHtml(m.title)}</span>
          <span style="color:var(--accent-blue);font-weight:600;">${m.predicted_score.toFixed(1)}★</span>
        `;
        list.appendChild(row);
      });
      container.appendChild(list);
    } catch (e) {
      container.innerHTML = '<p style="color:var(--text-dim);font-size:0.8rem">Could not load similar items.</p>';
    }
  }

  // ==========================================
  // Helper Utilities
  // ==========================================
  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  window.switchTab = switchTab;
  window.openLoginModal = openLoginModal;

  // Initialize Application
  init();
});
