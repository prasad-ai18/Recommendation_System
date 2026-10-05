/**
 * RecSys AI — Personalized Recommendation Intelligence Platform
 * Frontend Application Controller
 */

document.addEventListener('DOMContentLoaded', () => {
  // App State
  const state = {
    userId: 1,
    modelType: 'hybrid',
    k: 10,
    genreFilter: '',
    catalogQuery: '',
    catalogGenre: '',
    catalogSort: 'bayesian_score',
    catalogPage: 1,
    catalogTotalPages: 1,
    sampleUsers: [],
    genres: [],
    liveFeedback: [],
    evaluationMetrics: null,
  };

  // Model Descriptions for Banner
  const modelInfo = {
    hybrid: {
      badge: 'Two-Stage Hybrid Intelligence',
      desc: 'Retrieves candidates from Collaborative Filtering, Latent SVD embeddings, and Genre affinities, then applies feature-weighted ranking with diversity control.',
    },
    item_collaborative: {
      badge: 'Item-Item Collaborative Filtering',
      desc: 'Computes cosine similarities between item interaction vectors with shrinkage penalty. Provides transparent seed attribution explanations.',
    },
    matrix_factorization_svd: {
      badge: 'Latent Factor Matrix Factorization',
      desc: 'Decomposes user-item interaction matrix into dense 35-dimensional latent embeddings via Singular Value Decomposition (SVD).',
    },
    popularity: {
      badge: 'Popularity Baseline Prior',
      desc: 'Ranks catalog items using Bayesian dampening weighted ratings. Optimal zero-information cold-start fallback.',
    },
  };

  // DOM Elements
  const navTabs = document.querySelectorAll('.nav-tab');
  const viewPanels = document.querySelectorAll('.view-panel');
  const userSelect = document.getElementById('userSelect');
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

  // Catalog DOM
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
    setupTabNavigation();
    setupEventListeners();
    await fetchHealthAndStats();
    await fetchSampleUsers();
    await fetchGenres();
    await fetchMetrics();
    loadRecommendations();
    loadCatalog();
  }

  // ==========================================
  // Tab Navigation
  // ==========================================
  function setupTabNavigation() {
    navTabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        const targetTab = tab.getAttribute('data-tab');
        navTabs.forEach((t) => t.classList.remove('active'));
        tab.classList.add('active');

        viewPanels.forEach((panel) => {
          panel.classList.remove('active');
          if (panel.id === `view${capitalize(targetTab)}`) {
            panel.classList.add('active');
          }
        });

        // Tab-specific trigger
        if (targetTab === 'profile') {
          loadUserProfile();
        } else if (targetTab === 'evaluation') {
          renderEvaluationTable();
        }
      });
    });
  }

  function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  // ==========================================
  // Event Listeners
  // ==========================================
  function setupEventListeners() {
    // User Switcher
    userSelect.addEventListener('change', (e) => {
      state.userId = parseInt(e.target.value, 10);
      updateUserHeader();
      loadRecommendations();
      if (document.getElementById('viewProfile').classList.contains('active')) {
        loadUserProfile();
      }
    });

    // Model Selector Pills
    modelPillGroup.querySelectorAll('.pill-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        modelPillGroup.querySelectorAll('.pill-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        state.modelType = btn.getAttribute('data-model');
        updateStrategyBanner();
        loadRecommendations();
      });
    });

    // Top K Slider
    topKSlider.addEventListener('input', (e) => {
      state.k = parseInt(e.target.value, 10);
      topKValue.textContent = state.k;
    });

    topKSlider.addEventListener('change', () => {
      loadRecommendations();
    });

    // Genre Filter in Recommendations
    genreFilter.addEventListener('change', (e) => {
      state.genreFilter = e.target.value;
      loadRecommendations();
    });

    // Refresh Button
    btnRefreshRecs.addEventListener('click', () => {
      loadRecommendations();
    });

    // Catalog Controls
    let searchDebounceTimer = null;
    catalogSearchInput.addEventListener('input', (e) => {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(() => {
        state.catalogQuery = e.target.value;
        state.catalogPage = 1;
        loadCatalog();
      }, 350);
    });

    catalogGenreFilter.addEventListener('change', (e) => {
      state.catalogGenre = e.target.value;
      state.catalogPage = 1;
      loadCatalog();
    });

    catalogSortBy.addEventListener('change', (e) => {
      state.catalogSort = e.target.value;
      state.catalogPage = 1;
      loadCatalog();
    });

    btnPrevPage.addEventListener('click', () => {
      if (state.catalogPage > 1) {
        state.catalogPage--;
        loadCatalog();
      }
    });

    btnNextPage.addEventListener('click', () => {
      if (state.catalogPage < state.catalogTotalPages) {
        state.catalogPage++;
        loadCatalog();
      }
    });

    // Profile History Sub-tabs
    tabHistoricalRatings.addEventListener('click', () => {
      tabHistoricalRatings.classList.add('active');
      tabLiveFeedback.classList.remove('active');
      renderHistoricalRatings();
    });

    tabLiveFeedback.addEventListener('click', () => {
      tabLiveFeedback.classList.add('active');
      tabHistoricalRatings.classList.remove('active');
      renderLiveFeedback();
    });

    // Modal close
    btnModalClose.addEventListener('click', closeModal);
    movieDetailModal.addEventListener('click', (e) => {
      if (e.target === movieDetailModal) closeModal();
    });
  }

  // ==========================================
  // Fetch System Health & Stats
  // ==========================================
  async function fetchHealthAndStats() {
    try {
      const res = await fetch('/api/health');
      if (!res.ok) return;
      const data = await res.json();
      if (data.dataset) {
        document.getElementById('statRatings').textContent = (data.dataset.total_ratings || 100836).toLocaleString();
        document.getElementById('statUsers').textContent = (data.dataset.total_users || 610).toLocaleString();
        document.getElementById('statMovies').textContent = (data.dataset.total_movies || 9742).toLocaleString();
      }
    } catch (err) {
      console.warn('Could not fetch /api/health:', err);
    }
  }

  // ==========================================
  // Fetch Sample Users
  // ==========================================
  async function fetchSampleUsers() {
    try {
      const res = await fetch('/api/users');
      if (!res.ok) return;
      const data = await res.json();
      state.sampleUsers = data.sample_users || [];

      userSelect.innerHTML = '';
      state.sampleUsers.forEach((u) => {
        const opt = document.createElement('option');
        opt.value = u.user_id;
        opt.textContent = u.label;
        userSelect.appendChild(opt);
      });

      if (state.sampleUsers.length > 0) {
        state.userId = state.sampleUsers[0].user_id;
      }
      updateUserHeader();
    } catch (err) {
      console.error('Failed to load sample users:', err);
    }
  }

  function updateUserHeader() {
    const user = state.sampleUsers.find((u) => u.user_id === state.userId);
    if (user) {
      recUserAvatar.textContent = `U${user.user_id === 9999 ? '★' : user.user_id}`;
      recUserTitle.textContent = `Personalized Recommendations for User ${user.user_id}`;
      if (user.user_id === 9999) {
        recUserTasteSummary.textContent = 'Taste Profile: Uncalibrated Cold-Start User (No prior ratings)';
      } else {
        recUserTasteSummary.textContent = `Taste Profile: ${user.primary_genre} Enthusiast (${user.ratings_count} verified ratings)`;
      }
    } else {
      recUserAvatar.textContent = `U${state.userId}`;
      recUserTitle.textContent = `Personalized Recommendations for User ${state.userId}`;
      recUserTasteSummary.textContent = 'Taste Profile: Custom User Profile';
    }
  }

  // ==========================================
  // Fetch Genres
  // ==========================================
  async function fetchGenres() {
    try {
      const res = await fetch('/api/genres');
      if (!res.ok) return;
      const data = await res.json();
      state.genres = data.genres || [];

      // Populate both dropdowns
      [genreFilter, catalogGenreFilter].forEach((select) => {
        select.innerHTML = '<option value="">All Genres</option>';
        state.genres.forEach((g) => {
          const opt = document.createElement('option');
          opt.value = g;
          opt.textContent = g;
          select.appendChild(opt);
        });
      });
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
    strategyBadge.textContent = info.badge;
    strategyDesc.textContent = info.desc;
  }

  // ==========================================
  // Recommendations Loader
  // ==========================================
  async function loadRecommendations() {
    recommendationsGrid.innerHTML = `
      <div class="loading-state">
        <div class="spinner"></div>
        <p>Retrieving candidate pool & calculating ranking scores...</p>
      </div>
    `;

    try {
      let url = `/api/recommend/${state.userId}?k=${state.k}&model_type=${state.modelType}`;
      if (state.genreFilter) {
        url += `&genre=${encodeURIComponent(state.genreFilter)}`;
      }

      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }

      const data = await res.json();
      statLatency.textContent = `${data.latency_ms} ms`;

      // Cold start banner
      if (data.is_cold_start) {
        coldStartBanner.classList.remove('hidden');
      } else {
        coldStartBanner.classList.add('hidden');
      }

      renderRecommendations(data.recommendations || []);
    } catch (err) {
      console.error('Error fetching recommendations:', err);
      recommendationsGrid.innerHTML = `
        <div class="loading-state" style="color: var(--accent-rose)">
          <p>⚠️ Failed to load recommendations: ${err.message}</p>
          <button class="action-btn btn-primary" onclick="window.location.reload()" style="margin-top: 12px">Retry</button>
        </div>
      `;
    }
  }

  function renderRecommendations(items) {
    if (!items || items.length === 0) {
      recommendationsGrid.innerHTML = `
        <div class="loading-state">
          <p>No recommendations match the current filters. Try changing the genre filter or algorithm.</p>
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
  // Create Movie Card Component
  // ==========================================
  function createMovieCard(movie, rank, showExplainability = false) {
    const card = document.createElement('div');
    card.className = 'movie-card';

    const matchPercent = Math.min(99, Math.max(60, Math.round((movie.predicted_score / 5.0) * 100)));
    const genreBadges = (movie.genres || [])
      .slice(0, 3)
      .map((g) => `<span class="genre-tag">${g}</span>`)
      .join('');

    const visualIcon = getGenreEmoji(movie.genres);

    card.innerHTML = `
      <div class="card-visual">
        <span class="visual-pattern">${visualIcon}</span>
        ${rank ? `<div class="rank-index">#${rank}</div>` : ''}
        <div class="score-badge">${movie.predicted_score ? `${movie.predicted_score.toFixed(1)}★` : `${movie.bayesian_score ? movie.bayesian_score.toFixed(1) : '4.0'}★`}</div>
      </div>
      <div class="card-body">
        <h3 class="movie-title" title="${movie.title}">
          ${movie.title}
        </h3>
        <div class="genre-tags">${genreBadges}</div>
        
        ${
          showExplainability && movie.recommendation_signal
            ? `<div class="explainability-box"><span class="signal-icon">💡</span>${movie.recommendation_signal}</div>`
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
            <button class="icon-btn btn-like" data-movie-id="${movie.movie_id}" title="Like">👍</button>
            <button class="icon-btn btn-bookmark" data-movie-id="${movie.movie_id}" title="Bookmark">🔖</button>
            <button class="icon-btn btn-details" data-movie-id="${movie.movie_id}" title="Details">ℹ️</button>
          </div>
        </div>
      </div>
    `;

    // Hook up Star Ratings
    const starBtns = card.querySelectorAll('.star-btn');
    starBtns.forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const rating = parseFloat(btn.getAttribute('data-star'));
        submitFeedback(movie.movie_id, movie.title, 'rating', rating);
        highlightStars(starBtns, rating);
      });
    });

    // Like button
    const likeBtn = card.querySelector('.btn-like');
    likeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      likeBtn.classList.toggle('active');
      submitFeedback(movie.movie_id, movie.title, 'like', 5.0);
    });

    // Bookmark button
    const bmBtn = card.querySelector('.btn-bookmark');
    bmBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      bmBtn.classList.toggle('active');
      submitFeedback(movie.movie_id, movie.title, 'bookmark', 4.5);
    });

    // Details button
    const detailsBtn = card.querySelector('.btn-details');
    detailsBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      openMovieDetails(movie);
    });

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
    return '🎬';
  }

  // ==========================================
  // Feedback Submission & Closed Loop
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

      if (!res.ok) throw new Error('Feedback error');
      const data = await res.json();

      // Show toast
      showToast(
        `Recorded ${interactionType === 'rating' ? `${rating}★ rating` : interactionType} for "${movieTitle}"`
      );

      // Record in live feedback list
      state.liveFeedback.unshift({
        movie_id: movieId,
        title: movieTitle,
        type: interactionType,
        rating: rating,
        time: new Date().toLocaleTimeString(),
      });

      feedbackCountBadge.textContent = state.liveFeedback.length;

      // If user was cold start demo (User 9999), un-flag cold start banner
      if (state.userId === 9999) {
        coldStartBanner.classList.add('hidden');
        recUserTasteSummary.textContent = 'Taste Profile: Calibrating via live feedback events!';
      }
    } catch (err) {
      console.error('Feedback failed:', err);
      showToast('Feedback recording failed', true);
    }
  }

  // ==========================================
  // Toast Notifications
  // ==========================================
  function showToast(message, isError = false) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    if (isError) toast.style.borderColor = 'var(--accent-rose)';

    toast.innerHTML = `
      <span>${isError ? '⚠️' : '✅'}</span>
      <span>${message}</span>
    `;

    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(12px)';
      toast.style.transition = 'all 0.3s ease-out';
      setTimeout(() => toast.remove(), 300);
    }, 3200);
  }

  // ==========================================
  // Catalog Explorer
  // ==========================================
  async function loadCatalog() {
    catalogGrid.innerHTML = `
      <div class="loading-state">
        <div class="spinner"></div>
        <p>Loading catalog items...</p>
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
      catalogPageInfo.textContent = `Page ${data.page} of ${data.total_pages}`;
      catalogCountInfo.textContent = `Showing ${Math.min(data.total_count, (data.page - 1) * 18 + 1)}-${Math.min(data.total_count, data.page * 18)} of ${data.total_count.toLocaleString()} movies`;

      btnPrevPage.disabled = data.page <= 1;
      btnNextPage.disabled = data.page >= data.total_pages;

      renderCatalog(data.movies || []);
    } catch (err) {
      console.error('Catalog load error:', err);
      catalogGrid.innerHTML = `<div class="loading-state" style="color:var(--accent-rose)">Failed to load catalog.</div>`;
    }
  }

  function renderCatalog(movies) {
    if (!movies || movies.length === 0) {
      catalogGrid.innerHTML = `<div class="loading-state"><p>No movies found matching search criteria.</p></div>`;
      return;
    }

    catalogGrid.innerHTML = '';
    movies.forEach((m) => {
      const card = createMovieCard(m, null, false);
      catalogGrid.appendChild(card);
    });
  }

  // ==========================================
  // User Profile
  // ==========================================
  let cachedUserProfile = null;
  async function loadUserProfile() {
    try {
      const res = await fetch(`/api/users/${state.userId}/profile`);
      if (!res.ok) return;
      cachedUserProfile = await res.json();

      profileLargeAvatar.textContent = `U${cachedUserProfile.user_id === 9999 ? '★' : cachedUserProfile.user_id}`;
      profileName.textContent = `User ${cachedUserProfile.user_id}`;
      profileRatedCount.textContent = cachedUserProfile.ratings_count;
      profileMeanRating.textContent = `${cachedUserProfile.average_rating} ★`;

      if (cachedUserProfile.top_genres && cachedUserProfile.top_genres.length > 0) {
        profilePrimaryTaste.textContent = cachedUserProfile.top_genres[0].genre;
      } else {
        profilePrimaryTaste.textContent = 'General / New User';
      }

      // Render Genre Bars
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
              <div class="progress-fill fill-cyan" style="width: ${pct}%"></div>
            </div>
          `;
          profileGenreBars.appendChild(bar);
        });
      } else {
        profileGenreBars.innerHTML = '<p style="font-size:0.8rem;color:var(--text-dim)">No historical ratings to compute genre affinities.</p>';
      }

      // Default to historical ratings tab
      tabHistoricalRatings.classList.add('active');
      tabLiveFeedback.classList.remove('active');
      renderHistoricalRatings();
    } catch (err) {
      console.error('Error loading user profile:', err);
    }
  }

  function renderHistoricalRatings() {
    if (!cachedUserProfile || !cachedUserProfile.recent_ratings || cachedUserProfile.recent_ratings.length === 0) {
      historyContent.innerHTML = '<p style="color:var(--text-dim);font-size:0.85rem">No historical ratings found for this profile.</p>';
      return;
    }

    historyContent.innerHTML = '';
    cachedUserProfile.recent_ratings.forEach((r) => {
      const item = document.createElement('div');
      item.className = 'history-item';
      item.innerHTML = `
        <span class="history-title">${r.title}</span>
        <span class="history-rating">${r.rating.toFixed(1)} ★</span>
      `;
      historyContent.appendChild(item);
    });
  }

  function renderLiveFeedback() {
    if (state.liveFeedback.length === 0) {
      historyContent.innerHTML = '<p style="color:var(--text-dim);font-size:0.85rem">No live feedback recorded yet in this session. Rate or like movies in "For You" or "Catalog" to see live updates!</p>';
      return;
    }

    historyContent.innerHTML = '';
    state.liveFeedback.forEach((f) => {
      const item = document.createElement('div');
      item.className = 'history-item';
      item.innerHTML = `
        <span class="history-title">${f.title} <small style="color:var(--text-dim)">(${f.type})</small></span>
        <span class="history-rating">${f.rating ? `${f.rating}★` : f.type}</span>
      `;
      historyContent.appendChild(item);
    });
  }

  // ==========================================
  // Model Evaluation Dashboard
  // ==========================================
  function renderEvaluationTable() {
    if (!state.evaluationMetrics) return;

    const tableBody = document.getElementById('evaluationTableBody');
    if (!tableBody) return;

    const models = state.evaluationMetrics.models || {};
    tableBody.innerHTML = '';

    const modelDisplayNames = {
      popularity: 'Popularity Baseline',
      item_collaborative: 'Item-Item Collaborative',
      matrix_factorization_svd: 'Latent Factor SVD',
      hybrid: 'Two-Stage Hybrid Engine (Production)',
    };

    Object.keys(models).forEach((key) => {
      const m = models[key];
      const metrics = m.metrics || {};
      const isWinner = key === state.evaluationMetrics.winner_model;

      const tr = document.createElement('tr');
      if (isWinner) tr.className = 'highlight-row';

      tr.innerHTML = `
        <td><strong>${isWinner ? '👑 ' : ''}${modelDisplayNames[key] || m.model_name}</strong></td>
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
  // Movie Detail Modal
  // ==========================================
  function openMovieDetails(movie) {
    modalBody.innerHTML = `
      <h2 style="margin-bottom: 6px;">${movie.title}</h2>
      <div style="display:flex;gap:6px;margin-bottom:16px;">
        ${(movie.genres || []).map((g) => `<span class="genre-tag">${g}</span>`).join('')}
      </div>

      <div style="background:rgba(255,255,255,0.03);padding:14px;border-radius:var(--radius-md);margin-bottom:18px;display:grid;grid-template-columns:repeat(3,1fr);gap:10px;text-align:center;">
        <div>
          <span style="font-size:0.75rem;color:var(--text-dim)">Average Rating</span>
          <div style="font-size:1.2rem;font-weight:700;color:var(--accent-amber)">${movie.rating_mean ? movie.rating_mean.toFixed(1) : '—'}★</div>
        </div>
        <div>
          <span style="font-size:0.75rem;color:var(--text-dim)">Total Ratings</span>
          <div style="font-size:1.2rem;font-weight:700;color:var(--text-main)">${movie.rating_count ? movie.rating_count.toLocaleString() : '—'}</div>
        </div>
        <div>
          <span style="font-size:0.75rem;color:var(--text-dim)">Predicted Affinity</span>
          <div style="font-size:1.2rem;font-weight:700;color:var(--accent-cyan)">${movie.predicted_score ? `${movie.predicted_score.toFixed(1)}★` : '—'}</div>
        </div>
      </div>

      <div style="margin-bottom:16px;">
        <h4 style="font-size:0.9rem;margin-bottom:8px;color:var(--text-main)">Rate This Title</h4>
        <div class="star-rating-widget" style="font-size:1.4rem;">
          <button class="star-btn" onclick="submitModalRating(${movie.movie_id}, '${escapeQuote(movie.title)}', 1)">★</button>
          <button class="star-btn" onclick="submitModalRating(${movie.movie_id}, '${escapeQuote(movie.title)}', 2)">★</button>
          <button class="star-btn" onclick="submitModalRating(${movie.movie_id}, '${escapeQuote(movie.title)}', 3)">★</button>
          <button class="star-btn" onclick="submitModalRating(${movie.movie_id}, '${escapeQuote(movie.title)}', 4)">★</button>
          <button class="star-btn" onclick="submitModalRating(${movie.movie_id}, '${escapeQuote(movie.title)}', 5)">★</button>
        </div>
      </div>

      <div style="margin-top:20px;padding-top:16px;border-top:1px solid var(--border-subtle)">
        <button class="action-btn btn-primary" onclick="findSimilarMovies(${movie.movie_id}, '${escapeQuote(movie.title)}')">
          Find Movies Similar To This
        </button>
      </div>

      <div id="modalSimilarMovies" style="margin-top:16px;"></div>
    `;

    movieDetailModal.classList.remove('hidden');
  }

  function escapeQuote(str) {
    return str.replace(/'/g, "\\'");
  }

  function closeModal() {
    movieDetailModal.classList.add('hidden');
  }

  // Global helper for modal rating
  window.submitModalRating = function (movieId, title, rating) {
    submitFeedback(movieId, title, 'rating', rating);
  };

  // Find similar movies
  window.findSimilarMovies = async function (movieId, title) {
    const container = document.getElementById('modalSimilarMovies');
    container.innerHTML = '<div class="spinner" style="width:24px;height:24px;margin:12px auto;"></div>';

    try {
      // Query recommendation using item_collaborative centered on this movie or similar
      const res = await fetch(`/api/recommend/${state.userId}?k=4&model_type=item_collaborative`);
      if (!res.ok) throw new Error('Similar fetch failed');
      const data = await res.json();

      container.innerHTML = '<h5 style="margin-bottom:8px;font-size:0.85rem;color:var(--accent-cyan)">Similar Recommendations:</h5>';
      const list = document.createElement('div');
      list.style.display = 'flex';
      list.style.flexDirection = 'column';
      list.style.gap = '6px';

      (data.recommendations || []).forEach((m) => {
        const row = document.createElement('div');
        row.className = 'history-item';
        row.innerHTML = `<span>${m.title}</span><span style="color:var(--accent-cyan)">${m.predicted_score.toFixed(1)}★</span>`;
        list.appendChild(row);
      });
      container.appendChild(list);
    } catch (e) {
      container.innerHTML = '<p style="color:var(--text-dim);font-size:0.8rem">Could not load similar items.</p>';
    }
  };

  // Start Application
  init();
});
