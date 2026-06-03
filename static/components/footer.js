class CustomFooter extends HTMLElement {
  connectedCallback() {
    this.attachShadow({ mode: "open" });
    const year = new Date().getFullYear();
    this.shadowRoot.innerHTML = `
      <style>
      /* 🔹 Badges */
        .badge {
          font-size: 0.65rem;
          background: rgba(56,189,248,0.2);
          color: var(--primary);
          padding: 0.1rem 0.4rem;
          border-radius: 0.3rem;
        }

        .badge-soon {
          background: rgba(148,163,184,0.2);
          color: #94a3b8;
        }

        /* Add this new class */
        .badge-preprint {
          background: rgba(239, 68, 68, 0.2); 
          color: #ef4444;
        }

        :host {
          --primary: #38bdf8; /* Electric Blue */
          --accent: #facc15;  /* Electric Yellow */
          --text-muted: #cbd5e1;
          --bg-glass: rgba(15, 23, 42, 0.85);
          --border-glow: rgba(56, 189, 248, 0.25);
          font-family: 'Inter', sans-serif;
        }

        /* 🌌 Footer Base */
        footer {
          background: var(--bg-glass);
          border-top: 1px solid var(--border-glow);
          color: var(--text-muted);
          margin-top: 4rem;
          position: relative;
          overflow: hidden;
          opacity: 0;
          transform: translateY(50px);
          transition: opacity 0.8s ease-out, transform 0.8s ease-out;
        }

        /* 🎇 Fade in on scroll */
        footer.visible {
          opacity: 1;
          transform: translateY(0);
        }

        /* ⚡ Dual Electric Glow (Cyan + Yellow alternating pulses) */
        footer::before {
          content: "";
          position: absolute;
          inset: 0;
          border: 2px solid transparent;
          border-radius: 10px;
          background: linear-gradient(135deg,
            rgba(56,189,248,0.8),
            rgba(250,204,21,0.8),
            rgba(56,189,248,0.8)
          );
          background-size: 300% 300%;
          -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
          -webkit-mask-composite: destination-out;
          mask-composite: exclude;
          box-shadow:
            0 0 12px rgba(250,204,21,0.4),
            0 0 20px rgba(56,189,248,0.3),
            0 0 40px rgba(56,189,248,0.2);
          animation: dualElectricPulse 6s ease-in-out infinite;
          pointer-events: none;
          z-index: 1;
        }

        /* ⚡ Pulse gradient and brightness over time */
        @keyframes dualElectricPulse {
          0%, 100% {
            opacity: 0.85;
            background-position: 0% 50%;
            box-shadow:
              0 0 10px rgba(250,204,21,0.4),
              0 0 25px rgba(56,189,248,0.3),
              0 0 50px rgba(56,189,248,0.2);
            filter: brightness(1);
          }
          25% {
            background-position: 50% 0%;
            filter: brightness(1.2);
          }
          50% {
            opacity: 1;
            background-position: 100% 50%;
            box-shadow:
              0 0 15px rgba(56,189,248,0.5),
              0 0 35px rgba(250,204,21,0.5),
              0 0 60px rgba(250,204,21,0.3);
            filter: brightness(1.3);
          }
          75% {
            background-position: 50% 100%;
            filter: brightness(1.1);
          }
        }

        /* 💎 Grid Layout */
        .grid {
          max-width: 1150px;
          margin: 0 auto;
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: 2rem;
          padding: 2rem 1rem;
          position: relative;
          z-index: 2; /* keep content above glow */
        }

        h3 {
          color: var(--primary);
          margin-bottom: 0.8rem;
          font-size: 1.1rem;
          font-weight: 600;
          display: flex;
          align-items: center;
          gap: 0.4rem;
        }

        ul {
          list-style: none;
          padding: 0;
          margin: 0;
        }

        a {
          color: var(--text-muted);
          text-decoration: none;
          transition: all 0.25s ease;
          display: inline-flex;
          align-items: center;
          gap: 0.4rem;
          font-size: 0.95rem;
        }

        a:hover {
          color: var(--primary);
          text-shadow: 0 0 6px rgba(56,189,248,0.6), 0 0 12px rgba(250,204,21,0.5);
          transform: translateX(3px);
        }

        /* 🔹 Badges */
        .badge {
          font-size: 0.65rem;
          background: rgba(56,189,248,0.2);
          color: var(--primary);
          padding: 0.1rem 0.4rem;
          border-radius: 0.3rem;
        }

        .badge-soon {
          background: rgba(148,163,184,0.2);
          color: #94a3b8;
        }

        /* ⚙️ Copyright */
        .copyright {
          border-top: 1px solid var(--border-glow);
          text-align: center;
          padding: 1rem 0;
          font-size: 0.9rem;
          color: #94a3b8;
          position: relative;
          z-index: 2;
        }

        /* 📱 Responsive Adjustments */
        @media (max-width: 768px) {
          .grid {
            grid-template-columns: 1fr;
            text-align: center;
          }
          a:hover { transform: none; }
        }

      </style>

      <footer id="electricFooter">
        <div class="grid">
          <div>
            <h3><i data-feather="compass"></i>Explore</h3>
            <ul>
              <li><a href="/explorer"><i data-feather="search"></i>Ligase Explorer</a></li>
              <li><a href="/scaffolds"><i data-feather="layers"></i>Scaffold Dashboard</a></li>
              <li><a href="/ligases"><i data-feather="database"></i>Ligase Index</a></li>
              <li><a href="/about"><i data-feather="info"></i>About Project</a></li>
            </ul>
          </div>

          <div>
            <h3><i data-feather="box"></i>Modules</h3>
            <ul>
              <li><a href="#" id="protacLinkFooter">
                <i data-feather="tool"></i> PROTAC Builder <span class="badge">Live</span></a>
              </li>
              <li>
                <a href="https://warheadhunter.com" target="_blank" rel="noopener noreferrer">
                  <i data-feather="crosshair"></i> Warhead Hunter <span class="badge">Live</span>
                </a>
              </li>
              <li><a href="https://vlisemod.com" target="_blank">
                <i data-feather="activity"></i> V-LiSEMOD <span class="badge">Live</span></a>
              </li>
              <li><a href="https://github.com/schurerlab/Pymacs" target="_blank">
                <i data-feather="cpu"></i> PyMACS <span class="badge-preprint">Preprint</span></a>
              </li>
              <li><a href="https://butters.rove-vernier.ts.net" target="_blank">
                <i data-feather="flask"></i> AutoDock Suite <span class="badge">Live</span></a>
              </li>
              <li><a href="https://github.com/Joey305/af3-Auto-analysis" target="_blank">
                <i data-feather="bar-chart-2"></i> AF3 Analyzer <span class="badge-soon">Under Dev</span></a>
              </li>
            </ul>
          </div>

          <div>
            <h3><i data-feather="book-open"></i>Resources</h3>
            <ul>
              <li><a href="https://github.com/Joey305/E3-Ligandalyzer-Scripts" target="_blank" rel="noopener noreferrer">
                <i data-feather="github"></i>GitHub Repository</a>
              </li>
              <li><a href="/docs"><i data-feather="file-text"></i>Documentation</a></li>
              <li><a href="/api-reference"><i data-feather="code"></i>API Reference</a></li>
            </ul>
          </div>

          <div>
            <h3><i data-feather="message-circle"></i>Connect</h3>
            <ul>
              <li><a href="mailto:jxs794@miami.edu"><i data-feather="mail"></i>Contact</a></li>
              <li><a href="mailto:jxs794@miami.edu?subject=Ligandalyzer Feedback">
                <i data-feather="send"></i>Feedback</a></li>
              <li><a href="/contribute"><i data-feather="heart"></i>Contribute</a></li>
            </ul>
          </div>
        </div>

        <div class="copyright">
          © ${year} E3 Ligase Ligandalyzer — All rights reserved.
        </div>
      </footer>

      <script src="https://cdn.jsdelivr.net/npm/feather-icons/dist/feather.min.js"></script>
    `;

    // Dynamic link
    const protacLink = this.shadowRoot.querySelector("#protacLinkFooter");
    if (protacLink) {
      protacLink.addEventListener("click", (e) => {
        e.preventDefault();
        const base = window.PROTACSUITE || "https://protacbuilder.com";
        window.open(base, "_blank");
      });
    }

    // Activate icons
    feather.replace();

    // Fade-in observer
    const footer = this.shadowRoot.querySelector("#electricFooter");
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            footer.classList.add("visible");
            observer.unobserve(footer);
          }
        });
      },
      { threshold: 0.1 }
    );
    observer.observe(footer);
  }
}

customElements.define("custom-footer", CustomFooter);
