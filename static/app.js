const { createApp } = Vue;

createApp({
  data() {
    return {
      // ── 页面控制 ──
      currentPage: "preference",   // preference | rating | result
      isLoading:     false,
      isLoadingMore: false,
      loadingText:   "Working...",

      // ── 偏好选择 ──
      inputMode:     "select",     // select | text
      allGenres: [
        "Action", "Comedy", "Drama", "Romance", "Thriller",
        "Sci-Fi", "Horror", "Animation", "Documentary", "Fantasy",
        "Adventure", "Crime", "Mystery", "Family", "Music"
      ],
      genreEmoji: {
        "Action": "💥", "Comedy": "😂", "Drama": "🎭", "Romance": "💕",
        "Thriller": "😱", "Sci-Fi": "🚀", "Horror": "👻", "Animation": "🎨",
        "Documentary": "📽️", "Fantasy": "🧙", "Adventure": "🗺️",
        "Crime": "🔫", "Mystery": "🔍", "Family": "👨‍👩‍👧", "Music": "🎵"
      },
      selectedGenres: [],
      nlInput:        "",
      parsedGenres:   [],

      // ── 评分页 ──
      sampleMovies:  [],
      userRatings:   {},           // { movie_id: rating }  1-5 星
      hoverRatings:  {},           // { movie_id: hover星数 } 悬停预览

      // ── 推荐结果 ──
      mainRecs:     [],            // 协同过滤结果
      feedbackRecs: [],            // CBF 追加结果
      feedbackSummary: [],         // 反馈后用于解释推荐列表变化的小面板
      likedIds:     [],
      dislikedIds:  [],

      // ── 实验开关（从 URL 参数读取） ──
      version: "enhanced",
      algorithm: "enhanced",       // baseline | enhanced
      explain: true                // 推荐理由展示，不参与排序
    };
  },

  computed: {
    // 最终生效的 genres（兼容两种输入模式）
    effectiveGenres() {
      return this.inputMode === "text" ? this.parsedGenres : this.selectedGenres;
    },
    ratedCount() {
      return Object.values(this.userRatings).filter(r => r > 0).length;
    },
    // 供模板遍历（过滤掉 dislike 的）
    recommendations() {
      return [...this.mainRecs, ...this.feedbackRecs]
        .filter(m => !this.dislikedIds.includes(m.movie_id));
    },
    visibleMainRecs() {
      return this.mainRecs.filter(m => !this.dislikedIds.includes(m.movie_id));
    },
    visibleFeedbackRecs() {
      return this.feedbackRecs.filter(m => !this.dislikedIds.includes(m.movie_id));
    }
  },

  mounted() {
    const params = new URLSearchParams(window.location.search);
    this.version = params.get("version") || "enhanced";
    this.algorithm = params.get("algorithm") || (this.version === "baseline" ? "baseline" : "enhanced");
    this.explain = params.has("explain")
      ? ["1", "true", "yes", "on"].includes(params.get("explain").toLowerCase())
      : this.version !== "baseline";
  },

  methods: {
    // ────────────────────────────────────
    // 星级评分
    // ────────────────────────────────────

    setRating(movieId, stars) {
      // 再次点同一颗星 → 取消评分
      if (this.userRatings[movieId] === stars) {
        this.userRatings = { ...this.userRatings, [movieId]: 0 };
      } else {
        this.userRatings = { ...this.userRatings, [movieId]: stars };
      }
    },

    // ────────────────────────────────────
    // 图片加载处理（修复图片不显示问题）
    // ────────────────────────────────────

    /**
     * 图片成功加载：给 img 加 .loaded 让它显示在 fallback 上方
     */
    onImgLoad(event) {
      event.target.classList.add("loaded");
    },

    /**
     * 图片加载失败：隐藏 img，保留 CSS fallback（显示电影名+图标）
     */
    onImgError(event) {
      event.target.classList.add("has-error");
    },

    // ────────────────────────────────────
    // 偏好选择页
    // ────────────────────────────────────

    toggleGenre(genre) {
      const idx = this.selectedGenres.indexOf(genre);
      if (idx === -1) {
        if (this.selectedGenres.length < 5) this.selectedGenres.push(genre);
      } else {
        this.selectedGenres.splice(idx, 1);
      }
    },

    async parseNLInput() {
      if (!this.nlInput.trim()) return;
      this.isLoading  = true;
      this.loadingText = "Understanding your description...";
      try {
        const res  = await fetch("/api/parse-preference", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: this.nlInput })
        });
        const data = await res.json();
        this.parsedGenres = data.genres || [];
      } catch (e) {
        console.error("Failed to parse preference", e);
        alert("Could not understand that description. Please try selecting genres manually.");
      } finally {
        this.isLoading = false;
      }
    },

    // ────────────────────────────────────
    // 评分页
    // ────────────────────────────────────

    async goToRating() {
      if (this.effectiveGenres.length === 0) return;
      this.isLoading  = true;
      this.loadingText = "Finding movies for you...";
      try {
        const res  = await fetch("/api/sample-movies", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ genres: this.effectiveGenres })
        });
        const data = await res.json();
        this.sampleMovies = data.movies || [];
        this.currentPage  = "rating";
      } catch (e) {
        console.error(e);
        alert("Could not load the movie list. Please try again.");
      } finally {
        this.isLoading = false;
      }
    },

    async submitRatings() {
      if (this.ratedCount < 3) return;
      this.isLoading  = true;
      this.loadingText = "Generating your recommendations...";

      const ratings = Object.entries(this.userRatings)
        .filter(([, v]) => v > 0)
        .map(([k, v]) => ({ movie_id: parseInt(k), rating: v }));

      try {
        const query = new URLSearchParams({
          algorithm: this.algorithm,
          explain: String(this.explain)
        });
        const res  = await fetch(`/api/preferences?${query.toString()}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ genres: this.effectiveGenres, ratings })
        });
        const data = await res.json();
        this.mainRecs     = data.recommendations || [];
        this.feedbackRecs = [];
        this.feedbackSummary = [];
        this.likedIds     = [];
        this.dislikedIds  = [];
        this.currentPage  = "result";
      } catch (e) {
        console.error(e);
        alert("Could not get recommendations. Please try again.");
      } finally {
        this.isLoading = false;
      }
    },

    // ────────────────────────────────────
    // 推荐结果页
    // ────────────────────────────────────

    likeMovie(movieId) {
      if (!this.likedIds.includes(movieId)) {
        this.likedIds.push(movieId);
      }
      this.dislikedIds = this.dislikedIds.filter(id => id !== movieId);
    },

    async dislikeMovie(movieId) {
      if (!this.dislikedIds.includes(movieId)) {
        this.dislikedIds.push(movieId);
      }
      this.likedIds = this.likedIds.filter(id => id !== movieId);

      // 如果已经有正反馈，点 dislike 后立即刷新追加推荐与解释面板。
      if (this.likedIds.length > 0) {
        await this.fetchFeedbackRecs();
      }
    },

    async fetchFeedbackRecs() {
      if (this.likedIds.length === 0) return;
      this.isLoadingMore = true;
      try {
        const res  = await fetch("/api/feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            liked_movie_ids: this.likedIds,
            disliked_movie_ids: this.dislikedIds
          })
        });
        const data = await res.json();
        const newRecs = data.recommendations || [];

        // 去重追加（避免与已展示重复）
        const existingIds = new Set([
          ...this.mainRecs.map(m => m.movie_id),
          ...this.feedbackRecs.map(m => m.movie_id)
        ]);
        const unique = newRecs.filter(m => !existingIds.has(m.movie_id));
        this.feedbackRecs = [...this.feedbackRecs, ...unique];
        this.feedbackSummary = data.feedback_summary || [];
      } catch (e) {
        console.error(e);
      } finally {
        this.isLoadingMore = false;
      }
    },

    restart() {
      this.currentPage  = "preference";
      this.selectedGenres = [];
      this.nlInput      = "";
      this.parsedGenres = [];
      this.userRatings  = {};
      this.hoverRatings = {};
      this.mainRecs     = [];
      this.feedbackRecs = [];
      this.feedbackSummary = [];
      this.likedIds     = [];
      this.dislikedIds  = [];
    }
  }
}).mount("#app");
