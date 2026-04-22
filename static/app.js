const { createApp } = Vue;

createApp({
  data() {
    return {
      // ── 页面控制 ──
      currentPage: "preference",   // preference | rating | result
      isLoading:     false,
      isLoadingMore: false,
      loadingText:   "正在处理...",

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
      this.loadingText = "正在理解你的描述...";
      try {
        const res  = await fetch("/api/parse-preference", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: this.nlInput })
        });
        const data = await res.json();
        this.parsedGenres = data.genres || [];
      } catch (e) {
        console.error("解析失败", e);
        alert("解析失败，请尝试手动选择类型");
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
      this.loadingText = "正在筛选电影...";
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
        alert("获取电影列表失败，请重试");
      } finally {
        this.isLoading = false;
      }
    },

    async submitRatings() {
      if (this.ratedCount < 3) return;
      this.isLoading  = true;
      this.loadingText = "正在为你生成推荐，请稍候...";

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
        this.likedIds     = [];
        this.dislikedIds  = [];
        this.currentPage  = "result";
      } catch (e) {
        console.error(e);
        alert("获取推荐失败，请重试");
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
    },

    dislikeMovie(movieId) {
      if (!this.dislikedIds.includes(movieId)) {
        this.dislikedIds.push(movieId);
      }
    },

    async fetchFeedbackRecs() {
      if (this.likedIds.length === 0) return;
      this.isLoadingMore = true;
      try {
        const res  = await fetch("/api/feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ liked_movie_ids: this.likedIds })
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
      this.likedIds     = [];
      this.dislikedIds  = [];
    }
  }
}).mount("#app");
