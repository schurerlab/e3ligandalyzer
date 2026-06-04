class CustomNavbar extends HTMLElement {
  connectedCallback() {
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --primary: #38bdf8;
          --accent: #facc15;
          --text-muted: #cbd5e1;
          --bg-glass: rgba(15, 23, 42, 0.75);
          --border-glow: rgba(56, 189, 248, 0.25);
          font-family: 'Inter', sans-serif;
        }

        /* =====================================================
           NAV CONTAINER
        ===================================================== */
        nav {
          background: var(--bg-glass);
          border-bottom: 1px solid var(--border-glow);
          backdrop-filter: blur(10px);
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0.8rem 1.5rem;
          position: sticky;
          top: 0;
          z-index: 100;
        }

        /* Electric frame */
        nav::before {
          content: "";
          position: absolute;
          inset: 0;
          border-radius: 8px;
          border: 2px solid transparent;
          background: linear-gradient(
            135deg,
            rgba(56,189,248,0.9),
            rgba(250,204,21,0.9),
            rgba(56,189,248,0.9)
          ) border-box;
          -webkit-mask:
            linear-gradient(#000 0 0) padding-box,
            linear-gradient(#000 0 0);
          -webkit-mask-composite: xor;
          mask-composite: exclude;
          pointer-events: none;
        }

        /* =====================================================
           BRAND
        ===================================================== */
        .brand {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          color: var(--primary);
          text-decoration: none;
          font-weight: 600;
          font-size: 1.2rem;
          min-width: 0;
          z-index: 2;
        }

        .brand span {
          min-width: 0;
        }

        /* =====================================================
           DESKTOP MENU
        ===================================================== */
        .menu {
          display: flex;
          gap: 1.2rem;
          list-style: none;
          margin: 0;
          padding: 0;
          align-items: center;
          z-index: 2;
        }

        .menu a,
        .menu button {
          color: var(--text-muted);
          background: none;
          border: none;
          font-weight: 500;
          padding: 0.4rem 0.8rem;
          border-radius: 4px;
          cursor: pointer;
          display: flex;
          align-items: center;
          transition: background 0.2s ease, color 0.2s ease;
        }

        .menu a:hover,
        .menu button:hover {
          background: rgba(56,189,248,0.12);
          color: var(--primary);
        }

        .menu a.active {
          color: var(--accent);
          border-bottom: 2px solid var(--accent);
        }

        /* =====================================================
           DESKTOP DROPDOWN
        ===================================================== */
        .dropdown {
          position: relative;
        }

        .dropdown-content {
          position: absolute;
          top: 2.4rem;
          right: 0;
          min-width: 275px;
          background: rgba(15,23,42,0.97);
          border: 1px solid var(--border-glow);
          border-radius: 8px;
          padding: 0.4rem 0;
          opacity: 0;
          pointer-events: none;
          transition: opacity 0.2s ease;
          z-index: 200;
        }

        .dropdown.open .dropdown-content {
          opacity: 1;
          pointer-events: auto;
        }

        .dropdown-content a {
          padding: 0.6rem 1rem;
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 0.9rem;
          font-size: 0.9rem;
        }

        .module-label {
          display: flex;
          align-items: center;
          gap: 0.45rem;
          min-width: 0;
          white-space: nowrap;
        }

        .module-badges {
          display: flex;
          align-items: center;
          gap: 0.35rem;
          margin-left: auto;
          flex-shrink: 0;
        }

        .badge,
        .badge-soon,
        .badge-preprint,
        .badge-github {
          font-size: 0.68rem;
          font-weight: 700;
          line-height: 1;
          padding: 0.22rem 0.42rem;
          border-radius: 999px;
          text-transform: uppercase;
          letter-spacing: 0.04em;
          white-space: nowrap;
        }

        .badge {
          background: rgba(34, 197, 94, 0.18);
          color: #bbf7d0;
          border: 1px solid rgba(74, 222, 128, 0.65);
          box-shadow: 0 0 8px rgba(34, 197, 94, 0.25);
        }

        .badge-soon {
          background: rgba(250, 204, 21, 0.15);
          color: #fef08a;
          border: 1px solid rgba(250, 204, 21, 0.65);
          box-shadow: 0 0 8px rgba(250, 204, 21, 0.25);
        }

        .badge-preprint {
          background: rgba(239, 68, 68, 0.18);
          color: #fecaca;
          border: 1px solid rgba(248, 113, 113, 0.75);
          box-shadow: 0 0 8px rgba(239, 68, 68, 0.35);
        }

        .badge-github {
          background: rgba(148, 163, 184, 0.16);
          color: #e2e8f0;
          border: 1px solid rgba(203, 213, 225, 0.5);
          box-shadow: 0 0 8px rgba(148, 163, 184, 0.22);
        }

        /* =====================================================
           LUCKY BUTTON
        ===================================================== */
        .lucky-btn {
          background: var(--accent);
          color: #1e293b;
          font-weight: 600;
          padding: 0.45rem 0.9rem;
          border-radius: 6px;
          border: none;
        }

        /* =====================================================
           HAMBURGER BUTTON
        ===================================================== */
        .menu-toggle {
          display: none;
          width: 32px;
          height: 26px;
          flex-direction: column;
          justify-content: space-between;
          background: none;
          border: none;
          cursor: pointer;
        }

        .bar {
          height: 3px;
          background: var(--text-muted);
          border-radius: 3px;
        }

        .menu-backdrop {
          display: none;
        }

        /* =====================================================
           MOBILE OVERRIDES
        ===================================================== */
        @media (max-width: 768px) {
          nav {
            gap: 0.75rem;
            padding: 0.8rem 1rem;
          }

          .brand {
            flex: 1;
            font-size: 1rem;
          }

          .brand img {
            flex-shrink: 0;
          }

          .brand span {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          .menu-toggle {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 44px;
            height: 44px;
            padding: 0;
            border-radius: 10px;
            border: 1px solid rgba(56, 189, 248, 0.22);
            background: rgba(15, 23, 42, 0.8);
            z-index: 3;
          }

          .menu-backdrop {
            position: fixed;
            inset: 0;
            display: block;
            background: rgba(2, 6, 23, 0.72);
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.25s ease;
            z-index: 98;
          }

          .menu-backdrop.show {
            opacity: 1;
            pointer-events: auto;
          }

          .menu {
            position: fixed;
            top: calc(100% + 0.35rem);
            left: 0.75rem;
            right: 0.75rem;
            max-height: calc(100vh - 5.75rem);
            overflow-y: auto;
            background: rgba(2, 6, 23, 0.98);
            border: 1px solid rgba(56, 189, 248, 0.2);
            border-radius: 18px;
            flex-direction: column;
            align-items: stretch;
            padding: 0.35rem 0;
            gap: 0;
            opacity: 0;
            pointer-events: none;
            transform: translateY(-6px);
            transition: opacity 0.25s ease, transform 0.25s ease;
            z-index: 99;
          }

          .menu.show {
            opacity: 1;
            pointer-events: auto;
            transform: translateY(0);
          }

          .menu li {
            width: 100%;
          }

          .menu a,
          .menu button {
            width: 100%;
            min-height: 44px;
            padding: 0.9rem 1rem;
            border-radius: 0;
            background: transparent;
            text-align: left;
          }

          .menu li:not(:last-child) {
            border-bottom: 1px solid rgba(255,255,255,0.08);
          }

          .dropdown-content {
            position: static;
            opacity: 0;
            pointer-events: none;
            background: rgba(15, 23, 42, 0.55);
            border: 1px solid rgba(56, 189, 248, 0.14);
            border-radius: 12px;
            padding: 0;
            min-width: 100%;
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.25s ease, opacity 0.2s ease;
            margin: 0 0.75rem 0.5rem;
          }

          .dropdown.open .dropdown-content {
            opacity: 1;
            pointer-events: auto;
            max-height: 60vh;
          }

          .dropdown-content a {
            padding-left: 1.35rem;
          }

          .dropdown > button {
            font-size: 0.92rem;
            letter-spacing: normal;
            text-transform: none;
            color: var(--text-muted);
            cursor: pointer;
            justify-content: space-between;
          }

          .module-badges {
            margin-left: auto;
          }
        }

        a,
        a:visited,
        a:hover,
        a:active,
        a:focus {
          text-decoration: none !important;
        }

        @media (max-width: 768px) {
          #mobile-filter-block.collapsed {
            display: none;
          }
        }

        @media (max-width: 768px) {
          #search-results {
            max-height: calc(100vh - 160px);
          }
        }

        .adv-toggle {
          cursor: pointer;
        }

        .adv-toggle:hover {
          color: var(--primary);
        }
      </style>

      <nav>
        <a href="/" class="brand">
          <img src="/static/images/favicon2.png" alt="logo" width="26" height="26" style="border-radius:6px;">
          <span>Ligase Recruiter Ligandalyzer</span>
        </a>

        <!-- HAMBURGER -->
        <button class="menu-toggle" aria-label="Toggle navigation">
          <div class="bar bar1"></div>
          <div class="bar bar2"></div>
          <div class="bar bar3"></div>
        </button>

        <div class="menu-backdrop" hidden></div>

        <!-- MENU -->
        <ul class="menu">
          <li>
            <button id="luckyBtn" class="lucky-btn">
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
              <i data-feather="book-open"></i>Resources ▾
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
              <span><i data-feather="search"></i>🔍 Search</span>
            </a>
          </li>

          <!-- 🧩 Modules Dropdown -->
          <li class="dropdown" id="modulesDropdown">
            <button type="button">
              <i data-feather="box"></i>Modules ▾
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
                  <span class="badge-preprint">Preprint</span>
                </span>
              </a>

              <a href="https://butters.rove-vernier.ts.net" target="_blank" rel="noopener noreferrer">
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

    /* ELEMENT REFERENCES */
    const shadow = this.shadowRoot;
    const menuBtn = shadow.querySelector(".menu-toggle");
    const menuBackdrop = shadow.querySelector(".menu-backdrop");
    const menu = shadow.querySelector(".menu");
    const nav = shadow.querySelector("nav");
    const dropdowns = Array.from(shadow.querySelectorAll(".dropdown"));
    const protacLink = shadow.querySelector("#protacLink");
    const searchBtn = shadow.querySelector("#globalSearchBtn");

    searchBtn.addEventListener("click", (e) => {
      e.preventDefault();
      document.dispatchEvent(new Event("open-global-search"));
    });

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

    function closeDropdowns() {
      dropdowns.forEach((dropdown) => {
        dropdown.classList.remove("open");
        const button = dropdown.querySelector("button");
        if (button) button.setAttribute("aria-expanded", "false");
      });
    }

    function closeMenu() {
      menu.classList.remove("show");
      menuBtn.classList.remove("active");
      menuBtn.setAttribute("aria-expanded", "false");
      menuBackdrop.classList.remove("show");
      menuBackdrop.hidden = true;
      document.body.style.overflow = "";
      closeDropdowns();
    }

    function openMenu() {
      menu.classList.add("show");
      menuBtn.classList.add("active");
      menuBtn.setAttribute("aria-expanded", "true");
      menuBackdrop.hidden = false;
      menuBackdrop.classList.add("show");
      document.body.style.overflow = "hidden";
    }

    menuBtn.setAttribute("aria-expanded", "false");
    menuBtn.setAttribute("aria-controls", "primary-navigation");
    menu.id = "primary-navigation";

    /* ✅ Dynamic PROTAC Builder link */
    protacLink.addEventListener("click", (e) => {
      e.preventDefault();
      const base = window.PROTACSUITE || "https://protacbuilder.com/";
      window.open(base, "_blank");
    });

    /* 📱 Mobile menu toggle */
    menuBtn.addEventListener("click", () => {
      if (menu.classList.contains("show")) {
        closeMenu();
      } else {
        openMenu();
      }
    });

    menuBackdrop.addEventListener("click", closeMenu);
    menu.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        if (window.innerWidth <= 768) closeMenu();
      });
    });

    /* 🧭 Highlight active route */
    const currentPath = window.location.pathname.split("/")[1] || "home";
    shadow.querySelectorAll(".menu a").forEach((link) => {
      const page = link.getAttribute("data-page");
      if (page === currentPath) link.classList.add("active");
    });

    /* 🌫️ Scroll shrink effect */
    window.addEventListener("scroll", () => {
      if (window.scrollY > 20) {
        nav.style.padding = "0.5rem 1.2rem";
        nav.style.background = "rgba(15,23,42,0.9)";
      } else {
        nav.style.padding = "0.8rem 1.5rem";
        nav.style.background = "var(--bg-glass)";
      }
    });

    /* 🧩 Dropdowns: desktop hover, mobile tap */
    dropdowns.forEach((dropdown) => {
      const dropdownBtn = dropdown.querySelector("button");
      let dropdownTimer;

      dropdown.addEventListener("mouseenter", () => {
        if (window.innerWidth > 768) {
          clearTimeout(dropdownTimer);
          dropdown.classList.add("open");
        }
      });

      dropdown.addEventListener("mouseleave", () => {
        if (window.innerWidth > 768) {
          dropdownTimer = setTimeout(() => dropdown.classList.remove("open"), 200);
        }
      });

      dropdownBtn.addEventListener("click", (e) => {
        if (window.innerWidth <= 768) {
          e.preventDefault();
          const willOpen = !dropdown.classList.contains("open");
          closeDropdowns();
          dropdown.classList.toggle("open", willOpen);
          dropdownBtn.setAttribute("aria-expanded", String(willOpen));
        }
      });
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeMenu();
      }
    });

    window.addEventListener("resize", () => {
      if (window.innerWidth > 768) {
        closeMenu();
      }
    });

    /* 🎲 I'M FEELING LUCKY */
    const luckyBtn = shadow.querySelector("#luckyBtn");

    const blockedRecruiters = new Set([
      // Add blocked recruiter IDs here if needed.
    ]);

    function getRandomRecruiter() {
      while (true) {
        const num = Math.floor(Math.random() * 603) + 1;
        const code = "LR" + String(num).padStart(5, "0");
        if (!blockedRecruiters.has(code)) return code;
      }
    }

    luckyBtn.addEventListener("click", () => {
      luckyBtn.disabled = true;
      luckyBtn.textContent = "🎲 Loading...";
      const next = getRandomRecruiter();
      window.location.href = `/ligand/${next}`;
    });

    /* Feather icons */
    if (window.feather) {
      feather.replace();
    }
  }
}

customElements.define("custom-navbar", CustomNavbar);
