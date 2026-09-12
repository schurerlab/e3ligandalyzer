class CustomNavbar extends HTMLElement {
  connectedCallback() {
    if (this.shadowRoot) return;

    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --primary: #38bdf8;
          --primary-soft: rgba(56, 189, 248, 0.14);
          --accent: #facc15;
          --text: #f8fafc;
          --text-muted: #cbd5e1;
          --text-soft: #94a3b8;
          --bg-glass: rgba(15, 23, 42, 0.78);
          --bg-panel: rgba(2, 6, 23, 0.98);
          --border-glow: rgba(56, 189, 248, 0.26);
          --shadow-glow: 0 24px 80px rgba(0, 0, 0, 0.46), 0 0 30px rgba(56, 189, 248, 0.12);
          font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        *,
        *::before,
        *::after {
          box-sizing: border-box;
        }

        a,
        a:visited,
        a:hover,
        a:active,
        a:focus {
          text-decoration: none !important;
        }

        nav {
          position: sticky;
          top: 0;
          z-index: 1000;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 1rem;
          min-height: 64px;
          padding: 0.8rem 1.5rem;
          background: var(--bg-glass);
          border-bottom: 1px solid var(--border-glow);
          backdrop-filter: blur(14px);
          -webkit-backdrop-filter: blur(14px);
          transition: min-height 0.22s ease, padding 0.22s ease, background 0.22s ease;
        }

        nav.is-scrolled {
          min-height: 56px;
          padding-block: 0.55rem;
          background: rgba(15, 23, 42, 0.92);
        }

        nav::before {
          content: "";
          position: absolute;
          inset: 0;
          border-bottom: 1px solid transparent;
          background: linear-gradient(90deg, rgba(56, 189, 248, 0.65), rgba(250, 204, 21, 0.55), rgba(56, 189, 248, 0.65)) border-box;
          -webkit-mask: linear-gradient(#000 0 0) padding-box, linear-gradient(#000 0 0);
          -webkit-mask-composite: xor;
          mask-composite: exclude;
          pointer-events: none;
        }

        .brand {
          position: relative;
          z-index: 2;
          display: inline-flex;
          align-items: center;
          gap: 0.6rem;
          min-width: 0;
          color: var(--primary);
          font-size: 1.08rem;
          font-weight: 700;
          letter-spacing: -0.02em;
          white-space: nowrap;
        }

        .brand img {
          width: 28px;
          height: 28px;
          flex: 0 0 auto;
          border-radius: 7px;
          box-shadow: 0 0 16px rgba(56, 189, 248, 0.28);
        }

        .brand span {
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .menu {
          position: relative;
          z-index: 2;
          display: flex;
          align-items: center;
          gap: 0.45rem;
          list-style: none;
          margin: 0;
          padding: 0;
        }

        .menu li {
          position: relative;
        }

        .menu a,
        .menu button {
          appearance: none;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 0.42rem;
          min-height: 40px;
          padding: 0.5rem 0.72rem;
          border: 1px solid transparent;
          border-radius: 10px;
          background: transparent;
          color: var(--text-muted);
          font: inherit;
          font-size: 0.92rem;
          font-weight: 600;
          line-height: 1;
          white-space: nowrap;
          cursor: pointer;
          transition: background 0.18s ease, border-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
        }

        .menu a:hover,
        .menu button:hover,
        .menu a:focus-visible,
        .menu button:focus-visible {
          outline: none;
          color: var(--primary);
          background: var(--primary-soft);
          border-color: rgba(56, 189, 248, 0.2);
        }

        .menu a.active {
          color: var(--accent);
          background: rgba(250, 204, 21, 0.1);
          border-color: rgba(250, 204, 21, 0.34);
        }

        .menu svg {
          width: 16px;
          height: 16px;
          flex: 0 0 auto;
        }

        .mobile-menu-header {
          display: none;
        }

        .dropdown-content {
          position: absolute;
          top: calc(100% + 0.55rem);
          right: 0;
          min-width: 302px;
          padding: 0.45rem;
          border: 1px solid var(--border-glow);
          border-radius: 14px;
          background: rgba(15, 23, 42, 0.98);
          box-shadow: var(--shadow-glow);
          opacity: 0;
          visibility: hidden;
          pointer-events: none;
          transform: translateY(-4px) scale(0.985);
          transform-origin: top right;
          transition: opacity 0.18s ease, visibility 0.18s ease, transform 0.18s ease;
          z-index: 1100;
        }

        .dropdown.open .dropdown-content {
          opacity: 1;
          visibility: visible;
          pointer-events: auto;
          transform: translateY(0) scale(1);
        }

        .dropdown-content a {
          width: 100%;
          justify-content: space-between;
          min-height: 42px;
          padding: 0.64rem 0.72rem;
          border-radius: 10px;
          font-size: 0.9rem;
        }

        .module-label {
          display: inline-flex;
          align-items: center;
          gap: 0.48rem;
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .module-badges {
          display: inline-flex;
          align-items: center;
          gap: 0.35rem;
          flex: 0 0 auto;
          margin-left: 0.75rem;
        }

        .badge,
        .badge-soon,
        .badge-preprint,
        .badge-published,
        .badge-github {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 0.24rem 0.44rem;
          border-radius: 999px;
          font-size: 0.65rem;
          font-weight: 800;
          line-height: 1;
          letter-spacing: 0.045em;
          text-transform: uppercase;
          white-space: nowrap;
        }

        .badge {
          color: #bbf7d0;
          background: rgba(34, 197, 94, 0.18);
          border: 1px solid rgba(74, 222, 128, 0.64);
          box-shadow: 0 0 8px rgba(34, 197, 94, 0.22);
        }

        .badge-soon {
          color: #fef08a;
          background: rgba(250, 204, 21, 0.15);
          border: 1px solid rgba(250, 204, 21, 0.64);
          box-shadow: 0 0 8px rgba(250, 204, 21, 0.22);
        }

        .badge-preprint {
          color: #fecaca;
          background: rgba(239, 68, 68, 0.18);
          border: 1px solid rgba(248, 113, 113, 0.74);
          box-shadow: 0 0 8px rgba(239, 68, 68, 0.28);
        }

        .badge-published {
          color: #dcfce7;
          background: linear-gradient(135deg, rgba(34, 197, 94, 0.3), rgba(163, 230, 53, 0.2));
          border: 1px solid rgba(74, 222, 128, 0.9);
          box-shadow:
            0 0 10px rgba(74, 222, 128, 0.4),
            0 0 18px rgba(163, 230, 53, 0.18);
        }

        .badge-github {
          color: #e2e8f0;
          background: rgba(148, 163, 184, 0.16);
          border: 1px solid rgba(203, 213, 225, 0.5);
          box-shadow: 0 0 8px rgba(148, 163, 184, 0.18);
        }

        .lucky-btn {
          color: #172033 !important;
          background: linear-gradient(135deg, var(--accent), #fde68a) !important;
          border-color: rgba(250, 204, 21, 0.55) !important;
          box-shadow: 0 0 20px rgba(250, 204, 21, 0.16);
        }

        .lucky-btn:hover,
        .lucky-btn:focus-visible {
          color: #0f172a !important;
          transform: translateY(-1px);
        }

        .lucky-btn:disabled {
          cursor: wait;
          opacity: 0.75;
          transform: none;
        }

        .menu-toggle {
          position: relative;
          z-index: 1200;
          display: none;
          width: 44px;
          height: 44px;
          flex: 0 0 auto;
          align-items: center;
          justify-content: center;
          padding: 0;
          border: 1px solid rgba(56, 189, 248, 0.28);
          border-radius: 12px;
          background: rgba(15, 23, 42, 0.82);
          color: var(--text);
          cursor: pointer;
          box-shadow: 0 0 18px rgba(56, 189, 248, 0.12);
        }

        .menu-toggle:hover,
        .menu-toggle:focus-visible {
          outline: none;
          background: rgba(56, 189, 248, 0.12);
          border-color: rgba(56, 189, 248, 0.44);
        }

        .hamburger {
          position: relative;
          width: 22px;
          height: 16px;
          display: inline-block;
        }

        .bar {
          position: absolute;
          left: 0;
          width: 22px;
          height: 2px;
          border-radius: 999px;
          background: var(--text-muted);
          transition: transform 0.2s ease, opacity 0.2s ease, top 0.2s ease, background 0.2s ease;
        }

        .bar1 { top: 0; }
        .bar2 { top: 7px; }
        .bar3 { top: 14px; }

        .menu-toggle.active .bar {
          background: var(--primary);
        }

        .menu-toggle.active .bar1 {
          top: 7px;
          transform: rotate(45deg);
        }

        .menu-toggle.active .bar2 {
          opacity: 0;
        }

        .menu-toggle.active .bar3 {
          top: 7px;
          transform: rotate(-45deg);
        }

        .menu-backdrop {
          position: fixed;
          inset: 0;
          display: block;
          background: rgba(2, 6, 23, 0.68);
          backdrop-filter: blur(4px);
          -webkit-backdrop-filter: blur(4px);
          opacity: 0;
          pointer-events: none;
          transition: opacity 0.2s ease;
          z-index: 1001;
        }

        .menu-backdrop.show {
          opacity: 1;
          pointer-events: auto;
        }

        .menu-close {
          display: none;
        }

        @media (max-width: 1120px) and (min-width: 769px) {
          .brand span {
            max-width: 220px;
          }

          .menu {
            gap: 0.25rem;
          }

          .menu a,
          .menu button {
            padding-inline: 0.55rem;
            font-size: 0.86rem;
          }
        }

        @media (max-width: 768px) {
          nav,
          nav.is-scrolled {
            min-height: 60px;
            padding: 0.62rem max(0.9rem, env(safe-area-inset-left)) 0.62rem max(0.9rem, env(safe-area-inset-left));
          }

          .brand {
            flex: 1 1 auto;
            font-size: 0.98rem;
            gap: 0.5rem;
          }

          .brand img {
            width: 26px;
            height: 26px;
          }

          .brand span {
            max-width: min(62vw, 270px);
          }

          .menu-toggle {
            display: inline-flex;
          }

          .menu {
            position: fixed;
            top: 0;
            right: 0;
            bottom: 0;
            left: auto;
            z-index: 1002;
            width: min(88vw, 390px);
            max-width: 390px;
            height: 100dvh;
            max-height: 100dvh;
            display: flex;
            flex-direction: column;
            align-items: stretch;
            gap: 0;
            padding: max(0.85rem, env(safe-area-inset-top)) 0.85rem max(1.05rem, env(safe-area-inset-bottom));
            overflow-y: auto;
            overscroll-behavior: contain;
            background:
              radial-gradient(circle at top right, rgba(56, 189, 248, 0.18), transparent 34%),
              linear-gradient(180deg, rgba(15, 23, 42, 0.99), var(--bg-panel));
            border-left: 1px solid rgba(56, 189, 248, 0.26);
            box-shadow: var(--shadow-glow);
            opacity: 1;
            pointer-events: none;
            transform: translateX(104%);
            transition: transform 0.24s ease;
          }

          .menu.show {
            pointer-events: auto;
            transform: translateX(0);
          }

          .menu::-webkit-scrollbar {
            width: 8px;
          }

          .menu::-webkit-scrollbar-thumb {
            background: rgba(148, 163, 184, 0.35);
            border-radius: 999px;
          }

          .mobile-menu-header {
            display: flex !important;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 0.2rem 0.2rem 0.8rem;
            margin-bottom: 0.35rem;
            color: var(--text);
            border-bottom: 1px solid rgba(148, 163, 184, 0.16);
          }

          .mobile-menu-title {
            display: flex;
            flex-direction: column;
            gap: 0.16rem;
            min-width: 0;
          }

          .mobile-menu-title strong {
            color: var(--text);
            font-size: 0.98rem;
            letter-spacing: -0.01em;
          }

          .mobile-menu-title span {
            color: var(--text-soft);
            font-size: 0.76rem;
            line-height: 1.25;
          }

          .menu-close {
            display: inline-flex;
            width: 40px;
            height: 40px;
            flex: 0 0 auto;
            align-items: center;
            justify-content: center;
            padding: 0;
            border: 1px solid rgba(148, 163, 184, 0.24);
            border-radius: 12px;
            background: rgba(15, 23, 42, 0.72);
            color: var(--text-muted);
            font-size: 1.3rem;
            line-height: 1;
            cursor: pointer;
          }

          .menu-close:hover,
          .menu-close:focus-visible {
            outline: none;
            color: var(--primary);
            border-color: rgba(56, 189, 248, 0.42);
            background: rgba(56, 189, 248, 0.12);
          }

          .menu li {
            width: 100%;
          }

          .menu li + li {
            margin-top: 0.3rem;
          }

          .menu a,
          .menu button {
            width: 100%;
            justify-content: flex-start;
            min-height: 48px;
            padding: 0.88rem 0.9rem;
            border-radius: 13px;
            color: #e2e8f0;
            background: rgba(15, 23, 42, 0.38);
            border-color: rgba(148, 163, 184, 0.12);
            font-size: 0.95rem;
            line-height: 1.15;
          }

          .menu a:hover,
          .menu button:hover,
          .menu a:focus-visible,
          .menu button:focus-visible {
            background: rgba(56, 189, 248, 0.14);
            border-color: rgba(56, 189, 248, 0.26);
          }

          .menu a.active {
            color: var(--accent);
            background: rgba(250, 204, 21, 0.12);
            border-color: rgba(250, 204, 21, 0.32);
          }

          .lucky-btn {
            justify-content: center !important;
            min-height: 50px !important;
            margin: 0.1rem 0 0.25rem;
            border-radius: 15px !important;
            font-size: 0.96rem !important;
          }

          .dropdown > button {
            justify-content: space-between;
          }

          .dropdown > button::after {
            content: "";
            width: 8px;
            height: 8px;
            margin-left: auto;
            border-right: 2px solid currentColor;
            border-bottom: 2px solid currentColor;
            transform: rotate(45deg) translateY(-2px);
            transition: transform 0.18s ease;
            opacity: 0.8;
          }

          .dropdown.open > button::after {
            transform: rotate(225deg) translateY(-1px);
          }

          .dropdown-content {
            position: static;
            min-width: 0;
            width: 100%;
            max-height: 0;
            margin: 0;
            padding: 0 0.35rem;
            overflow: hidden;
            border: 0;
            border-radius: 14px;
            background: transparent;
            box-shadow: none;
            opacity: 1;
            visibility: visible;
            pointer-events: none;
            transform: none;
            transition: max-height 0.24s ease, padding 0.24s ease;
          }

          .dropdown.open .dropdown-content {
            max-height: 720px;
            padding-top: 0.35rem;
            padding-bottom: 0.35rem;
            pointer-events: auto;
          }

          .dropdown-content a {
            min-height: 44px;
            padding: 0.72rem 0.78rem 0.72rem 1rem;
            border-radius: 12px;
            color: var(--text-muted);
            background: rgba(15, 23, 42, 0.28);
            border-color: rgba(148, 163, 184, 0.08);
            font-size: 0.88rem;
          }

          .dropdown-content a + a {
            margin-top: 0.24rem;
          }

          .module-label {
            flex: 1 1 auto;
            white-space: normal;
          }

          .module-badges {
            margin-left: 0.55rem;
          }

          .badge,
          .badge-soon,
          .badge-preprint,
          .badge-published,
          .badge-github {
            font-size: 0.6rem;
            padding: 0.22rem 0.36rem;
          }

          #mobile-filter-block.collapsed {
            display: none;
          }

          #search-results {
            max-height: calc(100vh - 160px);
          }
        }

        @media (max-width: 420px) {
          .brand span {
            max-width: 55vw;
          }

          .menu {
            width: min(92vw, 390px);
          }
        }

        @media (prefers-reduced-motion: reduce) {
          *,
          *::before,
          *::after {
            scroll-behavior: auto !important;
            transition-duration: 0.01ms !important;
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
          }
        }
      </style>

      <nav aria-label="Primary navigation">
        <a href="/" class="brand" aria-label="Ligase Recruiter Ligandalyzer home">
          <img src="/static/images/favicon2.png" alt="" width="28" height="28">
          <span>Ligase Recruiter Ligandalyzer</span>
        </a>

        <button class="menu-toggle" type="button" aria-label="Open navigation" aria-expanded="false" aria-controls="primary-navigation">
          <span class="hamburger" aria-hidden="true">
            <span class="bar bar1"></span>
            <span class="bar bar2"></span>
            <span class="bar bar3"></span>
          </span>
        </button>

        <div class="menu-backdrop" hidden></div>

        <ul class="menu" id="primary-navigation">
          <li class="mobile-menu-header">
            <span class="mobile-menu-title">
              <strong>Navigation</strong>
              <span>E3 ligase recruitment tools and resources</span>
            </span>
            <button class="menu-close" type="button" aria-label="Close navigation">&times;</button>
          </li>

          <li>
            <button id="luckyBtn" class="lucky-btn" type="button">
              🎲 I'm Feeling Lucky
            </button>
          </li>

          <li>
            <a href="/" data-page="home">
              <i data-feather="home"></i>Home
            </a>
          </li>

          <li>
            <a href="/explorer" data-page="explorer">
              <i data-feather="search"></i>Explorer
            </a>
          </li>

          <li>
            <a href="/scaffolds" data-page="scaffolds">
              <i data-feather="layers"></i>Scaffolds
            </a>
          </li>

          <li>
            <a href="/ligases" data-page="ligases">
              <i data-feather="database"></i>Ligases
            </a>
          </li>

          <li>
            <a href="/about" data-page="about">
              <i data-feather="info"></i>About
            </a>
          </li>

          <li class="dropdown" id="resourcesDropdown">
            <button type="button">
              <span><i data-feather="book-open"></i>Resources</span>
            </button>

            <div class="dropdown-content">
              <a href="/docs" data-page="docs">
                <span class="module-label">
                  <i data-feather="file-text"></i> Documentation
                </span>
              </a>
              <a href="/faq" data-page="faq">
                <span class="module-label">
                  <i data-feather="help-circle"></i> FAQ
                </span>
              </a>
              <a href="/api-reference" data-page="api-reference">
                <span class="module-label">
                  <i data-feather="code"></i> API Reference
                </span>
              </a>
              <a href="/methods" data-page="methods">
                <span class="module-label">
                  <i data-feather="git-branch"></i> Methods
                </span>
              </a>
              <a href="/schema" data-page="schema">
                <span class="module-label">
                  <i data-feather="layout"></i> Database Schema
                </span>
              </a>
              <a href="/release" data-page="release">
                <span class="module-label">
                  <i data-feather="archive"></i> Release Notes
                </span>
              </a>
              <a href="/download-manifest" data-page="download-manifest">
                <span class="module-label">
                  <i data-feather="download"></i> Download Manifest
                </span>
              </a>
              <a href="/case-studies" data-page="case-studies">
                <span class="module-label">
                  <i data-feather="clipboard"></i> Case Studies
                </span>
              </a>
              <a href="/contribute" data-page="contribute">
                <span class="module-label">
                  <i data-feather="upload-cloud"></i> Submit Data / Contribute
                </span>
              </a>
            </div>
          </li>

          <li>
            <a href="#" id="globalSearchBtn">
              <i data-feather="search"></i>Search
            </a>
          </li>

          <li class="dropdown" id="modulesDropdown">
            <button type="button">
              <span><i data-feather="box"></i>Modules</span>
            </button>

            <div class="dropdown-content">
              <a href="#" id="protacLink">
                <span class="module-label">
                  <i data-feather="tool"></i> PROTAC Builder
                </span>
                <span class="module-badges">
                  <span class="badge">Live</span>
                </span>
              </a>

              <a href="https://warheadhunter.com" target="_blank" rel="noopener noreferrer">
                <span class="module-label">
                  <i data-feather="crosshair"></i> Warhead Hunter
                </span>
                <span class="module-badges">
                  <span class="badge">Live</span>
                </span>
              </a>

              <a href="https://vlisemod.com" target="_blank" rel="noopener noreferrer">
                <span class="module-label">
                  <i data-feather="activity"></i> V-LiSEMOD
                </span>
                <span class="module-badges">
                  <span class="badge">Live</span>
                </span>
              </a>

              <a href="https://github.com/schurerlab/Pymacs" target="_blank" rel="noopener noreferrer">
                <span class="module-label">
                  <i data-feather="cpu"></i> PyMACS
                </span>
                <span class="module-badges">
                  <span class="badge-github">GitHub</span>
                </span>
              </a>

              <a href="https://www.sciencedirect.com/science/article/pii/S0223523426004836" target="_blank" rel="noopener noreferrer">
                <span class="module-label">
                  <i data-feather="file-text"></i> PyMACS Paper
                </span>
                <span class="module-badges">
                  <span class="badge-published">Published</span>
                </span>
              </a>

              <a href="https://autodockvina.com" target="_blank" rel="noopener noreferrer">
                <span class="module-label">
                  <i data-feather="flask"></i> AutoDock Suite
                </span>
                <span class="module-badges">
                  <span class="badge">Live</span>
                </span>
              </a>

              <a href="https://github.com/Joey305/af3-Auto-analysis" target="_blank" rel="noopener noreferrer">
                <span class="module-label">
                  <i data-feather="bar-chart-2"></i> AF3 Auto Analyzer
                </span>
                <span class="module-badges">
                  <span class="badge-github">GitHub</span>
                </span>
              </a>
            </div>
          </li>
        </ul>
      </nav>
    `;

    const shadow = this.shadowRoot;
    const nav = shadow.querySelector("nav");
    const menuBtn = shadow.querySelector(".menu-toggle");
    const closeBtn = shadow.querySelector(".menu-close");
    const menuBackdrop = shadow.querySelector(".menu-backdrop");
    const menu = shadow.querySelector(".menu");
    const dropdowns = Array.from(shadow.querySelectorAll(".dropdown"));
    const protacLink = shadow.querySelector("#protacLink");
    const searchBtn = shadow.querySelector("#globalSearchBtn");
    const luckyBtn = shadow.querySelector("#luckyBtn");

    const mobileQuery = window.matchMedia("(max-width: 768px)");
    let previousBodyOverflow = "";

    const isMobile = () => mobileQuery.matches;

    const setDropdown = (dropdown, open) => {
      const button = dropdown.querySelector("button");
      dropdown.classList.toggle("open", open);
      if (button) button.setAttribute("aria-expanded", String(open));
    };

    const closeDropdowns = (except = null) => {
      dropdowns.forEach((dropdown) => {
        if (dropdown !== except) setDropdown(dropdown, false);
      });
    };

    const setMenuState = (open) => {
      menu.classList.toggle("show", open);
      menuBtn.classList.toggle("active", open);
      menuBtn.setAttribute("aria-expanded", String(open));
      menuBtn.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
      menuBackdrop.hidden = !open;
      menuBackdrop.classList.toggle("show", open);

      if (open) {
        previousBodyOverflow = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        setTimeout(() => closeBtn?.focus(), 0);
      } else {
        document.body.style.overflow = previousBodyOverflow || "";
        closeDropdowns();
      }
    };

    const closeMenu = () => setMenuState(false);
    const toggleMenu = () => setMenuState(!menu.classList.contains("show"));

    dropdowns.forEach((dropdown) => {
      const button = dropdown.querySelector("button");
      const content = dropdown.querySelector(".dropdown-content");
      const dropdownId = dropdown.id || `dropdown-${Math.random().toString(36).slice(2, 8)}`;

      dropdown.id = dropdownId;
      content.id = `${dropdownId}-content`;
      button.setAttribute("aria-haspopup", "true");
      button.setAttribute("aria-expanded", "false");
      button.setAttribute("aria-controls", content.id);
    });

    menuBtn.addEventListener("click", toggleMenu);
    closeBtn?.addEventListener("click", closeMenu);
    menuBackdrop.addEventListener("click", closeMenu);

    searchBtn?.addEventListener("click", (event) => {
      event.preventDefault();
      document.dispatchEvent(new Event("open-global-search"));
      if (isMobile()) closeMenu();
    });

    protacLink?.addEventListener("click", (event) => {
      event.preventDefault();
      const base = window.PROTACSUITE || "https://protacbuilder.com/";
      window.open(base, "_blank", "noopener,noreferrer");
      if (isMobile()) closeMenu();
    });

    menu.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        if (isMobile() && link.id !== "protacLink" && link.id !== "globalSearchBtn") closeMenu();
      });
    });

    const currentPath = window.location.pathname.split("/").filter(Boolean)[0] || "home";
    shadow.querySelectorAll(".menu a[data-page]").forEach((link) => {
      const page = link.getAttribute("data-page");
      if (page === currentPath) link.classList.add("active");
    });

    const handleScroll = () => {
      nav.classList.toggle("is-scrolled", window.scrollY > 20);
    };

    handleScroll();
    window.addEventListener("scroll", handleScroll, { passive: true });

    dropdowns.forEach((dropdown) => {
      const dropdownBtn = dropdown.querySelector("button");
      let dropdownTimer = null;

      dropdown.addEventListener("mouseenter", () => {
        if (!isMobile()) {
          clearTimeout(dropdownTimer);
          closeDropdowns(dropdown);
          setDropdown(dropdown, true);
        }
      });

      dropdown.addEventListener("mouseleave", () => {
        if (!isMobile()) {
          dropdownTimer = setTimeout(() => setDropdown(dropdown, false), 160);
        }
      });

      dropdownBtn.addEventListener("click", (event) => {
        event.preventDefault();
        const willOpen = !dropdown.classList.contains("open");
        closeDropdowns(dropdown);
        setDropdown(dropdown, willOpen);
      });
    });

    document.addEventListener("click", (event) => {
      const path = event.composedPath();
      if (!path.includes(this)) closeDropdowns();
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeMenu();
        closeDropdowns();
      }
    });

    mobileQuery.addEventListener?.("change", () => {
      closeMenu();
      closeDropdowns();
    });

    luckyBtn?.addEventListener("click", async () => {
      luckyBtn.disabled = true;
      luckyBtn.textContent = "🎲 Loading...";
      try {
        const response = await fetch("/api/random-recruiter");
        if (!response.ok) throw new Error(`random-recruiter returned ${response.status}`);
        const result = await response.json();
        if (!result?.recruiter_instance_id || !result?.url) {
          throw new Error("random-recruiter returned no exact V1 instance");
        }
        window.location.href = result.url;
      } catch (error) {
        console.error("Unable to select a random V1 recruiter instance:", error);
        luckyBtn.disabled = false;
        luckyBtn.textContent = "🎲 I'm Feeling Lucky";
      }
    });

    if (window.feather?.icons) {
      shadow.querySelectorAll("i[data-feather]").forEach((icon) => {
        const name = icon.getAttribute("data-feather");
        if (window.feather.icons[name]) {
          icon.outerHTML = window.feather.icons[name].toSvg({
            "aria-hidden": "true",
            focusable: "false",
            width: 16,
            height: 16,
            "stroke-width": 2,
          });
        }
      });
    }
  }
}

if (!customElements.get("custom-navbar")) {
  customElements.define("custom-navbar", CustomNavbar);
}
